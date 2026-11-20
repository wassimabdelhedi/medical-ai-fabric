# 🏥 Medical AI Fabric — Analyse Médicale Sécurisée & Traçable par IA et Hyperledger Fabric

> **Prototype de recherche académique** combinant le diagnostic cardiologique par Intelligence Artificielle (ECG 12 dérivations, dataset PTB-XL) et la traçabilité immuable par Blockchain de consortium (**Hyperledger Fabric v2.5**).

---

## 📌 Table des matières
1. [Architecture Globale](#-architecture-globale)
2. [Principe d'Intégration On-Chain / Off-Chain](#-principe-dintégration-on-chain--off-chain)
3. [Les 9 Étapes du Pipeline Médical](#-les-9-étapes-du-pipeline-médical)
4. [Arborescence du Projet](#-arborescence-du-projet)
5. [Guide de Démarrage Rapide](#-guide-de-démarrage-rapide)
6. [Documentation de l'API REST](#-documentation-de-lapi-rest)
7. [Démonstration & Audit de Sécurité](#-démonstration--audit-de-sécurité)

---

## 🏗 Architecture Globale

Le système repose sur un découpage strict garantissant **la confidentialité médicale (RGPD)** et **l'intégrité mathématique** :

```
┌─────────────────────────┐       ┌─────────────────────────┐       ┌─────────────────────────┐
│       MODULE IA         │       │     BACKEND REST        │       │   BLOCKCHAIN FABRIC     │
│   (Python / Scikit)     │       │     (Node.js / Express) │       │   (Hyperledger v2.5)    │
│                         │       │                         │       │                         │
│  - Signal ECG brut      │       │  - Passerelle gRPC TLS  │       │  - Canal "mychannel"    │
│  - Filtrage & Features  │──────►│  - Stockage Off-Chain   │──────►│  - Smart Contract       │
│  - Modèle Random Forest │       │  - Hachage SHA-256      │       │    "ArtifactContract"   │
│  - Validation & XAI     │       │  - Contrôle d'intégrité │       │  - Consensus Org1+Org2  │
└─────────────────────────┘       └─────────────────────────┘       └─────────────────────────┘
             │                                 │
             ▼                                 ▼
   [ AI/outputs/CASE00001 ]        [ BLOCKCHAIN/storage/ ]
    (Tracés & JSON bruts)           (Fichiers locaux protégés)
```

---

## 🔒 Principe d'Intégration On-Chain / Off-Chain

Pour respecter la confidentialité médicale et optimiser les performances :

* **Ce qui reste Hors-Chaîne (Off-Chain Storage) :**  
  Les données volumineuses et sensibles (signaux bruts `.csv`, rapports `.json`, tracé d'ondes `.png`, binaire du modèle `.pkl`). Elles sont stockées dans `BLOCKCHAIN/storage/{caseId}/`.
* **Ce qui est inscrit sur la Blockchain (On-Chain Ledger) :**  
  Uniquement les empreintes cryptographiques **SHA-256** (64 caractères hexadécimaux), l'identifiant pseudonymisé du patient (`FABCASE-...`), l'horodatage certifié UTC et les liens de filiation causale.

---

## 🧬 Les 9 Étapes du Pipeline Médical

Chaque exécution IA génère un graphe acyclique dirigé (DAG) de 9 artefacts inviolables :

```
[1. ECG_ORIGINAL] (Tracé brut patient)
       │
       ▼
[2. ECG_PROCESSED] (Signal filtré et standardisé)
       ├──► [3. PREPROCESSING_REPORT] (Rapport de qualité du signal)
       │
       └──► [4. FEATURES] (Extraction 12 dérivations) ──┐
                                                        ▼
[5. AI_MODEL] (Modèle Random Forest entraîné) ──► [6. AI_PREDICTION] (Sortie modèle : Normal/Anormal)
                                                        │
       ┌────────────────────────────────────────────────┴────────────────┐
       ▼                                                                 ▼
[7. AI_VALIDATION] (Règle clinique métier)                        [8. AI_EXPLANATION] (XAI / SHAP)
       │                                                                 │
       └────────────────────────────────┬────────────────────────────────┘
                                        ▼
                             [9. AI_FINAL_RESULT] (Arbitrage clinique scellé)
```

Toute tentative de modification d'un fichier en amont (ex: modifier un chiffre dans l'ECG brut) altère son empreinte SHA-256 et brise la chaîne d'intégrité jusqu'au résultat final.

---

## 📂 Arborescence du Projet

```text
medical-ai-fabric/
├── AI/                                 # Module d'Intelligence Artificielle (Python)
│   ├── pipeline/                       # Scripts de prétraitement, inférence et XAI
│   ├── outputs/CASE00001/              # Données générées et fabric_package.json
│   └── FABRIC_HANDOFF.md               # Contrat d'interface technique IA → Fabric
│
├── BLOCKCHAIN/
│   ├── chaincode/                      # Smart Contract Hyperledger Fabric
│   │   ├── lib/artifact.js             # Modèle de données & validation
│   │   └── lib/artifactContract.js     # Méthodes (Register, Read, Verify, History)
│   │
│   ├── backend/                        # API REST Node.js (Gateway Fabric)
│   │   ├── src/app.js                  # Point d'entrée du serveur Express (Port 3001)
│   │   ├── src/config/fabric.js        # Connexion gRPC TLS & certificats Org1
│   │   ├── src/routes/artifacts.js     # Routes REST d'enregistrement & consultation
│   │   ├── src/services/               # Métier (fabricService, artifactService, storageService)
│   │   └── src/middleware/             # Gestionnaire d'erreurs centralisé
│   │
│   ├── storage/                        # Stockage sécurisé hors-chaîne (Off-Chain)
│   └── tests/                          # Bancs de tests et scripts de démonstration
│       ├── test_artifact_contract.sh   # Tests CLI du Chaincode (Phase 3)
│       ├── test_phase5.sh              # Tests du stockage & falsification (Phase 5)
│       ├── test_phase6_api.sh          # Validation complète de l'API REST (Phase 6)
│       └── demo_scenario.sh            # Démonstration pas-à-pas pour soutenance (Phase 8)
│
├── SCRIPTS/                            # Scripts de déploiement et d'initialisation
└── README.md                           # Documentation générale du système
```

---

## 🚀 Guide de Démarrage Rapide

### Prérequis
* Ubuntu 22.04 / 24.04 (ou WSL2 sous Windows)
* Docker Desktop & Docker Compose
* Node.js v18+ et npm
* Python 3.10+
* Hyperledger Fabric v2.5.16 (`fabric-samples/test-network`)

### 1. Démarrer le réseau Hyperledger Fabric
```bash
cd ~/hyperledger/fabric-samples/test-network
./network.sh up createChannel -c mychannel
```

### 2. Déployer le Chaincode (ArtifactContract)
```bash
cd /mnt/d/medical-ai-fabric
./SCRIPTS/deployment/deploy_chaincode.sh
```

### 3. Lancer le Backend Blockchain
Dans un premier terminal :
```bash
cd /mnt/d/medical-ai-fabric/BLOCKCHAIN/backend
npm install
node src/app.js
```
> Le serveur écoute sur `http://localhost:3001`.

---

## 📡 Documentation de l'API REST

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | **API Explorer** : Accueil JSON documentant toutes les routes |
| `GET` | `/health` | **Sonde de santé** : Statut du serveur et du canal Fabric |
| `POST` | `/api/artifacts` | **Enregistrement unitaire** d'un artefact sur le ledger |
| `POST` | `/api/artifacts/register-ai-case` | **Ancrage complet** des 9 artefacts du dossier IA (`CASE00001`) |
| `POST` | `/api/artifacts/store-case` | **Copie off-chain** et vérification des fichiers physiques |
| `GET` | `/api/artifacts/:id` | **Lecture** des métadonnées d'un artefact depuis la blockchain |
| `GET` | `/api/artifacts/case/:caseId` | **Traçabilité** : Récupération de toute la chaîne causale |
| `GET` | `/api/artifacts/:id/exists` | **Vérification d'existence** booléenne sur le ledger |
| `GET` | `/api/artifacts/:id/verify?hash=...` | **Vérification mathématique** d'empreinte SHA-256 |
| `GET` | `/api/artifacts/:id/verify-file` | **Vérification en direct** du fichier physique sur disque |
| `GET` | `/api/artifacts/:id/history` | **Audit immuable** : Historique des blocs et transactions |
| `GET` | `/api/artifacts/storage/:caseId` | **Inventaire** des fichiers stockés hors-chaîne |

### Exemples d'appels `curl` :

```bash
# 1. Vérifier un artefact sain (Réponse : VALID - HTTP 200)
curl -s "http://localhost:3001/api/artifacts/1f1fe950-9cb8-40dc-9406-38cbff1fc513/verify-file" | jq

# 2. Consulter la chaîne causale d'un patient
curl -s "http://localhost:3001/api/artifacts/case/FABCASE-a224017d-dbf1-45eb-bb1a-978e4b2d3c59" | jq

# 3. Consulter l'historique de transaction (Audit blockchain)
curl -s "http://localhost:3001/api/artifacts/1f1fe950-9cb8-40dc-9406-38cbff1fc513/history" | jq
```

---

## 🎯 Démonstration & Audit de Sécurité

Un scénario interactif officiel a été développé pour la présentation et la soutenance :

```bash
bash /mnt/d/medical-ai-fabric/BLOCKCHAIN/tests/demo_scenario.sh
```

### Déroulement de la démonstration :
1. **Traçabilité** : Affichage des 9 étapes du diagnostic ECG et de leur filiation.
2. **Conformité** : Vérification en direct du tracé d'origine (`status: VALID`, `match: true`).
3. **Simulation d'attaque** : Injection d'une modification malveillante dans le fichier local `original_ecg.csv`.
4. **Détection de fraude** : L'API détecte immédiatement la falsification (`status: CORRUPTED`, `match: false`, Code HTTP 409).
5. **Restauration** : Retour à l'état sain certifié et validation de la preuve médico-légale (`txId`).

---

## ⚖️ Mentions Légales & Cadre Académique
Ce projet est un prototype expérimental conçu à des fins de démonstration académique et technique. Il ne constitue pas un dispositif médical de diagnostic clinique en production.
