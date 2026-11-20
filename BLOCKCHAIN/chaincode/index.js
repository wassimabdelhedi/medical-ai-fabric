'use strict';

/**
 * Point d'entrée du chaincode — Système Agentique d'Analyse Médicale
 * Enregistre ArtifactContract comme contrat Hyperledger Fabric actif.
 */

const { ArtifactContract } = require('./lib/artifactContract');

module.exports.ArtifactContract = ArtifactContract;
module.exports.contracts = [ArtifactContract];
