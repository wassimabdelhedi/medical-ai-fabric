"""
test_validation.py
-------------------
Tests unitaires pour la logique de validation (sans I/O disque).

Vérifie les 3 statuts : ACCEPTED, REVIEW_REQUIRED, REJECTED
en simulant différents scénarios de confiance et de qualité.
"""

import sys
import os
import math
import pytest

# ─────────────────────────────────────────────
# Logique de validation extraite (pure, testable sans fichiers)
# ─────────────────────────────────────────────
# On teste la logique métier indépendamment du système de fichiers.

def check_confidence(confidence: float,
                     threshold_accept: float = 0.80,
                     threshold_review: float = 0.60) -> str:
    """Réplique de la règle de confiance de validation.py."""
    if confidence >= threshold_accept:
        return "OK"
    elif confidence >= threshold_review:
        return "REVIEW"
    else:
        return "FAIL"


def check_ecg_quality(features_by_lead: dict) -> dict:
    """
    Réplique de la règle qualité de validation.py.
    Signal plat = std ≈ 0 sur toutes les dérivations → mauvaise qualité.
    """
    stds = []
    for lead_stats in features_by_lead.values():
        # diff_rms est un proxy de variabilité disponible dans features.json
        stds.append(lead_stats.get("diff_rms", 1.0))
    mean_variability = sum(stds) / len(stds) if stds else 0.0
    if mean_variability < 1e-4:
        return {"status": "FAIL", "score": 0.0, "message": "Signal quasi-plat détecté"}
    return {"status": "OK", "score": min(1.0, mean_variability), "message": "Qualité correcte"}


def determine_status(confidence_check: str, quality_check: str,
                     artifacts_check: str) -> str:
    """Détermine le statut final selon les règles du plan."""
    if artifacts_check == "FAIL":
        return "REJECTED"
    if confidence_check == "FAIL":
        return "REJECTED"
    if confidence_check == "REVIEW" or quality_check == "FAIL":
        return "REVIEW_REQUIRED"
    return "ACCEPTED"


# ─────────────────────────────────────────────
# Test 1 : check_confidence
# ─────────────────────────────────────────────

@pytest.mark.parametrize("conf,expected", [
    (0.95, "OK"),
    (0.80, "OK"),      # exactement au seuil → ACCEPTED
    (0.79, "REVIEW"),
    (0.60, "REVIEW"),  # exactement au seuil bas → REVIEW
    (0.59, "FAIL"),
    (0.0,  "FAIL"),
])
def test_check_confidence(conf, expected):
    result = check_confidence(conf)
    assert result == expected, f"confiance={conf} → attendu {expected}, obtenu {result}"


# ─────────────────────────────────────────────
# Test 2 : check_ecg_quality
# ─────────────────────────────────────────────

def make_good_features():
    """Features simulées d'un ECG de bonne qualité (diff_rms > 0)."""
    leads = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
    return {lead: {"q01": -1.5, "q99": 2.0, "diff_rms": 0.15} for lead in leads}


def make_flat_features():
    """Features simulées d'un signal plat (diff_rms ≈ 0)."""
    leads = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
    return {lead: {"q01": 0.0, "q99": 0.0, "diff_rms": 0.0} for lead in leads}


def test_good_signal_quality_ok():
    result = check_ecg_quality(make_good_features())
    assert result["status"] == "OK"


def test_flat_signal_quality_fail():
    result = check_ecg_quality(make_flat_features())
    assert result["status"] == "FAIL"
    assert "plat" in result["message"].lower() or "flat" in result["message"].lower()


# ─────────────────────────────────────────────
# Test 3 : determine_status — les 3 scénarios
# ─────────────────────────────────────────────

def test_status_accepted():
    """ACCEPTED : confiance OK, qualité OK, artefacts PASS."""
    status = determine_status("OK", "OK", "PASS")
    assert status == "ACCEPTED"


def test_status_review_low_confidence():
    """REVIEW_REQUIRED : confiance REVIEW (entre 0.60 et 0.80)."""
    status = determine_status("REVIEW", "OK", "PASS")
    assert status == "REVIEW_REQUIRED"


def test_status_review_bad_quality():
    """REVIEW_REQUIRED : qualité FAIL même si la confiance est OK."""
    status = determine_status("OK", "FAIL", "PASS")
    assert status == "REVIEW_REQUIRED"


def test_status_rejected_low_confidence():
    """REJECTED : confiance FAIL (< 0.60)."""
    status = determine_status("FAIL", "OK", "PASS")
    assert status == "REJECTED"


def test_status_rejected_missing_artifact():
    """REJECTED : artefact manquant, peu importe la confiance."""
    status = determine_status("OK", "OK", "FAIL")
    assert status == "REJECTED"


def test_status_rejected_takes_priority_over_review():
    """REJECTED est prioritaire sur REVIEW_REQUIRED."""
    status = determine_status("FAIL", "FAIL", "FAIL")
    assert status == "REJECTED"
