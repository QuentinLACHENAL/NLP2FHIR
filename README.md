# Clinical NLP to FHIR Pipeline

 #### VIDEO DEMO: https://www.youtube.com/watch?v=SZrI40DlZew

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

## Design choices and limitations

The most obvious question is: why not use an NLP library like spaCy or a pre-trained biomedical model? The short answer is scope. For CS50P, the goal was to demonstrate solid Python fundamentals — clean function design, proper error handling, testable code — rather than glue a few large models together. A dictionary-based lookup is also far more transparent and auditable: when it matches "pneumonia," there's no black box involved, just a key lookup. That actually matters in a clinical context where you'd want to know exactly why something was flagged, not just trust a confidence score.

Flask was chosen over a pure command-line interface because most people who would use something like this in practice — radiologists, medical assistants — aren't going to be typing JSON into a terminal. Even a basic HTML form makes it accessible to someone who just wants to paste in a report and see what comes out. The `/api/process` endpoint also means the pipeline can be called programmatically from other tools if needed.

That said, the current approach has real limitations worth being honest about. The matching is purely lexical and has no understanding of context. If a report says "no signs of pneumonia" or "pneumonia ruled out," the pipeline will still match the term and create an active `Condition` — which is wrong. A production system would need negation detection at minimum, and probably some awareness of sentence boundaries. The `terminology.json` file is also tiny compared to a real SNOMED-CT database, which contains over 350,000 concepts. Scaling this to a real-world tool would mean replacing the local JSON with calls to a proper terminology server like HAPI FHIR. The current design makes that swap relatively straightforward — `extract_entities` just needs a different data source — but there's still a long way to go before this is production-ready.
