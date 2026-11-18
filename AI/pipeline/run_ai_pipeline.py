"""Run the IA and Fabric-demo artefact workflow for one ECG case."""

import argparse
import re
from uuid import uuid4

from AI.preprocessing.preprocessing import run_preprocessing
from AI.feature_extraction.feature_extraction import run_feature_extraction
from AI.prediction.prediction import run_prediction
from AI.validation.validation import validate_case
from AI.explanation.explanation import explain_case
from AI.pipeline.final_result import finalize_case
from AI.pipeline.fabric_package import build_fabric_package


def run_pipeline(case_id: str) -> dict:
    if not re.fullmatch(r"CASE\d{5,}", case_id):
        raise ValueError("case_id doit respecter le format CASE suivi d'au moins cinq chiffres.")
    run_id = str(uuid4())
    print(f"Démarrage du pipeline pour {case_id}; run_id={run_id}")
    run_preprocessing(case_id, run_id=run_id)
    run_feature_extraction(case_id)
    run_prediction(case_id)
    validation = validate_case(case_id)
    explanation = explain_case(case_id)
    final_result = finalize_case(case_id)
    package = build_fabric_package(case_id)
    print(f"Pipeline terminé: {validation['status']}")
    print(f"Artefacts: {validation['artifact_id']}, {explanation['artifact_id']}, {final_result['artifact_id']}")
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exécuter toute la chaîne IA ECG et préparer l'exemple Fabric")
    parser.add_argument("--case_id", required=True, help="Exemple: CASE00001")
    run_pipeline(parser.parse_args().case_id)
