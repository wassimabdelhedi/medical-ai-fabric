"""Train and evaluate the PTB-XL baseline with the inference preprocessing."""

import json
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
import wfdb
from joblib import Parallel, delayed
from scipy.stats import skew, kurtosis
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, average_precision_score, classification_report,
    confusion_matrix, f1_score, roc_auc_score,
)

from preprocessing import (
    LEAD_NAMES, SAMPLING_RATE, denoise_signal, normalize_signal,
    repair_invalid_values,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MODELS_DIR = os.path.join(BASE_DIR, "models")
TRAIN_CSV = os.path.join(DATASET_DIR, "train_set.csv")
VALIDATION_CSV = os.path.join(DATASET_DIR, "validation_set.csv")
TEST_CSV = os.path.join(DATASET_DIR, "test_set.csv")
MODEL_PATH = os.path.join(MODELS_DIR, "ecg_classifier.pkl")
META_PATH = os.path.join(MODELS_DIR, "model_metadata.json")

FILTER_LOWCUT = 0.5
FILTER_HIGHCUT = 40.0
FILTER_ORDER = 4
STAT_ORDER = ["q01", "q05", "q25", "q75", "q95", "q99", "skewness", "kurtosis", "diff_rms"]


def extract_features(signal: np.ndarray) -> np.ndarray:
    """Create the same 9 per-lead features as feature_extraction.py."""
    values = []
    for column in signal.T:
        values.extend([
            np.percentile(column, 1), np.percentile(column, 5),
            np.percentile(column, 25), np.percentile(column, 75),
            np.percentile(column, 95), np.percentile(column, 99),
            skew(column, bias=False), kurtosis(column, bias=False),
            np.sqrt(np.mean(np.diff(column) ** 2)),
        ])
    result = np.asarray(values, dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError("Les caractéristiques calculées contiennent NaN ou Inf.")
    return result


def extract_single_ecg(filename: str, label: str):
    """Read, validate, repair and preprocess one 12-lead ECG."""
    try:
        record_path = os.path.join(DATASET_DIR, filename)
        signal, fields = wfdb.rdsamp(record_path)
        if fields.get("fs") != SAMPLING_RATE:
            raise ValueError(f"Fréquence inattendue: {fields.get('fs')} Hz")
        if signal.shape != (5000, len(LEAD_NAMES)):
            raise ValueError(f"Dimensions inattendues: {signal.shape}")
        signal, _ = repair_invalid_values(signal)
        signal = denoise_signal(signal, fs=SAMPLING_RATE, verbose=False)
        signal, _ = normalize_signal(signal, verbose=False)
        return extract_features(signal), label, None
    except Exception as exc:
        return None, label, f"{filename}: {type(exc).__name__}: {exc}"


def process_dataset(df: pd.DataFrame, name: str):
    start = time.time()
    results = []
    rows = list(df.itertuples(index=False))
    n_jobs = max(1, min(6, os.cpu_count() or 1))
    print(f"{name}: démarrage sur {len(rows)} ECGs avec {n_jobs} workers.", flush=True)
    generated = Parallel(n_jobs=n_jobs, batch_size=64, return_as="generator_unordered")(
        delayed(extract_single_ecg)(row.filename_hr, row.label) for row in rows
    )
    for index, result in enumerate(generated, start=1):
        results.append(result)
        if index % 500 == 0 or index == len(rows):
            print(f"{name}: {index}/{len(rows)} ECGs prétraités.", flush=True)
    valid = [(features, label) for features, label, error in results if features is not None]
    errors = [error for _, _, error in results if error]
    if not valid:
        raise RuntimeError(f"Aucun ECG valide dans la partition {name}.")
    x = np.stack([item[0] for item in valid])
    y = np.asarray([item[1] for item in valid])
    print(f"{name}: {len(valid)}/{len(df)} ECG valides; {len(errors)} rejetés; {time.time()-start:.1f}s")
    return x, y, errors


def evaluate(model, x, y) -> dict:
    predicted = model.predict(x)
    probabilities = model.predict_proba(x)
    abnormal_index = list(model.classes_).index("Abnormal")
    return {
        "n_samples": int(len(y)),
        "accuracy": float(accuracy_score(y, predicted)),
        "f1_macro": float(f1_score(y, predicted, average="macro")),
        "classification_report": classification_report(
            y, predicted, labels=["Normal", "Abnormal"], output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(
            y, predicted, labels=["Normal", "Abnormal"]
        ).tolist(),
        "confusion_matrix_labels": ["Normal", "Abnormal"],
        "roc_auc_abnormal": float(roc_auc_score(y == "Abnormal", probabilities[:, abnormal_index])),
        "pr_auc_abnormal": float(average_precision_score(y == "Abnormal", probabilities[:, abnormal_index])),
    }


def train_complete_pipeline():
    os.makedirs(MODELS_DIR, exist_ok=True)
    train_df = pd.read_csv(TRAIN_CSV)
    validation_df = pd.read_csv(VALIDATION_CSV)
    test_df = pd.read_csv(TEST_CSV)

    x_train, y_train, train_errors = process_dataset(train_df, "train")
    x_val, y_val, val_errors = process_dataset(validation_df, "validation")
    x_test, y_test, test_errors = process_dataset(test_df, "test")

    model = RandomForestClassifier(
        n_estimators=300, max_depth=None, min_samples_leaf=2,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    started = time.time()
    model.fit(x_train, y_train)
    fit_seconds = time.time() - started

    validation_metrics = evaluate(model, x_val, y_val)
    test_metrics = evaluate(model, x_test, y_test)
    feature_names = [f"{lead}_{stat}" for lead in LEAD_NAMES for stat in STAT_ORDER]
    metadata = {
        "model_name": "PTB-XL ECG Normal-Abnormal Random Forest",
        "model_version": "2.0.0",
        "algorithm": "RandomForestClassifier",
        "model_parameters": model.get_params(),
        "software_versions": {
            "numpy": np.__version__, "pandas": pd.__version__,
            "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
            "wfdb": wfdb.__version__,
        },
        "dataset": "PTB-XL v1.0.3",
        "label_definition": "Normal only when NORM is the sole positive diagnostic SCP code; otherwise Abnormal when another positive diagnostic code exists.",
        "split_definition": "PTB-XL strat_fold: folds 1-8 train, fold 9 validation, fold 10 test; patient-separated folds.",
        "preprocessing": {
            "sampling_rate_hz": SAMPLING_RATE,
            "filter": {"type": "Butterworth bandpass", "low_hz": FILTER_LOWCUT, "high_hz": FILTER_HIGHCUT, "order": FILTER_ORDER},
            "invalid_values": "interpolate per lead only up to 0.5%; otherwise reject ECG",
            "normalization": "per-record, per-lead z-score",
            "features": STAT_ORDER,
        },
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "classes": list(model.classes_),
        "confidence_note": "Random Forest class probability; not clinically calibrated.",
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "rejected_ecgs": {"train": train_errors, "validation": val_errors, "test": test_errors},
        "n_train_samples": len(y_train),
        "n_validation_samples": len(y_val),
        "n_test_samples": len(y_test),
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "training_duration_seconds": round(fit_seconds, 2),
    }
    joblib.dump(model, MODEL_PATH)
    with open(META_PATH, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)

    print("Validation:", json.dumps(validation_metrics, ensure_ascii=False))
    print("Test:", json.dumps(test_metrics, ensure_ascii=False))
    print(f"Modèle et métadonnées sauvegardés dans {MODELS_DIR}")


if __name__ == "__main__":
    train_complete_pipeline()
