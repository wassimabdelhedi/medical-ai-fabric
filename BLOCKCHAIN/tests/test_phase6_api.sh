#!/usr/bin/env bash
# =================================================================
#  test_phase6_api.sh — Tests complets de l'API REST (Phase 6)
#  Localisation : BLOCKCHAIN/tests/test_phase6_api.sh
# =================================================================

BACKEND="http://localhost:3001"
TIMESTAMP=$(date +%s)
TEST_ARTIFACT_ID="TEST-PHASE6-${TIMESTAMP}"
TEST_CASE_ID="CASE-PHASE6-${TIMESTAMP}"
TEST_HASH="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

AI_CASE_ID="FABCASE-a224017d-dbf1-45eb-bb1a-978e4b2d3c59"
ECG_ARTIFACT_ID="1f1fe950-9cb8-40dc-9406-38cbff1fc513"
ECG_VALID_HASH="c65e4abe0eb0e561c37284024c3668afe14e4cc5001b9420b17781e4906c65b6"
FAKE_HASH="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

PASS=0; FAIL=0

echo ""
echo "================================================================="
echo "  TESTS PHASE 6 — Validation Complète de l'API REST Blockchain   "
echo "================================================================="
echo ""

pass() { echo "  ✅ $1"; ((PASS++)); }
fail() { echo "  ❌ $1"; ((FAIL++)); }

# -----------------------------------------------------------------
# 0. Vérification du Backend
# -----------------------------------------------------------------
if ! curl -s "$BACKEND/health" > /dev/null 2>&1; then
    echo "❌ Le backend n'est pas démarré sur $BACKEND."
    echo "   Lancez d'abord dans un terminal : cd BLOCKCHAIN/backend && node src/app.js"
    exit 1
fi
echo "Backend opérationnel sur $BACKEND."
echo ""

# -----------------------------------------------------------------
# TEST 1 : GET / — Exploration de l'API & Documentation
# -----------------------------------------------------------------
echo "[TEST 1] GET / — API Explorer & Sitemap"
RESP=$(curl -s "$BACKEND/")
STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
if [ "$STATUS" = "ONLINE" ]; then
    pass "GET / retourne la documentation de l'API (status: ONLINE)"
else
    fail "GET / status inattendu: '$STATUS'"
fi

# -----------------------------------------------------------------
# TEST 2 : GET /health — État de santé
# -----------------------------------------------------------------
echo "[TEST 2] GET /health — Health Check"
RESP=$(curl -s "$BACKEND/health")
HEALTH=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
if [ "$HEALTH" = "UP" ]; then
    pass "GET /health est UP (connecté à mychannel / artifacts)"
else
    fail "GET /health status: '$HEALTH'"
fi

# -----------------------------------------------------------------
# TEST 3 : POST /api/artifacts — Enregistrement d'un artefact unitaire
# -----------------------------------------------------------------
echo "[TEST 3] POST /api/artifacts — Enregistrement unitaire d'un artefact"
BODY=$(cat <<EOF
{
  "artifactId": "$TEST_ARTIFACT_ID",
  "caseId": "$TEST_CASE_ID",
  "artifactType": "ECG_ORIGINAL",
  "hash": "$TEST_HASH",
  "parentArtifactId": null,
  "storageRef": "offchain://$TEST_CASE_ID/raw.csv",
  "modelVersion": "1.0.0",
  "creator": "Phase6-Automated-Test"
}
EOF
)
RESP=$(curl -s -X POST "$BACKEND/api/artifacts" \
  -H "Content-Type: application/json" \
  -d "$BODY")

TXID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('txId',''))" 2>/dev/null || echo "")
if [ -n "$TXID" ] && [ "$TXID" != "None" ]; then
    pass "Artefact enregistré avec succès | txId: ${TXID:0:16}..."
else
    fail "Enregistrement sans txId valide: $RESP"
fi

# -----------------------------------------------------------------
# TEST 4 : POST /api/artifacts — Rejet d'immuabilité (Ré-enregistrement)
# -----------------------------------------------------------------
echo "[TEST 4] POST /api/artifacts — Rejet d'immuabilité (doublon interdit)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BACKEND/api/artifacts" \
  -H "Content-Type: application/json" \
  -d "$BODY" 2>&1 || echo "000")

if [ "$HTTP_CODE" -ge 400 ]; then
    pass "Tentative de réécriture correctement rejetée (Code HTTP: $HTTP_CODE)"
else
    fail "La réécriture aurait dû être rejetée (Code HTTP: $HTTP_CODE)"
fi

# -----------------------------------------------------------------
# TEST 5 : GET /api/artifacts/:artifactId — Consultation par identifiant
# -----------------------------------------------------------------
echo "[TEST 5] GET /api/artifacts/:id — Consultation d'un artefact"
RESP=$(curl -s "$BACKEND/api/artifacts/$TEST_ARTIFACT_ID")
READ_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('artifactId',''))" 2>/dev/null || echo "")
if [ "$READ_ID" = "$TEST_ARTIFACT_ID" ]; then
    pass "Artefact lu correctement depuis le World State Fabric"
else
    fail "Lecture d'artefact erronée: $RESP"
fi

# -----------------------------------------------------------------
# TEST 6 : GET /api/artifacts/:artifactId/exists — Vérification d'existence
# -----------------------------------------------------------------
echo "[TEST 6] GET /api/artifacts/:id/exists — Vérification d'existence"
RESP=$(curl -s "$BACKEND/api/artifacts/$TEST_ARTIFACT_ID/exists")
EXISTS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('exists',False))" 2>/dev/null || echo "False")
if [ "$EXISTS" = "True" ]; then
    pass "Vérification d'existence confirmée (exists: true)"
else
    fail "exists a retourné faux: $RESP"
fi

# -----------------------------------------------------------------
# TEST 7 : GET /api/artifacts/case/:caseId — Consultation de l'arborescence
# -----------------------------------------------------------------
echo "[TEST 7] GET /api/artifacts/case/:caseId — Traçabilité causale du dossier"
RESP=$(curl -s "$BACKEND/api/artifacts/case/$AI_CASE_ID")
COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")
if [ "$COUNT" -ge 9 ]; then
    pass "Dossier médical complet récupéré ($COUNT artefacts dans la chaîne causale)"
else
    fail "Nombre d'artefacts inattendu dans le dossier: $COUNT"
fi

# -----------------------------------------------------------------
# TEST 8 : GET /api/artifacts/:id/verify — Vérification hash (Cas VALIDE)
# -----------------------------------------------------------------
echo "[TEST 8] GET /api/artifacts/:id/verify — Empreinte conforme (VALID)"
RESP=$(curl -s "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify?hash=$ECG_VALID_HASH")
STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
MATCH=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('match',False))" 2>/dev/null || echo "False")
if [ "$STATUS" = "VALID" ] && [ "$MATCH" = "True" ]; then
    pass "Intégrité validée par le smart contract (status: VALID, match: true)"
else
    fail "Vérification hash inattendue: $RESP"
fi

# -----------------------------------------------------------------
# TEST 9 : GET /api/artifacts/:id/verify — Vérification hash (Cas CORROMPU)
# -----------------------------------------------------------------
echo "[TEST 9] GET /api/artifacts/:id/verify — Falsification détectée (CORRUPTED)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/verify?hash=$FAKE_HASH" 2>&1 || echo "000")
if [ "$HTTP_CODE" = "409" ]; then
    pass "Faux hash rejeté avec Code HTTP 409 Conflict (Alerte corruption)"
else
    fail "Code HTTP inattendu pour un faux hash: $HTTP_CODE (attendu 409)"
fi

# -----------------------------------------------------------------
# TEST 10 : GET /api/artifacts/:id/history — Audit des transactions
# -----------------------------------------------------------------
echo "[TEST 10] GET /api/artifacts/:id/history — Audit des blocs Fabric"
RESP=$(curl -s "$BACKEND/api/artifacts/$ECG_ARTIFACT_ID/history")
TX_COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('txCount',0))" 2>/dev/null || echo "0")
if [ "$TX_COUNT" -ge 1 ]; then
    pass "Historique d'audit blockchain accessible ($TX_COUNT transaction(s) certifiée(s))"
else
    fail "Historique vide ou invalide: $RESP"
fi

# -----------------------------------------------------------------
# TEST 11 : GET /api/artifacts/storage/:caseId — Consultation stockage off-chain
# -----------------------------------------------------------------
echo "[TEST 11] GET /api/artifacts/storage/:caseId — Inventaire stockage hors-chaîne"
RESP=$(curl -s "$BACKEND/api/artifacts/storage/$AI_CASE_ID")
FILE_COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "0")
if [ "$FILE_COUNT" -ge 8 ]; then
    pass "Stockage hors-chaîne inventorié avec succès ($FILE_COUNT fichiers)"
else
    fail "Nombre de fichiers hors-chaîne inattendu: $FILE_COUNT"
fi

# -----------------------------------------------------------------
# Bilan
# -----------------------------------------------------------------
echo ""
echo "================================================================="
printf "  Résultats Phase 6 : ✅ %d réussis | ❌ %d échoués\n" "$PASS" "$FAIL"
echo "================================================================="
echo ""

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
