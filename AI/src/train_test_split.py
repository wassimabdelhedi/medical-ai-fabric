"""Patient-safe PTB-XL split using the database's recommended strat_fold."""

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
PSEUDO_CSV = os.path.join(DATASET_DIR, "pseudonymized_database.csv")
TRAIN_CSV = os.path.join(DATASET_DIR, "train_set.csv")
VALIDATION_CSV = os.path.join(DATASET_DIR, "validation_set.csv")
TEST_CSV = os.path.join(DATASET_DIR, "test_set.csv")


def split_data(df: pd.DataFrame):
    """Use PTB-XL folds 1–8 / 9 / 10; folds are patient-separated by design."""
    required = {"strat_fold", "label"}
    if not required.issubset(df.columns):
        raise ValueError(f"Colonnes obligatoires absentes : {sorted(required - set(df.columns))}")

    usable = df[df["label"].isin(["Normal", "Abnormal"])].copy()
    usable["strat_fold"] = pd.to_numeric(usable["strat_fold"], errors="coerce")
    if usable["strat_fold"].isna().any():
        raise ValueError("Des ECG étiquetés n'ont pas de strat_fold valide.")

    train = usable[usable["strat_fold"].between(1, 8)].copy()
    validation = usable[usable["strat_fold"] == 9].copy()
    test = usable[usable["strat_fold"] == 10].copy()
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("Au moins une partition PTB-XL est vide.")
    if set(train.index) & set(validation.index) or set(train.index) & set(test.index) or set(validation.index) & set(test.index):
        raise AssertionError("Un ECG apparaît dans plusieurs partitions.")
    return train, validation, test


def _show(name: str, part: pd.DataFrame) -> None:
    counts = part["label"].value_counts().to_dict()
    print(f"{name}: {len(part)} ECGs — {counts}")


def run_split():
    df = pd.read_csv(PSEUDO_CSV, index_col="ecg_id")
    train, validation, test = split_data(df)
    train.to_csv(TRAIN_CSV, index=True)
    validation.to_csv(VALIDATION_CSV, index=True)
    test.to_csv(TEST_CSV, index=True)
    _show("Train (folds 1–8)", train)
    _show("Validation (fold 9)", validation)
    _show("Test (fold 10)", test)
    print("Partitions patient-séparées enregistrées.")
    return train, validation, test


if __name__ == "__main__":
    run_split()
