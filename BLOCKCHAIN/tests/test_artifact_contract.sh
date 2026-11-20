#!/usr/bin/env bash
# ==============================================================================
# Étape 5 — Tests Fonctionnels du Chaincode ArtifactContract
# Tests : RegisterArtifact | ReadArtifact | GetArtifactsByCase | VerifyArtifact
# ==============================================================================
set -eo pipefail

# --- Couleurs ---
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

PASS=0; FAIL=0

# --- Détection automatique de fabric-samples ---
if [ -n "$FABRIC_SAMPLES_DIR" ] && [ -d "$FABRIC_SAMPLES_DIR/test-network" ]; then
    FABRIC_BASE="$FABRIC_SAMPLES_DIR"
elif [ -d "$HOME/hyperledger/fabric-samples/test-network" ]; then
    FABRIC_BASE="$HOME/hyperledger/fabric-samples"
elif [ -d "$HOME/fabric-samples/test-network" ]; then
    FABRIC_BASE="$HOME/fabric-samples"
else
    echo -e "${RED}❌ fabric-samples introuvable.${NC}"; exit 1
fi

export PATH="$FABRIC_BASE/bin:$PATH"
export FABRIC_CFG_PATH="$FABRIC_BASE/config"
TEST_NET="$FABRIC_BASE/test-network"

CHANNEL_NAME="mychannel"
CC_NAME="artifacts"
ORDERER_CA="$TEST_NET/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

# Environnement Org1 par défaut
setOrg1() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org1MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:7051
}

setOrg2() {
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="Org2MSP"
    export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:9051
}

# Helpers
checkPass() { echo -e "  ✅ ${GREEN}$1${NC}"; PASS=$((PASS+1)); }
checkFail() { echo -e "  ❌ ${RED}$1${NC}"; FAIL=$((FAIL+1)); }

echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}  TESTS FONCTIONNELS — ArtifactContract                         ${NC}"
echo -e "${BLUE}=================================================================${NC}"

# Hash SHA-256 de test (64 chars hex valides)
HASH_ORIGINAL="b94d27b9934d3e08a52e52d7da7dabfac484efe04294e576f7a9e9ea9f1d8a52"
HASH_PROCESSED="c94d27b9934d3e08a52e52d7da7dabfac484efe04294e576f7a9e9ea9f1d8a53"
HASH_FEATURES="d94d27b9934d3e08a52e52d7da7dabfac484efe04294e576f7a9e9ea9f1d8a54"
HASH_PREDICTION="e94d27b9934d3e08a52e52d7da7dabfac484efe04294e576f7a9e9ea9f1d8a55"
HASH_FAKE="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Identifiants uniques basés sur le timestamp (évite les conflits avec les exécutions précédentes)
TS=$(date +%s)
CASE_ID="CASE${TS}"
ORIG_ID="ORIG${TS}"
PRED_ID="PRED${TS}"

echo -e "  Identifiants de ce run : ${GREEN}$ORIG_ID / $PRED_ID / $CASE_ID${NC}"

# ==============================================================
# TEST 1 : RegisterArtifact — Données originales (ORIGINAL_DATA)
# ==============================================================
echo -e "\n${YELLOW}[TEST 1] RegisterArtifact — ORIGINAL_DATA${NC}"
setOrg1

ARTIFACT_ORIGINAL=$(cat <<EOF
{"artifactId":"$ORIG_ID","caseId":"$CASE_ID","artifactType":"ORIGINAL_DATA","hash":"$HASH_ORIGINAL","parentArtifactId":null,"storageRef":"storage/$CASE_ID/original_ecg.csv","modelVersion":"1.0","creator":"agent-orchestrator","timestamp":"$NOW"}
EOF
)

RESULT=$(peer chaincode invoke \
    -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com \
    --tls --cafile "$ORDERER_CA" \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    --peerAddresses localhost:7051 \
    --tlsRootCertFiles "$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
    --peerAddresses localhost:9051 \
    --tlsRootCertFiles "$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" \
    -c "{\"function\":\"RegisterArtifact\",\"Args\":[$(echo $ARTIFACT_ORIGINAL | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')]}" \
    2>&1) || true

if echo "$RESULT" | grep -q "status:200\|Chaincode invoke successful"; then
    checkPass "$ORIG_ID enregistré (ORIGINAL_DATA)"
else
    checkFail "$ORIG_ID — $RESULT"
fi

sleep 2

# ==============================================================
# TEST 2 : RegisterArtifact — Prédiction IA (AI_PREDICTION)
# ==============================================================
echo -e "\n${YELLOW}[TEST 2] RegisterArtifact — AI_PREDICTION${NC}"

ARTIFACT_PRED=$(cat <<EOF
{"artifactId":"$PRED_ID","caseId":"$CASE_ID","artifactType":"AI_PREDICTION","hash":"$HASH_PREDICTION","parentArtifactId":"$ORIG_ID","storageRef":"storage/$CASE_ID/prediction.json","modelVersion":"1.0","creator":"agent-ia","timestamp":"$NOW"}
EOF
)

RESULT=$(peer chaincode invoke \
    -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com \
    --tls --cafile "$ORDERER_CA" \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    --peerAddresses localhost:7051 \
    --tlsRootCertFiles "$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
    --peerAddresses localhost:9051 \
    --tlsRootCertFiles "$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" \
    -c "{\"function\":\"RegisterArtifact\",\"Args\":[$(echo $ARTIFACT_PRED | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')]}" \
    2>&1) || true

if echo "$RESULT" | grep -q "status:200\|Chaincode invoke successful"; then
    checkPass "$PRED_ID enregistré (AI_PREDICTION, parent=$ORIG_ID)"
else
    checkFail "$PRED_ID — $RESULT"
fi

sleep 2

# ==============================================================
# TEST 3 : ReadArtifact — Lecture de ORIG001
# ==============================================================
echo -e "\n${YELLOW}[TEST 3] ReadArtifact — Lecture de ORIG001${NC}"
setOrg1

RESULT=$(peer chaincode query \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    -c "{\"function\":\"ReadArtifact\",\"Args\":[\"$ORIG_ID\"]}" 2>&1) || true

if echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['artifactId']=='$ORIG_ID'; assert d['artifactType']=='ORIGINAL_DATA'; print('artifactId OK, type OK')" 2>/dev/null; then
    checkPass "$ORIG_ID lu correctement"
else
    checkFail "ReadArtifact $ORIG_ID — Résultat : $RESULT"
fi

# ==============================================================
# TEST 4 : GetArtifactsByCase — Historique de CASE001
# ==============================================================
echo -e "\n${YELLOW}[TEST 4] GetArtifactsByCase — Dossier CASE001${NC}"

RESULT=$(peer chaincode query \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    -c "{\"function\":\"GetArtifactsByCase\",\"Args\":[\"$CASE_ID\"]}" 2>&1) || true

COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "0")

if [ "$COUNT" -ge "2" ]; then
    checkPass "GetArtifactsByCase CASE001 : $COUNT artefact(s) trouvé(s)"
    echo "$RESULT" | python3 -c "
import sys, json
artifacts = json.load(sys.stdin)
for a in artifacts:
    print(f'    → {a[\"artifactId\"]} | {a[\"artifactType\"]} | parent: {a.get(\"parentArtifactId\",\"N/A\")}')
" 2>/dev/null || true
else
    checkFail "GetArtifactsByCase CASE001 : seulement $COUNT artefact(s) — Résultat : $RESULT"
fi

# ==============================================================
# TEST 5 : VerifyArtifact — Vérification VALIDE (hash correct)
# ==============================================================
echo -e "\n${YELLOW}[TEST 5] VerifyArtifact — Intégrité VALIDE (bon hash)${NC}"

RESULT=$(peer chaincode query \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    -c "{\"function\":\"VerifyArtifact\",\"Args\":[\"$ORIG_ID\",\"$HASH_ORIGINAL\"]}" 2>&1) || true

STATUS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "ERREUR")

if [ "$STATUS" = "VALID" ]; then
    checkPass "VerifyArtifact ORIG001 → statut : $STATUS ✔"
else
    checkFail "VerifyArtifact ORIG001 — Statut attendu: VALID, obtenu: $STATUS — $RESULT"
fi

# ==============================================================
# TEST 6 : VerifyArtifact — Détection d'ALTÉRATION (faux hash)
# ==============================================================
echo -e "\n${YELLOW}[TEST 6] VerifyArtifact — Détection ALTÉRATION (faux hash)${NC}"

RESULT=$(peer chaincode query \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    -c "{\"function\":\"VerifyArtifact\",\"Args\":[\"$ORIG_ID\",\"$HASH_FAKE\"]}" 2>&1) || true

STATUS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "ERREUR")

if [ "$STATUS" = "CORRUPTED" ]; then
    checkPass "VerifyArtifact ORIG001 (faux hash) → statut : $STATUS ✔ ALTÉRATION DÉTECTÉE"
else
    checkFail "VerifyArtifact (faux hash) — Statut attendu: CORRUPTED, obtenu: $STATUS"
fi

# ==============================================================
# TEST 7 : ArtifactExists — Existence
# ==============================================================
echo -e "\n${YELLOW}[TEST 7] ArtifactExists — Vérification d'existence${NC}"

EXISTS=$(peer chaincode query \
    -C "$CHANNEL_NAME" -n "$CC_NAME" \
    -c "{\"function\":\"ArtifactExists\",\"Args\":[\"$PRED_ID\"]}" 2>&1) || true

if echo "$EXISTS" | grep -q "true"; then
    checkPass "ArtifactExists PRED001 → true ✔"
else
    checkFail "ArtifactExists PRED001 — Résultat : $EXISTS"
fi

# ==============================================================
# RÉSUMÉ
# ==============================================================
TOTAL=$((PASS+FAIL))
echo -e "\n${BLUE}=================================================================${NC}"
echo -e "${BLUE}  RÉSUMÉ DES TESTS                                               ${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo -e "  Tests passés : ${GREEN}$PASS / $TOTAL${NC}"
[ "$FAIL" -gt 0 ] && echo -e "  Tests échoués : ${RED}$FAIL / $TOTAL${NC}"

if [ "$FAIL" -eq 0 ]; then
    echo -e "\n${GREEN}  🎉 SUCCÈS COMPLET — ArtifactContract 100% opérationnel !     ${NC}"
    echo -e "${GREEN}=================================================================${NC}"
    exit 0
else
    echo -e "\n${RED}  ⚠️  $FAIL test(s) échoué(s) — Vérifiez les logs ci-dessus.    ${NC}"
    echo -e "${RED}=================================================================${NC}"
    exit 1
fi
