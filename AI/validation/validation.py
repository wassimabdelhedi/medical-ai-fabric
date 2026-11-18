"""Rule-based technical validation of the IA pipeline artefacts.

The three statuses concern workflow acceptance only, never medical diagnosis.
"""

import argparse
import ast
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from AI.common.artifact_utils import sha256_file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
MODELS_DIR = os.path.join(BASE_DIR, "model")
CONFIDENCE_ACCEPT_THRESHOLD = 0.80
REQUIRED_FILES = {
    "original_ecg": "original_ecg.csv",
    "processed_ecg": "processed_ecg.csv",
    "processing_report": "processing_report.json",
    "features": "features.json",
    "prediction": "prediction.json",
    "model": os.path.join("..", "model", "ecg_classifier.pkl"),
    "model_metadata": os.path.join("..", "model", "model_metadata.json"),
}


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _expected_report_label(report: dict) -> str | None:
    """Derive the PTB-XL structured report label, if SCP codes are available."""
    raw = report.get("scp_codes")
    try:
        codes = ast.literal_eval(raw) if isinstance(raw, str) else raw
        if not isinstance(codes, dict):
            return None
        table = pd.read_csv(os.path.join(DATASET_DIR, "scp_statements.csv"), index_col=0)
        diagnostic_codes = set(table.index[table["diagnostic"] == 1].astype(str))
        positive = {
            str(code) for code, likelihood in codes.items()
            if str(code) in diagnostic_codes and float(likelihood) > 0
        }
        if not positive:
            return None
        return "Normal" if positive == {"NORM"} else "Abnormal"
    except (ValueError, TypeError, SyntaxError, OSError, KeyError):
        return None


def validate_case(case_id: str) -> dict:
    case_dir = Path(OUTPUTS_DIR) / case_id
    report_path = case_dir / "processing_report.json"
    features_path = case_dir / "features.json"
    prediction_path = case_dir / "prediction.json"
    report = _read_json(report_path)
    features = _read_json(features_path)
    prediction = _read_json(prediction_path)
    model_meta = _read_json(Path(MODELS_DIR) / "model_metadata.json")

    entries = []
    for key, relative in REQUIRED_FILES.items():
        path = (case_dir / relative).resolve()
        if key in {"model", "model_metadata"}:
            path = (Path(MODELS_DIR) / os.path.basename(relative)).resolve()
        exists = path.is_file() and path.stat().st_size > 0
        artifact_id = None
        artifact_type = key.upper()
        if key == "original_ecg" and report:
            item = report.get("artifacts", {}).get("original_ecg", {})
            artifact_id, artifact_type = item.get("artifact_id"), item.get("artifact_type", artifact_type)
        elif key == "processed_ecg" and report:
            item = report.get("artifacts", {}).get("processed_ecg", {})
            artifact_id, artifact_type = item.get("artifact_id"), item.get("artifact_type", artifact_type)
        elif key == "processing_report" and report:
            artifact_id, artifact_type = report.get("artifact_id"), report.get("artifact_type", artifact_type)
        elif key == "features" and features:
            artifact_id, artifact_type = features.get("artifact_id"), features.get("artifact_type", artifact_type)
        elif key == "prediction" and prediction:
            artifact_id, artifact_type = prediction.get("artifact_id"), prediction.get("artifact_type", artifact_type)
        entries.append({
            "name": key,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "available": bool(exists),
            "sha256": sha256_file(path) if exists else None,
        })
    missing = [item["name"] for item in entries if not item["available"]]
    artifact_check = {
        "status": "FAIL" if missing else "PASS",
        "missing_artifacts": missing,
        "details": entries,
    }

    format_check = (report or {}).get("format_check", {})
    missing_check = (report or {}).get("missing_check", {})
    repaired = (report or {}).get("interpolated_samples_by_lead", {})
    if not report or not format_check.get("format_ok", False) or missing_check.get("quality") == "BAD":
        quality_check = {"status": "FAIL", "reason": "Rapport qualité absent ou contrôle de format/qualité en échec."}
    elif missing_check.get("total_missing", 0) > 0 or any(int(v) > 0 for v in repaired.values()):
        quality_check = {"status": "REVIEW", "reason": "Des échantillons ECG ont été manquants ou interpolés."}
    elif (report.get("status") or "").upper() not in {"OK", "ACCEPTED"}:
        quality_check = {"status": "REVIEW", "reason": "Le rapport de préparation signale un avertissement."}
    else:
        quality_check = {"status": "PASS", "reason": "Format conforme, aucune valeur invalide détectée ni interpolée."}

    confidence = (prediction or {}).get("confidence")
    predicted_class = (prediction or {}).get("predicted_class")
    probabilities = (prediction or {}).get("probabilities", {})
    try:
        probability_values = [float(x) for x in probabilities.values()] if isinstance(probabilities, dict) else []
        probabilities_valid = (
            bool(probability_values)
            and all(math.isfinite(x) and 0 <= x <= 1 for x in probability_values)
            and abs(sum(probability_values) - 1.0) <= 0.02
        )
    except (TypeError, ValueError):
        probabilities_valid = False
    if (not isinstance(confidence, (int, float)) or not math.isfinite(confidence)
            or not 0 <= confidence <= 1 or predicted_class not in {"Normal", "Abnormal"}
            or not probabilities_valid):
        confidence_check = {"status": "FAIL", "reason": "Prédiction ou probabilités absentes ou invalides."}
    elif confidence < CONFIDENCE_ACCEPT_THRESHOLD:
        confidence_check = {
            "status": "REVIEW",
            "reason": f"Confiance {confidence:.3f} inférieure au seuil opérationnel {CONFIDENCE_ACCEPT_THRESHOLD:.2f}.",
            "confidence": confidence,
            "threshold": CONFIDENCE_ACCEPT_THRESHOLD,
        }
    else:
        confidence_check = {
            "status": "PASS",
            "reason": f"Confiance {confidence:.3f} supérieure ou égale au seuil opérationnel {CONFIDENCE_ACCEPT_THRESHOLD:.2f}.",
            "confidence": confidence,
            "threshold": CONFIDENCE_ACCEPT_THRESHOLD,
        }

    if features and model_meta:
        values = features.get("features_flat", [])
        feature_ok = (
            features.get("n_features") == model_meta.get("n_features") == len(values)
            and features.get("feature_names") == model_meta.get("feature_names")
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
        )
    else:
        feature_ok = False
    model_path = Path(MODELS_DIR) / "ecg_classifier.pkl"
    current_model_hash = sha256_file(model_path) if model_path.is_file() else None
    model_ok = bool(
        prediction and model_meta
        and prediction.get("model_version") == model_meta.get("model_version")
        and prediction.get("model_sha256") == current_model_hash
        and feature_ok
    )
    consistency_check = None
    expected_label = _expected_report_label(report or {}) if report else None
    if expected_label is None:
        consistency_check = {
            "status": "REVIEW",
            "result": "NOT_ASSESSABLE",
            "method": "PTB-XL structured diagnostic SCP codes",
            "reason": "Codes diagnostiques structurés indisponibles; le texte libre n'est pas interprété automatiquement.",
        }
    elif prediction and expected_label == predicted_class:
        consistency_check = {
            "status": "PASS",
            "result": "CONSISTENT",
            "reference_class": expected_label,
            "method": "PTB-XL structured diagnostic SCP codes",
            "reason": "La classe prédite correspond à la classe dérivée des codes diagnostiques du rapport.",
        }
    else:
        consistency_check = {
            "status": "REVIEW",
            "result": "INCONSISTENT",
            "reference_class": expected_label,
            "method": "PTB-XL structured diagnostic SCP codes",
            "reason": "La prédiction diffère de la classe dérivée des codes diagnostiques du rapport.",
        }

    run_ids = [x.get("run_id") for x in (report, features, prediction) if x]
    run_check = {
        "status": "PASS" if run_ids and len(set(run_ids)) == 1 else "FAIL",
        "run_ids_match": bool(run_ids and len(set(run_ids)) == 1),
    }
    checks = {
        "required_artifacts": artifact_check,
        "signal_quality": quality_check,
        "prediction_confidence": confidence_check,
        "report_consistency": consistency_check,
        "model_and_features": {"status": "PASS" if model_ok else "FAIL", "compatible": model_ok},
        "run_provenance": run_check,
    }
    statuses = [value["status"] for value in checks.values()]
    overall = "REJECTED" if "FAIL" in statuses else "REVIEW_REQUIRED" if "REVIEW" in statuses else "ACCEPTED"
    run_id = (prediction or {}).get("run_id") or (report or {}).get("run_id") or str(uuid4())
    artifact = {
        "artifact_id": str(uuid4()),
        "artifact_type": "AI_VALIDATION",
        "case_id": case_id,
        "run_id": run_id,
        "status": overall,
        "rules_version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parent_artifact_ids": [x for x in [
            (report or {}).get("artifact_id"), (features or {}).get("artifact_id"),
            (prediction or {}).get("artifact_id")
        ] if x],
        "checks": checks,
        "reasons": [
            check.get("reason", ", ".join(check.get("missing_artifacts", [])))
            for check in checks.values() if check["status"] != "PASS"
        ],
        "scope": "Contrôles du pipeline uniquement; aucune validation clinique.",
    }
    output = case_dir / "validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Validation {case_id}: {overall} -> {output}")
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validation technique du résultat IA ECG")
    parser.add_argument("--case_id", required=True)
    args = parser.parse_args()
    validate_case(args.case_id)
