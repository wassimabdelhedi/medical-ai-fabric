'use strict';
/**
 * fabric.js — Configuration et connexion au réseau Hyperledger Fabric
 * ====================================================================
 * Localisation : BLOCKCHAIN/backend/src/config/fabric.js
 *
 * Rôle : Établir la connexion gRPC sécurisée avec le peer Org1 via
 *        @hyperledger/fabric-gateway (SDK officiel Fabric 2.4+).
 *        Expose getGateway() utilisé par tous les services.
 */

const path  = require('path');
const fs    = require('fs');
const grpc  = require('@grpc/grpc-js');
const { connect, hash, signers } = require('@hyperledger/fabric-gateway');
const crypto = require('crypto');

// --- Chemins vers les certificats du test-network ---
const FABRIC_SAMPLES = process.env.FABRIC_SAMPLES_DIR
    || path.join(process.env.HOME, 'hyperledger', 'fabric-samples');

const TEST_NET = path.join(FABRIC_SAMPLES, 'test-network');
const ORG1_DIR = path.join(TEST_NET, 'organizations', 'peerOrganizations', 'org1.example.com');

const PEER_ENDPOINT      = process.env.PEER_ENDPOINT      || 'localhost:7051';
const PEER_HOST_OVERRIDE = process.env.PEER_HOST_OVERRIDE || 'peer0.org1.example.com';
const MSP_ID             = process.env.MSP_ID             || 'Org1MSP';
const CHANNEL_NAME       = process.env.CHANNEL_NAME       || 'mychannel';
const CHAINCODE_NAME     = process.env.CHAINCODE_NAME     || 'artifacts';

/**
 * Lit le certificat TLS du peer pour la connexion gRPC sécurisée.
 */
function newGrpcConnection() {
    const tlsCertPath = path.join(
        ORG1_DIR, 'peers', 'peer0.org1.example.com', 'tls', 'ca.crt'
    );
    const tlsRootCert = fs.readFileSync(tlsCertPath);
    const tlsCredentials = grpc.credentials.createSsl(tlsRootCert);
    return new grpc.Client(PEER_ENDPOINT, tlsCredentials, {
        'grpc.ssl_target_name_override': PEER_HOST_OVERRIDE,
    });
}

/**
 * Crée l'identité (certificat x509) de l'Admin Org1.
 */
function newIdentity() {
    const certDir = path.join(ORG1_DIR, 'users', 'Admin@org1.example.com', 'msp', 'signcerts');
    const certFiles = fs.readdirSync(certDir);
    const certPem = fs.readFileSync(path.join(certDir, certFiles[0]));
    return { mspId: MSP_ID, credentials: certPem };
}

/**
 * Crée le signataire à partir de la clé privée de l'Admin Org1.
 */
function newSigner() {
    const keyDir = path.join(ORG1_DIR, 'users', 'Admin@org1.example.com', 'msp', 'keystore');
    const keyFiles = fs.readdirSync(keyDir);
    const privateKeyPem = fs.readFileSync(path.join(keyDir, keyFiles[0]));
    const privateKey = crypto.createPrivateKey(privateKeyPem);
    return signers.newPrivateKeySigner(privateKey);
}

/**
 * Établit la connexion Gateway et retourne { gateway, client, network, contract }.
 * Appeler gateway.close() et client.close() après usage.
 */
async function getGateway() {
    const client = newGrpcConnection();
    const gateway = connect({
        client,
        identity: newIdentity(),
        signer: newSigner(),
        hash: hash.sha256,
        evaluateOptions: () => ({ deadline: Date.now() + 10_000 }),   // 10s timeout
        endorseOptions:  () => ({ deadline: Date.now() + 30_000 }),   // 30s timeout
        submitOptions:   () => ({ deadline: Date.now() + 30_000 }),
        commitStatusOptions: () => ({ deadline: Date.now() + 60_000 }),
    });
    const network  = gateway.getNetwork(CHANNEL_NAME);
    const contract = network.getContract(CHAINCODE_NAME);
    return { gateway, client, network, contract };
}

module.exports = { getGateway, CHANNEL_NAME, CHAINCODE_NAME };
