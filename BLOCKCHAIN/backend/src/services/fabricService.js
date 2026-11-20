'use strict';
/**
 * fabricService.js — Couche d'accès Hyperledger Fabric
 * =====================================================
 * Localisation : BLOCKCHAIN/backend/src/services/fabricService.js
 *
 * Rôle : Encapsuler toutes les interactions avec le ledger Fabric.
 *   - submitTransaction()  : écriture (invoke) avec récupération du txId
 *   - evaluateTransaction() : lecture (query) sans transaction blockchain
 *
 * Chaque appel ouvre et ferme proprement la connexion Gateway.
 */

const { getGateway } = require('../config/fabric');

/**
 * Soumet une transaction en écriture au chaincode (invoke).
 * Retourne { result, txId } — txId est l'identifiant blockchain de la transaction.
 *
 * @param {string} functionName  Nom de la fonction chaincode (ex: 'RegisterArtifact')
 * @param {...string} args       Arguments de la fonction (doivent être des strings)
 * @returns {{ result: object, txId: string }}
 */
async function submitTransaction(functionName, ...args) {
    const { gateway, client, contract } = await getGateway();
    try {
        const stringArgs = args.map(a => typeof a === 'string' ? a : JSON.stringify(a));

        // submitAsync → soumet la transaction et retourne un objet avec txId + résultat
        const submitResult = await contract.submitAsync(functionName, { arguments: stringArgs });
        const txId         = Buffer.from(submitResult.getTransactionId()).toString();
        const resultBytes  = submitResult.getResult();

        const result = resultBytes && resultBytes.length > 0
            ? JSON.parse(Buffer.from(resultBytes).toString())
            : {};

        // Attendre le commit sur le ledger
        const status = await submitResult.getStatus();
        if (!status.successful) {
            throw new Error(`Transaction ${txId} a échoué avec le code ${status.code}.`);
        }

        console.info(`[Fabric] ✅ ${functionName} | txId: ${txId}`);
        return { result, txId };

    } finally {
        gateway.close();
        client.close();
    }
}

/**
 * Évalue une transaction en lecture (query) — aucun bloc créé sur le ledger.
 *
 * @param {string} functionName  Nom de la fonction chaincode (ex: 'ReadArtifact')
 * @param {...string} args       Arguments
 * @returns {object} Résultat parsé depuis le ledger
 */
async function evaluateTransaction(functionName, ...args) {
    const { gateway, client, contract } = await getGateway();
    try {
        const stringArgs = args.map(a => typeof a === 'string' ? a : JSON.stringify(a));
        const resultBytes = await contract.evaluateTransaction(functionName, ...stringArgs);

        const result = JSON.parse(Buffer.from(resultBytes).toString());
        console.info(`[Fabric] 📋 ${functionName} | ${args[0]}`);
        return result;

    } finally {
        gateway.close();
        client.close();
    }
}

module.exports = { submitTransaction, evaluateTransaction };
