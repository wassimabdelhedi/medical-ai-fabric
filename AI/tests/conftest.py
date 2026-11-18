"""
conftest.py — Configuration pytest partagée pour tous les tests IA.

Ce fichier est automatiquement chargé par pytest avant toute exécution.
Il ajoute le dossier src/ au sys.path pour que tous les tests
puissent importer les modules IA sans configuration manuelle.
"""

import sys
import os

# Ajoute IA/src/ au path Python pour tous les tests du dossier tests/
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(SRC_DIR))
