"""Generate a short, auditable, non-clinical explanation from validation output."""

import argparse
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")


def explain_case(case_id: str) -> dict:
    case_dir = os.path.join(OUTPUTS_DIR, case_id)
    with open(os.path.join(case_dir, "prediction.json"), encoding="utf-8") as handle:
        prediction = json.load(handle)
    with open(os.path.join(case_dir, "validation.json"), encoding="utf-8") as handle:
        validation = json.load(handle)

    status = validation["status"]
    predicted = prediction["predicted_class"]
    confidence = float(prediction["confidence"])
    if status == "ACCEPTED":
        summary = (
            f"Le modèle a proposé la classe {predicted} avec un score de {confidence:.1%}. "
            "Les contrôles techniques configurés ont été satisfaits."
        )
    elif status == "REVIEW_REQUIRED":
        summary = (
            f"Le modèle a proposé la classe {predicted} avec un score de {confidence:.1%}, "
            "mais au moins un contrôle nécessite une révision humaine."
        )
    else:
        summary = "Le pipeline n'a pas fourni tous les éléments valides requis; aucun résultat ne doit être accepté automatiquement."

    artifact = {
        "artifact_id": str(uuid4()),
        "artifact_type": "AI_EXPLANATION",
        "case_id": case_id,
        "run_id": prediction["run_id"],
        "parent_artifact_ids": [prediction["artifact_id"], validation["artifact_id"]],
        "summary": summary,
        "validation_status": status,
        "findings": validation["reasons"],
        "confidence_kind": prediction.get("confidence_kind"),
        "human_review_required": status != "ACCEPTED",
        "scope": "Explication de règles techniques; ni diagnostic ni explication causale médicale.",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(os.path.join(case_dir, "explanation.json"), "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, ensure_ascii=False)
    print(f"Explication générée pour {case_id}.")
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case_id", required=True)
    explain_case(parser.parse_args().case_id)
