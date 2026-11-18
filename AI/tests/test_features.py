"""
test_features.py
-----------------
Tests unitaires pour src/feature_extraction.py

Vérifie :
  1. Les features sont tous des floats valides (pas de NaN ni Inf)
  2. Le nombre de features est exactement 108 (9 × 12)
  3. Les noms des features sont corrects et dans le bon ordre
  4. Le dict features_by_lead contient bien les 12 dérivations
"""

import sys
import os
import math
import numpy as np
import pytest

from AI.feature_extraction.feature_extraction import (
    compute_features_one_lead,
    extract_all_features,
    flatten_features,
    LEAD_NAMES,
)


# ─────────────────────────────────────────────
# Fixture : signal normalisé synthétique
# ─────────────────────────────────────────────

def make_normalized_signal():
    """Signal z-scoré synthétique : 5000 × 12."""
    np.random.seed(42)
    signal = np.random.randn(5000, 12)
    # Z-score par dérivation (simulation de la sortie de preprocessing)
    for i in range(12):
        signal[:, i] = (signal[:, i] - signal[:, i].mean()) / signal[:, i].std()
    return signal


# ─────────────────────────────────────────────
# Test 1 : compute_features_one_lead
# ─────────────────────────────────────────────

def test_one_lead_returns_9_features():
    """compute_features_one_lead doit retourner exactement 9 clés."""
    col = np.random.randn(5000)
    feats = compute_features_one_lead(col, "I")
    assert len(feats) == 9, f"Attendu 9 features, obtenu {len(feats)}"


def test_one_lead_all_floats():
    """Toutes les valeurs de features doivent être des float valides (pas NaN, pas Inf)."""
    col = np.random.randn(5000)
    feats = compute_features_one_lead(col, "I")
    for key, val in feats.items():
        assert isinstance(val, float), f"{key} n'est pas un float : {type(val)}"
        assert math.isfinite(val), f"{key} = {val} n'est pas fini"


def test_one_lead_expected_keys():
    """Les 9 clés attendues doivent toutes être présentes."""
    expected = {"q01", "q05", "q25", "q75", "q95", "q99", "skewness", "kurtosis", "diff_rms"}
    col = np.random.randn(5000)
    feats = compute_features_one_lead(col, "I")
    assert set(feats.keys()) == expected, (
        f"Clés manquantes ou inattendues : {set(feats.keys()) ^ expected}"
    )


def test_one_lead_quantile_ordering():
    """Les quantiles doivent être dans l'ordre croissant : q01 ≤ q05 ≤ q25 ≤ q75 ≤ q95 ≤ q99."""
    col = np.random.randn(5000)
    f = compute_features_one_lead(col, "I")
    assert f["q01"] <= f["q05"] <= f["q25"] <= f["q75"] <= f["q95"] <= f["q99"]


def test_diff_rms_positive():
    """diff_rms doit toujours être ≥ 0."""
    col = np.random.randn(5000)
    feats = compute_features_one_lead(col, "I")
    assert feats["diff_rms"] >= 0


# ─────────────────────────────────────────────
# Test 2 : extract_all_features (12 dérivations)
# ─────────────────────────────────────────────

def test_extract_all_features_has_all_leads():
    """Le dict retourné doit contenir exactement les 12 noms de dérivations."""
    signal = make_normalized_signal()
    feats = extract_all_features(signal)
    assert set(feats.keys()) == set(LEAD_NAMES), (
        f"Dérivations manquantes : {set(LEAD_NAMES) - set(feats.keys())}"
    )


def test_extract_all_features_all_valid():
    """Toutes les 108 valeurs doivent être des floats finis."""
    signal = make_normalized_signal()
    feats = extract_all_features(signal)
    for lead, stats in feats.items():
        for key, val in stats.items():
            assert math.isfinite(val), f"{lead}.{key} = {val} n'est pas fini"


# ─────────────────────────────────────────────
# Test 3 : flatten_features
# ─────────────────────────────────────────────

def test_flatten_produces_108_values():
    """Le vecteur aplati doit contenir exactement 108 valeurs (9 × 12)."""
    signal = make_normalized_signal()
    feats = extract_all_features(signal)
    flat = flatten_features(feats)
    assert len(flat) == 108, f"Attendu 108, obtenu {len(flat)}"


def test_flatten_all_floats():
    """Toutes les valeurs du vecteur plat doivent être des floats finis."""
    signal = make_normalized_signal()
    feats = extract_all_features(signal)
    flat = flatten_features(feats)
    for i, val in enumerate(flat):
        assert math.isfinite(val), f"flat[{i}] = {val} n'est pas fini"


def test_flatten_order_matches_leads():
    """
    Les 9 premières valeurs du vecteur plat doivent correspondre
    aux features de la dérivation I dans le bon ordre.
    """
    signal = make_normalized_signal()
    feats = extract_all_features(signal)
    flat = flatten_features(feats)
    stat_order = ["q01", "q05", "q25", "q75", "q95", "q99", "skewness", "kurtosis", "diff_rms"]
    for j, stat in enumerate(stat_order):
        expected = feats["I"][stat]
        assert flat[j] == pytest.approx(expected, rel=1e-6), (
            f"flat[{j}] ({flat[j]}) ≠ I.{stat} ({expected})"
        )
