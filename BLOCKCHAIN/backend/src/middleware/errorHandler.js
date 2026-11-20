'use strict';
/**
 * errorHandler.js — Middleware de gestion centralisée des erreurs
 * ===============================================================
 * Localisation : BLOCKCHAIN/backend/src/middleware/errorHandler.js
 */

function errorHandler(err, req, res, next) {
    let fullMsg = err.message || '';
    if (err.details && Array.isArray(err.details)) {
        fullMsg += ' ' + err.details.map(d => d.message || JSON.stringify(d)).join(' ');
    }
    console.error(`[ERROR] ${req.method} ${req.path} →`, fullMsg);

    // Erreurs Fabric spécifiques
    if (fullMsg.includes('existe déjà')) {
        return res.status(409).json({ error: 'Artefact déjà enregistré (immuabilité blockchain).', detail: fullMsg });
    }
    if (fullMsg.includes('introuvable')) {
        return res.status(404).json({ error: 'Artefact introuvable sur le ledger.', detail: fullMsg });
    }
    if (fullMsg.includes('hash') || fullMsg.includes('Hash')) {
        return res.status(400).json({ error: 'Hash SHA-256 invalide.', detail: fullMsg });
    }

    // Erreur générique
    res.status(500).json({
        error: 'Erreur interne du serveur Fabric.',
        detail: fullMsg || err.message,
    });
}

module.exports = errorHandler;
