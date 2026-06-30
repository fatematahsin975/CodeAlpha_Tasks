import argparse
import os
import pickle

from tensorflow.keras.layers import GRU, LSTM, Activation, Dense, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam

from preprocess import run_preprocessing


def train_network(
    epochs=20,
    dataset_path="dataset",
    model_dir="models",
    model_type="lstm",
):
    print("Starting preprocessing...")
    (
        network_input,
        network_output,
        notes,
        note_to_int,
        int_to_note,
        n_vocab,
    ) = run_preprocessing(dataset_path=dataset_path)

    model_type = model_type.lower()
    print(f"Building {model_type.upper()} model...")
    model = Sequential()
    recurrent_layer = GRU if model_type == "gru" else LSTM
    model.add(
        recurrent_layer(
            256,
            input_shape=(network_input.shape[1], network_input.shape[2]),
            return_sequences=True,
        )
    )
    model.add(Dropout(0.3))
    model.add(recurrent_layer(256))
    model.add(Dense(256))
    model.add(Dropout(0.3))
    model.add(Dense(n_vocab))
    model.add(Activation("softmax"))
    model.compile(loss="categorical_crossentropy", optimizer=Adam())

    os.makedirs(model_dir, exist_ok=True)
    model_filename = f"music_{model_type}_model.keras"
    model_prefix = f"music_{model_type}_model"

    print(f"Saving notes and mappings as default and {model_prefix}_* files...")
    for prefix in ("", f"{model_prefix}_"):
        with open(
            os.path.join(model_dir, f"{prefix}notes.pkl"),
            "wb",
        ) as handle:
            pickle.dump(notes, handle)
        with open(
            os.path.join(model_dir, f"{prefix}note_to_int.pkl"),
            "wb",
        ) as handle:
            pickle.dump(note_to_int, handle)
        with open(
            os.path.join(model_dir, f"{prefix}int_to_note.pkl"),
            "wb",
        ) as handle:
            pickle.dump(int_to_note, handle)

    print(f"Training model for {epochs} epochs...")
    model.fit(network_input, network_output, epochs=epochs, batch_size=64)

    model_path = os.path.join(model_dir, model_filename)
    model.save(model_path)
    print(f"Training complete and model saved to {model_path}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train an LSTM or GRU model for music generation"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
        help="Number of epochs to train",
    )
    parser.add_argument(
        "--model_type",
        default="lstm",
        choices=["lstm", "gru"],
        help="Recurrent model architecture",
    )
    arguments = parser.parse_args()
    train_network(epochs=arguments.epochs, model_type=arguments.model_type)
