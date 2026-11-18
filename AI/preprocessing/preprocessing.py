"""
preprocessing.py
-----------------
Étape 3 du pipeline IA — Prétraitement du signal ECG.

Pour UN cas donné (case_id), ce module :
  1. Charge le fichier ECG brut (format WFDB, 500 Hz, 12 dérivations)
  2. Vérifie le format du signal
  3. Détecte les valeurs manquantes ou invalides
  4. Applique un filtre passe-bande (débruitage)
  5. Normalise le signal (z-score par dérivation)
  6. Sauvegarde le signal traité en CSV  → outputs/CASE00001/processed_ecg.csv
  7. Copie l'ECG brut en CSV            → outputs/CASE00001/original_ecg.csv
  8. Retourne un rapport de traitement  (dict)

Utilisation en ligne de commande :
  python preprocessing.py --case_id CASE00001

Utilisation depuis un autre script :
  from AI.preprocessing.preprocessing import run_preprocessing
  report = run_preprocessing("CASE00001")
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import wfdb
from scipy.signal import butter, filtfilt
from datetime import datetime, timezone
from uuid import uuid4

# ─────────────────────────────────────────────────────────
# CHEMINS
# ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
PSEUDO_CSV  = os.path.join(DATASET_DIR, "pseudonymized_database.csv")

# Noms des 12 dérivations ECG standard
LEAD_NAMES = ["I", "II", "III", "aVR", "aVL", "aVF",
              "V1", "V2", "V3", "V4", "V5", "V6"]

# Paramètres du signal
SAMPLING_RATE = 500      # Hz (fichiers records500)
EXPECTED_LEADS = 12
EXPECTED_SAMPLES = 5000  # 10 secondes × 500 Hz

# Paramètres du filtre passe-bande
FILTER_LOWCUT  = 0.5    # Hz — coupe la dérive de la ligne de base
FILTER_HIGHCUT = 40.0   # Hz — coupe le bruit haute fréquence (EMG)
FILTER_ORDER   = 4      # Ordre du filtre Butterworth


# ─────────────────────────────────────────────────────────
# 1. CHARGEMENT
# ─────────────────────────────────────────────────────────

def load_case_info(case_id: str) -> dict:
    """
    Charge les métadonnées du cas depuis pseudonymized_database.csv.
    Retourne un dict avec case_id, filename_hr, label, report, scp_codes.
    """
    df = pd.read_csv(PSEUDO_CSV, index_col="ecg_id")
    row = df[df["case_id"] == case_id]

    if row.empty:
        raise ValueError(f"[ERREUR] case_id '{case_id}' introuvable dans la base.")

    r = row.iloc[0]
    return {
        "case_id"    : case_id,
        "ecg_id"     : int(row.index[0]),
        "filename_hr": str(r["filename_hr"]),   # ex: records500/00000/00001_hr
        "filename_lr": str(r["filename_lr"]),
        "label"      : str(r["label"]),
        "report"     : str(r["report"]),
        "scp_codes"  : str(r["scp_codes"]),
    }


def load_ecg_signal(filename_hr: str) -> tuple:
    """
    Charge le signal ECG brut depuis les fichiers WFDB (.hea + .dat).

    PTB-XL stocke les fichiers dans dataset/records500/XXXXX/NNNNN_hr
    wfdb.rdsamp() retourne :
      - signal : numpy array de shape (nb_échantillons, nb_dérivations)
      - fields  : dict avec fréquence d'échantillonnage, unités, noms des signaux

    Retourne : (signal numpy, fields dict)
    """
    record_path = os.path.join(DATASET_DIR, filename_hr)
    print(f"  [INFO] Chargement du fichier : {record_path}")
    signal, fields = wfdb.rdsamp(record_path)
    print(f"  [INFO] Signal chargé — forme : {signal.shape} "
          f"({fields['fs']} Hz, {len(fields['sig_name'])} dérivations)")
    return signal, fields


# ─────────────────────────────────────────────────────────
# 2. VÉRIFICATION DU FORMAT
# ─────────────────────────────────────────────────────────

def check_format(signal: np.ndarray, fields: dict) -> dict:
    """
    Vérifie que le signal respecte le format attendu :
      - 12 dérivations
      - 5000 échantillons (10 s × 500 Hz)
      - Fréquence d'échantillonnage = 500 Hz

    Retourne un dict de résultats de vérification.
    """
    issues = []
    n_samples, n_leads = signal.shape

    if n_leads != EXPECTED_LEADS:
        issues.append(f"Nombre de dérivations : {n_leads} (attendu {EXPECTED_LEADS})")
    if n_samples != EXPECTED_SAMPLES:
        issues.append(f"Nombre d'échantillons : {n_samples} (attendu {EXPECTED_SAMPLES})")
    if fields.get("fs") != SAMPLING_RATE:
        issues.append(f"Fréquence : {fields.get('fs')} Hz (attendu {SAMPLING_RATE} Hz)")

    result = {
        "n_samples"  : n_samples,
        "n_leads"    : n_leads,
        "fs"         : fields.get("fs"),
        "format_ok"  : len(issues) == 0,
        "issues"     : issues
    }
    if result["format_ok"]:
        print("  [OK]  Format vérifié : 12 dérivations, 5000 échantillons, 500 Hz")
    else:
        print(f"  [WARN] Problèmes de format détectés : {issues}")
    return result


# ─────────────────────────────────────────────────────────
# 3. DÉTECTION DES VALEURS MANQUANTES
# ─────────────────────────────────────────────────────────

def detect_missing_values(signal: np.ndarray) -> dict:
    """
    Détecte les NaN (Not a Number) et les valeurs infinies dans le signal.
    Un ECG peut contenir des NaN si un électrode était mal posé.

    Pour chaque dérivation, compte :
      - nan_count   : nombre de valeurs NaN
      - inf_count   : nombre de valeurs infinies
      - missing_pct : pourcentage total de valeurs manquantes

    Retourne un dict avec le détail par dérivation + statut global.
    """
    report = {}
    total_missing = 0

    for i, lead in enumerate(LEAD_NAMES):
        col = signal[:, i]
        nan_count = int(np.sum(np.isnan(col)))
        inf_count = int(np.sum(np.isinf(col)))
        total = nan_count + inf_count
        total_missing += total
        report[lead] = {
            "nan_count"   : nan_count,
            "inf_count"   : inf_count,
            "missing_pct" : round(total / len(col) * 100, 2)
        }

    total_values = signal.size
    global_missing_pct = round(total_missing / total_values * 100, 2)

    result = {
        "per_lead"           : report,
        "total_missing"      : total_missing,
        "global_missing_pct" : global_missing_pct,
        "quality"            : "OK" if total_missing == 0 else
                               "WARN" if global_missing_pct < 5 else "BAD"
    }

    if total_missing == 0:
        print("  [OK]  Aucune valeur manquante détectée.")
    else:
        print(f"  [WARN] {total_missing} valeurs manquantes ({global_missing_pct}%)")

    return result


# ─────────────────────────────────────────────────────────
# 4. DÉBRUITAGE — FILTRE PASSE-BANDE
# ─────────────────────────────────────────────────────────

def denoise_signal(signal: np.ndarray, fs: int = SAMPLING_RATE, verbose: bool = True) -> np.ndarray:
    """
    Applique un filtre passe-bande de Butterworth (ordre 4) au signal ECG.

    Un ECG contient deux types de bruit principaux :
      - Dérive de la ligne de base (< 0.5 Hz) : mouvements du patient, respiration
      - Bruit EMG (> 40 Hz)                   : activité musculaire, interférences

    Le filtre passe-bande [0.5 – 40 Hz] supprime ces deux bruits tout en
    conservant l'information cardiaque utile (onde P, complexe QRS, onde T).

    filtfilt() applique le filtre dans les deux sens (aller + retour) pour
    éviter tout décalage de phase dans le signal filtré.

    signal : array (n_samples, 12) — signal brut
    Retourne : array (n_samples, 12) — signal filtré
    """
    if not np.isfinite(signal).all():
        raise ValueError("Le signal contient encore des valeurs non finies après réparation.")
    if fs <= 2 * FILTER_HIGHCUT:
        raise ValueError(f"Fréquence d'échantillonnage trop faible pour le filtre: {fs} Hz")
    nyq = fs / 2.0
    low  = FILTER_LOWCUT  / nyq
    high = FILTER_HIGHCUT / nyq

    # Conception du filtre Butterworth d'ordre 4
    b, a = butter(FILTER_ORDER, [low, high], btype="band")

    # Application colonne par colonne (une dérivation à la fois)
    denoised = np.zeros_like(signal)
    for i in range(signal.shape[1]):
        col = signal[:, i].copy()
        denoised[:, i] = filtfilt(b, a, col)

    if verbose:
        print(f"  [OK]  Filtre passe-bande appliqué "
              f"[{FILTER_LOWCUT}–{FILTER_HIGHCUT} Hz], ordre {FILTER_ORDER}")
    return denoised


def repair_invalid_values(signal: np.ndarray, max_missing_fraction: float = 0.005) -> tuple:
    """Interpolate sparse invalid samples and reject substantially corrupt leads."""
    values = np.asarray(signal, dtype=np.float64).copy()
    if values.ndim != 2 or values.shape[1] != EXPECTED_LEADS:
        raise ValueError(f"Signal attendu de forme (échantillons, {EXPECTED_LEADS} dérivations).")
    details = {}
    for index, lead in enumerate(LEAD_NAMES):
        column = values[:, index]
        valid = np.isfinite(column)
        count = int((~valid).sum())
        details[lead] = count
        fraction = count / max(1, len(column))
        if not valid.any() or fraction > max_missing_fraction:
            raise ValueError(
                f"Dérivation {lead} invalide: {count} échantillons non finis "
                f"({fraction:.2%}; limite {max_missing_fraction:.2%})."
            )
        if count:
            positions = np.arange(len(column))
            column[~valid] = np.interp(positions[~valid], positions[valid], column[valid])
        if float(np.std(column)) < 1e-8:
            raise ValueError(f"Dérivation {lead} quasi-plate: signal inexploitable.")
    return values, details


# ─────────────────────────────────────────────────────────
# 5. NORMALISATION
# ─────────────────────────────────────────────────────────

def normalize_signal(signal: np.ndarray, verbose: bool = True) -> tuple:
    """
    Normalise chaque dérivation indépendamment par z-score :
      x_norm = (x - mean) / std

    Résultat : chaque dérivation a une moyenne ≈ 0 et un écart-type ≈ 1.
    Cela évite qu'une dérivation avec de grandes amplitudes "écrase" les autres
    lors de l'entraînement du modèle.

    Si std ≈ 0 (signal plat → électrode déconnectée), on évite la division
    par zéro en laissant la dérivation à 0.

    Retourne :
      - signal normalisé (array)
      - stats de normalisation (dict) pour éventuellement dénormaliser plus tard
    """
    normalized = np.zeros_like(signal, dtype=np.float64)
    stats = {}

    for i, lead in enumerate(LEAD_NAMES):
        col  = signal[:, i]
        mean = float(np.mean(col))
        std  = float(np.std(col))

        if std < 1e-8:   # Signal plat (std ≈ 0)
            normalized[:, i] = 0.0
            if verbose:
                print(f"  [WARN] Dérivation {lead} : signal plat (std≈0), normalisée à 0")
        else:
            normalized[:, i] = (col - mean) / std

        stats[lead] = {"mean": round(mean, 6), "std": round(std, 6)}

    if verbose:
        print(f"  [OK]  Normalisation z-score appliquée (12 dérivations)")
    return normalized, stats


# ─────────────────────────────────────────────────────────
# 6. SAUVEGARDE
# ─────────────────────────────────────────────────────────

def save_original_ecg(signal_raw: np.ndarray, case_dir: str) -> str:
    """
    Sauvegarde le signal ECG BRUT (avant traitement) en CSV.
    → outputs/CASE00001/original_ecg.csv

    Chaque colonne = une dérivation (I, II, III, ...)
    Chaque ligne = un échantillon (5000 lignes pour 10 secondes à 500 Hz)
    """
    path = os.path.join(case_dir, "original_ecg.csv")
    df = pd.DataFrame(signal_raw, columns=LEAD_NAMES)
    df.index.name = "sample"
    df.to_csv(path)
    print(f"  [OK]  ECG brut sauvegardé         : {path}")
    return path


def save_processed_ecg(signal_norm: np.ndarray, case_dir: str) -> str:
    """
    Sauvegarde le signal ECG TRAITÉ (filtré + normalisé) en CSV.
    → outputs/CASE00001/processed_ecg.csv
    """
    path = os.path.join(case_dir, "processed_ecg.csv")
    df = pd.DataFrame(signal_norm, columns=LEAD_NAMES)
    df.index.name = "sample"
    df.to_csv(path)
    print(f"  [OK]  ECG traité sauvegardé        : {path}")
    return path


def save_processing_report(report: dict, case_dir: str) -> str:
    """
    Sauvegarde le rapport de traitement en JSON.
    → outputs/CASE00001/processing_report.json
    """
    path = os.path.join(case_dir, "processing_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  [OK]  Rapport de traitement sauvegardé : {path}")
    return path


# ─────────────────────────────────────────────────────────
# 7. FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────

def run_preprocessing(case_id: str, run_id: str | None = None) -> dict:
    """
    Lance le pipeline complet de prétraitement pour un cas donné.

    Paramètre :
      case_id : identifiant pseudonymisé, ex. "CASE00001"

    Retourne :
      rapport : dict contenant tous les résultats des vérifications
                et les chemins des fichiers produits.
    """
    print("=" * 60)
    print(f"  PREPROCESSING — {case_id}")
    print("=" * 60)
    start_time = datetime.now(timezone.utc)
    run_id = run_id or str(uuid4())
    original_artifact_id = str(uuid4())
    processed_artifact_id = str(uuid4())
    processing_artifact_id = str(uuid4())

    # Dossier de sortie du cas
    case_dir = os.path.join(OUTPUTS_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)

    # ── Étape 1 : Chargement des métadonnées ──────────────
    print("\n[1/6] Chargement des métadonnées...")
    info = load_case_info(case_id)
    print(f"  Label   : {info['label']}")
    print(f"  Rapport : {info['report'][:80]}...")

    # ── Étape 2 : Chargement du signal ECG ────────────────
    print("\n[2/6] Chargement du signal ECG brut...")
    signal_raw, fields = load_ecg_signal(info["filename_hr"])

    # ── Étape 3 : Vérification du format ──────────────────
    print("\n[3/6] Vérification du format...")
    format_check = check_format(signal_raw, fields)
    if not format_check["format_ok"]:
        raise ValueError(f"Format ECG non conforme: {format_check['issues']}")

    # ── Étape 4 : Détection des valeurs manquantes ─────────
    print("\n[4/6] Détection des valeurs manquantes...")
    missing_check = detect_missing_values(signal_raw)

    # Ne filtre jamais un signal incomplet sans enregistrer/réparer le problème.
    signal_repaired, repaired_counts = repair_invalid_values(signal_raw)

    # ── Étape 5 : Débruitage ───────────────────────────────
    print("\n[5/6] Débruitage du signal (filtre passe-bande)...")
    signal_denoised = denoise_signal(signal_repaired, fs=fields["fs"])

    # ── Étape 6 : Normalisation ────────────────────────────
    print("\n[6/6] Normalisation du signal (z-score)...")
    signal_norm, norm_stats = normalize_signal(signal_denoised)

    # ── Sauvegarde ─────────────────────────────────────────
    print("\n[SAVE] Sauvegarde des fichiers...")
    path_original  = save_original_ecg(signal_raw,  case_dir)
    path_processed = save_processed_ecg(signal_norm, case_dir)

    # ── Rapport de traitement ──────────────────────────────
    end_time = datetime.now(timezone.utc)
    report = {
        "artifact_id": processing_artifact_id,
        "artifact_type": "PREPROCESSING_REPORT",
        "run_id": run_id,
        "case_id"           : case_id,
        "ecg_id"            : info["ecg_id"],
        "label"             : info["label"],
        "report_text"       : info["report"],
        "scp_codes"         : info["scp_codes"],
        "timestamp_start"   : start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_end"     : end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_file"       : info["filename_hr"],
        "artifacts": {
            "original_ecg": {
                "artifact_id": original_artifact_id,
                "artifact_type": "ECG_ORIGINAL",
                "parent_artifact_ids": [],
                "filename": "original_ecg.csv",
            },
            "processed_ecg": {
                "artifact_id": processed_artifact_id,
                "artifact_type": "ECG_PROCESSED",
                "parent_artifact_ids": [original_artifact_id],
                "filename": "processed_ecg.csv",
            },
        },
        "format_check"      : format_check,
        "missing_check"     : missing_check,
        "interpolated_samples_by_lead": repaired_counts,
        "normalization_stats": norm_stats,
        "filter_params"     : {
            "type"     : "butterworth_bandpass",
            "lowcut_hz": FILTER_LOWCUT,
            "highcut_hz": FILTER_HIGHCUT,
            "order"    : FILTER_ORDER,
            "fs_hz"    : SAMPLING_RATE
        },
        "output_files"      : {
            "original_ecg"  : path_original,
            "processed_ecg" : path_processed,
        },
        "status": "OK" if format_check["format_ok"] and
                          missing_check["quality"] == "OK" else "WARNING"
    }

    path_report = os.path.join(case_dir, "processing_report.json")
    report["output_files"]["processing_report"] = path_report
    save_processing_report(report, case_dir)

    print("\n" + "=" * 60)
    print(f"  PREPROCESSING TERMINÉ — Statut : {report['status']}")
    print(f"  Durée : {(end_time - start_time).total_seconds():.2f}s")
    print("=" * 60)
    return report


# ─────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prétraitement ECG — PTB-XL")
    parser.add_argument(
        "--case_id",
        type=str,
        default="CASE00001",
        help="Identifiant pseudonymisé du cas (ex: CASE00001)"
    )
    args = parser.parse_args()
    run_preprocessing(args.case_id)
