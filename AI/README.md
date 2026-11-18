# Pipeline IA ECG — PTB-XL

Prototype pédagogique de classification binaire d’ECG 12 dérivations. Il ne fournit pas un diagnostic médical.

## Installation et exécution

Depuis la racine du projet, avec l’environnement Python activé :

```powershell
python -m pip install -r IA/requirements.txt
python -X utf8 IA/src/pseudonymization.py
python -X utf8 IA/src/train_test_split.py
python -X utf8 IA/src/train_model.py
```

Les données PTB-XL doivent être dans `IA/dataset`, avec `ptbxl_database.csv`, `scp_statements.csv` et `records500/`.
L’entraînement utilise les folds PTB-XL : 1–8 pour l’entraînement, 9 pour la validation et 10 pour le test.
Les fichiers `train_set.csv`, `validation_set.csv` et `test_set.csv` sont générés à partir de ces folds.

Pour traiter puis prédire un cas :

```powershell
python -X utf8 IA/src/preprocessing.py --case_id CASE00001
python -X utf8 IA/src/feature_extraction.py --case_id CASE00001
python -X utf8 IA/src/prediction.py --case_id CASE00001
```

Pour générer tout le flux, y compris validation, explication, résultat final et manifeste Fabric :

```powershell
python -X utf8 IA/src/run_ai_pipeline.py --case_id CASE00001
```

Le flux produit `validation.json`, `explanation.json`, `final_result.json` et `fabric_package.json`
dans `IA/outputs/<case_id>`. Seuil de confiance initial : 0,80. Une confiance plus faible, une
qualité nécessitant correction ou une incohérence avec les codes diagnostiques PTB-XL entraîne
`REVIEW_REQUIRED`. Une pièce obligatoire absente/invalide entraîne `REJECTED`. `ACCEPTED` signifie
uniquement que les contrôles techniques configurés passent.

Le paquet Fabric contient des empreintes SHA-256, des liens parent-enfant et des payloads de
résultat expurgés. Les signaux, les caractéristiques, le texte du rapport et le modèle restent
hors chaîne. Dans ce prototype, `storage_ref` reste `null` : il faut le remplacer par une référence
réelle quand le stockage hors chaîne sera configuré. Aucun contrat Fabric n'est invoqué ici.

## Règle des classes

Les codes de `scp_codes` sont comparés aux codes diagnostiques de `scp_statements.csv`.
Un ECG est `Normal` si `NORM` est le seul code diagnostique positif, `Abnormal` s’il existe
un autre code diagnostique positif, et `Unknown` s’il n’existe aucun code diagnostique positif.
Les `Unknown` ne participent pas à l’apprentissage ni aux métriques.

## Prétraitement et modèle

Le pipeline lit les ECG haute résolution à 500 Hz, exige 12 dérivations et 5 000 échantillons,
interpole les valeurs non finies si elles touchent au plus 0,5 % d’une dérivation et rejette
l’enregistrement au-delà de cette limite ou si une dérivation est plate. Il applique le filtre
Butterworth 0,5–40 Hz puis un z-score par dérivation. Les 108 caractéristiques sont des quantiles,
asymétrie, kurtosis et RMS des différences successives (9 par dérivation).

Le modèle, ses versions logicielles, sa règle d’étiquetage et les métriques de validation/test
sont enregistrés dans `IA/models/model_metadata.json`. Les probabilités Random Forest ne sont pas
calibrées cliniquement. Le fichier `IA/dataset/id_mapping_SECURE.json` est confidentiel et exclu de Git.
