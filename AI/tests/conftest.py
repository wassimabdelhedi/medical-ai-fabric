"""
conftest.py — Configuration pytest partagée pour tous les tests IA.

Ce fichier est automatiquement chargé par pytest avant toute exécution.
Il ajoute la racine du dépôt au sys.path pour les imports du package AI.
"""

import sys
import os

# Ajoute la racine du dépôt au path Python pour tous les tests IA.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
