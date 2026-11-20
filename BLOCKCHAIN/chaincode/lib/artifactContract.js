'use strict';

const { Contract } = require('fabric-contract-api');
const { Artifact, ARTIFACT_TYPES, INTEGRITY_STATUS } = require('./artifact');

/**
 * ArtifactContract — Smart Contract Hyperledger Fabric
 * ======================================================
 * Gère l'enregistrement, la consultation et la vérification
 * d'intégrité des artefacts du pipeline d'analyse médicale IA.
 *
 * Fonctions exposées sur le canal mychannel :
 *   - RegisterArtifact    : Enregistrer un nouvel artefact
 *   - ReadArtifact        : Lire un artefact par son ID
 *   - GetArtifactsByCase  : Obtenir tous les artefacts d'un dossier
 *   - VerifyArtifact      : Vérifier l'intégrité par comparaison de hash
 */
class ArtifactContract extends Contract {

    constructor() {
        // Nom du namespace du contrat sur le channel
        super('ArtifactContract');
    }

    // ==============================================================
    // Méthode d'initialisation du ledger (appelée au déploiement)
    // ==============================================================

    /**
     * InitLedger — Initialise le ledger avec un artefact de démonstration.
     * Appelée automatiquement lors du premier déploiement pour valider
     * que le chaincode est opérationnel sur le channel.
     *
     * @param {Context} ctx - Contexte de la transaction Fabric
     */
    async InitLedger(ctx) {
        console.info('===== Initialisation du Ledger ArtifactContract =====');

        const demoArtifact = new Artifact(
            'DEMO001',
            'CASE000',
            ARTIFACT_TYPES.ORIGINAL_DATA,
            'a'.repeat(64),                // Hash de démonstration (64 chars hex)
            null,
            'storage/demo/CASE000/original_ecg.csv',
            '1.0',
            'system',
            new Date().toISOString()
        );

        await ctx.stub.putState(demoArtifact.artifactId, demoArtifact.toBuffer());
        console.info(`Artefact de démonstration enregistré : ${demoArtifact.artifactId}`);
    }

    // ==============================================================
    // 1. RegisterArtifact — Enregistrer un nouvel artefact
    // ==============================================================

    /**
     * Enregistre un nouvel artefact médical sur la blockchain.
     *
     * Workflow :
     *  1. Désérialise le payload JSON fourni par l'agent orchestrateur
     *  2. Valide que l'artifactId n'existe pas déjà sur le ledger (idempotence)
     *  3. Crée l'objet Artifact (validation du hash SHA-256 et du type)
     *  4. Écrit l'artefact sérialisé sur l'état du ledger (putState)
     *  5. Émet un événement blockchain notifiant les listeners (backend, agents)
     *
     * @param {Context} ctx         - Contexte de la transaction Fabric
     * @param {string}  artifactJson - JSON stringifié contenant les champs de l'Artifact
     * @returns {string} JSON de l'artefact créé
     * @throws {Error} Si l'artefact existe déjà ou si les données sont invalides
     */
    async RegisterArtifact(ctx, artifactJson) {
        console.info('===== RegisterArtifact =====');

        // --- Désérialisation du payload ---
        let data;
        try {
            data = JSON.parse(artifactJson);
        } catch (err) {
            throw new Error(`Payload JSON invalide : ${err.message}`);
        }

        const {
            artifactId, caseId, artifactType, hash,
            parentArtifactId, storageRef, modelVersion, creator, timestamp
        } = data;

        // --- Vérification de l'idempotence (l'artefact ne doit pas déjà exister) ---
        const existing = await ctx.stub.getState(artifactId);
        if (existing && existing.length > 0) {
            throw new Error(
                `Artefact "${artifactId}" existe déjà sur le ledger. ` +
                `Un artefact ne peut pas être modifié une fois enregistré (immuabilité).`
            );
        }

        // --- Création et validation via le constructeur Artifact ---
        // Le constructeur lance une erreur si le hash ou le type sont invalides
        const artifact = new Artifact(
            artifactId,
            caseId,
            artifactType,
            hash,
            parentArtifactId,
            storageRef,
            modelVersion,
            creator || ctx.clientIdentity.getID(),
            timestamp || new Date().toISOString()
        );

        // --- Écriture sur le ledger Fabric ---
        await ctx.stub.putState(artifact.artifactId, artifact.toBuffer());
        console.info(`✅ Artefact enregistré : ${artifact.artifactId} (Type: ${artifact.artifactType}, Cas: ${artifact.caseId})`);

        // --- Émission d'un événement blockchain pour le backend Node.js ---
        const eventPayload = Buffer.from(JSON.stringify({
            event: 'ArtifactRegistered',
            artifactId: artifact.artifactId,
            caseId: artifact.caseId,
            artifactType: artifact.artifactType,
            timestamp: artifact.timestamp,
        }));
        ctx.stub.setEvent('ArtifactRegistered', eventPayload);

        return JSON.stringify(artifact);
    }

    // ==============================================================
    // 2. ReadArtifact — Lire un artefact par son ID
    // ==============================================================

    /**
     * Récupère un artefact depuis le ledger par son identifiant unique.
     *
     * @param {Context} ctx        - Contexte de la transaction Fabric
     * @param {string}  artifactId - Identifiant de l'artefact à lire
     * @returns {string} JSON de l'artefact trouvé
     * @throws {Error} Si l'artefact n'existe pas
     */
    async ReadArtifact(ctx, artifactId) {
        console.info(`===== ReadArtifact : ${artifactId} =====`);

        const buffer = await ctx.stub.getState(artifactId);

        if (!buffer || buffer.length === 0) {
            throw new Error(
                `Artefact "${artifactId}" introuvable sur le ledger. ` +
                `Vérifiez l'identifiant ou si l'artefact a bien été enregistré.`
            );
        }

        const artifact = JSON.parse(buffer.toString('utf8'));
        console.info(`📋 Artefact lu : ${artifactId}`);
        return JSON.stringify(artifact);
    }

    // ==============================================================
    // 3. GetArtifactsByCase — Historique complet d'un dossier médical
    // ==============================================================

    /**
     * Récupère tous les artefacts appartenant à un dossier médical donné.
     * Permet à l'interface utilisateur et aux agents de reconstituer
     * la chaîne causale complète de traitement.
     *
     * Stratégie de requête :
     *   - Utilise une plage de clés composites {caseId}\x00{artifactId}
     *   - Compatible LevelDB (défaut du test-network) ET CouchDB
     *   - Les artefacts sont retournés dans l'ordre lexicographique des IDs
     *
     * @param {Context} ctx    - Contexte de la transaction Fabric
     * @param {string}  caseId - Identifiant pseudonymisé du dossier patient
     * @returns {string} JSON array de tous les artefacts du dossier
     */
    async GetArtifactsByCase(ctx, caseId) {
        console.info(`===== GetArtifactsByCase : ${caseId} =====`);

        // Itérateur sur toutes les clés du ledger pour filtrer par caseId
        // GetStateByRange avec startKey="" et endKey="" parcourt tout le ledger
        const iterator = await ctx.stub.getStateByRange('', '');

        const results = [];

        // Itération sur tous les artefacts et filtrage par caseId
        let result = await iterator.next();
        while (!result.done) {
            const strValue = Buffer.from(result.value.value.toString()).toString('utf8');
            let artifact;
            try {
                artifact = JSON.parse(strValue);
            } catch (_err) {
                console.error(`Impossible de parser l'artefact : ${strValue}`);
                result = await iterator.next();
                continue;
            }

            // Filtrage : ne retenir que les artefacts du dossier demandé
            if (artifact.caseId === caseId) {
                results.push(artifact);
            }

            result = await iterator.next();
        }

        // Fermeture obligatoire de l'itérateur Fabric
        await iterator.close();

        // Tri par timestamp pour reconstruire la chronologie du pipeline
        results.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        console.info(`📁 Dossier ${caseId} : ${results.length} artefact(s) trouvé(s)`);
        return JSON.stringify(results);
    }

    // ==============================================================
    // 4. VerifyArtifact — Vérification d'intégrité par hash SHA-256
    // ==============================================================

    /**
     * Vérifie l'intégrité d'un artefact en comparant l'empreinte SHA-256
     * enregistrée sur la blockchain avec un hash recalculé hors-chaîne.
     *
     * Principe de détection de falsification (Section 4.5 du cahier des charges) :
     *   Si hash_recalculé == hash_blockchain  → le fichier n'a pas été modifié (VALID)
     *   Si hash_recalculé != hash_blockchain  → le fichier a été altéré (CORRUPTED)
     *
     * @param {Context} ctx          - Contexte de la transaction Fabric
     * @param {string}  artifactId   - ID de l'artefact à vérifier
     * @param {string}  providedHash - Hash SHA-256 recalculé sur le fichier hors-chaîne
     * @returns {string} JSON contenant le statut, le hash enregistré et le hash fourni
     */
    async VerifyArtifact(ctx, artifactId, providedHash) {
        console.info(`===== VerifyArtifact : ${artifactId} =====`);

        // --- Validation du format du hash fourni ---
        if (!providedHash || !/^[a-fA-F0-9]{64}$/.test(providedHash)) {
            throw new Error(
                `Hash fourni invalide : "${providedHash}". ` +
                `Un hash SHA-256 doit comporter exactement 64 caractères hexadécimaux.`
            );
        }

        // --- Lecture de l'artefact sur le ledger ---
        const buffer = await ctx.stub.getState(artifactId);

        if (!buffer || buffer.length === 0) {
            // Artefact introuvable sur la blockchain
            const response = {
                artifactId,
                status:         INTEGRITY_STATUS.NOT_FOUND,
                registeredHash: null,
                providedHash,
                message:        `Aucun artefact avec l'identifiant "${artifactId}" n'existe sur le ledger.`,
                verifiedAt:     new Date().toISOString(),
            };
            console.warn(`⚠️  Artefact introuvable : ${artifactId}`);
            return JSON.stringify(response);
        }

        const artifact = JSON.parse(buffer.toString('utf8'));
        const registeredHash = artifact.hash;

        // --- Comparaison des empreintes ---
        const isIntact = (registeredHash.toLowerCase() === providedHash.toLowerCase());

        const response = {
            artifactId,
            caseId:         artifact.caseId,
            artifactType:   artifact.artifactType,
            status:         isIntact ? INTEGRITY_STATUS.VALID : INTEGRITY_STATUS.CORRUPTED,
            registeredHash,
            providedHash,
            match:          isIntact,
            verifiedAt:     new Date().toISOString(),
            message:        isIntact
                ? `✅ Artefact "${artifactId}" VALIDE — le fichier correspond à l'enregistrement blockchain.`
                : `❌ Artefact "${artifactId}" CORROMPU — le fichier a été modifié après son enregistrement.`,
        };

        if (isIntact) {
            console.info(`✅ Intégrité vérifiée OK : ${artifactId}`);
        } else {
            console.warn(`❌ Altération détectée ! Artefact : ${artifactId}`);
            console.warn(`   Hash enregistré : ${registeredHash}`);
            console.warn(`   Hash fourni     : ${providedHash}`);
        }

        return JSON.stringify(response);
    }

    // ==============================================================
    // 5. ArtifactExists — Vérification d'existence (méthode utilitaire)
    // ==============================================================

    /**
     * Vérifie si un artefact existe sur le ledger sans le lire complètement.
     * Utilisé par RegisterArtifact et directement interrogeable depuis le backend.
     *
     * @param {Context} ctx        - Contexte de la transaction Fabric
     * @param {string}  artifactId - Identifiant à vérifier
     * @returns {boolean}
     */
    async ArtifactExists(ctx, artifactId) {
        const buffer = await ctx.stub.getState(artifactId);
        return !!(buffer && buffer.length > 0);
    }

    // ==============================================================
    // 6. GetArtifactHistory — Historique des versions sur le ledger
    // ==============================================================

    /**
     * Retourne l'historique complet des transactions pour un artefact donné.
     * Chaque entrée inclut le numéro de transaction, le timestamp et l'état.
     * Utile pour l'audit et la démonstration de l'immuabilité de la blockchain.
     *
     * @param {Context} ctx        - Contexte de la transaction Fabric
     * @param {string}  artifactId - Identifiant de l'artefact
     * @returns {string} JSON array de l'historique des transactions
     */
    async GetArtifactHistory(ctx, artifactId) {
        console.info(`===== GetArtifactHistory : ${artifactId} =====`);

        const iterator = await ctx.stub.getHistoryForKey(artifactId);
        const history = [];

        let result = await iterator.next();
        while (!result.done) {
            const record = {
                txId:      result.value.txId,
                timestamp: result.value.timestamp,
                isDelete:  result.value.isDelete,
                data:      result.value.value
                    ? JSON.parse(result.value.value.toString('utf8'))
                    : null,
            };
            history.push(record);
            result = await iterator.next();
        }

        await iterator.close();
        console.info(`📜 Historique de ${artifactId} : ${history.length} transaction(s)`);
        return JSON.stringify(history);
    }
}

module.exports = { ArtifactContract };
