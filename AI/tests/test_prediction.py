"""
test_prediction.py
-------------------
Tests unitaires pour la structure et les contraintes de prediction.json

Vérifie (sans charger le vrai modèle .pkl) :
  1. La confiance est toujours entre 0 et 1
  2. Les probabilités somment à 1.0
  3. La classe prédite est bien "Normal" ou "Abnormal"
  4. Les champs obligatoires pour la Blockchain sont tous présents
  5. Le timestamp respecte le format ISO 8601 UTC
"""

import sys
import os
import json
import math
import re
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ─────────────────────────────────────────────
# Fixture : prediction JSON minimal valide
# ─────────────────────────────────────────────

def make_prediction(predicted_class="Normal", confidence=0.89):
    """Construit un objet prediction.json conforme au schéma convenu."""
    other = round(1.0 - confidence, 4)
    if predicted_class == "Normal":
        probs = {"Normal": confidence, "Abnormal": other}
    else:
        probs = {"Abnormal": confidence, "Normal": other}
    return {
        "artifact_id": "test-uuid-1234",
        "case_id": "CASE00001",
        "run_id": "run-uuid-5678",
        "artifact_type": "AI_PREDICTION",
        "predicted_class": predicted_class,
        "confidence": confidence,
        "probabilities": probs,
        "model_name": "PTB-XL ECG Normal-Abnormal Random Forest",
        "model_version": "2.0.0",
        "model_sha256": "abc123",
        "confidence_kind": "random_forest_probability_not_clinically_calibrated",
        "parent_artifact_id": "feat-uuid-9999",
        "parent_artifact_ids": ["feat-uuid-9999"],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ─────────────────────────────────────────────
# Test 1 : Confiance entre 0 et 1
# ─────────────────────────────────────────────

@pytest.mark.parametrize("confidence", [0.0, 0.5, 0.8, 0.94, 1.0])
def test_confidence_in_range(confidence):
    """La confiance doit être dans [0, 1]."""
    pred = make_prediction(confidence=confidence)
    c = pred["confidence"]
    assert 0.0 <= c <= 1.0, f"Confiance hors plage : {c}"


def test_confidence_is_finite():
    """La confiance ne doit pas être NaN ou Inf."""
    pred = make_prediction(confidence=0.88)
    assert math.isfinite(pred["confidence"])


# ─────────────────────────────────────────────
# Test 2 : Les probabilités somment à 1
# ─────────────────────────────────────────────

@pytest.mark.parametrize("cls,conf", [
    ("Normal", 0.94),
    ("Abnormal", 0.72),
    ("Normal", 0.80),
])
def test_probabilities_sum_to_one(cls, conf):
    """Normal + Abnormal doit valoir 1.0 (à ±0.01 près pour les arrondis)."""
    pred = make_prediction(predicted_class=cls, confidence=conf)
    total = sum(pred["probabilities"].values())
    assert abs(total - 1.0) < 0.01, f"Somme des probabilités = {total} ≠ 1.0"


def test_probabilities_both_in_range():
    """Chaque probabilité individuelle doit être dans [0, 1]."""
    pred = make_prediction(confidence=0.76)
    for cls, prob in pred["probabilities"].items():
        assert 0.0 <= prob <= 1.0, f"P({cls}) = {prob} hors [0,1]"


# ─────────────────────────────────────────────
# Test 3 : Classe prédite valide
# ─────────────────────────────────────────────

@pytest.mark.parametrize("cls", ["Normal", "Abnormal"])
def test_predicted_class_valid(cls):
    """La classe prédite doit être exactement 'Normal' ou 'Abnormal'."""
    pred = make_prediction(predicted_class=cls)
    assert pred["predicted_class"] in {"Normal", "Abnormal"}


def test_predicted_class_matches_max_probability():
    """La classe prédite doit correspondre à la probabilité la plus haute."""
    pred = make_prediction(predicted_class="Normal", confidence=0.89)
    dominant = max(pred["probabilities"], key=pred["probabilities"].get)
    assert pred["predicted_class"] == dominant, (
        f"Classe prédite '{pred['predicted_class']}' ≠ classe dominante '{dominant}'"
    )


# ─────────────────────────────────────────────
# Test 4 : Champs obligatoires pour la Blockchain
# ─────────────────────────────────────────────

REQUIRED_BLOCKCHAIN_FIELDS = [
    "artifact_id", "case_id", "artifact_type", "predicted_class",
    "confidence", "probabilities", "model_name", "model_version",
    "parent_artifact_ids", "timestamp",
]

def test_all_blockchain_fields_present():
    """Tous les champs requis par l'équipe Blockchain doivent être présents."""
    pred = make_prediction()
    for field in REQUIRED_BLOCKCHAIN_FIELDS:
        assert field in pred, f"Champ obligatoire manquant : '{field}'"


def test_artifact_type_correct():
    """artifact_type doit valoir exactement 'AI_PREDICTION'."""
    pred = make_prediction()
    assert pred["artifact_type"] == "AI_PREDICTION"


# ─────────────────────────────────────────────
# Test 5 : Format du timestamp ISO 8601 UTC
# ─────────────────────────────────────────────

ISO8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

def test_timestamp_format():
    """Le timestamp doit respecter le format ISO 8601 UTC : YYYY-MM-DDTHH:MM:SSZ."""
    pred = make_prediction()
    ts = pred["timestamp"]
    assert ISO8601_UTC_PATTERN.match(ts), (
        f"Timestamp '{ts}' ne respecte pas le format YYYY-MM-DDTHH:MM:SSZ"
    )


def test_timestamp_is_parseable():
    """Le timestamp doit être parseable par datetime.strptime."""
    pred = make_prediction()
    # Ne doit pas lever d'exception
    datetime.strptime(pred["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
