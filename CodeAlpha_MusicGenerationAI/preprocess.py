from pathlib import Path

import numpy as np
from music21 import chord, converter, instrument, note
from tensorflow.keras.utils import to_categorical


def find_midi_files(dataset_path="dataset"):
    """Find MIDI files, including files inside MAESTRO year subfolders."""

    dataset_dir = Path(dataset_path)
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset folder '{dataset_path}' does not exist.")

    midi_files = sorted(
        list(dataset_dir.rglob("*.mid")) + list(dataset_dir.rglob("*.midi"))
    )
    if not midi_files:
        raise ValueError(
            f"No MIDI files found in '{dataset_path}'. Please copy MIDI files here."
        )
    return midi_files


def get_notes(dataset_path="dataset"):
    """Read MIDI files and extract note and chord tokens."""

    midi_files = find_midi_files(dataset_path)
    notes = []

    for file in midi_files:
        print(f"Parsing file: {file}")
        try:
            midi = converter.parse(file)
            try:
                partitioned = instrument.partitionByInstrument(midi)
                if partitioned:
                    notes_to_parse = partitioned.parts[0].recurse()
                else:
                    notes_to_parse = midi.flatten().notes
            except Exception:
                notes_to_parse = midi.flatten().notes

            for element in notes_to_parse:
                if isinstance(element, note.Note):
                    notes.append(str(element.pitch))
                elif isinstance(element, chord.Chord):
                    notes.append(
                        ".".join(str(chord_note.pitch.midi) for chord_note in element.notes)
                    )
        except Exception as exc:
            print(f"Error parsing {file}: {exc}")

    if not notes:
        raise ValueError("No notes were extracted from the MIDI files.")
    return notes


def prepare_sequences(notes, n_vocab, sequence_length=100):
    """Prepare normalized input sequences and one-hot encoded targets."""

    if len(notes) <= sequence_length:
        raise ValueError(
            f"Not enough notes extracted ({len(notes)}) for sequence length "
            f"{sequence_length}."
        )

    pitch_names = sorted(set(notes))
    note_to_int = {
        pitch_name: number for number, pitch_name in enumerate(pitch_names)
    }
    int_to_note = {
        number: pitch_name for number, pitch_name in enumerate(pitch_names)
    }

    network_input = []
    network_output = []
    for index in range(len(notes) - sequence_length):
        sequence_in = notes[index : index + sequence_length]
        sequence_out = notes[index + sequence_length]
        network_input.append([note_to_int[token] for token in sequence_in])
        network_output.append(note_to_int[sequence_out])

    n_patterns = len(network_input)
    network_input = np.reshape(
        network_input,
        (n_patterns, sequence_length, 1),
    )
    network_input = network_input / float(n_vocab)
    network_output = to_categorical(network_output, num_classes=n_vocab)
    return network_input, network_output, note_to_int, int_to_note


def run_preprocessing(dataset_path="dataset", sequence_length=100):
    notes = get_notes(dataset_path)
    n_vocab = len(set(notes))

    print(f"Total notes extracted: {len(notes)}")
    print(f"Unique notes (vocabulary size): {n_vocab}")

    network_input, network_output, note_to_int, int_to_note = prepare_sequences(
        notes,
        n_vocab,
        sequence_length,
    )
    return (
        network_input,
        network_output,
        notes,
        note_to_int,
        int_to_note,
        n_vocab,
    )


if __name__ == "__main__":
    run_preprocessing()
