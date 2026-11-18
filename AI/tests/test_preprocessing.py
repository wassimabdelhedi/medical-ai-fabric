"""
test_preprocessing.py
----------------------
Tests unitaires pour src/preprocessing.py

Vérifie :
  1. Le filtre passe-bande produit un signal de la bonne forme
  2. La normalisation z-score centre chaque dérivation à 0 et std ≈ 1
  3. Les valeurs manquantes sont détectées et rejetées au-delà du seuil
  4. La vérification de format rejette un signal mal formé
"""

import sys
import os
import numpy as np
import pytest

# Ajoute src/ au path pour importer les modules IA
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing import (
    check_format,
    denoise_signal,
    normalize_signal,
    repair_invalid_values,
    SAMPLING_RATE,
    EXPECTED_LEADS,
    EXPECTED_SAMPLES,
)

# Faux champs WFDB minimal pour check_format (qui attend aussi un dict 'fields')
def make_valid_fields():
    return {"fs": SAMPLING_RATE, "sig_name": [str(i) for i in range(EXPECTED_LEADS)]}


# ─────────────────────────────────────────────
# Fixtures : signaux synthétiques de test
# ─────────────────────────────────────────────

def make_valid_signal(amplitude=1.0):
    """Signal valide : 5000 échantillons × 12 dérivations, sinusoïde 1 Hz."""
    t = np.linspace(0, 10, EXPECTED_SAMPLES)
    signal = np.zeros((EXPECTED_SAMPLES, EXPECTED_LEADS))
    for i in range(EXPECTED_LEADS):
        signal[:, i] = amplitude * np.sin(2 * np.pi * 1.0 * t + i * 0.1)
    return signal


# ─────────────────────────────────────────────
# Test 1 : check_format
# ─────────────────────────────────────────────

def test_check_format_valid():
    """Un signal valide (5000 × 12) doit être accepté."""
    signal = make_valid_signal()
    fields = make_valid_fields()
    result = check_format(signal, fields)
    assert result["format_ok"], f"Signal valide refusé : {result['issues']}"


def test_check_format_wrong_leads():
    """Un signal avec 10 dérivations (au lieu de 12) doit être rejeté."""
    bad = np.zeros((EXPECTED_SAMPLES, 10))
    fields = {"fs": SAMPLING_RATE, "sig_name": [str(i) for i in range(10)]}
    result = check_format(bad, fields)
    assert not result["format_ok"]
    assert any("12" in issue or "dérivation" in issue.lower() for issue in result["issues"])


def test_check_format_wrong_samples():
    """Un signal avec 4000 échantillons (au lieu de 5000) doit être rejeté."""
    bad = np.zeros((4000, EXPECTED_LEADS))
    fields = make_valid_fields()
    result = check_format(bad, fields)
    assert not result["format_ok"]
    assert any("5000" in issue or "échantillon" in issue.lower() for issue in result["issues"])


# ─────────────────────────────────────────────
# Test 2 : denoise_signal (filtre passe-bande)
# ─────────────────────────────────────────────

def test_denoise_output_shape():
    """Le signal filtré doit conserver exactement la même forme."""
    signal = make_valid_signal()
    filtered = denoise_signal(signal, fs=SAMPLING_RATE)
    assert filtered.shape == signal.shape, (
        f"Forme attendue {signal.shape}, obtenue {filtered.shape}"
    )


def test_denoise_output_finite():
    """Le signal filtré ne doit contenir aucun NaN ni Inf."""
    signal = make_valid_signal()
    filtered = denoise_signal(signal, fs=SAMPLING_RATE)
    assert np.isfinite(filtered).all(), "Le signal filtré contient des NaN ou Inf"


def test_denoise_attenuates_high_freq():
    """
    Un signal pur à 100 Hz (hors bande 0.5–40 Hz) doit être fortement atténué.
    L'énergie après filtre doit être < 1% de l'énergie originale.
    """
    t = np.linspace(0, 10, EXPECTED_SAMPLES)
    # Signal haute fréquence (100 Hz) bien au-dessus de la coupure à 40 Hz
    hf = np.tile(np.sin(2 * np.pi * 100 * t).reshape(-1, 1), (1, EXPECTED_LEADS))
    filtered = denoise_signal(hf, fs=SAMPLING_RATE)
    energy_original = np.sum(hf ** 2)
    energy_filtered = np.sum(filtered ** 2)
    ratio = energy_filtered / energy_original
    assert ratio < 0.01, f"Le filtre n'a pas assez atténué le 100 Hz (ratio={ratio:.4f})"


# ─────────────────────────────────────────────
# Test 3 : normalize_signal (z-score)
# ─────────────────────────────────────────────

def test_normalize_mean_near_zero():
    """Après normalisation z-score, la moyenne de chaque dérivation doit être ≈ 0."""
    signal = make_valid_signal(amplitude=5.0)
    normed, _ = normalize_signal(signal, verbose=False)
    for i in range(EXPECTED_LEADS):
        mean = np.mean(normed[:, i])
        assert abs(mean) < 1e-10, f"Dérivation {i} : moyenne = {mean:.6f} ≠ 0"


def test_normalize_std_near_one():
    """Après normalisation z-score, l'écart-type de chaque dérivation doit être ≈ 1."""
    signal = make_valid_signal(amplitude=5.0)
    normed, _ = normalize_signal(signal, verbose=False)
    for i in range(EXPECTED_LEADS):
        std = np.std(normed[:, i])
        assert abs(std - 1.0) < 1e-6, f"Dérivation {i} : std = {std:.6f} ≠ 1"


def test_normalize_output_shape():
    """La normalisation ne doit pas modifier la forme du signal."""
    signal = make_valid_signal()
    normed, _ = normalize_signal(signal, verbose=False)
    assert normed.shape == signal.shape


# ─────────────────────────────────────────────
# Test 4 : repair_invalid_values
# ─────────────────────────────────────────────

def test_repair_valid_signal_unchanged():
    """Un signal sans NaN ne doit pas être modifié (aucune interpolation)."""
    signal = make_valid_signal()
    repaired, details = repair_invalid_values(signal)
    assert np.allclose(signal, repaired)
    # details est un dict {lead: count_invalid}, tous à 0
    assert all(v == 0 for v in details.values())


def test_repair_few_nans_interpolated():
    """
    Quelques NaN sur une dérivation (< 0.5% de 5000 = 25 pts max)
    doivent être interpolés sans lever d'erreur.
    """
    signal = make_valid_signal()
    # Introduit 5 NaN sur la dérivation 0 (0.1% < 0.5%)
    signal[100:105, 0] = np.nan
    repaired, details = repair_invalid_values(signal)
    assert np.isfinite(repaired).all(), "Des NaN subsistent après réparation"
    assert details["I"] > 0  # La dérivation I avait des invalides


def test_repair_too_many_nans_raises():
    """
    Plus de 0.5% de NaN sur une dérivation (> 25 pts sur 5000)
    doit lever une ValueError car le signal est inexploitable.
    """
    signal = make_valid_signal()
    # Introduit 100 NaN sur la dérivation 1 (2% >> 0.5%)
    signal[0:100, 1] = np.nan
    with pytest.raises(ValueError, match=r"(?i)(NaN|invalide|inexploitable|nan)"):
        repair_invalid_values(signal)
