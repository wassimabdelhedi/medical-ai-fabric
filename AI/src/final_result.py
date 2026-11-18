"""Create the final workflow outcome without presenting it as a diagnosis."""

import argparse
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")


def finalize_case(case_id: str) -> dict:
    case_dir = os.path.join(OUTPUTS_DIR, case_id)
    with open(os.path.join(case_dir, "prediction.json"), encoding="utf-8") as handle:
        prediction = json.load(handle)
    with open(os.path.join(case_dir, "validation.json"), encoding="utf-8") as handle:
        validation = json.load(handle)
    with open(os.path.join(case_dir, "explanation.json"), encoding="utf-8") as handle:
        explanation = json.load(handle)

    status = validation["status"]
    artifact = {
        "artifact_id": str(uuid4()),
        "artifact_type": "AI_FINAL_RESULT",
        "case_id": case_id,
        "run_id": prediction["run_id"],
        "parent_artifact_ids": [prediction["artifact_id"], validation["artifact_id"], explanation["artifact_id"]],
        "status": status,
        "predicted_class": prediction["predicted_class"],
        "confidence": prediction["confidence"],
        "human_review_required": status != "ACCEPTED",
        "workflow_outcome": "PIPELINE_REJECTED" if status == "REJECTED" else "RESULT_AVAILABLE",
        "explanation": explanation["summary"],
        "scope": "Statut d'acceptation du flux technique uniquement; ne constitue pas une décision médicale.",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(os.path.join(case_dir, "final_result.json"), "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, ensure_ascii=False)
    print(f"Résultat final généré pour {case_id}: {status}.")
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case_id", required=True)
    finalize_case(parser.parse_args().case_id)
