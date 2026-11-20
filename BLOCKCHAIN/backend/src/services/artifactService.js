'use strict';
/**
 * artifactService.js — Logique métier principale (IA → Blockchain)
 * ================================================================
 * Localisation : BLOCKCHAIN/backend/src/services/artifactService.js
 *
 * Rôle : Couche d'orchestration entre le package IA et le chaincode.
 *   1. Lire un fabric_package.json produit par l'équipe IA
 *   2. Enregistrer chaque ledger_record sur Hyperledger Fabric
 *   3. Lire / vérifier / historiser les artefacts via le chaincode
 *
 * Règle de compatibilité IA ↔ Chaincode :
 *   - Les types IA (ECG_ORIGINAL, AI_VALIDATION…) sont maintenant
 *     directement acceptés par le chaincode mis à jour.
 *   - parent_artifact_ids[] (tableau) → parentArtifactId (JSON string)
 *   - storage_ref null → remplacé par storageRef généré par storageService
 */

const path = require('path');
const fs = require('fs');
const { submitTransaction, evaluateTransaction } = require('./fabricService');
const { storeCaseFiles, verifyStoredFile, listCaseFiles, STORAGE_ROOT, ARTIFACT_TYPE_TO_FILE } = require('./storageService');

// Répertoire des outputs IA (relatif à la racine du projet)
const AI_OUTPUTS_DIR = process.env.AI_OUTPUTS_DIR
    || path.join(__dirname, '..', '..', '..', '..', 'AI', 'outputs');

// ================================================================
// 0. Enregistrement d'un artefact unique
// ================================================================

/**
 * Enregistre un artefact médical individuel sur le ledger Hyperledger Fabric.
 * @param {object} payload  { artifactId, caseId, artifactType, hash, parentArtifactId, storageRef, modelVersion, creator }
 * @returns {object} { artifactId, txId, status: 'REGISTERED' }
 */
async function registerSingleArtifact(payload) {
    if (!payload || !payload.artifactId || !payload.caseId || !payload.artifactType || !payload.hash) {
        throw new Error('Champs obligatoires manquants : artifactId, caseId, artifactType, hash requis.');
    }

    // Timestamp déterministe : obligatoire pour que tous les pairs endosseurs (Org1 et Org2)
    // calculent exactement le même WriteSet Fabric et évitent l'erreur "ProposalResponsePayloads do not match".
    const deterministicPayload = {
        artifactId: payload.artifactId,
        caseId: payload.caseId,
        artifactType: payload.artifactType,
        hash: payload.hash,
        parentArtifactId: payload.parentArtifactId
            ? (typeof payload.parentArtifactId === 'string' ? payload.parentArtifactId : JSON.stringify(payload.parentArtifactId))
            : null,
        storageRef: payload.storageRef || `offchain://${payload.caseId}/${payload.artifactType}_${payload.artifactId}`,
        modelVersion: payload.modelVersion || '1.0',
        creator: payload.creator || 'Doctor',
        timestamp: payload.timestamp || new Date().toISOString(),
    };

    const { txId, result } = await submitTransaction('RegisterArtifact', JSON.stringify(deterministicPayload));
    return {
        message: 'Artefact enregistré avec succès sur Hyperledger Fabric.',
        artifactId: payload.artifactId,
        caseId: payload.caseId,
        txId,
        data: result,
    };
}

// ================================================================
// 1. Enregistrement d'un package IA complet sur le ledger
// ================================================================

/**
 * Prend un fabric_package.json (produit par AI/pipeline/fabric_package.py)
 * et enregistre séquentiellement chaque ledger_record sur Hyperledger Fabric.
 *
 * @param {object} fabricPackage  Contenu parsé de fabric_package.json
 * @param {string} [aiCaseId]     ID local IA (ex: "CASE00001") pour résoudre les chemins
 * @returns {object[]}  Tableau de résultats par artefact { artifactId, txId, status }
 */
async function registerFabricPackage(fabricPackage, aiCaseId) {
    const { ledger_records, case_id: fabricCaseId } = fabricPackage;

    if (!Array.isArray(ledger_records) || ledger_records.length === 0) {
        throw new Error('fabric_package.json invalide : ledger_records manquant ou vide.');
    }

    console.info(`\n[ArtifactService] 🚀 Enregistrement de ${ledger_records.length} artefacts | Dossier Fabric : ${fabricCaseId}`);

    const results = [];

    for (const record of ledger_records) {
        try {
            // --- Construction du payload chaincode ---
            // parent_artifact_ids[] → JSON string (le chaincode stocke 1 champ string)
            const parentArtifactId = record.parent_artifact_ids && record.parent_artifact_ids.length > 0
                ? JSON.stringify(record.parent_artifact_ids)
                : null;

            // storage_ref : utiliser la valeur IA si disponible, sinon référence par défaut
            const storageRef = record.storage_ref
                || `offchain://${fabricCaseId}/${record.artifact_type}_${record.artifact_id}`;

            const artifactPayload = {
                artifactId: record.artifact_id,
                caseId: record.case_id,          // fabricCaseId pseudonymisé
                artifactType: record.artifact_type,    // ECG_ORIGINAL, AI_PREDICTION…
                hash: record.sha256,           // empreinte SHA-256 exacte
                parentArtifactId: parentArtifactId,
                storageRef: storageRef,
                modelVersion: record.model_version || '1.0',
                creator: record.producer || 'IA-ECG-prototype',
                timestamp: record.created_at_utc,
            };

            // --- Soumission au chaincode ---
            const { txId } = await submitTransaction(
                'RegisterArtifact',
                JSON.stringify(artifactPayload)
            );

            results.push({
                artifactId: record.artifact_id,
                artifactType: record.artifact_type,
                txId,
                status: 'REGISTERED',
            });

            console.info(`  ✅ ${record.artifact_type} | ${record.artifact_id.slice(0, 8)}... | txId: ${txId.slice(0, 16)}...`);

        } catch (err) {
            const alreadyExists = err.message && err.message.includes('existe déjà');
            results.push({
                artifactId: record.artifact_id,
                artifactType: record.artifact_type,
                txId: null,
                status: alreadyExists ? 'ALREADY_EXISTS' : 'ERROR',
                error: err.message,
            });
            console.warn(`  ⚠️  ${record.artifact_type} | ${record.artifact_id.slice(0, 8)}... | ${alreadyExists ? 'Déjà enregistré' : err.message}`);
        }
    }

    const registered = results.filter(r => r.status === 'REGISTERED').length;
    const skipped = results.filter(r => r.status === 'ALREADY_EXISTS').length;
    const errors = results.filter(r => r.status === 'ERROR').length;
    console.info(`[ArtifactService] ✅ ${registered} enregistrés | ⏭  ${skipped} déjà présents | ❌ ${errors} erreurs\n`);

    return { fabricCaseId, results };
}

// ================================================================
// 2. Enregistrement depuis le disque (chemin vers fabric_package.json)
// ================================================================

/**
 * Charge un fabric_package.json depuis le disque et l'enregistre sur Fabric.
 * Utile pour les appels API POST /api/artifacts/register-from-file
 *
 * @param {string} packagePath  Chemin absolu vers fabric_package.json
 * @returns {object}
 */
async function registerFromFile(packagePath) {
    if (!fs.existsSync(packagePath)) {
        throw new Error(`Fichier introuvable : ${packagePath}`);
    }
    const content = fs.readFileSync(packagePath, 'utf8');
    const fabricPackage = JSON.parse(content);
    return registerFabricPackage(fabricPackage);
}

/**
 * Enregistre le package d'un dossier IA local par son ID (ex: "CASE00001").
 * @param {string} aiCaseId  ex: "CASE00001"
 */
async function registerAiCase(aiCaseId) {
    const packagePath = path.join(AI_OUTPUTS_DIR, aiCaseId, 'fabric_package.json');
    return registerFromFile(packagePath);
}

// ================================================================
// 3. Lecture d'un artefact
// ================================================================

/**
 * Lit un artefact depuis le ledger Fabric.
 * @param {string} artifactId
 */
async function readArtifact(artifactId) {
    return evaluateTransaction('ReadArtifact', artifactId);
}

// ================================================================
// 4. Historique complet d'un dossier
// ================================================================

/**
 * Retourne tous les artefacts liés à un dossier (fabric case_id).
 * Reconstruit la chaîne causale en ordre chronologique.
 * @param {string} caseId  fabricCaseId (UUID pseudonymisé)
 */
async function getArtifactsByCase(caseId) {
    return evaluateTransaction('GetArtifactsByCase', caseId);
}

// ================================================================
// 5. Vérification d'intégrité
// ================================================================

/**
 * Vérifie l'intégrité d'un artefact en comparant son hash blockchain
 * avec un hash recalculé fourni par l'appelant.
 *
 * @param {string} artifactId     ID de l'artefact
 * @param {string} providedHash   Hash SHA-256 recalculé hors-chaîne (64 hex)
 */
async function verifyArtifact(artifactId, providedHash) {
    return evaluateTransaction('VerifyArtifact', artifactId, providedHash);
}

// ================================================================
// 6. Vérification d'existence
// ================================================================

async function artifactExists(artifactId) {
    return evaluateTransaction('ArtifactExists', artifactId);
}

// ================================================================
// 7. Historique des transactions blockchain d'un artefact
// ================================================================

/**
 * Retourne l'historique complet des transactions pour un artefact.
 * Utile pour l'audit et la démonstration de l'immuabilité.
 * @param {string} artifactId
 */
async function getArtifactHistory(artifactId) {
    return evaluateTransaction('GetArtifactHistory', artifactId);
}

// ================================================================
// 8. Stockage hors-chaîne + vérification d'intégrité (Phase 5)
// ================================================================

/**
 * Transfère tous les fichiers du dossier IA vers le stockage hors-chaîne
 * et vérifie l'intégrité de chaque fichier vs son hash blockchain.
 *
 * @param {string} aiCaseId  ID IA local (ex: "CASE00001")
 * @returns {object} { fabricCaseId, storageRoot, results[], summary }
 */
async function storeAiCaseFiles(aiCaseId) {
    const packagePath = path.join(AI_OUTPUTS_DIR, aiCaseId, 'fabric_package.json');
    if (!fs.existsSync(packagePath)) {
        throw new Error(`fabric_package.json introuvable : ${packagePath}`);
    }
    const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    const fabricCaseId = pkg.case_id;

    console.info(`\n[ArtifactService] 📦 Stockage hors-chaîne | Dossier : ${aiCaseId} → ${fabricCaseId}`);

    const results = storeCaseFiles(aiCaseId, fabricCaseId, pkg.ledger_records);

    const ok = results.filter(r => r.integrityMatch === true).length;
    const skipped = results.filter(r => r.skipped).length;
    const corrupted = results.filter(r => r.integrityMatch === false && !r.skipped).length;

    console.info(`[ArtifactService] ✅ ${ok} intègres | ⏭ ${skipped} ignorés | ❌ ${corrupted} compromis\n`);

    return {
        fabricCaseId,
        storageRoot: require('./storageService').STORAGE_ROOT,
        results,
        summary: { ok, skipped, corrupted, total: results.length },
    };
}

/**
 * Vérifie l'intégrité d'un fichier stocké hors-chaîne en comparant
 * son SHA-256 recalculé avec le hash inscrit sur le ledger Fabric.
 *
 * @param {string} artifactId  UUID de l'artefact
 * @returns {object} { status: 'VALID'|'CORRUPTED'|'MISSING', ... }
 */
async function verifyStoredArtifact(artifactId) {
    // 1. Récupérer les métadonnées blockchain
    const artifact = await evaluateTransaction('ReadArtifact', artifactId);

    // 2. Extraire le chemin depuis storageRef (offchain://caseId/filename)
    const storageRef = artifact.storageRef || '';
    const match = storageRef.match(/^offchain:\/\/([^/]+)\/(.+)$/);
    if (!match) {
        return {
            status: 'NO_STORAGE_REF',
            artifactId,
            storageRef,
            message: 'Aucune référence de stockage hors-chaîne enregistrée pour cet artefact.',
        };
    }

    const [, caseId, filename] = match;
    const result = verifyStoredFile(caseId, filename, artifact.hash, artifact.artifactType);

    if (!result.exists) {
        return {
            status: 'MISSING',
            artifactId,
            artifactType: artifact.artifactType,
            caseId,
            filename,
            storageRef,
            blockchainHash: artifact.hash,
            message: `❌ Fichier hors-chaîne introuvable : ${filename}`,
        };
    }

    if (result.match) {
        return {
            status: 'VALID',
            artifactId,
            artifactType: artifact.artifactType,
            caseId,
            filename,
            storageRef,
            blockchainHash: artifact.hash,
            actualHash: result.actualHash,
            match: true,
            message: `✅ Fichier hors-chaîne INTÈGRE — hash identique au registre blockchain.`,
        };
    } else {
        return {
            status: 'CORRUPTED',
            artifactId,
            artifactType: artifact.artifactType,
            caseId,
            filename,
            storageRef,
            blockchainHash: artifact.hash,
            actualHash: result.actualHash,
            match: false,
            message: `🚨 ALERTE : fichier hors-chaîne MODIFIÉ ou CORROMPU ! Le hash ne correspond plus au registre.`,
        };
    }
}

/**
 * Liste tous les fichiers stockés hors-chaîne pour un dossier (avec leur SHA-256).
 * @param {string} caseId fabricCaseId
 */
function listStoredFiles(caseId) {
    return listCaseFiles(caseId);
}

module.exports = {
    registerFabricPackage,
    registerSingleArtifact,
    registerFromFile,
    registerAiCase,
    readArtifact,
    getArtifactsByCase,
    verifyArtifact,
    artifactExists,
    getArtifactHistory,
    // Phase 5 — Stockage off-chain
    storeAiCaseFiles,
    verifyStoredArtifact,
    listStoredFiles,
};
