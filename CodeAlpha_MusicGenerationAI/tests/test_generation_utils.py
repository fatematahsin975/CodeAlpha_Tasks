"""Fast tests for generation helpers that do not load the neural network."""

import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from generate_music import (
    _render_audio_preview,
    _sample_prediction,
    _token_to_midi_pitches,
    discover_model_bundles,
)


class GenerationUtilityTests(unittest.TestCase):
    def test_model_bundles_are_discovered(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_directory = Path(temporary_directory)
            (model_directory / "demo.keras").touch()
            for suffix in ("notes", "note_to_int", "int_to_note"):
                (model_directory / f"demo_{suffix}.pkl").touch()
            self.assertEqual(
                discover_model_bundles(model_directory),
                ["demo.keras"],
            )

    def test_training_tokens_convert_to_midi(self):
        self.assertEqual(_token_to_midi_pitches("C4"), [60])
        self.assertEqual(_token_to_midi_pitches("60.64.67"), [60, 64, 67])
        self.assertEqual(_token_to_midi_pitches("not-a-note"), [])

    def test_top_one_sampling_is_argmax(self):
        probabilities = np.array([0.1, 0.7, 0.2])
        result = _sample_prediction(
            probabilities,
            np.random.default_rng(7),
            temperature=1.0,
            top_k=1,
        )
        self.assertEqual(result, 1)

    def test_audio_preview_is_valid_wave(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "preview.wav"
            duration = _render_audio_preview(
                [([60], 90), ([64, 67], 82)],
                output,
                tempo_bpm=120,
                step_beats=0.5,
                note_beats=0.75,
            )
            self.assertGreater(duration, 0)
            self.assertTrue(output.exists())
            with wave.open(str(output), "rb") as wav_file:
                self.assertEqual(wav_file.getnchannels(), 1)
                self.assertEqual(wav_file.getframerate(), 22_050)
                self.assertGreater(wav_file.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
