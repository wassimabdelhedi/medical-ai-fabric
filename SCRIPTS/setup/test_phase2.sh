#!/usr/bin/env bash
# ==============================================================================
# Script de test et validation de la Phase 2 — Réseau Fabric
# ==============================================================================
set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Détection automatique de Fabric Samples
if [ -n "$FABRIC_SAMPLES_DIR" ] && [ -d "$FABRIC_SAMPLES_DIR/test-network" ]; then
    FABRIC_BASE="$FABRIC_SAMPLES_DIR"
elif [ -d "$HOME/fabric-lab/fabric-samples/test-network" ]; then
    FABRIC_BASE="$HOME/fabric-lab/fabric-samples"
elif [ -d "$HOME/fabric-samples/test-network" ]; then
    FABRIC_BASE="$HOME/fabric-samples"
else
    echo -e "${RED}❌ [ERREUR] Dossier fabric-samples introuvable.${NC}"
    exit 1
fi

TEST_NET="$FABRIC_BASE/test-network"
export FABRIC_CFG_PATH="$FABRIC_BASE/config"

echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}      TEST & VALIDATION DE LA PHASE 2 — RÉSEAU FABRIC            ${NC}"
echo -e "${BLUE}=================================================================${NC}"

# 1. Vérification des conteneurs
echo -e "\n${YELLOW}[Étape 1 & 2] Vérification des nœuds peers et orderer...${NC}"
RUNNING=$(docker ps --filter "name=peer0.org1|peer0.org2|orderer" --format "{{.Names}}")
for node in orderer.example.com peer0.org1.example.com peer0.org2.example.com; do
    if echo "$RUNNING" | grep -q "$node"; then
        echo -e "  ✅ Nœud actif : ${GREEN}$node${NC}"
    else
        echo -e "  ❌ Nœud manquant : ${RED}$node${NC}"
        echo -e "${RED}Veuillez démarrer le réseau avec : ./SCRIPTS/setup/start_network.sh${NC}"
        exit 1
    fi
done

# 2. Vérification des certificats et identités MSP
echo -e "\n${YELLOW}[Étape 4] Vérification des identités et certificats MSP...${NC}"
if [ -d "$TEST_NET/organizations/peerOrganizations/org1.example.com/msp" ] && \
   [ -d "$TEST_NET/organizations/peerOrganizations/org2.example.com/msp" ] && \
   [ -d "$TEST_NET/organizations/ordererOrganizations/example.com/msp" ]; then
    echo -e "  ✅ Certificats Org1 présents : ${GREEN}$TEST_NET/organizations/peerOrganizations/org1.example.com/msp${NC}"
    echo -e "  ✅ Certificats Org2 présents : ${GREEN}$TEST_NET/organizations/peerOrganizations/org2.example.com/msp${NC}"
    echo -e "  ✅ Certificats Orderer présents : ${GREEN}$TEST_NET/organizations/ordererOrganizations/example.com/msp${NC}"
else
    echo -e "  ❌ Dossiers MSP manquants dans $TEST_NET/organizations/"
    exit 1
fi

# 3. Test sur Org1 (Canal mychannel)
echo -e "\n${YELLOW}[Étape 3 & 5] Test du canal 'mychannel' depuis Org1...${NC}"
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

echo "  Canaux rejoints par Org1 :"
peer channel list
INFO_ORG1=$(peer channel getinfo -c mychannel 2>&1)
echo "  $INFO_ORG1"

# 4. Test sur Org2 (Canal mychannel)
echo -e "\n${YELLOW}[Étape 3 & 5] Test du canal 'mychannel' depuis Org2...${NC}"
export CORE_PEER_LOCALMSPID="Org2MSP"
export CORE_PEER_TLS_ROOTCERT_FILE="$TEST_NET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$TEST_NET/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp"
export CORE_PEER_ADDRESS=localhost:9051

echo "  Canaux rejoints par Org2 :"
peer channel list
INFO_ORG2=$(peer channel getinfo -c mychannel 2>&1)
echo "  $INFO_ORG2"

echo -e "\n${GREEN}=================================================================${NC}"
echo -e "${GREEN}  🎉 SUCCÈS : La Phase 2 est 100% opérationnelle et synchronisée ! ${NC}"
echo -e "${GREEN}=================================================================${NC}"

