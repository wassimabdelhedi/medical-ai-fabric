'use strict';
/**
 * app.js — Serveur Express principal du backend Blockchain
 * =========================================================
 * Localisation : BLOCKCHAIN/backend/src/app.js
 *
 * Démarrage : node src/app.js  (depuis BLOCKCHAIN/backend/)
 * Port      : 3001 (configurable via PORT env)
 */

const express      = require('express');
const errorHandler = require('./middleware/errorHandler');
const artifactRoutes = require('./routes/artifacts');

const app  = express();
const PORT = process.env.PORT || 3001;

// --- Middlewares globaux ---
app.use(express.json({ limit: '10mb' }));  // body JSON (fabric_package peut être volumineux)
app.use(express.urlencoded({ extended: true }));

// --- Logger minimal ---
app.use((req, _res, next) => {
    console.info(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    next();
});

// --- Routes API ---
app.use('/api/artifacts', artifactRoutes);

// --- Page d'accueil / API Explorer ---
app.get('/', (_req, res) => {
    res.json({
        name:        'Medical AI Fabric API',
        description: "API REST de traçabilité et d'intégrité médicale par Blockchain Hyperledger Fabric",
        version:     '1.0.0',
        status:      'ONLINE',
        network: {
            channel:   process.env.CHANNEL_NAME   || 'mychannel',
            chaincode: process.env.CHAINCODE_NAME || 'artifacts',
        },
        endpoints: {
            health:          { method: 'GET',  path: '/health',                                      description: 'État du service et connectivité Fabric' },
            registerSingle:  { method: 'POST', path: '/api/artifacts',                               description: 'Enregistre un artefact unitaire sur le ledger' },
            registerAiCase:  { method: 'POST', path: '/api/artifacts/register-ai-case',              description: 'Ancre les 9 artefacts du dossier IA sur Fabric' },
            registerPackage: { method: 'POST', path: '/api/artifacts/register-package',              description: 'Ancre un fabric_package.json complet' },
            storeCase:       { method: 'POST', path: '/api/artifacts/store-case',                      description: 'Stocke les fichiers médicaux hors-chaîne (Phase 5)' },
            listStorage:     { method: 'GET',  path: '/api/artifacts/storage/:caseId',                 description: 'Liste les fichiers stockés hors-chaîne pour un cas' },
            readArtifact:    { method: 'GET',  path: '/api/artifacts/:artifactId',                  description: 'Lit les métadonnées blockchain d’un artefact' },
            getCaseHistory:  { method: 'GET',  path: '/api/artifacts/case/:caseId',                 description: 'Récupère la chaîne causale complète d’un dossier' },
            verifyHash:      { method: 'GET',  path: '/api/artifacts/:artifactId/verify?hash=...',   description: 'Vérifie l’intégrité via un hash fourni' },
            verifyFile:      { method: 'GET',  path: '/api/artifacts/:artifactId/verify-file',      description: 'Vérifie l’intégrité du fichier physique hors-chaîne' },
            history:         { method: 'GET',  path: '/api/artifacts/:artifactId/history',          description: 'Historique des transactions Fabric (Audit)' },
            exists:          { method: 'GET',  path: '/api/artifacts/:artifactId/exists',           description: 'Vérifie l’existence sur le ledger' },
        },
    });
});

// --- Health check ---
app.get('/health', (_req, res) => {
    res.json({
        status:    'UP',
        service:   'medical-fabric-backend',
        timestamp: new Date().toISOString(),
        fabric: {
            channel:   process.env.CHANNEL_NAME   || 'mychannel',
            chaincode: process.env.CHAINCODE_NAME || 'artifacts',
        },
    });
});

// --- Gestion des routes inconnues ---
app.use((_req, res) => {
    res.status(404).json({ error: 'Route introuvable.' });
});

// --- Middleware d'erreurs (doit être en dernier) ---
app.use(errorHandler);

// --- Démarrage du serveur ---
app.listen(PORT, () => {
    console.info('='.repeat(60));
    console.info('  🏥 Medical AI Fabric — Backend Blockchain');
    console.info('='.repeat(60));
    console.info(`  Serveur    : http://localhost:${PORT}`);
    console.info(`  Health     : http://localhost:${PORT}/health`);
    console.info(`  Artifacts  : http://localhost:${PORT}/api/artifacts`);
    console.info(`  Channel    : ${process.env.CHANNEL_NAME || 'mychannel'}`);
    console.info(`  Chaincode  : ${process.env.CHAINCODE_NAME || 'artifacts'}`);
    console.info('='.repeat(60));
});

module.exports = app;
