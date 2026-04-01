import pytest
from project import (
    app,
    clean_text,
    extract_entities,
    serialize_to_fhir,
    DataIngestionError,
    ExtractionError,
    FHIRSerializationError
)

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

# Test clean_text
def test_clean_text():
    # Valid normalizations
    assert clean_text("  This is a TEST!  ") == "this is a test"
    assert clean_text("Patient's heart rate: 80 bpm.") == "patient s heart rate 80 bpm"
    assert clean_text("Newline \n and \t tab!!") == "newline and tab"
    # Unidecode specific tests for accents
    assert clean_text("fémur") == "femur"
    assert clean_text("L'asthme !") == "l asthme"
    
    # Error checking
    with pytest.raises(DataIngestionError, match="Input text must be a non-empty string."):
        clean_text("")
    with pytest.raises(DataIngestionError, match="Input text must be a non-empty string."):
        clean_text("   ")
    with pytest.raises(DataIngestionError, match="Input text must be a non-empty string."):
        clean_text(None)  # type: ignore
        
    with pytest.raises(DataIngestionError, match="Text became empty after cleaning."):
        clean_text("!@#$%^")

# Test extract_entities
def test_extract_entities():
    mock_dict = {
        "pneumonie": {"system": "http://snomed.info/sct", "code": "233604007", "display": "Pneumonia / Pneumonie", "type": "pathology"},
        "pneumonia": {"system": "http://snomed.info/sct", "code": "233604007", "display": "Pneumonia / Pneumonie", "type": "pathology"},
        "poumon gauche": {"system": "http://snomed.info/sct", "code": "39607008", "display": "Structure du poumon gauche", "type": "anatomy"}
    }
    
    # Valid extraction with synonyms, should not duplicate SNOMED code
    cleaned = "patient a une pneumonie (pneumonia) dans le poumon gauche"
    entities = extract_entities(cleaned, mock_dict)
    assert len(entities) == 2
    assert {"system": "http://snomed.info/sct", "code": "233604007", "display": "Pneumonia / Pneumonie", "type": "pathology"} in entities
    assert {"system": "http://snomed.info/sct", "code": "39607008", "display": "Structure du poumon gauche", "type": "anatomy"} in entities
    
    # Missing term ignores gracefully
    entities_missing = extract_entities("patient en bonne sante", mock_dict)
    assert len(entities_missing) == 0
    
    # Error checking
    with pytest.raises(ExtractionError, match="Terminology dictionary cannot be empty or invalid."):
        extract_entities(cleaned, {})
        
    invalid_dict = {"pneumonie": {"system": "http://snomed.info/sct"}} # Missing display and code
    with pytest.raises(ExtractionError, match="Terminology missing required key:"):
        extract_entities("pneumonie", invalid_dict)

# Test serialize_to_fhir
def test_serialize_to_fhir():
    entities = [
        {"system": "http://snomed.info/sct", "code": "233604007", "display": "Pneumonie", "type": "pathology"},
        {"system": "http://snomed.info/sct", "code": "39607008", "display": "Poumon Gauche", "type": "anatomy"}
    ]
    
    # Valid serialization combining into Condition + bodySite
    fhir_doc = serialize_to_fhir("pat-123", entities)
    assert fhir_doc["resourceType"] == "DiagnosticReport"
    assert fhir_doc["subject"]["reference"] == "Patient/pat-123"
    
    # It should group the anatomy under the condition
    assert len(fhir_doc["contained"]) == 1
    condition = fhir_doc["contained"][0]
    assert condition["resourceType"] == "Condition"
    assert condition["code"]["coding"][0]["code"] == "233604007"
    assert "bodySite" in condition
    assert len(condition["bodySite"]) == 1
    assert condition["bodySite"][0]["coding"][0]["code"] == "39607008"
    assert fhir_doc["result"][0]["reference"] == f"#{condition['id']}"
    
    # Empty entities array is allowed, returns report without contained elements
    empty_doc = serialize_to_fhir("pat-123", [])
    assert len(empty_doc["contained"]) == 0
    assert "result" not in empty_doc
    
    # Error checking for missing patient
    with pytest.raises(FHIRSerializationError, match="Patient ID is required for FHIR serialization."):
        serialize_to_fhir("", entities)
        
    with pytest.raises(FHIRSerializationError, match="Patient ID is required for FHIR serialization."):
        serialize_to_fhir("   ", entities)
        
    # Error checking for invalid entities
    invalid_entities = [{"system": "http://snomed.info/sct", "type": "pathology"}] # missing code, display
    with pytest.raises(FHIRSerializationError, match="Entity at index 0 is missing required FHIR coding fields."):
        serialize_to_fhir("pat-123", invalid_entities)

# Integration tests for Flask endpoints
def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200

def test_process_valid(client):
    payload = {"text": "Patient with pneumonia", "patient_id": "pat-001"}
    response = client.post("/api/process", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["resourceType"] == "DiagnosticReport"
    assert data["subject"]["reference"] == "Patient/pat-001"

def test_process_missing_fields(client):
    # Missing patient_id
    response = client.post("/api/process", json={"text": "some text"})
    assert response.status_code == 400
    assert "error" in response.get_json()

def test_process_empty_text(client):
    response = client.post("/api/process", json={"text": "", "patient_id": "pat-001"})
    assert response.status_code == 400
    assert "error" in response.get_json()

def test_process_no_matches(client):
    # Text with no known clinical terms — valid but returns empty contained list
    response = client.post("/api/process", json={"text": "the patient is fine", "patient_id": "pat-002"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["contained"] == []
    assert "result" not in data

def test_process_payload_too_large(client):
    big_text = "a" * (65 * 1024)
    response = client.post("/api/process", json={"text": big_text, "patient_id": "pat-001"})
    assert response.status_code == 413
