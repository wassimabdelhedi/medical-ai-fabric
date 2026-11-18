"""
prediction.py
-------------
Étape 6 du pipeline IA — Exécution du modèle IA pour prédire la classe ECG.

Ce module :
  1. Charge models/ecg_classifier.pkl et ses métadonnées
  2. Charge outputs/<case_id>/features.json
  3. Effectue la prédiction et calcule les probabilités par classe
  4. Génère outputs/<case_id>/prediction.json avec le format exact
     convenu avec l'équipe Blockchain :
     {
       "artifact_id": "PRED00001",
       "case_id": "CASE00001",
       "artifact_type": "AI_PREDICTION",
       "predicted_class": "Normal",
       "confidence": 0.94,
       "probabilities": {
         "Normal": 0.94,
         "Abnormal": 0.06
       },
       "model_name": "ECG_Classifier",
       "model_version": "1.0",
       "parent_artifact_id": "FEAT00001",
       "timestamp": "2026-11-15T14:00:00Z"
     }

Utilisation :
  python prediction.py --case_id CASE00001
"""

import os
import sys
import json
import argparse
import joblib
import numpy as np
from datetime import datetime, timezone
from uuid import uuid4

from artifact_utils import sha256_file

# ─────────────────────────────────────────────────────────
# CHEMINS
# ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR  = os.path.join(BASE_DIR, "models")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

MODEL_PATH  = os.path.join(MODELS_DIR, "ecg_classifier.pkl")
META_PATH   = os.path.join(MODELS_DIR, "model_metadata.json")


def load_model_and_meta():
    """Charge le modèle sérialisé et ses métadonnées."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"[ERREUR] Modèle introuvable : {MODEL_PATH}\n"
            f"  -> Exécute d'abord : python train_model.py"
        )

    model = joblib.load(MODEL_PATH)
    meta = {}
    if os.path.exists(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)

    if meta.get("model_version") != "2.0.0":
        raise RuntimeError(
            "Le modèle présent n'a pas été réentraîné avec le pipeline corrigé. "
            "Lancez train_model.py avant de générer une prédiction."
        )

    return model, meta


def load_features(case_id: str) -> tuple[dict, list]:
    """Charge le fichier features.json généré par feature_extraction.py."""
    feat_path = os.path.join(OUTPUTS_DIR, case_id, "features.json")
    if not os.path.exists(feat_path):
        raise FileNotFoundError(
            f"[ERREUR] features.json introuvable pour {case_id}.\n"
            f"  -> Exécute d'abord : python feature_extraction.py --case_id {case_id}"
        )

    with open(feat_path, "r", encoding="utf-8") as f:
        feat_data = json.load(f)

    return feat_data, feat_data["features_flat"]


def run_prediction(case_id: str) -> dict:
    """
    Exécute la prédiction pour un cas et écrit prediction.json.
    """
    print("=" * 60)
    print(f"  PRÉDICTION IA — {case_id}")
    print("=" * 60)

    # 1. Chargement modèle et données
    model, meta = load_model_and_meta()
    feat_data, X_flat = load_features(case_id)

    expected = int(meta.get("n_features", len(X_flat)))
    if len(X_flat) != expected:
        raise ValueError(
            f"Nombre de caractéristiques incompatible: {len(X_flat)} reçu, "
            f"{expected} attendu par le modèle. Régénérez features.json."
        )
    if meta.get("feature_names") and feat_data.get("feature_names") != meta["feature_names"]:
        raise ValueError("L'ordre ou les noms des caractéristiques ne correspondent pas au modèle.")

    model_name = meta.get("model_name", "ECG_Classifier")
    model_version = meta.get("model_version", "1.0")
    model_digest = sha256_file(MODEL_PATH)

    # 2. Prédiction
    X = np.array(X_flat).reshape(1, -1)
    predicted_class = str(model.predict(X)[0])
    probabilities_raw = model.predict_proba(X)[0]

    # Map classes -> probabilités
    classes = list(model.classes_)
    probs = {}
    for c, p in zip(classes, probabilities_raw):
        probs[str(c)] = round(float(p), 4)

    confidence = probs[predicted_class]

    # 3. Structure convenue de l'artefact
    prediction_artifact_id = str(uuid4())
    artifact = {
        "artifact_id"        : prediction_artifact_id,
        "case_id"            : case_id,
        "run_id"             : feat_data["run_id"],
        "artifact_type"      : "AI_PREDICTION",
        "predicted_class"    : predicted_class,
        "confidence"         : confidence,
        "probabilities"      : probs,
        "model_name"         : model_name,
        "model_version"      : model_version,
        "model_sha256"       : model_digest,
        "model_artifact_id"  : f"MODEL-{model_digest[:24]}",
        "confidence_kind"    : "random_forest_probability_not_clinically_calibrated",
        "parent_artifact_id" : feat_data["artifact_id"],
        "parent_artifact_ids": [feat_data["artifact_id"]],
        "timestamp"          : datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    # 4. Sauvegarde
    out_path = os.path.join(OUTPUTS_DIR, case_id, "prediction.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Classe prédite  : {predicted_class}")
    print(f"  [OK] Confiance       : {confidence * 100:.2f}%")
    print(f"  [OK] Probabilités    : {probs}")
    print(f"  [SAVE] prediction.json : {out_path}")
    print("=" * 60)

    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prédiction IA ECG")
    parser.add_argument("--case_id", type=str, default="CASE00001", help="ID du cas (ex: CASE00001)")
    args = parser.parse_args()

    run_prediction(args.case_id)
