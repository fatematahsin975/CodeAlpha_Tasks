"""Streamlit interface for the trained MAESTRO music-generation model."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from generate_music import discover_model_bundles, generate_music


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset"
MODELS_PATH = BASE_DIR / "models"
GENERATED_PATH = BASE_DIR / "generated_music"

MODEL_LABELS = {
    "best_music_gru_model.keras": "Best GRU checkpoint",
    "music_gru_model.keras": "Final GRU model",
    "music_lstm_model.keras": "LSTM model",
}
RHYTHMS = {
    "Eighth notes · flowing": 0.5,
    "Quarter notes · spacious": 1.0,
    "Sixteenth notes · energetic": 0.25,
}


def _model_label(filename: str) -> str:
    return f"{MODEL_LABELS.get(filename, Path(filename).stem)}  ·  {filename}"


def _midi_count() -> int:
    if not DATASET_PATH.exists():
        return 0
    return sum(1 for suffix in ("*.mid", "*.midi") for _ in DATASET_PATH.rglob(suffix))


st.set_page_config(
    page_title="MAESTRO AI Piano Studio",
    page_icon="🎹",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 12% 8%, rgba(112, 78, 255, .16), transparent 28rem),
            radial-gradient(circle at 88% 18%, rgba(26, 180, 170, .11), transparent 25rem);
    }
    .hero {
        padding: 2.2rem 2.4rem;
        border: 1px solid rgba(138, 126, 255, .25);
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(24, 21, 52, .95), rgba(30, 54, 69, .88));
        box-shadow: 0 18px 55px rgba(0, 0, 0, .20);
        margin-bottom: 1.4rem;
    }
    .hero-kicker {
        color: #8de5dc;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .16em;
        text-transform: uppercase;
        margin-bottom: .7rem;
    }
    .hero h1 {
        color: #fff;
        font-size: clamp(2rem, 5vw, 3.7rem);
        letter-spacing: -.045em;
        line-height: 1.02;
        margin: 0;
    }
    .hero p {
        color: rgba(255, 255, 255, .72);
        max-width: 700px;
        font-size: 1.04rem;
        margin: 1rem 0 0;
    }
    [data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 160, .18);
        border-radius: 16px;
        padding: .9rem 1.1rem;
        background: rgba(128, 128, 160, .055);
    }
    [data-testid="stForm"] {
        border: 1px solid rgba(128, 128, 160, .20);
        border-radius: 18px;
        padding: 1.25rem 1.35rem 1.4rem;
        background: rgba(128, 128, 160, .045);
    }
    .small-note {
        opacity: .68;
        font-size: .86rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

GENERATED_PATH.mkdir(parents=True, exist_ok=True)
available_models = discover_model_bundles(MODELS_PATH)
metadata_path = GENERATED_PATH / "generated_output.json"
if "generation" not in st.session_state and metadata_path.exists():
    try:
        saved_generation = json.loads(metadata_path.read_text(encoding="utf-8"))
        saved_midi = Path(saved_generation["midi_path"])
        saved_audio = Path(saved_generation["audio_path"])
        if saved_midi.exists() and saved_audio.exists():
            st.session_state["generation"] = saved_generation
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        pass

st.markdown(
    """
    <section class="hero">
      <div class="hero-kicker">CodeAlpha · Artificial Intelligence Task 3</div>
      <h1>MAESTRO AI Piano Studio</h1>
      <p>Compose a new piano passage with a GRU trained on the MAESTRO MIDI
      collection. Shape its pace and creativity, then listen or export it.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

metric_model, metric_data, metric_output = st.columns(3)
metric_model.metric("Trained models", len(available_models), "ready" if available_models else "missing")
metric_data.metric("MAESTRO MIDI files", f"{_midi_count():,}", "training source")
previous_midi = GENERATED_PATH / "generated_output.mid"
metric_output.metric("Latest composition", "Available" if previous_midi.exists() else "Not generated")

if not available_models:
    st.error(
        "No complete trained model bundle was found. Add a `.keras` model and "
        "its notes, note_to_int, and int_to_note pickle files to `models/`."
    )
    st.stop()

default_index = (
    available_models.index("best_music_gru_model.keras")
    if "best_music_gru_model.keras" in available_models
    else 0
)

with st.sidebar:
    st.header("Composition controls")
    selected_model = st.selectbox(
        "Model",
        available_models,
        index=default_index,
        format_func=_model_label,
        help="The best checkpoint is recommended when it is available.",
    )
    architecture = (
        "LSTM"
        if "lstm" in selected_model.lower()
        else "GRU"
        if "gru" in selected_model.lower()
        else "Recurrent neural network"
    )
    note_count = st.slider(
        "Length (generated events)",
        min_value=32,
        max_value=300,
        value=120,
        step=8,
    )
    tempo_bpm = st.slider("Tempo (BPM)", 60, 180, 110, 5)
    rhythm_name = st.selectbox("Rhythmic feel", list(RHYTHMS))
    temperature = st.slider(
        "Creativity",
        min_value=0.20,
        max_value=1.50,
        value=0.80,
        step=0.05,
        help="Lower values are safer and more repetitive; higher values explore less likely notes.",
    )
    top_k = st.slider(
        "Note choices (top-k)",
        min_value=1,
        max_value=100,
        value=30,
        help="Restricts sampling to the model's most likely next notes.",
    )
    seed_value = st.number_input(
        "Seed (0 = random)",
        min_value=0,
        max_value=4_294_967_295,
        value=0,
        step=1,
        help="Reuse a non-zero seed with the same settings to reproduce a piece.",
    )
    st.divider()
    st.caption(
        "The network generates pitches and chords. The studio adds tempo, "
        "timing, dynamics, and a synthesized preview."
    )

left, right = st.columns([1.45, 1], gap="large")
with left:
    st.subheader("Create a composition")
    estimated_seconds = (
        note_count * RHYTHMS[rhythm_name] * 60.0 / tempo_bpm
    )
    st.write(
        "The model continues from a randomly selected passage in its learned "
        "MAESTRO vocabulary. Generation runs locally on this computer."
    )
    st.markdown(
        f'<p class="small-note">Estimated playback length: about '
        f"{estimated_seconds:.0f} seconds · Output: MIDI + WAV</p>",
        unsafe_allow_html=True,
    )

    with st.form("generation_form"):
        generate_clicked = st.form_submit_button(
            "Generate new music",
            type="primary",
            use_container_width=True,
        )

    if generate_clicked:
        progress = st.progress(0, text="Loading the trained model…")

        def update_progress(current: int, total: int) -> None:
            progress.progress(
                current / total,
                text=f"Composing event {current} of {total}…",
            )

        try:
            result = generate_music(
                output_file=GENERATED_PATH / "generated_output.mid",
                model_dir=MODELS_PATH,
                model_file=selected_model,
                num_notes_to_generate=note_count,
                temperature=temperature,
                top_k=top_k,
                tempo_bpm=tempo_bpm,
                step_beats=RHYTHMS[rhythm_name],
                seed=None if seed_value == 0 else int(seed_value),
                progress_callback=update_progress,
            )
            progress.progress(1.0, text="Composition ready")
            st.session_state["generation"] = {
                "midi_path": str(result.midi_path),
                "audio_path": str(result.audio_path),
                "model_name": result.model_name,
                "note_count": result.note_count,
                "duration_seconds": result.duration_seconds,
                "seed": result.seed,
            }
            st.success("Your new composition is ready to play.")
        except Exception as exc:
            progress.empty()
            st.error(f"Generation failed: {exc}")

with right:
    st.subheader("Model status")
    st.success("Trained model and vocabulary mappings are ready.")
    st.markdown(
        f"""
        - **Active checkpoint:** `{selected_model}`
        - **Architecture:** {architecture}
        - **Training data:** MAESTRO classical-piano MIDI
        - **Sequence memory:** 100 musical events
        """
    )
    with st.expander("How the generation works"):
        st.write(
            "A 100-event seed is selected from the training representation. "
            "The model predicts one event at a time; creativity and top-k "
            "control how those predictions are sampled. Generated pitch tokens "
            "are then arranged into a timed MIDI performance and a WAV preview."
        )

generation = st.session_state.get("generation")
if generation:
    midi_path = Path(generation["midi_path"])
    audio_path = Path(generation["audio_path"])
    if midi_path.exists() and audio_path.exists():
        st.divider()
        st.subheader("Listen and export")
        st.audio(audio_path.read_bytes(), format="audio/wav")

        details, midi_download, wav_download = st.columns([1.2, 1, 1])
        with details:
            st.caption(
                f"{generation['note_count']} events · "
                f"{generation['duration_seconds']:.1f} sec · "
                f"seed {generation['seed']}"
            )
        with midi_download:
            st.download_button(
                "Download MIDI",
                data=midi_path.read_bytes(),
                file_name="maestro_ai_composition.mid",
                mime="audio/midi",
                use_container_width=True,
            )
        with wav_download:
            st.download_button(
                "Download WAV",
                data=audio_path.read_bytes(),
                file_name="maestro_ai_preview.wav",
                mime="audio/wav",
                use_container_width=True,
            )

st.caption(
    "Built with TensorFlow/Keras, music21, NumPy, and Streamlit. "
    "The WAV uses a lightweight built-in synthesizer; import the MIDI into a "
    "DAW or notation app for higher-quality instruments."
)
