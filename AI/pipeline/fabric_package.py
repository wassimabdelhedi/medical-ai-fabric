"""Build a privacy-minimised manifest/example payload for the Fabric team.

Only hashes and provenance go into the ledger manifest. Medical files, features,
the full processing report, model weights, and the secure mapping remain off-chain.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from AI.common.artifact_utils import sha256_file

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"
MODELS_DIR = BASE_DIR / "model"


def _json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_fabric_package(case_id: str) -> dict:
    case_dir = OUTPUTS_DIR / case_id
    report = _json(case_dir / "processing_report.json")
    features = _json(case_dir / "features.json")
    prediction = _json(case_dir / "prediction.json")
    validation = _json(case_dir / "validation.json")
    explanation = _json(case_dir / "explanation.json")
    final_result = _json(case_dir / "final_result.json")
    model_meta = _json(MODELS_DIR / "model_metadata.json")

    fabric_case_id = f"FABCASE-{uuid4()}"
    run_id = prediction["run_id"]
    model_hash = sha256_file(MODELS_DIR / "ecg_classifier.pkl")
    model_artifact_id = f"MODEL-{model_hash[:24]}"
    artifact_specs = [
        (report["artifacts"]["original_ecg"]["artifact_id"], "ECG_ORIGINAL", case_dir / "original_ecg.csv", [], report["timestamp_start"]),
        (report["artifacts"]["processed_ecg"]["artifact_id"], "ECG_PROCESSED", case_dir / "processed_ecg.csv", [report["artifacts"]["original_ecg"]["artifact_id"]], report["timestamp_end"]),
        (report["artifact_id"], "PREPROCESSING_REPORT", case_dir / "processing_report.json", [report["artifacts"]["processed_ecg"]["artifact_id"]], report["timestamp_end"]),
        (features["artifact_id"], "FEATURES", case_dir / "features.json", [report["artifacts"]["processed_ecg"]["artifact_id"]], features["timestamp"]),
        (model_artifact_id, "AI_MODEL", MODELS_DIR / "ecg_classifier.pkl", [], model_meta["trained_at"]),
        (prediction["artifact_id"], "AI_PREDICTION", case_dir / "prediction.json", [features["artifact_id"], model_artifact_id], prediction["timestamp"]),
        (validation["artifact_id"], "AI_VALIDATION", case_dir / "validation.json", [report["artifact_id"], features["artifact_id"], prediction["artifact_id"]], validation["timestamp"]),
        (explanation["artifact_id"], "AI_EXPLANATION", case_dir / "explanation.json", [prediction["artifact_id"], validation["artifact_id"]], explanation["timestamp"]),
        (final_result["artifact_id"], "AI_FINAL_RESULT", case_dir / "final_result.json", [prediction["artifact_id"], validation["artifact_id"], explanation["artifact_id"]], final_result["timestamp"]),
    ]
    ledger_records = []
    for artifact_id, artifact_type, path, parents, created_at in artifact_specs:
        ledger_records.append({
            "schema_version": "1.0",
            "artifact_id": artifact_id,
            "case_id": fabric_case_id,
            "run_id": run_id,
            "artifact_type": artifact_type,
            "sha256": sha256_file(path),
            "created_at_utc": created_at,
            "parent_artifact_ids": parents,
            "model_name": model_meta["model_name"],
            "model_version": model_meta["model_version"],
            "storage_ref": None,
            "storage_state": "LOCAL_ONLY_REFERENCE_NOT_CONFIGURED",
            "producer": "IA-ECG-prototype",
        })

    # Include only result payloads. Rewrite the internal, sequential case ID;
    # never export the PTB ecg_id, report text, local paths, waveform or feature vector.
    payloads = {}
    for name, source in [
        ("prediction", prediction), ("validation", validation),
        ("explanation", explanation), ("final_result", final_result),
    ]:
        payload = dict(source)
        payload["case_id"] = fabric_case_id
        payloads[name] = payload

    package = {
        "schema_version": "1.0",
        "package_type": "FABRIC_IA_DEMO_PACKAGE",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "case_id": fabric_case_id,
        "run_id": run_id,
        "ledger_records": ledger_records,
        "application_result_payloads_offchain": payloads,
        "transmission_scope": {
            "submit_to_fabric": "ledger_records only, after setting a real storage_ref",
            "do_not_store_on_ledger": "application_result_payloads_offchain and all medical files",
        },
        "privacy": {
            "contains_raw_ecg": False,
            "contains_medical_report_text": False,
            "contains_feature_vector": False,
            "contains_patient_mapping": False,
            "note": "Démonstrateur PTB-XL public : les empreintes peuvent être comparées aux enregistrements publics et ne garantissent pas l'anonymat.",
        },
        "integration_note": "storage_ref est null tant que le connecteur de stockage hors chaîne n'est pas configuré; ne pas soumettre en production avant de le renseigner.",
    }
    target = case_dir / "fabric_package.json"
    target.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Paquet Fabric généré: {target}")
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Créer le paquet d'exemple pour Hyperledger Fabric")
    parser.add_argument("--case_id", required=True)
    build_fabric_package(parser.parse_args().case_id)
