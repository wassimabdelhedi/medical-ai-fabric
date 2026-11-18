# Contrat de transfert IA → Hyperledger Fabric

## Ce que reçoit Fabric

Le tableau `ledger_records` de `fabric_package.json` est l'exemple de transaction proposé.
Chaque enregistrement contient :

- `schema_version`, `artifact_id`, `case_id`, `run_id` ;
- `artifact_type` ;
- `sha256`, calculé sur les octets exacts du fichier créé ;
- `created_at_utc` ;
- `parent_artifact_ids` pour reconstruire la filiation ;
- `model_name`, `model_version`, `producer` ;
- `storage_ref`, référence vers le stockage hors chaîne.

Les types générés sont `ECG_ORIGINAL`, `ECG_PROCESSED`, `PREPROCESSING_REPORT`, `FEATURES`,
`AI_MODEL`, `AI_PREDICTION`, `AI_VALIDATION`, `AI_EXPLANATION` et `AI_FINAL_RESULT`.

## Ce qui reste hors chaîne

N'envoyez pas les signaux ECG, le rapport en texte clair, le vecteur de caractéristiques,
le modèle `.pkl`, le mapping patient, ni les chemins de fichiers locaux. Les champs
`application_result_payloads_offchain` sont un exemple pour l'application consommatrice ;
ils ne sont pas destinés au ledger. Le ledger reçoit les empreintes et la provenance.

Le `case_id` exporté est un UUID de démonstration opaque et ne contient pas le `CASE00001`
local. Les IDs d'artefacts et de traitement sont uniques par exécution.

## Stockage hors chaîne et intégration restante

Dans cette version, `storage_ref` est `null` et `storage_state` vaut
`LOCAL_ONLY_REFERENCE_NOT_CONFIGURED`. Le package est donc un exemple réel de structure et
d'empreintes, mais **pas encore une transaction prête à soumettre en production**. Avant
l'appel au chaincode, l'application doit déposer les artefacts protégés dans le stockage
hors chaîne, renseigner une référence opaque accessible au service autorisé, puis soumettre
uniquement `ledger_records`. Aucun appel Fabric n'est encore implémenté dans ce module.

Le hachage porte sur les octets exacts sauvegardés. Pour vérifier un artefact, recalculer
SHA-256 sur ces mêmes octets et comparer au champ `sha256`. Ne re-sérialisez pas le JSON
avant comparaison. Le hash du modèle identifie le binaire déployé ; le hash du rapport de
prétraitement permet de vérifier le fichier complet sans en exposer le texte au ledger.

## Règles de validation actuelles

- `ACCEPTED` : artefacts requis présents et cohérents, qualité correcte, confiance ≥ 0,80,
  et classe prédite cohérente avec les codes diagnostiques structurés PTB-XL.
- `REVIEW_REQUIRED` : confiance sous le seuil, valeur interpolée, ou rapport manquant/non
  interprétable/désaccordant. Le texte libre n'est pas interprété automatiquement.
- `REJECTED` : artefact requis manquant/invalide, données ECG gravement invalides, modèle
  incompatible, ou provenance de traitement incohérente.

Ces statuts expriment uniquement le résultat des contrôles techniques du prototype. Ils ne
valident pas un diagnostic ni la sécurité clinique du modèle. Le seuil de 0,80 est une règle
opérationnelle de démonstration, pas une valeur médicale validée.

## Générer l'exemple

Depuis la racine du projet :

```powershell
python -X utf8 -m AI.pipeline.run_ai_pipeline --case_id CASE00001
```

Le paquet est écrit dans `AI/outputs/CASE00001/fabric_package.json`.
