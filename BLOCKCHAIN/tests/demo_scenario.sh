#!/usr/bin/env bash
# =================================================================
#  demo_scenario.sh — Démonstration Complète du Système (Phase 8)
#  Système Médical IA + Blockchain Hyperledger Fabric
#  Localisation : BLOCKCHAIN/tests/demo_scenario.sh
# =================================================================
set -euo pipefail

BACKEND="http://localhost:3001"
FABCASE_ID="FABCASE-a224017d-dbf1-45eb-bb1a-978e4b2d3c59"
ECG_ARTIFACT_ID="1f1fe950-9cb8-40dc-9406-38cbff1fc513"
STORAGE_DIR="/mnt/d/medical-ai-fabric/BLOCKCHAIN/storage/$FABCASE_ID"
ECG_FILE="$STORAGE_DIR/original_ecg.csv"
BACKUP_FILE="$STORAGE_DIR/original_ecg.csv.bak_demo"

clear
echo "================================================================="
echo "   🏥 DÉMONSTRATION DU SYSTÈME IA MÉDICALE & HYPERLEDGER FABRIC   "
echo "================================================================="
echo "  Dossier Patient : $FABCASE_ID"
echo "  Réseau          : Hyperledger Fabric v2.5 (mychannel)"
echo "  Smart Contract  : ArtifactContract v1.0"
echo "================================================================="
echo ""

AUTO_MODE=false
for arg in "$@"; do
    if [ "$arg" = "--auto" ] || [ "$arg" = "-y" ]; then
        AUTO_MODE=true
    fi
done

pause_step() {
    local msg="${1:-Appuyez sur [Entrée] pour continuer...}"
    if [ "$AUTO_MODE" = "true" ]; then
        echo "⏳ (Mode auto) $msg"
        sleep 2
    else
        read -p "👉 $msg" || true
    fi
}
if ! curl -s "$BACKEND/health" > /dev/null 2>&1; then
    echo "❌ Erreur : Le backend n'est pas démarré sur $BACKEND."
    echo "   Lancez d'abord : cd BLOCKCHAIN/backend && node src/app.js"
    exit 1
fi

sleep 1

# -----------------------------------------------------------------
# ÉTAPE 1 : Consultation de la chaîne causale complète du dossier
# -----------------------------------------------------------------
echo "-----------------------------------------------------------------"
echo "  [SCÉNARIO 1] Traçabilité de bout en bout du pipeline IA"
echo "-----------------------------------------------------------------"
echo "Interrogation de la Blockchain pour reconstituer la chaîne causale..."
echo ""
curl -s "$BACKEND/api/artifacts/case/$FABCASE_ID" | python3 -c '
import sys, json
data = json.load(sys.stdin)
print(f"✅ Dossier Fabric : {data.get(\"caseId\")}")
print(f"📊 Nombre d'\''artefacts scellés : {data.get(\"count\")}\n")
for i, a in enumerate(data.get("artifacts", []), 1):
    parents = a.get("parentArtifactId")
    p_str = "Origine racine (Patient)" if not parents else f"Parent(s): {parents}"
    print(f"  {i}. [{a.get(\"artifactType\")}] {a.get(\"artifactId\")[:18]}...")
    print(f"     Hash SHA-256 : {a.get(\"hash\")[:20]}...")
    print(f"     Filiation    : {p_str}")
'
echo ""
pause_step "Appuyez sur [Entrée] pour passer à la vérification d'intégrité..."
echo ""

# -----------------------------------------------------------------
# ÉTAPE 2 : Vérification d'intégrité d'un fichier sain
# -----------------------------------------------------------------
echo "-----------------------------------------------------------------"
echo "  [SCÉNARIO 2] Contrôle d'intégrité sur fichier sain (Non altéré)"
echo "-----------------------------------------------------------------"
echo "Vérification en direct du fichier hors-chaîne ECG original vs le registre Fabric..."
echo ""

RESP=$(curl -s "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify-file")
echo "$RESP" | python3 -m json.tool
echo ""

STATUS=$(echo "$RESP" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("status",""))')
if [ "$STATUS" = "VALID" ]; then
    echo "✅ SUCCÈS : L'\''empreinte du fichier local correspond exactement au registre immuable !"
fi
echo ""
pause_step "Appuyez sur [Entrée] pour simuler une tentative de falsification..."
echo ""

# -----------------------------------------------------------------
# ÉTAPE 3 : Simulation d'attaque — Modification malveillante du fichier
# -----------------------------------------------------------------
echo "-----------------------------------------------------------------"
echo "  [SCÉNARIO 3] Attaque : Altération du tracé ECG hors-chaîne"
echo "-----------------------------------------------------------------"
echo "Simulation : Un individu malveillant modifie le fichier ECG stocké sur disque..."
cp "$ECG_FILE" "$BACKUP_FILE"
echo "FRAUDE_DONNEES_ALTEREES_$(date +%s)" >> "$ECG_FILE"
echo "⚠️  Fichier local modifié avec succès : $ECG_FILE"
echo ""

echo "Relance immédiate du contrôle d'intégrité par l'API..."
echo ""
RESP_CORRUPT=$(curl -s "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify-file")
echo "$RESP_CORRUPT" | python3 -m json.tool
echo ""

STATUS_C=$(echo "$RESP_CORRUPT" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("status",""))')
if [ "$STATUS_C" = "CORRUPTED" ]; then
    echo "🚨 ALERTE SÉCURITÉ : Falsification détectée par la Blockchain !"
    echo "   La Blockchain a prouvé mathématiquement que le fichier n'\''est plus conforme."
fi
echo ""
pause_step "Appuyez sur [Entrée] pour restaurer le fichier et rétablir l'intégrité..."
echo ""

# -----------------------------------------------------------------
# ÉTAPE 4 : Restauration et retour à la conformité
# -----------------------------------------------------------------
echo "-----------------------------------------------------------------"
echo "  [SCÉNARIO 4] Restauration du fichier intègre d'origine"
echo "-----------------------------------------------------------------"
cp "$BACKUP_FILE" "$ECG_FILE"
rm "$BACKUP_FILE"
echo "↩️  Fichier rétabli dans son état authentique certifié."
echo ""
echo "Nouvelle vérification par l'API :"
curl -s "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify-file" | python3 -m json.tool
echo ""
pause_step "Appuyez sur [Entrée] pour consulter la preuve médico-légale (Audit)..."
echo ""

# -----------------------------------------------------------------
# ÉTAPE 5 : Audit médico-légal & Historique des transactions
# -----------------------------------------------------------------
echo "-----------------------------------------------------------------"
echo "  [SCÉNARIO 5] Preuve Médico-Légale & Historique Blockchain"
echo "-----------------------------------------------------------------"
echo "Consultation des transactions enregistrées sur les blocs Fabric :"
echo ""
curl -s "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/history" | python3 -c '
import sys, json
data = json.load(sys.stdin)
print(f"Identifiant Artefact : {data.get(\"artifactId\")}")
print(f"Nombre de transactions certifiées : {data.get(\"txCount\")}\n")
for h in data.get("history", []):
    print(f"  🔹 TxId Blockchain : {h.get(\"txId\")}")
    print(f"     Créateur        : {h.get(\"data\", {}).get(\"creator\")}")
    print(f"     Horodatage UTC  : {h.get(\"data\", {}).get(\"timestamp\")}")
    print(f"     Supprimé        : {h.get(\"isDelete\")}")
'

echo ""
echo "================================================================="
echo "  🎉 DÉMONSTRATION TERMINÉE AVEC SUCCÈS — SYSTÈME 100% OPÉRATIONNEL"
echo "================================================================="
