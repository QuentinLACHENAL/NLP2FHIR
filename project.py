import json
import logging
import os
import re
import unidecode
from typing import Any, Dict, List
from flask import Flask, request, jsonify, render_template

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 KB max per request

class PipelineError(Exception):
    """Base class for pipeline-specific errors."""
    pass

class DataIngestionError(PipelineError):
    """Raised when the input text can't be cleaned (empty, wrong type, etc.)."""
    pass

class ExtractionError(PipelineError):
    """Raised when entity extraction hits a problem with the terminology dict."""
    pass

class FHIRSerializationError(PipelineError):
    """Raised when building the FHIR output fails (bad patient ID, missing fields)."""
    pass

def clean_text(text: str) -> str:
    """
    Normalizes raw clinical text: strips accents, removes special chars,
    collapses whitespace, and lowercases everything.
    Raises DataIngestionError if input is empty or not a string.
    """
    if not isinstance(text, str) or not text.strip():
        raise DataIngestionError("Input text must be a non-empty string.")

    # Strip accents so "fémur" and "femur" both match
    text = unidecode.unidecode(text)

    # Keep only letters, digits and spaces
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()

    if not cleaned:
        raise DataIngestionError("Text became empty after cleaning.")

    return cleaned

def extract_entities(cleaned_text: str, terminology: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Scans the cleaned text for known clinical terms and returns the matching
    SNOMED/LOINC entries. Duplicate codes are skipped.
    Raises ExtractionError if the terminology dict is empty or malformed.
    """
    if not terminology or not isinstance(terminology, dict):
        raise ExtractionError("Terminology dictionary cannot be empty or invalid.")

    extracted_entities = []
    seen_codes = set()

    for term, code_info in terminology.items():
        if term.lower() in cleaned_text:
            try:
                code = code_info["code"]
                if code not in seen_codes:
                    entity = {
                        "system": code_info["system"],
                        "code": code,
                        "display": code_info["display"],
                        "type": code_info.get("type", "pathology")
                    }
                    extracted_entities.append(entity)
                    seen_codes.add(code)
            except KeyError as e:
                raise ExtractionError(f"Terminology missing required key: {e}")

    return extracted_entities

def serialize_to_fhir(patient_id: str, entities: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Builds a FHIR R4 DiagnosticReport from the extracted entities.
    Pathology entities become Condition resources; anatomy is attached as
    bodySite on the last condition, or as a standalone Observation otherwise.
    Raises FHIRSerializationError if the patient ID is blank or an entity is missing fields.
    """
    if not patient_id or not patient_id.strip():
        raise FHIRSerializationError("Patient ID is required for FHIR serialization.")

    report: Dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11528-7",
                "display": "Radiology or other imaging report"
            }]
        },
        "subject": {
            "reference": f"Patient/{patient_id}"
        },
        "contained": []
    }

    if not entities:
        return report

    report["result"] = []

    last_condition = None

    for i, entity in enumerate(entities, start=1):
        if not all(key in entity for key in ["system", "code", "display", "type"]):
            raise FHIRSerializationError(f"Entity at index {i-1} is missing required FHIR coding fields.")

        ent_type = entity["type"]
        resource_id = f"res-{i}"

        if ent_type == "pathology":
            condition: Dict[str, Any] = {
                "resourceType": "Condition",
                "id": resource_id,
                "clinicalStatus": {
                    "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
                },
                "code": {
                    "coding": [{
                        "system": entity["system"],
                        "code": entity["code"],
                        "display": entity["display"]
                    }]
                },
                "subject": {
                    "reference": f"Patient/{patient_id}"
                }
            }
            report["contained"].append(condition) # type: ignore
            report["result"].append({"reference": f"#{resource_id}"}) # type: ignore
            last_condition = condition

        elif ent_type == "anatomy":
            if last_condition is not None:
                if "bodySite" not in last_condition:
                    last_condition["bodySite"] = []
                last_condition["bodySite"].append({
                    "coding": [{
                        "system": entity["system"],
                        "code": entity["code"],
                        "display": entity["display"]
                    }]
                })
            else:
                observation: Dict[str, Any] = {
                    "resourceType": "Observation",
                    "id": resource_id,
                    "status": "final",
                    "code": {
                        "coding": [{
                            "system": entity["system"],
                            "code": entity["code"],
                            "display": entity["display"]
                        }]
                    },
                    "subject": {
                        "reference": f"Patient/{patient_id}"
                    }
                }
                report["contained"].append(observation) # type: ignore
                report["result"].append({"reference": f"#{resource_id}"}) # type: ignore

        elif ent_type == "procedure":
            observation: Dict[str, Any] = {
                "resourceType": "Observation",
                "id": resource_id,
                "status": "final",
                "code": {
                    "coding": [{
                        "system": entity["system"],
                        "code": entity["code"],
                        "display": entity["display"]
                    }]
                },
                "subject": {
                    "reference": f"Patient/{patient_id}"
                }
            }
            report["contained"].append(observation) # type: ignore
            report["result"].append({"reference": f"#{resource_id}"}) # type: ignore

    return report

TERMINOLOGY_PATH = os.path.join(os.path.dirname(__file__), "terminology.json")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process():
    """Accepts a JSON payload with 'text' and 'patient_id', returns FHIR output."""
    data = request.get_json()
    if not data or 'text' not in data or 'patient_id' not in data:
        return jsonify({"error": "Missing 'text' or 'patient_id' in JSON payload."}), 400

    try:
        with open(TERMINOLOGY_PATH, "r") as file:
            terminology = json.load(file)

        cleaned = clean_text(data['text'])
        entities = extract_entities(cleaned, terminology)
        fhir_doc = serialize_to_fhir(data['patient_id'], entities)

        return jsonify(fhir_doc)
    except PipelineError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "An unexpected error occurred."}), 500

def main() -> None:
    logger.info("NLP2FHIR — local server starting on http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    main()
