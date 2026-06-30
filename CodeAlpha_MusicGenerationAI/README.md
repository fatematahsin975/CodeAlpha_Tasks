# MAESTRO AI Piano Studio

CodeAlpha Artificial Intelligence Task 3: **Music Generation with AI**

This project trains a recurrent neural network on MAESTRO piano MIDI and uses
the trained model to compose new note and chord sequences. A Streamlit
interface lets the user control the composition, listen to a generated preview,
and download both MIDI and WAV files.

## What is complete

- Recursive MAESTRO MIDI discovery and `music21` preprocessing
- Note/chord tokenization and 100-event training sequences
- LSTM or GRU training with TensorFlow/Keras
- Support for trained GRU checkpoints and matching vocabulary mappings
- Temperature and top-k sampling from the trained model
- MIDI creation with tempo, rhythm, dynamics, and piano instrumentation
- Browser-playable WAV rendering with no external SoundFont requirement
- Streamlit interface with generation controls, playback, and downloads
- Command-line generation for scripting or testing

The locally trained GRU artifacts use a 3,158-token vocabulary learned from
more than 3.6 million extracted MAESTRO events. Large model, mapping, dataset,
and generated-output files are intentionally excluded from Git.

## Project structure

```text
CodeAlpha_MusicGenerationAI/
├── app.py                 # Streamlit interface
├── generate_music.py      # Model inference, MIDI creation, WAV rendering
├── preprocess.py          # MIDI parsing and training sequences
├── train_model.py         # LSTM/GRU training
├── requirements.txt
├── dataset/               # MAESTRO MIDI files (year subfolders supported)
├── models/                # .keras checkpoints and vocabulary .pkl files
└── generated_music/       # Generated MIDI and WAV outputs
```

## Install and launch

Python 3.10–3.12 is recommended.

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Before launching a fresh clone, either train a model or place one complete
bundle in `models/`: a `.keras` checkpoint plus its matching `_notes.pkl`,
`_note_to_int.pkl`, and `_int_to_note.pkl` files.

Streamlit prints a local address, normally `http://localhost:8501`. Open it in
a browser, choose the composition controls in the sidebar, and select
**Generate new music**.

If the Windows `python` command opens the Microsoft Store instead, call your
installed interpreter explicitly or fix the Python App Execution Alias.

## Interface controls

- **Model:** selects a complete trained checkpoint bundle.
- **Length:** controls the number of generated musical events.
- **Tempo:** sets playback speed and MIDI tempo.
- **Rhythmic feel:** sets the spacing between generated events.
- **Creativity:** adjusts sampling temperature. Low is safer; high is more
  exploratory.
- **Note choices:** limits sampling to the top-k model predictions.
- **Seed:** use `0` for a new random composition, or reuse a non-zero value for
  reproducible output with the same settings.

The generated files are written to:

```text
generated_music/generated_output.mid
generated_music/generated_output.wav
```

The built-in WAV synthesizer is intended for convenient browser preview.
Import the MIDI into a DAW, MuseScore, or another MIDI player with a quality
piano instrument for the best sound.

## Generate from the command line

```powershell
python generate_music.py `
  --model best_music_gru_model.keras `
  --notes 120 `
  --temperature 0.8 `
  --top-k 30 `
  --tempo 110 `
  --seed 2026
```

Omit `--seed` to generate a different result each time.

## Train another model

Training is optional when you already have a compatible trained model bundle.

```powershell
python train_model.py --model_type gru --epochs 20
```

Training scans all MIDI files under `dataset/`. The full MAESTRO collection can
take substantial time and memory; use a smaller subset for a quick
demonstration.

## CodeAlpha requirement mapping

| Requirement | Implementation |
|---|---|
| Collect MIDI music data | MAESTRO piano MIDI under `dataset/` |
| Preprocess into note sequences | `preprocess.py` with `music21` |
| Build an RNN/LSTM or GAN | LSTM and GRU options in `train_model.py` |
| Train and generate new sequences | Saved Keras checkpoints used by `generate_music.py` |
| Convert to MIDI and play/save audio | MIDI export plus playable/downloadable WAV in `app.py` |

## Limitations

- The model learned pitch and chord order, not expressive timing, so rhythm and
  velocity are added during generation.
- CPU inference is supported and may take several seconds for long pieces.
- Generated music is experimental and can be repetitive.
- TensorFlow 2.11+ on native Windows uses the CPU; GPU acceleration requires
  WSL2 or another supported environment.

## Submission checklist

1. Run the Streamlit interface and generate a piece.
2. Demonstrate playback and both download buttons in the project video.
3. Explain the MAESTRO preprocessing, GRU sequence model, and sampling controls.
4. Push source code to the required `CodeAlpha_ProjectName` GitHub repository.
5. Share the GitHub link with the LinkedIn explanation and submission form.
