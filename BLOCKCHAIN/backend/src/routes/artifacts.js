'use strict';
/**
 * artifacts.js — Routes REST de l'API Blockchain
 * ===============================================
 * Localisation : BLOCKCHAIN/backend/src/routes/artifacts.js
 *
 * Endpoints exposés :
 *
 *  POST  /api/artifacts/register-package         Enregistre un fabric_package.json (body JSON)
 *  POST  /api/artifacts/register-ai-case         Enregistre un dossier IA local par aiCaseId
 *  POST  /api/artifacts/store-case               [Phase 5] Stocke les fichiers hors-chaîne + vérifie intégrité
 *  GET   /api/artifacts/storage/:caseId          [Phase 5] Liste les fichiers stockés hors-chaîne
 *  GET   /api/artifacts/:artifactId              Lit un artefact du ledger
 *  GET   /api/artifacts/case/:caseId             Historique d'un dossier médical
 *  GET   /api/artifacts/:artifactId/verify       Vérifie l'intégrité (hash en query param)
 *  GET   /api/artifacts/:artifactId/verify-file  [Phase 5] Vérifie le fichier hors-chaîne vs blockchain
 *  GET   /api/artifacts/:artifactId/history      Historique des transactions blockchain
 *  GET   /api/artifacts/:artifactId/exists       Vérifie l'existence sur le ledger
 */

const express = require('express');
const router  = express.Router();
const svc     = require('../services/artifactService');

// ----------------------------------------------------------------
// POST /api/artifacts
// Body : { artifactId, caseId, artifactType, hash, ... }
// Enregistre un artefact médical unitaire sur le ledger
// ----------------------------------------------------------------
router.post('/', async (req, res, next) => {
    try {
        const result = await svc.registerSingleArtifact(req.body);
        res.status(201).json(result);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// POST /api/artifacts/register-package
// Body : contenu complet d'un fabric_package.json
// ----------------------------------------------------------------
router.post('/register-package', async (req, res, next) => {
    try {
        const fabricPackage = req.body;
        if (!fabricPackage || !fabricPackage.ledger_records) {
            return res.status(400).json({
                error: 'Body invalide : ledger_records manquant. Fournir un fabric_package.json valide.',
            });
        }
        const result = await svc.registerFabricPackage(fabricPackage);
        res.status(201).json({
            message: 'Package IA enregistré sur Hyperledger Fabric.',
            ...result,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// POST /api/artifacts/register-ai-case
// Body : { "aiCaseId": "CASE00001" }
// Charge le fabric_package.json depuis AI/outputs/{aiCaseId}/
// ----------------------------------------------------------------
router.post('/register-ai-case', async (req, res, next) => {
    try {
        const { aiCaseId } = req.body;
        if (!aiCaseId) {
            return res.status(400).json({ error: 'aiCaseId requis dans le body.' });
        }
        const result = await svc.registerAiCase(aiCaseId);
        res.status(201).json({
            message: `Dossier IA "${aiCaseId}" enregistré sur Hyperledger Fabric.`,
            ...result,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// POST /api/artifacts/store-case  [PHASE 5]
// Body : { "aiCaseId": "CASE00001" }
// Transfère les fichiers médicaux vers le stockage hors-chaîne
// et vérifie leur intégrité SHA-256 vs le ledger Fabric.
// ----------------------------------------------------------------
router.post('/store-case', async (req, res, next) => {
    try {
        const { aiCaseId } = req.body;
        if (!aiCaseId) {
            return res.status(400).json({ error: 'aiCaseId requis dans le body.' });
        }
        const result = await svc.storeAiCaseFiles(aiCaseId);

        // Code HTTP selon le résultat d'intégrité
        const hasCorruption = result.summary.corrupted > 0;
        const statusCode    = hasCorruption ? 207 : 200; // 207 Multi-Status si au moins un fichier corrompu

        res.status(statusCode).json({
            message: hasCorruption
                ? `⚠️  Stockage terminé avec ${result.summary.corrupted} fichier(s) compromis !`
                : `✅ Tous les fichiers de "${aiCaseId}" sont stockés et intègres.`,
            ...result,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/storage/:caseId  [PHASE 5]
// Liste les fichiers stockés hors-chaîne pour un dossier
// IMPORTANT : avant les routes /:artifactId pour éviter collision
// ----------------------------------------------------------------
router.get('/storage/:caseId', async (req, res, next) => {
    try {
        const files = svc.listStoredFiles(req.params.caseId);
        res.json({
            caseId:    req.params.caseId,
            count:     files.length,
            files,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/case/:caseId
// IMPORTANT : cette route doit être AVANT /:artifactId pour éviter
// que "case" soit intercepté comme un artifactId
// ----------------------------------------------------------------
router.get('/case/:caseId', async (req, res, next) => {
    try {
        const artifacts = await svc.getArtifactsByCase(req.params.caseId);
        res.json({
            caseId:    req.params.caseId,
            count:     artifacts.length,
            artifacts,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId
// ----------------------------------------------------------------
router.get('/:artifactId', async (req, res, next) => {
    try {
        const artifact = await svc.readArtifact(req.params.artifactId);
        res.json(artifact);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/verify?hash=<sha256>
// ----------------------------------------------------------------
router.get('/:artifactId/verify', async (req, res, next) => {
    try {
        const { hash } = req.query;
        if (!hash) {
            return res.status(400).json({
                error: 'Paramètre query ?hash=<sha256> requis pour la vérification.',
            });
        }
        const result = await svc.verifyArtifact(req.params.artifactId, hash);
        const statusCode = result.status === 'VALID'     ? 200
            : result.status === 'NOT_FOUND'              ? 404
            : 409; // CORRUPTED → conflict
        res.status(statusCode).json(result);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/verify-file  [PHASE 5]
// Relit le fichier hors-chaîne, recalcule son SHA-256 et compare
// avec le hash immuable inscrit sur le ledger Fabric.
// ----------------------------------------------------------------
router.get('/:artifactId/verify-file', async (req, res, next) => {
    try {
        const result = await svc.verifyStoredArtifact(req.params.artifactId);
        const statusCode = result.status === 'VALID'     ? 200
            : result.status === 'MISSING'                ? 404
            : result.status === 'NO_STORAGE_REF'         ? 422
            : 409; // CORRUPTED → conflict
        res.status(statusCode).json(result);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/history
// ----------------------------------------------------------------
router.get('/:artifactId/history', async (req, res, next) => {
    try {
        const history = await svc.getArtifactHistory(req.params.artifactId);
        res.json({
            artifactId: req.params.artifactId,
            txCount:    history.length,
            history,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/exists
// ----------------------------------------------------------------
router.get('/:artifactId/exists', async (req, res, next) => {
    try {
        const exists = await svc.artifactExists(req.params.artifactId);
        res.json({ artifactId: req.params.artifactId, exists });
    } catch (err) { next(err); }
});

module.exports = router;


// ----------------------------------------------------------------
// POST /api/artifacts
// Body : { artifactId, caseId, artifactType, hash, ... }
// Enregistre un artefact médical unitaire sur le ledger
// ----------------------------------------------------------------
router.post('/', async (req, res, next) => {
    try {
        const result = await svc.registerSingleArtifact(req.body);
        res.status(201).json(result);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// POST /api/artifacts/register-package
// Body : contenu complet d'un fabric_package.json
// ----------------------------------------------------------------
router.post('/register-package', async (req, res, next) => {
    try {
        const fabricPackage = req.body;
        if (!fabricPackage || !fabricPackage.ledger_records) {
            return res.status(400).json({
                error: 'Body invalide : ledger_records manquant. Fournir un fabric_package.json valide.',
            });
        }
        const result = await svc.registerFabricPackage(fabricPackage);
        res.status(201).json({
            message: 'Package IA enregistré sur Hyperledger Fabric.',
            ...result,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// POST /api/artifacts/register-ai-case
// Body : { "aiCaseId": "CASE00001" }
// Charge le fabric_package.json depuis AI/outputs/{aiCaseId}/
// ----------------------------------------------------------------
router.post('/register-ai-case', async (req, res, next) => {
    try {
        const { aiCaseId } = req.body;
        if (!aiCaseId) {
            return res.status(400).json({ error: 'aiCaseId requis dans le body.' });
        }
        const result = await svc.registerAiCase(aiCaseId);
        res.status(201).json({
            message: `Dossier IA "${aiCaseId}" enregistré sur Hyperledger Fabric.`,
            ...result,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/case/:caseId
// IMPORTANT : cette route doit être AVANT /:artifactId pour éviter
// que "case" soit intercepté comme un artifactId
// ----------------------------------------------------------------
router.get('/case/:caseId', async (req, res, next) => {
    try {
        const artifacts = await svc.getArtifactsByCase(req.params.caseId);
        res.json({
            caseId:    req.params.caseId,
            count:     artifacts.length,
            artifacts,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId
// ----------------------------------------------------------------
router.get('/:artifactId', async (req, res, next) => {
    try {
        const artifact = await svc.readArtifact(req.params.artifactId);
        res.json(artifact);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/verify?hash=<sha256>
// ----------------------------------------------------------------
router.get('/:artifactId/verify', async (req, res, next) => {
    try {
        const { hash } = req.query;
        if (!hash) {
            return res.status(400).json({
                error: 'Paramètre query ?hash=<sha256> requis pour la vérification.',
            });
        }
        const result = await svc.verifyArtifact(req.params.artifactId, hash);
        const statusCode = result.status === 'VALID' ? 200
            : result.status === 'NOT_FOUND'          ? 404
            : 409; // CORRUPTED → conflict
        res.status(statusCode).json(result);
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/history
// ----------------------------------------------------------------
router.get('/:artifactId/history', async (req, res, next) => {
    try {
        const history = await svc.getArtifactHistory(req.params.artifactId);
        res.json({
            artifactId: req.params.artifactId,
            txCount:    history.length,
            history,
        });
    } catch (err) { next(err); }
});

// ----------------------------------------------------------------
// GET /api/artifacts/:artifactId/exists
// ----------------------------------------------------------------
router.get('/:artifactId/exists', async (req, res, next) => {
    try {
        const exists = await svc.artifactExists(req.params.artifactId);
        res.json({ artifactId: req.params.artifactId, exists });
    } catch (err) { next(err); }
});

module.exports = router;
