import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_service_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "jd-analytics"
    assert "version" in data


def test_module_health(client):
    response = client.get("/api/v1/jd-analytics/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ready", "degraded"]
    assert "supported_formats" in data
    assert "pdf" in data["supported_formats"]
    assert "docx" in data["supported_formats"]
    # Check that secrets are not leaked
    assert "api_key" not in data
    assert "llm_api_key" not in data


def test_analyze_valid_pdf(client, make_pdf):
    pdf_bytes = make_pdf([
        "Company: Acme Inc\nJob Title: Backend Engineer\n\nRequirements:\n- 3+ years with Python and PostgreSQL.\n- Docker experience."
    ])
    files = {"file": ("backend_jd.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/v1/jd-analytics/analyze", files=files)
    assert response.status_code == 200

    data = response.json()
    assert data["source_type"] == "jd"
    assert data["source_file"] == "backend_jd.pdf"
    assert data["company"] == "Acme Inc"
    assert data["role"] == "Backend Engineer"
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) > 0

    # Validate individual skill structure
    first_skill = data["skills"][0]
    assert "skill_name" in first_skill
    assert "category_code" in first_skill
    assert "evidence" in first_skill
    assert "confidence" in first_skill
    assert first_skill["confidence"] in ["high", "medium", "low"]


def test_analyze_valid_docx(client, make_docx):
    docx_bytes = make_docx([
        "Role: Cloud Architect",
        "Required Skills: AWS, Terraform, and Kubernetes."
    ])
    files = {"file": ("cloud_jd.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = client.post("/api/v1/jd-analytics/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "jd"
    assert data["source_file"] == "cloud_jd.docx"
    assert any(s["skill_name"] == "AWS" for s in data["skills"])


def test_analyze_unsupported_file_extension(client):
    files = {"file": ("document.txt", b"plain text content", "text/plain")}
    response = client.post("/api/v1/jd-analytics/analyze", files=files)
    assert response.status_code == 415
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_analyze_missing_file(client):
    response = client.post("/api/v1/jd-analytics/analyze")
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "error" in data


def test_analyze_malformed_pdf(client):
    files = {"file": ("bad.pdf", b"%PDF-corrupted_content_here_is_invalid", "application/pdf")}
    response = client.post("/api/v1/jd-analytics/analyze", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] in ["MALFORMED_DOCUMENT", "SCANNED_PDF_UNSUPPORTED", "EMPTY_DOCUMENT"]


def test_validate_endpoint_valid_payload(client):
    valid_payload = {
        "source_type": "jd",
        "source_file": "sample_jd.pdf",
        "company": "Tech Corp",
        "role": "Software Engineer",
        "skills": [
            {
                "skill_name": "Python",
                "category_code": "COD",
                "evidence": "Experience with Python programming",
                "confidence": "high",
                "requirement_type": "required",
                "requirement_strength": "explicit"
            }
        ]
    }
    response = client.post("/api/v1/jd-analytics/validate", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["skill_count"] == 1
    assert "COD" in data["categories_present"]


def test_validate_endpoint_invalid_payload(client):
    invalid_payload = {
        "source_type": "invalid_type",  # Must be 'jd'
        "source_file": "sample_jd.pdf",
        "skills": [
            {
                "skill_name": "Python",
                "category_code": "INVALID_CODE",  # Not a RADIX category
                "confidence": "unknown"  # Not a valid confidence level
                # Missing 'evidence' field
            }
        ]
    }
    response = client.post("/api/v1/jd-analytics/validate", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0
