"""
feature_extraction.py
----------------------
Étape 4 du pipeline IA — Extraction des caractéristiques du signal ECG.

Pour UN cas donné (case_id), ce module :
  1. Charge processed_ecg.csv (signal filtré + normalisé)
  2. Calcule 9 caractéristiques pour chacune des 12 dérivations = 108 features
  3. Sauvegarde le résultat → outputs/CASE00001/features.json

Les 9 caractéristiques par dérivation : quantiles robustes, asymétrie,
aplatissement et RMS des différences successives. Ces résumés statistiques
ne constituent pas une interprétation clinique du tracé.

Utilisation en ligne de commande :
  python feature_extraction.py --case_id CASE00001

Utilisation depuis un autre script :
  from AI.feature_extraction.feature_extraction import run_feature_extraction
  features = run_feature_extraction("CASE00001")
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis
from datetime import datetime, timezone
from uuid import uuid4

# ─────────────────────────────────────────────────────────
# CHEMINS
# ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# 12 dérivations ECG standard
LEAD_NAMES = ["I", "II", "III", "aVR", "aVL", "aVF",
              "V1", "V2", "V3", "V4", "V5", "V6"]


# ─────────────────────────────────────────────────────────
# 1. CHARGEMENT
# ─────────────────────────────────────────────────────────

def load_processed_ecg(case_id: str) -> np.ndarray:
    """
    Charge processed_ecg.csv depuis le dossier du cas.
    Retourne un numpy array de shape (5000, 12).

    Si le fichier n'existe pas, lève une erreur claire :
    cela signifie que preprocessing.py n'a pas encore été exécuté pour ce cas.
    """
    path = os.path.join(OUTPUTS_DIR, case_id, "processed_ecg.csv")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"[ERREUR] processed_ecg.csv introuvable pour {case_id}.\n"
            f"  → Lance d'abord : python preprocessing.py --case_id {case_id}"
        )

    df = pd.read_csv(path, index_col="sample")
    signal = df.values.astype(np.float64)
    print(f"  [OK]  processed_ecg.csv chargé — forme : {signal.shape}")
    return signal


# ─────────────────────────────────────────────────────────
# 2. CALCUL DES FEATURES
# ─────────────────────────────────────────────────────────

def compute_features_one_lead(col: np.ndarray, lead_name: str) -> dict:
    """
    Calcule les 9 caractéristiques pour UNE dérivation.

    Paramètre :
      col : numpy array de 5000 valeurs (une colonne du signal)

    Entrée: une dérivation z-normalisée. Les quantiles et la forme statistique
    restent informatifs après cette normalisation, contrairement à mean/std/RMS.
    """
    return {
        "q01": float(round(np.percentile(col, 1), 6)),
        "q05": float(round(np.percentile(col, 5), 6)),
        "q25": float(round(np.percentile(col, 25), 6)),
        "q75": float(round(np.percentile(col, 75), 6)),
        "q95": float(round(np.percentile(col, 95), 6)),
        "q99": float(round(np.percentile(col, 99), 6)),
        "skewness": float(round(skew(col, bias=False), 6)),
        "kurtosis": float(round(kurtosis(col, bias=False), 6)),
        "diff_rms": float(round(np.sqrt(np.mean(np.diff(col) ** 2)), 6)),
    }


def extract_all_features(signal: np.ndarray) -> dict:
    """
    Calcule les features pour les 12 dérivations.

    Entrée  : signal numpy (5000, 12)
    Sortie  : dict  { "I": {mean, std, ...}, "II": {...}, ..., "V6": {...} }

    Total : 9 features × 12 dérivations = 108 features par ECG.
    Ces 108 valeurs seront l'entrée du modèle Random Forest.
    """
    features = {}
    for i, lead in enumerate(LEAD_NAMES):
        col = signal[:, i]
        features[lead] = compute_features_one_lead(col, lead)
        print(f"  [OK]  {lead:>4} → q05={features[lead]['q05']:+.4f}  "
              f"q95={features[lead]['q95']:+.4f}  "
              f"diff_rms={features[lead]['diff_rms']:.4f}")
    return features


def flatten_features(features: dict) -> list:
    """
    Aplatit le dict de features en une liste de 108 valeurs numériques.
    C'est ce format (liste) que sklearn attend pour faire une prédiction.

    Ordre : pour chaque dérivation dans l'ordre LEAD_NAMES,
            puis pour chaque caractéristique dans l'ordre STAT_ORDER.

    Exemple :
      [I_q01, I_q05, ..., II_q01, ..., V6_diff_rms]
    """
    STAT_ORDER = ["q01", "q05", "q25", "q75", "q95", "q99", "skewness", "kurtosis", "diff_rms"]
    flat = []
    for lead in LEAD_NAMES:
        for stat in STAT_ORDER:
            flat.append(features[lead][stat])
    return flat  # longueur = 108


# ─────────────────────────────────────────────────────────
# 3. SAUVEGARDE
# ─────────────────────────────────────────────────────────

def save_features(features: dict, case_id: str, case_dir: str) -> str:
    """
    Sauvegarde features.json avec la structure convenue avec l'équipe Blockchain.

    Structure :
    {
      "artifact_id"      : "FEAT00001",
      "case_id"          : "CASE00001",
      "artifact_type"    : "FEATURES",
      "n_features"       : 108,
      "feature_names"    : ["I_q01", "I_q05", ...],   ← 108 noms
      "features_by_lead" : { "I": {...}, "II": {...} }, ← détail par dérivation
      "features_flat"    : [0.001, 0.045, ...],         ← 108 valeurs pour sklearn
      "parent_artifact_id": "PROC00001",
      "timestamp"        : "2026-11-15T22:00:00Z"
    }
    """
    # Génération des noms de features dans l'ordre
    STAT_ORDER = ["q01", "q05", "q25", "q75", "q95", "q99", "skewness", "kurtosis", "diff_rms"]
    feature_names = [f"{lead}_{stat}" for lead in LEAD_NAMES for stat in STAT_ORDER]

    # Numéro du cas (extrait de CASE00001 → 00001)
    num = case_id.replace("CASE", "")
    report_path = os.path.join(case_dir, "processing_report.json")
    with open(report_path, "r", encoding="utf-8") as handle:
        processing_report = json.load(handle)
    run_id = processing_report["run_id"]
    processed_id = processing_report["artifacts"]["processed_ecg"]["artifact_id"]
    artifact_id = str(uuid4())

    artifact = {
        "artifact_id"       : artifact_id,
        "case_id"           : case_id,
        "run_id"            : run_id,
        "artifact_type"     : "FEATURES",
        "n_features"        : len(feature_names),
        "feature_names"     : feature_names,
        "features_by_lead"  : features,
        "features_flat"     : flatten_features(features),
        "parent_artifact_id": processed_id,
        "parent_artifact_ids": [processed_id],
        "timestamp"         : datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    path = os.path.join(case_dir, "features.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)

    print(f"\n  [OK]  features.json sauvegardé : {path}")
    return path


# ─────────────────────────────────────────────────────────
# 4. FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────

def run_feature_extraction(case_id: str) -> dict:
    """
    Lance l'extraction complète des features pour un cas donné.

    Paramètre :
      case_id : identifiant pseudonymisé, ex. "CASE00001"

    Retourne :
      artifact : dict complet (même contenu que features.json)
    """
    print("=" * 60)
    print(f"  FEATURE EXTRACTION — {case_id}")
    print("=" * 60)

    case_dir = os.path.join(OUTPUTS_DIR, case_id)

    # ── Étape 1 : Chargement ──────────────────────────────
    print("\n[1/3] Chargement de processed_ecg.csv...")
    signal = load_processed_ecg(case_id)

    # ── Étape 2 : Calcul des features ─────────────────────
    print("\n[2/3] Calcul des 108 features (9 × 12 dérivations)...")
    features = extract_all_features(signal)

    # ── Étape 3 : Sauvegarde ──────────────────────────────
    print("\n[3/3] Sauvegarde de features.json...")
    path = save_features(features, case_id, case_dir)

    # Résumé
    flat = flatten_features(features)
    print("\n" + "=" * 60)
    print(f"  FEATURE EXTRACTION TERMINÉE")
    print(f"  Features extraites : {len(flat)} (9 features × 12 dérivations)")
    print(f"  Plage de valeurs   : [{min(flat):.4f}, {max(flat):.4f}]")
    print("=" * 60)

    # Recharge et retourne l'artefact complet
    with open(path) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Feature Extraction ECG — PTB-XL")
    parser.add_argument(
        "--case_id",
        type=str,
        default="CASE00001",
        help="Identifiant pseudonymisé du cas (ex: CASE00001)"
    )
    args = parser.parse_args()
    run_feature_extraction(args.case_id)
