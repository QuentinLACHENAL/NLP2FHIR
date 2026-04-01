# Pipeline NLP clinique vers FHIR

#### Démo vidéo : https://www.youtube.com/watch?v=SZrI40DlZew

## Vue d'ensemble
Ce projet est un pipeline de traitement de texte médical écrit en Python. Il prend du texte clinique non structuré (comptes-rendus de radiologie, notes de médecin, etc.), en extrait les termes cliniques et anatomiques pertinents, puis les convertit en une structure JSON **HL7 FHIR R4** valide.

Développé comme projet final du cours CS50P de Harvard.

## Fonctionnement
Le pipeline s'exécute en trois étapes :
1. **`clean_text`** — Normalise le texte brut : supprime les accents, retire la ponctuation, réduit les espaces, met tout en minuscules.
2. **`extract_entities`** — Parcourt le texte nettoyé à la recherche de correspondances dans un fichier de terminologie local (`terminology.json`) qui simule des codes SNOMED-CT/LOINC. Retourne la liste des entités cliniques trouvées.
3. **`serialize_to_fhir`** — Assemble les entités dans une ressource `DiagnosticReport`, chaque résultat étant encapsulé en `Condition` ou `Observation`.

## Prérequis et installation

1. Python 3.8+ requis.
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

## Lancer l'application

```bash
python project.py
```

Ouvrez ensuite `http://localhost:5000` dans votre navigateur. L'interface permet de coller n'importe quel texte clinique, de renseigner un identifiant patient, et d'obtenir immédiatement le JSON FHIR correspondant.

**Endpoints API :**
- `GET /` — sert l'interface utilisateur
- `POST /api/process` — accepte `{"text": "...", "patient_id": "..."}`, retourne le document FHIR

### Conformité RGPD

Le pipeline est entièrement sans état et tourne en local :
- Aucune donnée n'est écrite sur le disque — le texte est traité en mémoire puis supprimé.
- Aucun appel API externe — la correspondance des entités repose uniquement sur le fichier local `terminology.json`, donc aucune donnée patient ne quitte la machine.

### Lancer les tests

```bash
pytest test_project.py
```

La suite de tests couvre : la normalisation du texte, les cas limites (entrée vide, caractères spéciaux uniquement, `None`), la déduplication des entités, les clés de terminologie manquantes, et la validation du schéma FHIR.

## Notes d'architecture

- **Hiérarchie d'exceptions** : `PipelineError` est la classe de base, avec trois sous-classes (`DataIngestionError`, `ExtractionError`, `FHIRSerializationError`) pour capturer les erreurs au bon niveau.
- **Typage** : toutes les fonctions sont typées avec `Dict`, `List`, `Any` du module `typing`.
- **Fonctions sans état** : aucune mutation d'état global — les données traversent le pipeline sans détour : `Texte brut` → `Texte nettoyé` → `Liste d'entités` → `JSON FHIR`.
- **`terminology.json`** : une petite base de données fictive qui remplace un vrai serveur SNOMED-CT/LOINC, pour garder le projet autonome.

## Choix de conception et limites

La question la plus évidente est : pourquoi ne pas utiliser une bibliothèque NLP comme spaCy ou un modèle biomédical pré-entraîné ? La réponse courte, c'est la portée du projet. Pour CS50P, l'objectif était de démontrer des bases solides en Python — conception propre des fonctions, gestion correcte des erreurs, code testable — plutôt que d'assembler quelques modèles lourds. Un lookup par dictionnaire est aussi bien plus transparent et vérifiable : quand le pipeline trouve « pneumonia », il n'y a aucune boîte noire impliquée, juste une correspondance de clé. C'est important dans un contexte clinique où l'on veut savoir exactement pourquoi un terme a été identifié, plutôt que de faire confiance à un score de confiance.

Flask a été préféré à un simple outil en ligne de commande parce que la plupart des personnes qui utiliseraient un tel outil au quotidien — radiologues, assistants médicaux — ne vont pas taper du JSON dans un terminal. Même un formulaire HTML basique rend l'outil accessible à quelqu'un qui veut juste coller un compte-rendu et voir ce qui en sort. L'endpoint `/api/process` permet aussi d'appeler le pipeline de manière programmatique depuis d'autres outils si besoin.

Cela dit, l'approche actuelle a de vraies limites qu'il vaut mieux reconnaître honnêtement. La correspondance est purement lexicale et n'a aucune compréhension du contexte. Si un compte-rendu dit « pas de signe de pneumonie » ou « pneumonie écartée », le pipeline détectera quand même le terme et créera une `Condition` active — ce qui est incorrect. Un système en production aurait besoin au minimum d'une détection de la négation, et probablement d'une prise en compte des limites de phrases. Le fichier `terminology.json` est également minuscule comparé à une vraie base SNOMED-CT, qui contient plus de 350 000 concepts. Passer à l'échelle nécessiterait de remplacer le JSON local par des appels à un serveur de terminologie comme HAPI FHIR. La conception actuelle rend ce remplacement relativement simple — `extract_entities` aurait juste besoin d'une source de données différente — mais il reste encore loin d'un outil prêt pour la production.
