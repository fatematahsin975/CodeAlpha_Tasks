"""Generate MIDI music from a trained Keras sequence model.

The model predicts pitch/chord tokens.  Rhythm, tempo, velocity, and the audio
preview are added during generation because the training representation only
contains pitch information.
"""

from __future__ import annotations

import argparse
import json
import pickle
import secrets
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
from music21 import chord, instrument, meter, note, stream, tempo
from music21.pitch import PitchException


ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class GenerationResult:
    """Files and metadata produced by one generation run."""

    midi_path: Path
    audio_path: Path
    model_name: str
    note_count: int
    duration_seconds: float
    seed: int

    def __bool__(self) -> bool:
        return self.midi_path.exists() and self.audio_path.exists()


def discover_model_bundles(model_dir: str | Path = "models") -> list[str]:
    """Return model filenames that have all required vocabulary files."""

    directory = Path(model_dir)
    if not directory.exists():
        return []

    bundles: list[str] = []
    for model_path in sorted(directory.glob("*.keras")):
        try:
            _resolve_mapping_paths(directory, model_path.stem)
        except FileNotFoundError:
            continue
        bundles.append(model_path.name)
    return bundles


def _resolve_model_path(
    model_dir: str | Path, model_file: str | None
) -> Path:
    directory = Path(model_dir).resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Model directory does not exist: {directory}")

    if model_file:
        candidate = (directory / model_file).resolve()
        if candidate.parent != directory:
            raise ValueError("model_file must be a filename inside the model directory")
        if not candidate.exists():
            raise FileNotFoundError(f"Model not found: {candidate}")
        return candidate

    available = discover_model_bundles(directory)
    if not available:
        raise FileNotFoundError(
            f"No complete .keras model bundle was found in {directory}"
        )

    for preferred in (
        "best_music_gru_model.keras",
        "music_gru_model.keras",
        "music_lstm_model.keras",
    ):
        if preferred in available:
            return directory / preferred
    return directory / available[0]


def _resolve_mapping_paths(
    model_dir: Path, model_prefix: str
) -> tuple[Path, Path, Path]:
    paths = []
    for suffix in ("notes", "note_to_int", "int_to_note"):
        specific = model_dir / f"{model_prefix}_{suffix}.pkl"
        generic = model_dir / f"{suffix}.pkl"
        selected = specific if specific.exists() else generic
        if not selected.exists():
            raise FileNotFoundError(
                f"Missing {suffix}.pkl for model '{model_prefix}'"
            )
        paths.append(selected)
    return paths[0], paths[1], paths[2]


@lru_cache(maxsize=4)
def _load_generation_assets(
    model_path: str,
    model_mtime: int,
    notes_path: str,
    notes_mtime: int,
    note_to_int_path: str,
    note_to_int_mtime: int,
    int_to_note_path: str,
    int_to_note_mtime: int,
):
    """Load and cache a model bundle; mtimes invalidate overwritten artifacts."""

    # TensorFlow is intentionally imported lazily so the interface starts fast.
    from tensorflow.keras.models import load_model

    model = load_model(model_path, compile=False)
    with open(notes_path, "rb") as handle:
        notes = pickle.load(handle)
    with open(note_to_int_path, "rb") as handle:
        note_to_int = pickle.load(handle)
    with open(int_to_note_path, "rb") as handle:
        int_to_note = pickle.load(handle)

    input_shape = model.input_shape
    output_shape = model.output_shape
    if isinstance(input_shape, list) or len(input_shape) != 3:
        raise ValueError(f"Unsupported model input shape: {input_shape}")
    if input_shape[-1] != 1:
        raise ValueError(f"Expected one input feature, received: {input_shape}")
    if isinstance(output_shape, list) or len(output_shape) != 2:
        raise ValueError(f"Unsupported model output shape: {output_shape}")
    if output_shape[-1] != len(int_to_note):
        raise ValueError(
            "Model output size does not match its int_to_note vocabulary "
            f"({output_shape[-1]} != {len(int_to_note)})"
        )
    if len(note_to_int) != len(int_to_note):
        raise ValueError("note_to_int and int_to_note mappings have different sizes")

    return model, notes, note_to_int, int_to_note


def _load_model_bundle(model_path: Path):
    notes_path, note_to_int_path, int_to_note_path = _resolve_mapping_paths(
        model_path.parent, model_path.stem
    )
    paths = (model_path, notes_path, note_to_int_path, int_to_note_path)
    args: list[str | int] = []
    for path in paths:
        args.extend((str(path), path.stat().st_mtime_ns))
    return _load_generation_assets(*args)


def _sample_prediction(
    probabilities: np.ndarray,
    rng: np.random.Generator,
    temperature: float,
    top_k: int,
) -> int:
    """Sample one vocabulary index with temperature and top-k filtering."""

    values = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("The model returned invalid prediction probabilities")

    top_k = max(1, min(int(top_k), values.size))
    if top_k == 1:
        return int(np.argmax(values))

    temperature = max(float(temperature), 0.05)
    candidate_indices = np.argpartition(values, -top_k)[-top_k:]
    candidate_values = np.maximum(values[candidate_indices], 1e-12)
    scaled = np.log(candidate_values) / temperature
    scaled -= np.max(scaled)
    weights = np.exp(scaled)
    weights /= weights.sum()
    return int(rng.choice(candidate_indices, p=weights))


def _token_to_midi_pitches(token: str) -> list[int]:
    """Convert the training token format to one or more MIDI pitch numbers."""

    text = str(token)
    try:
        if "." in text or text.isdigit():
            pitches = [int(value) for value in text.split(".")]
        else:
            pitches = [int(note.Note(text).pitch.midi)]
    except (TypeError, ValueError, PitchException):
        return []
    return [pitch for pitch in pitches if 0 <= pitch <= 127]


def _write_midi(
    tokens: list[str],
    output_path: Path,
    tempo_bpm: int,
    step_beats: float,
    note_beats: float,
    rng: np.random.Generator,
) -> list[tuple[list[int], int]]:
    """Write generated tokens to MIDI and return events for WAV rendering."""

    composition = stream.Stream()
    composition.insert(0, tempo.MetronomeMark(number=tempo_bpm))
    composition.insert(0, meter.TimeSignature("4/4"))
    composition.insert(0, instrument.Piano())

    rendered_events: list[tuple[list[int], int]] = []
    for index, token in enumerate(tokens):
        pitches = _token_to_midi_pitches(token)
        if not pitches:
            continue

        velocity = int(rng.integers(68, 101))
        offset = index * step_beats
        if len(pitches) == 1:
            event = note.Note(pitches[0])
        else:
            event = chord.Chord(pitches)
        event.offset = offset
        event.quarterLength = note_beats
        event.volume.velocity = velocity
        composition.insert(offset, event)
        rendered_events.append((pitches, velocity))

    if not rendered_events:
        raise ValueError("The generated sequence did not contain valid MIDI notes")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    composition.write("midi", fp=str(output_path))
    return rendered_events


def _render_audio_preview(
    events: list[tuple[list[int], int]],
    output_path: Path,
    tempo_bpm: int,
    step_beats: float,
    note_beats: float,
    sample_rate: int = 22_050,
) -> float:
    """Render a portable piano-like WAV without requiring a system SoundFont."""

    spacing_seconds = step_beats * 60.0 / tempo_bpm
    note_seconds = note_beats * 60.0 / tempo_bpm
    duration_seconds = (len(events) - 1) * spacing_seconds + note_seconds + 0.15
    audio = np.zeros(int(duration_seconds * sample_rate) + 1, dtype=np.float32)

    for event_index, (pitches, velocity) in enumerate(events):
        start = int(event_index * spacing_seconds * sample_rate)
        sample_count = max(1, int(note_seconds * sample_rate))
        time = np.arange(sample_count, dtype=np.float32) / sample_rate

        attack = max(1, min(sample_count, int(0.012 * sample_rate)))
        release = max(1, min(sample_count, int(0.12 * sample_rate)))
        envelope = np.exp(-2.4 * time / max(note_seconds, 0.01)).astype(np.float32)
        envelope[:attack] *= np.linspace(0.0, 1.0, attack, dtype=np.float32)
        envelope[-release:] *= np.linspace(1.0, 0.0, release, dtype=np.float32)

        event_wave = np.zeros(sample_count, dtype=np.float32)
        for pitch in pitches[:10]:
            frequency = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
            tone = np.zeros(sample_count, dtype=np.float32)
            for harmonic, strength in ((1, 1.0), (2, 0.32), (3, 0.14)):
                if frequency * harmonic < sample_rate / 2:
                    tone += strength * np.sin(
                        2.0 * np.pi * frequency * harmonic * time
                    )
            event_wave += tone

        event_wave /= max(len(pitches[:10]), 1)
        event_wave *= envelope * (velocity / 127.0)
        end = min(start + sample_count, audio.size)
        audio[start:end] += event_wave[: end - start]

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio *= 0.92 / peak
    pcm = np.asarray(audio * 32767.0, dtype="<i2")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return duration_seconds


def generate_music(
    output_file: str | Path = "generated_music/generated_output.mid",
    sequence_length: int | None = None,
    num_notes_to_generate: int = 120,
    model_dir: str | Path = "models",
    model_file: str | None = None,
    temperature: float = 0.8,
    top_k: int = 30,
    tempo_bpm: int = 110,
    step_beats: float = 0.5,
    seed: int | None = None,
    audio_file: str | Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> GenerationResult:
    """Generate a MIDI composition and a browser-playable WAV preview."""

    if not 1 <= int(num_notes_to_generate) <= 2_000:
        raise ValueError("num_notes_to_generate must be between 1 and 2000")
    if not 30 <= int(tempo_bpm) <= 300:
        raise ValueError("tempo_bpm must be between 30 and 300")
    if not 0.125 <= float(step_beats) <= 4:
        raise ValueError("step_beats must be between 0.125 and 4")

    model_path = _resolve_model_path(model_dir, model_file)
    model, notes, note_to_int, int_to_note = _load_model_bundle(model_path)

    model_sequence_length = int(model.input_shape[1])
    if sequence_length is not None and sequence_length != model_sequence_length:
        raise ValueError(
            f"Model expects sequence length {model_sequence_length}, "
            f"not {sequence_length}"
        )
    sequence_length = model_sequence_length
    if len(notes) <= sequence_length:
        raise ValueError(
            f"Only {len(notes)} training notes are available; "
            f"at least {sequence_length + 1} are required"
        )

    actual_seed = int(seed) if seed is not None else secrets.randbits(32)
    rng = np.random.default_rng(actual_seed)
    start = int(rng.integers(0, len(notes) - sequence_length))
    seed_tokens = notes[start : start + sequence_length]
    try:
        pattern = [int(note_to_int[token]) for token in seed_tokens]
    except KeyError as exc:
        raise ValueError(f"Seed token is missing from note_to_int: {exc}") from exc

    vocabulary_size = len(int_to_note)
    generated_tokens: list[str] = []
    total = int(num_notes_to_generate)
    for index in range(total):
        prediction_input = np.asarray(pattern, dtype=np.float32).reshape(
            1, sequence_length, 1
        )
        prediction_input /= float(vocabulary_size)
        prediction = model.predict(prediction_input, verbose=0)[0]
        predicted_index = _sample_prediction(
            prediction, rng, temperature=temperature, top_k=top_k
        )
        if predicted_index not in int_to_note:
            raise ValueError(
                f"Prediction index {predicted_index} is missing from int_to_note"
            )
        generated_tokens.append(str(int_to_note[predicted_index]))
        pattern.append(predicted_index)
        pattern = pattern[-sequence_length:]
        if progress_callback and (index == total - 1 or index % 4 == 0):
            progress_callback(index + 1, total)

    midi_path = Path(output_file).resolve()
    wav_path = (
        Path(audio_file).resolve()
        if audio_file
        else midi_path.with_suffix(".wav")
    )
    note_beats = min(max(step_beats * 1.55, 0.25), 2.0)
    events = _write_midi(
        generated_tokens,
        midi_path,
        int(tempo_bpm),
        float(step_beats),
        note_beats,
        rng,
    )
    duration = _render_audio_preview(
        events,
        wav_path,
        int(tempo_bpm),
        float(step_beats),
        note_beats,
    )

    result = GenerationResult(
        midi_path=midi_path,
        audio_path=wav_path,
        model_name=model_path.name,
        note_count=len(events),
        duration_seconds=duration,
        seed=actual_seed,
    )
    metadata = {
        "midi_path": str(result.midi_path),
        "audio_path": str(result.audio_path),
        "model_name": result.model_name,
        "note_count": result.note_count,
        "duration_seconds": result.duration_seconds,
        "seed": result.seed,
        "temperature": float(temperature),
        "top_k": int(top_k),
        "tempo_bpm": int(tempo_bpm),
        "step_beats": float(step_beats),
    }
    midi_path.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate MIDI and WAV music from a trained model"
    )
    parser.add_argument("--model", default=None, help="Model filename in models/")
    parser.add_argument("--notes", type=int, default=120, help="Number of notes")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--tempo", type=int, default=110, help="Tempo in BPM")
    parser.add_argument("--step", type=float, default=0.5, help="Beats per event")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--output",
        default="generated_music/generated_output.mid",
        help="Output MIDI path",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    result = generate_music(
        output_file=args.output,
        model_file=args.model,
        num_notes_to_generate=args.notes,
        temperature=args.temperature,
        top_k=args.top_k,
        tempo_bpm=args.tempo,
        step_beats=args.step,
        seed=args.seed,
    )
    print(f"MIDI: {result.midi_path}")
    print(f"Audio preview: {result.audio_path}")
    print(f"Seed: {result.seed}")
