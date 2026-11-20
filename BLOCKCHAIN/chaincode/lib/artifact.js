'use strict';

/**
 * Modèle de données — Artefact Médical
 * ======================================
 * Représente un artefact traçable enregistré sur Hyperledger Fabric.
 * Chaque étape du pipeline IA produit un artefact référençant l'étape parente.
 *
 * Séquence de traçabilité :
 *  ORIGINAL_DATA → PROCESSED_DATA → FEATURES → AI_PREDICTION → VALIDATION → EXPLANATION → FINAL_RESULT
 */

/** Types d'artefacts valides — couvre les deux nomenclatures (chaincode + pipeline IA) */
const ARTIFACT_TYPES = Object.freeze({
    // --- Types génériques (cahier des charges Section 5) ---
    ORIGINAL_DATA:        'ORIGINAL_DATA',
    PROCESSED_DATA:       'PROCESSED_DATA',
    FEATURES:             'FEATURES',
    AI_PREDICTION:        'AI_PREDICTION',
    VALIDATION:           'VALIDATION',
    EXPLANATION:          'EXPLANATION',
    FINAL_RESULT:         'FINAL_RESULT',
    // --- Types natifs du pipeline IA (fabric_package.json) ---
    ECG_ORIGINAL:         'ECG_ORIGINAL',
    ECG_PROCESSED:        'ECG_PROCESSED',
    PREPROCESSING_REPORT: 'PREPROCESSING_REPORT',
    AI_MODEL:             'AI_MODEL',
    AI_VALIDATION:        'AI_VALIDATION',
    AI_EXPLANATION:       'AI_EXPLANATION',
    AI_FINAL_RESULT:      'AI_FINAL_RESULT',
});

/** Statuts de validation possibles (Section 4.4) */
const VALIDATION_STATUS = Object.freeze({
    ACCEPTED:         'ACCEPTED',         // Satisfait tous les contrôles
    REVIEW_REQUIRED:  'REVIEW_REQUIRED',  // Confiance ou qualité insuffisante
    REJECTED:         'REJECTED',         // Pipeline incomplet ou problème d'intégrité
});

/** Statuts d'intégrité retournés par VerifyArtifact */
const INTEGRITY_STATUS = Object.freeze({
    VALID:            'VALID',      // Hash recalculé == Hash enregistré
    CORRUPTED:        'CORRUPTED',  // Hash recalculé != Hash enregistré
    NOT_FOUND:        'NOT_FOUND',  // Aucun artefact trouvé avec cet ID
});

/**
 * Classe Artifact — Structure complète d'un artefact médical blockchain
 */
class Artifact {

    /**
     * @param {string} artifactId       - Clé primaire unique sur le ledger (ex: "PRED001")
     * @param {string} caseId           - Identifiant pseudonymisé du dossier patient (ex: "CASE001")
     * @param {string} artifactType     - Type de l'étape (voir ARTIFACT_TYPES)
     * @param {string} hash             - Empreinte SHA-256 du fichier hors-chaîne
     * @param {string} parentArtifactId - ID de l'artefact amont (null pour ORIGINAL_DATA)
     * @param {string} storageRef       - Chemin ou URI du fichier protégé hors-chaîne
     * @param {string} modelVersion     - Version du modèle IA ou du script utilisé
     * @param {string} creator          - Identité du composant ayant soumis la transaction
     * @param {string} timestamp        - Horodatage ISO 8601 de la création
     */
    constructor(
        artifactId,
        caseId,
        artifactType,
        hash,
        parentArtifactId,
        storageRef,
        modelVersion,
        creator,
        timestamp
    ) {
        // ---- Validation des champs obligatoires ----
        if (!artifactId || typeof artifactId !== 'string') {
            throw new Error('artifactId est requis et doit être une chaîne de caractères.');
        }
        if (!caseId || typeof caseId !== 'string') {
            throw new Error('caseId est requis et doit être une chaîne de caractères.');
        }
        if (!Object.values(ARTIFACT_TYPES).includes(artifactType)) {
            throw new Error(`artifactType invalide : "${artifactType}". Valeurs acceptées : ${Object.values(ARTIFACT_TYPES).join(', ')}`);
        }
        if (!hash || !/^[a-fA-F0-9]{64}$/.test(hash)) {
            throw new Error('hash doit être une empreinte SHA-256 valide (64 caractères hexadécimaux).');
        }
        if (!creator || typeof creator !== 'string') {
            throw new Error('creator est requis.');
        }

        // ---- Affectation des champs ----
        this.artifactId       = artifactId;
        this.caseId           = caseId;
        this.artifactType     = artifactType;
        this.hash             = hash;
        this.parentArtifactId = parentArtifactId || null;
        this.storageRef       = storageRef || '';
        this.modelVersion     = modelVersion || '1.0';
        this.creator          = creator;
        this.timestamp        = timestamp || new Date().toISOString();

        // Champ de type interne pour Fabric (docType facilite les requêtes CouchDB)
        this.docType = 'artifact';
    }

    // ----------------------------------------------------------------
    // Méthodes de sérialisation / désérialisation pour le ledger Fabric
    // ----------------------------------------------------------------

    /**
     * Convertit l'objet en Buffer pour l'écriture sur le ledger.
     * @returns {Buffer}
     */
    toBuffer() {
        return Buffer.from(JSON.stringify(this));
    }

    /**
     * Désérialise un Buffer lu depuis le ledger en instance Artifact.
     * @param {Buffer} buffer
     * @returns {Artifact}
     */
    static deserialize(buffer) {
        const data = JSON.parse(buffer.toString('utf8'));
        return new Artifact(
            data.artifactId,
            data.caseId,
            data.artifactType,
            data.hash,
            data.parentArtifactId,
            data.storageRef,
            data.modelVersion,
            data.creator,
            data.timestamp
        );
    }
}

module.exports = { Artifact, ARTIFACT_TYPES, VALIDATION_STATUS, INTEGRITY_STATUS };
