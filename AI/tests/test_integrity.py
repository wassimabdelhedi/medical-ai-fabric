"""
test_integrity.py
------------------
Tests d'intégrité SHA-256 des artefacts.

Vérifie :
  1. Le hash d'un fichier est reproductible (même fichier → même hash)
  2. Modifier un fichier change son hash (détection de falsification)
  3. Deux fichiers différents ont des hashes différents
  4. Le hash est une chaîne hexadécimale de 64 caractères (SHA-256)
  5. Le hash des fichiers de CASE00001 correspond à ceux du fabric_package.json
"""

import sys
import os
import json
import tempfile
import hashlib
import pytest

from AI.common.artifact_utils import sha256_file

BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
CASE_DIR   = os.path.join(BASE_DIR, "outputs", "CASE00001")
FABRIC_PKG = os.path.join(CASE_DIR, "fabric_package.json")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def write_temp_file(content: bytes) -> str:
    """Écrit du contenu dans un fichier temporaire, retourne son chemin."""
    fd, path = tempfile.mkstemp(suffix=".bin")
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


# ─────────────────────────────────────────────
# Test 1 : Reproductibilité
# ─────────────────────────────────────────────

def test_hash_is_reproducible():
    """Le même fichier doit produire le même hash à chaque appel."""
    path = write_temp_file(b"ECG data sample 12345")
    try:
        h1 = sha256_file(path)
        h2 = sha256_file(path)
        assert h1 == h2, "Le hash n'est pas reproductible !"
    finally:
        os.remove(path)


# ─────────────────────────────────────────────
# Test 2 : Détection de falsification
# ─────────────────────────────────────────────

def test_modified_file_has_different_hash():
    """
    Modifier un seul octet du fichier doit changer le hash.
    C'est le test fondamental de la détection de falsification.
    """
    original = b"Normal ECG result - confidence 0.94"
    tampered = b"Normal ECG result - confidence 0.44"  # 1 chiffre changé

    path_orig = write_temp_file(original)
    path_tamp = write_temp_file(tampered)
    try:
        h_orig = sha256_file(path_orig)
        h_tamp = sha256_file(path_tamp)
        assert h_orig != h_tamp, (
            "ALERTE : un fichier falsifié produit le même hash que l'original !"
        )
    finally:
        os.remove(path_orig)
        os.remove(path_tamp)


def test_single_byte_change_detected():
    """Changer un seul octet parmi 1000 doit être détecté."""
    data = b"A" * 1000
    tampered = b"A" * 500 + b"B" + b"A" * 499  # 1 octet différent

    p1 = write_temp_file(data)
    p2 = write_temp_file(tampered)
    try:
        assert sha256_file(p1) != sha256_file(p2)
    finally:
        os.remove(p1)
        os.remove(p2)


# ─────────────────────────────────────────────
# Test 3 : Deux fichiers différents → hashes différents
# ─────────────────────────────────────────────

def test_different_files_have_different_hashes():
    """Deux fichiers avec des contenus différents ont des hashes différents."""
    p1 = write_temp_file(b"prediction: Normal")
    p2 = write_temp_file(b"prediction: Abnormal")
    try:
        assert sha256_file(p1) != sha256_file(p2)
    finally:
        os.remove(p1)
        os.remove(p2)


# ─────────────────────────────────────────────
# Test 4 : Format du hash SHA-256
# ─────────────────────────────────────────────

def test_hash_is_64_hex_chars():
    """Le hash SHA-256 doit être une chaîne hexadécimale de 64 caractères."""
    path = write_temp_file(b"test content")
    try:
        h = sha256_file(path)
        assert isinstance(h, str), f"Le hash n'est pas une str : {type(h)}"
        assert len(h) == 64, f"Longueur attendue 64, obtenue {len(h)}"
        assert all(c in "0123456789abcdef" for c in h.lower()), (
            f"Le hash contient des caractères non hexadécimaux : {h}"
        )
    finally:
        os.remove(path)


def test_empty_file_has_known_sha256():
    """Le SHA-256 d'un fichier vide est une constante connue."""
    # SHA-256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    path = write_temp_file(b"")
    try:
        h = sha256_file(path)
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert h == expected, f"Hash fichier vide incorrect : {h}"
    finally:
        os.remove(path)


# ─────────────────────────────────────────────
# Test 5 : Vérification des hashes du fabric_package.json réel
# ─────────────────────────────────────────────

@pytest.mark.skipif(
    not os.path.exists(FABRIC_PKG),
    reason="fabric_package.json absent — exécute d'abord run_ai_pipeline.py"
)
def test_fabric_package_hashes_match_files():
    """
    Recalcule les SHA-256 des artefacts référencés dans fabric_package.json
    et vérifie qu'ils correspondent aux valeurs enregistrées.

    C'est exactement ce que l'équipe Blockchain doit faire pour vérifier
    l'intégrité avant d'écrire sur le ledger Hyperledger Fabric.
    """
    with open(FABRIC_PKG, encoding="utf-8") as f:
        package = json.load(f)

    # Mapping artifact_type → chemin local attendu
    type_to_file = {
        "AI_PREDICTION":   os.path.join(CASE_DIR, "prediction.json"),
        "AI_VALIDATION":   os.path.join(CASE_DIR, "validation.json"),
        "AI_EXPLANATION":  os.path.join(CASE_DIR, "explanation.json"),
        "AI_FINAL_RESULT": os.path.join(CASE_DIR, "final_result.json"),
        "FEATURES":        os.path.join(CASE_DIR, "features.json"),
    }

    failures = []
    for record in package.get("ledger_records", []):
        atype = record["artifact_type"]
        expected_hash = record["sha256"]
        file_path = type_to_file.get(atype)

        if file_path and os.path.exists(file_path):
            actual_hash = sha256_file(file_path)
            if actual_hash != expected_hash:
                failures.append(
                    f"{atype}: hash attendu={expected_hash[:16]}... "
                    f"hash réel={actual_hash[:16]}..."
                )

    assert not failures, (
        "FALSIFICATION DÉTECTÉE — les fichiers ont changé depuis la génération du package :\n"
        + "\n".join(failures)
    )
