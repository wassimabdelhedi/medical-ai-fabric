#!/usr/bin/env bash
# =================================================================
#  test_phase5.sh — Tests Phase 5 : Stockage off-chain & Intégrité
#  Localisation : BLOCKCHAIN/tests/test_phase5.sh
# =================================================================
set -euo pipefail

BACKEND="http://localhost:3001"
AI_CASE_ID="CASE00001"
FABRIC_CASE_ID="FABCASE-a224017d-dbf1-45eb-bb1a-978e4b2d3c59"
ECG_ARTIFACT_ID="1f1fe950-9cb8-40dc-9406-38cbff1fc513"
ECG_HASH="c65e4abe0eb0e561c37284024c3668afe14e4cc5001b9420b17781e4906c65b6"
STORAGE_DIR="/mnt/d/medical-ai-fabric/BLOCKCHAIN/storage/$FABRIC_CASE_ID"
PASS=0; FAIL=0

echo ""
echo "================================================================="
echo "  TESTS PHASE 5 — Stockage off-chain & Vérification d'intégrité "
echo "================================================================="
echo ""

check_backend() {
    if ! curl -sf "$BACKEND/health" > /dev/null 2>&1; then
        echo "❌ Backend non disponible sur $BACKEND"
        echo "   Lance d'abord : cd BLOCKCHAIN/backend && node src/app.js"
        exit 1
    fi
    echo "✅ Backend opérationnel"
}

pass() { echo "  ✅ $1"; ((PASS++)); }
fail() { echo "  ❌ $1"; ((FAIL++)); }

# -----------------------------------------------------------------
# TEST 1 : Stockage des fichiers hors-chaîne + vérification intégrité
# -----------------------------------------------------------------
echo "[TEST 1] Transfert des fichiers IA vers le stockage hors-chaîne"
check_backend
echo ""

RESP=$(curl -sf -X POST "$BACKEND/api/artifacts/store-case" \
  -H "Content-Type: application/json" \
  -d "{\"aiCaseId\": \"$AI_CASE_ID\"}" 2>&1) || { fail "store-case a échoué"; RESP="{}"; }

echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
echo ""

# Vérifier que le résumé indique 0 compromis
CORRUPTED=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('corrupted',99))" 2>/dev/null || echo "99")
OK_COUNT=$(echo "$RESP"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('ok',0))" 2>/dev/null || echo "0")

if [ "$CORRUPTED" = "0" ] && [ "$OK_COUNT" -ge 7 ]; then
    pass "Tous les fichiers stockés et intègres (ok=$OK_COUNT, compromis=$CORRUPTED)"
else
    fail "Résultat inattendu (ok=$OK_COUNT, compromis=$CORRUPTED)"
fi

# -----------------------------------------------------------------
# TEST 2 : Les fichiers sont bien présents sur le disque
# -----------------------------------------------------------------
echo ""
echo "[TEST 2] Présence physique des fichiers dans BLOCKCHAIN/storage/"
echo "  Répertoire : $STORAGE_DIR"
echo ""

for FILE in original_ecg.csv processed_ecg.csv processing_report.json \
            features.json prediction.json validation.json \
            explanation.json final_result.json; do
    if [ -f "$STORAGE_DIR/$FILE" ]; then
        HASH=$(sha256sum "$STORAGE_DIR/$FILE" | cut -d' ' -f1)
        pass "$FILE | sha256: ${HASH:0:16}..."
    else
        fail "$FILE → ABSENT"
    fi
done

# -----------------------------------------------------------------
# TEST 3 : verify-file — Cas VALIDE (fichier intact)
# -----------------------------------------------------------------
echo ""
echo "[TEST 3] verify-file — ECG_ORIGINAL intact (attendu: VALID)"
RESP=$(curl -sf "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify-file" 2>&1) || { fail "verify-file a échoué"; RESP="{}"; }
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
echo ""

STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
if [ "$STATUS" = "VALID" ]; then
    pass "verify-file → VALID ✅"
else
    fail "verify-file → $STATUS (attendu: VALID)"
fi

# -----------------------------------------------------------------
# TEST 4 : Simulation de falsification + détection CORRUPTED
# -----------------------------------------------------------------
echo ""
echo "[TEST 4] Simulation de falsification — Modification d'un fichier hors-chaîne"
echo "  Modification de : $STORAGE_DIR/original_ecg.csv"

BACKUP="$STORAGE_DIR/original_ecg.csv.bak"
cp "$STORAGE_DIR/original_ecg.csv" "$BACKUP"
echo "DONNEES_FALSIFIEES_$(date +%s)" >> "$STORAGE_DIR/original_ecg.csv"

RESP=$(curl -sf "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify-file" 2>&1) || { fail "verify-file (corrompu) a échoué"; RESP="{}"; }
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
echo ""

STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
if [ "$STATUS" = "CORRUPTED" ]; then
    pass "Falsification détectée ! → CORRUPTED 🚨"
else
    fail "Falsification non détectée → $STATUS (attendu: CORRUPTED)"
fi

# Restauration du fichier original
cp "$BACKUP" "$STORAGE_DIR/original_ecg.csv"
rm "$BACKUP"
echo "  ↩️  Fichier restauré à l'état original."

# -----------------------------------------------------------------
# TEST 5 : Après restauration, verify-file doit repasser en VALID
# -----------------------------------------------------------------
echo ""
echo "[TEST 5] Vérification après restauration (attendu: VALID)"
RESP=$(curl -sf "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify-file" 2>&1) || { fail "verify-file post-restauration a échoué"; RESP="{}"; }
STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
if [ "$STATUS" = "VALID" ]; then
    pass "Fichier restauré → VALID ✅"
else
    fail "Après restauration → $STATUS (attendu: VALID)"
fi

# -----------------------------------------------------------------
# TEST 6 : Lister les fichiers stockés hors-chaîne via l'API
# -----------------------------------------------------------------
echo ""
echo "[TEST 6] Listing des fichiers hors-chaîne via GET /api/artifacts/storage/{caseId}"
RESP=$(curl -sf "$BACKEND/api/artifacts/storage/$FABRIC_CASE_ID" 2>&1) || { fail "storage listing a échoué"; RESP="{}"; }
echo "$RESP" | python3 -m json.tool 2>/dev/null || echo "$RESP"
echo ""

COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")
if [ "$COUNT" -ge 8 ]; then
    pass "Listing → $COUNT fichiers hors-chaîne trouvés"
else
    fail "Listing → $COUNT fichiers (attendu ≥ 8)"
fi

# -----------------------------------------------------------------
# Résumé
# -----------------------------------------------------------------
echo ""
echo "================================================================="
printf "  Résultats : ✅ %d réussis | ❌ %d échoués\n" "$PASS" "$FAIL"
echo "================================================================="
echo ""

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
