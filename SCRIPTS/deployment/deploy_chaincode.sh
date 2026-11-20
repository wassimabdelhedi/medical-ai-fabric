#!/usr/bin/env bash
# ==============================================================================
# Étape 4 — Déploiement du Chaincode ArtifactContract
# Pipeline : Package → Install → Approve (Org1 + Org2) → Commit
# ==============================================================================
set -e

# --- Couleurs ---
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

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

# --- Paramètres du chaincode ---
CHAINCODE_NAME="artifacts"
CHAINCODE_VERSION="1.0"
CHAINCODE_SEQUENCE="1"
CHANNEL_NAME="mychannel"
CC_LANGUAGE="node"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CC_SRC_PATH="$PROJECT_ROOT/BLOCKCHAIN/chaincode"

echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}  DÉPLOIEMENT DU CHAINCODE — ArtifactContract v${CHAINCODE_VERSION}  ${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo -e "  Chaincode    : ${GREEN}$CHAINCODE_NAME${NC}"
echo -e "  Version      : ${GREEN}$CHAINCODE_VERSION${NC}"
echo -e "  Canal        : ${GREEN}$CHANNEL_NAME${NC}"
echo -e "  Source       : ${GREEN}$CC_SRC_PATH${NC}"
echo ""

# ==============================================================
# Étape 4.1 — PACKAGE
# ==============================================================
echo -e "${YELLOW}[4.1] Création du package chaincode...${NC}"
cd "$CC_SRC_PATH"
npm install --omit=dev --silent 2>/dev/null || true
cd "$TEST_NET"

PACKAGE_FILE="/tmp/${CHAINCODE_NAME}.tar.gz"

peer lifecycle chaincode package "$PACKAGE_FILE" \
    --path "$CC_SRC_PATH" \
    --lang "$CC_LANGUAGE" \
    --label "${CHAINCODE_NAME}_${CHAINCODE_VERSION}"

echo -e "  ✅ Package créé : $PACKAGE_FILE"

# ==============================================================
# Étape 4.2 — INSTALL sur peer0.org1
# ==============================================================
echo -e "\n${YELLOW}[4.2] Installation sur peer0.org1...${NC}"
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

peer lifecycle chaincode install "$PACKAGE_FILE"
echo -e "  ✅ Installé sur peer0.org1"

# Récupération du Package ID
PACKAGE_ID=$(peer lifecycle chaincode queryinstalled \
    --output json 2>/dev/null \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
# Prendre le DERNIER package installé correspondant au label (le plus récent)
matches = [cc['package_id'] for cc in data.get('installed_chaincodes', [])
           if '${CHAINCODE_NAME}_${CHAINCODE_VERSION}' in cc['label']]
print(matches[-1]) if matches else ''
")
echo -e "  📦 Package ID  : ${GREEN}$PACKAGE_ID${NC}"

# ==============================================================
# Étape 4.2 (suite) — INSTALL sur peer0.org2
# ==============================================================
echo -e "\n${YELLOW}[4.2] Installation sur peer0.org2...${NC}"
export CORE_PEER_LOCALMSPID="Org2MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
export CORE_PEER_ADDRESS=localhost:9051

peer lifecycle chaincode install "$PACKAGE_FILE"
echo -e "  ✅ Installé sur peer0.org2"

# ==============================================================
# Étape 4.3 — APPROVE pour Org1
# ==============================================================
echo -e "\n${YELLOW}[4.3] Approbation de la définition par Org1...${NC}"
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

peer lifecycle chaincode approveformyorg \
    -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com \
    --channelID "$CHANNEL_NAME" \
    --name "$CHAINCODE_NAME" \
    --version "$CHAINCODE_VERSION" \
    --package-id "$PACKAGE_ID" \
    --sequence "$CHAINCODE_SEQUENCE" \
    --tls \
    --cafile "$TEST_NET/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

echo -e "  ✅ Approuvé par Org1"

# ==============================================================
# Étape 4.3 (suite) — APPROVE pour Org2
# ==============================================================
echo -e "\n${YELLOW}[4.3] Approbation de la définition par Org2...${NC}"
export CORE_PEER_LOCALMSPID="Org2MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
export CORE_PEER_ADDRESS=localhost:9051

peer lifecycle chaincode approveformyorg \
    -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com \
    --channelID "$CHANNEL_NAME" \
    --name "$CHAINCODE_NAME" \
    --version "$CHAINCODE_VERSION" \
    --package-id "$PACKAGE_ID" \
    --sequence "$CHAINCODE_SEQUENCE" \
    --tls \
    --cafile "$TEST_NET/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

echo -e "  ✅ Approuvé par Org2"

# Vérification du consensus (les 2 orgs doivent avoir approuvé)
echo -e "\n${YELLOW}  Vérification du consensus d'approbation...${NC}"
peer lifecycle chaincode checkcommitreadiness \
    --channelID "$CHANNEL_NAME" \
    --name "$CHAINCODE_NAME" \
    --version "$CHAINCODE_VERSION" \
    --sequence "$CHAINCODE_SEQUENCE" \
    --tls \
    --cafile "$TEST_NET/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem" \
    --output json

# ==============================================================
# Étape 4.4 — COMMIT sur le canal mychannel
# ==============================================================
echo -e "\n${YELLOW}[4.4] Commit du chaincode sur le canal '$CHANNEL_NAME'...${NC}"
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

peer lifecycle chaincode commit \
    -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com \
    --channelID "$CHANNEL_NAME" \
    --name "$CHAINCODE_NAME" \
    --version "$CHAINCODE_VERSION" \
    --sequence "$CHAINCODE_SEQUENCE" \
    --tls \
    --cafile "$TEST_NET/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem" \
    --peerAddresses localhost:7051 \
    --tlsRootCertFiles "$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" \
    --peerAddresses localhost:9051 \
    --tlsRootCertFiles "$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

echo -e "  ✅ Chaincode commité avec succès sur '$CHANNEL_NAME'"

# Vérification finale
echo -e "\n${YELLOW}  Vérification du déploiement...${NC}"
peer lifecycle chaincode querycommitted \
    --channelID "$CHANNEL_NAME" \
    --name "$CHAINCODE_NAME" \
    --output json

echo -e "\n${GREEN}=================================================================${NC}"
echo -e "${GREEN}  🎉 DÉPLOIEMENT RÉUSSI — ArtifactContract est actif !           ${NC}"
echo -e "${GREEN}  Canal : $CHANNEL_NAME | Nom : $CHAINCODE_NAME | Version : $CHAINCODE_VERSION ${NC}"
echo -e "${GREEN}=================================================================${NC}"
echo -e "\n  Prochaine étape : ${YELLOW}./BLOCKCHAIN/tests/test_artifact_contract.sh${NC}"
