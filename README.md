# Clinical NLP to FHIR Pipeline

## Overview
This project is a clinical text processing pipeline written in Python. It takes unstructured medical text (radiology reports, doctor's notes, etc.), pulls out the relevant clinical and anatomical terms, and converts them into a valid **HL7 FHIR R4** JSON structure.

Built as the final project for Harvard's CS50P course.

## What it does
The pipeline runs in three steps:
1. **`clean_text`** — Normalizes the raw input: strips accents, removes punctuation, collapses whitespace, lowercases everything.
2. **`extract_entities`** — Scans the cleaned text against a local terminology file (`terminology.json`) that mimics SNOMED-CT/LOINC codes. Returns a list of matched clinical entities.
3. **`serialize_to_fhir`** — Packages the entities into a `DiagnosticReport` resource, with each finding wrapped as a `Condition` or `Observation`.

## Prerequisites & Installation

1. Python 3.8+ required.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the app

```bash
python project.py
```

Then open `http://localhost:5000` in your browser. The interface lets you paste any clinical text, enter a patient ID, and get the FHIR JSON back immediately.

**API endpoint:**
- `GET /` — serves the UI
- `POST /api/process` — accepts `{"text": "...", "patient_id": "..."}`, returns the FHIR document

### GDPR / RGPD compliance

The whole pipeline is stateless and runs locally:
- No data is written to disk — text is processed in memory and discarded.
- No external API calls — entity matching uses only the local `terminology.json` file, so no patient data ever leaves the machine.

### Running the tests

```bash
pytest test_project.py
```

The test suite covers: text normalization, edge cases (empty input, special chars only, `None`), entity deduplication, missing terminology keys, and FHIR schema validation.

## Architecture notes

- **Exception hierarchy**: `PipelineError` is the base, with three subclasses (`DataIngestionError`, `ExtractionError`, `FHIRSerializationError`) so errors can be caught at the right level.
- **Type hints**: all functions are typed with `Dict`, `List`, `Any` from the `typing` module.
- **Stateless functions**: no global state mutations — data flows straight through: `Raw text` → `Cleaned text` → `Entity list` → `FHIR JSON`.
- **`terminology.json`**: a small mock database that stands in for a real SNOMED-CT/LOINC server, keeping the project self-contained.
