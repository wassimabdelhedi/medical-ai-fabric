'use strict';
/**
 * storageService.js — Stockage hors-chaîne des artefacts médicaux
 * ================================================================
 * Localisation : BLOCKCHAIN/backend/src/services/storageService.js
 *
 * Rôle :
 *  1. Copier les fichiers médicaux dans BLOCKCHAIN/storage/{caseId}/
 *  2. Calculer leur SHA-256 (vérification d'intégrité)
 *  3. Retourner une storage_ref opaque (chemin relatif sécurisé)
 *
 * Les fichiers originaux restent hors-chaîne — seuls les hashes
 * et les storage_ref sont enregistrés sur Hyperledger Fabric.
 */

const fs      = require('fs');
const path    = require('path');
const crypto  = require('crypto');

// Racine du stockage hors-chaîne protégé
const STORAGE_ROOT = process.env.STORAGE_ROOT
    || path.join(__dirname, '..', '..', '..', 'storage');

/**
 * Calcule le SHA-256 d'un fichier (lecture par blocs, identique à artifact_utils.py).
 * @param {string} filePath
 * @returns {string} Hash hexadécimal 64 caractères
 */
function sha256File(filePath) {
    const hash = crypto.createHash('sha256');
    const buffer = fs.readFileSync(filePath);   // Fichiers médicaux ≤ quelques MB
    hash.update(buffer);
    return hash.digest('hex');
}

/**
 * Calcule le SHA-256 d'un Buffer ou d'un objet JSON (sérialisé de façon stable).
 * Utilisé pour les artefacts générés en mémoire.
 * @param {Buffer|object|string} data
 * @returns {string}
 */
function sha256Data(data) {
    const hash = crypto.createHash('sha256');
    if (Buffer.isBuffer(data)) {
        hash.update(data);
    } else if (typeof data === 'object') {
        hash.update(JSON.stringify(data));
    } else {
        hash.update(String(data));
    }
    return hash.digest('hex');
}

/**
 * Copie un fichier source dans le stockage hors-chaîne sous {caseId}/{filename}.
 * Crée le dossier si nécessaire.
 *
 * @param {string} srcPath    Chemin absolu du fichier source (côté IA)
 * @param {string} caseId     Identifiant pseudonymisé du dossier
 * @param {string} filename   Nom de fichier de destination
 * @returns {{ storageRef: string, sha256: string }}
 */
function storeFile(srcPath, caseId, filename) {
    const caseDir = path.join(STORAGE_ROOT, caseId);
    fs.mkdirSync(caseDir, { recursive: true });

    const destPath = path.join(caseDir, filename);
    fs.copyFileSync(srcPath, destPath);

    const fileHash = sha256File(destPath);
    // storage_ref : chemin relatif opaque depuis la racine du stockage
    const storageRef = `offchain://${caseId}/${filename}`;

    console.info(`[Storage] 📁 Stocké : ${storageRef} | sha256: ${fileHash.slice(0, 16)}...`);
    return { storageRef, sha256: fileHash };
}

/**
 * Vérifie si un fichier stocké correspond à un hash attendu.
 * Gère automatiquement la résolution si le nom de fichier est sous forme standard (original_ecg.csv)
 * ou sous forme d'URI blockchain (ECG_ORIGINAL_uuid).
 *
 * @param {string} caseId
 * @param {string} filename
 * @param {string} expectedHash
 * @param {string} [artifactType]
 * @returns {{ exists: boolean, match: boolean, actualHash: string|null, filePath?: string }}
 */
function verifyStoredFile(caseId, filename, expectedHash, artifactType) {
    let filePath = null;

    // 1. Priorité absolue au fichier médical canonique (ex: original_ecg.csv)
    if (artifactType && ARTIFACT_TYPE_TO_FILE[artifactType]) {
        const stdPath = path.join(STORAGE_ROOT, caseId, ARTIFACT_TYPE_TO_FILE[artifactType]);
        if (fs.existsSync(stdPath)) {
            filePath = stdPath;
        }
    }

    // 2. Si non résolu, chercher si le filename commence par un type connu (ex: ECG_ORIGINAL_uuid)
    if (!filePath) {
        for (const [type, stdName] of Object.entries(ARTIFACT_TYPE_TO_FILE)) {
            if (filename.startsWith(type)) {
                const stdPath = path.join(STORAGE_ROOT, caseId, stdName);
                if (fs.existsSync(stdPath)) {
                    filePath = stdPath;
                    break;
                }
            }
        }
    }

    // 3. Chemin direct tel quel
    if (!filePath) {
        const directPath = path.join(STORAGE_ROOT, caseId, filename);
        if (fs.existsSync(directPath)) {
            filePath = directPath;
        }
    }

    if (!filePath || !fs.existsSync(filePath)) {
        return { exists: false, match: false, actualHash: null };
    }

    const actualHash = sha256File(filePath);
    return {
        exists: true,
        match: actualHash.toLowerCase() === expectedHash.toLowerCase(),
        actualHash,
        filePath,
    };
}

// Répertoire des outputs IA
const AI_OUTPUTS_DIR = process.env.AI_OUTPUTS_DIR
    || path.join(__dirname, '..', '..', '..', '..', 'AI', 'outputs');

// Correspondance artifact_type → nom de fichier dans AI/outputs/{caseId}/
const ARTIFACT_TYPE_TO_FILE = {
    ECG_ORIGINAL:         'original_ecg.csv',
    ECG_PROCESSED:        'processed_ecg.csv',
    PREPROCESSING_REPORT: 'processing_report.json',
    FEATURES:             'features.json',
    AI_PREDICTION:        'prediction.json',
    AI_VALIDATION:        'validation.json',
    AI_EXPLANATION:       'explanation.json',
    AI_FINAL_RESULT:      'final_result.json',
    // AI_MODEL = binaire .pkl, pas copié dans le storage
};

/**
 * Liste tous les fichiers stockés pour un dossier médical (avec hash + taille).
 * @param {string} caseId
 * @returns {{ filename: string, sha256: string, sizeBytes: number }[]}
 */
function listCaseFiles(caseId) {
    const caseDir = path.join(STORAGE_ROOT, caseId);
    if (!fs.existsSync(caseDir)) return [];
    return fs.readdirSync(caseDir).map(filename => {
        const filePath = path.join(caseDir, filename);
        const stat     = fs.statSync(filePath);
        return { filename, sha256: sha256File(filePath), sizeBytes: stat.size };
    });
}

/**
 * Transfère tous les fichiers d'un dossier IA vers le stockage hors-chaîne
 * et vérifie que les SHA-256 calculés correspondent aux hashes du ledger Fabric.
 *
 * @param {string}   aiCaseId       ID IA local (ex: "CASE00001")
 * @param {string}   fabricCaseId   ID pseudonymisé Fabric (ex: "FABCASE-...")
 * @param {object[]} ledgerRecords  Tableau ledger_records de fabric_package.json
 * @returns {object[]} Résultats par artefact
 */
function storeCaseFiles(aiCaseId, fabricCaseId, ledgerRecords) {
    const aiCaseDir = path.join(AI_OUTPUTS_DIR, aiCaseId);
    if (!fs.existsSync(aiCaseDir)) {
        throw new Error(`Dossier IA introuvable : ${aiCaseDir}`);
    }

    const results = [];

    for (const record of ledgerRecords) {
        const filename = ARTIFACT_TYPE_TO_FILE[record.artifact_type];

        if (!filename) {
            // AI_MODEL et autres types sans fichier direct sont ignorés
            console.info(`[Storage] ⏭  ${record.artifact_type} → pas de fichier à stocker.`);
            results.push({ artifactId: record.artifact_id, artifactType: record.artifact_type, skipped: true });
            continue;
        }

        const srcPath = path.join(aiCaseDir, filename);
        if (!fs.existsSync(srcPath)) {
            console.warn(`[Storage] ⚠️  Fichier source absent : ${srcPath}`);
            results.push({ artifactId: record.artifact_id, artifactType: record.artifact_type,
                           filename, integrityMatch: false, error: `Fichier absent : ${filename}` });
            continue;
        }

        try {
            const { storageRef, sha256: computedHash } = storeFile(srcPath, fabricCaseId, filename);

            // Créer également une copie avec le nom d'URI exact (TYPE_ID) pour compatibilité
            const aliasName = `${record.artifact_type}_${record.artifact_id}`;
            const aliasPath = path.join(STORAGE_ROOT, fabricCaseId, aliasName);
            if (!fs.existsSync(aliasPath)) {
                try { fs.copyFileSync(srcPath, aliasPath); } catch (_) {}
            }

            const integrityMatch = computedHash.toLowerCase() === (record.sha256 || '').toLowerCase();

            if (integrityMatch) {
                console.info(`[Storage] ✅ Intégrité OK : ${record.artifact_type}`);
            } else {
                console.error(`[Storage] ❌ COMPROMIS : ${record.artifact_type} | attendu: ${record.sha256} | calculé: ${computedHash}`);
            }

            results.push({
                artifactId:     record.artifact_id,
                artifactType:   record.artifact_type,
                filename,
                storageRef,
                sha256:         computedHash,
                blockchainHash: record.sha256,
                integrityMatch,
                skipped:        false,
            });
        } catch (err) {
            results.push({ artifactId: record.artifact_id, artifactType: record.artifact_type, filename, error: err.message });
        }
    }

    return results;
}

module.exports = {
    sha256File, sha256Data,
    storeFile, storeCaseFiles,
    verifyStoredFile, listCaseFiles,
    STORAGE_ROOT, AI_OUTPUTS_DIR, ARTIFACT_TYPE_TO_FILE,
};
