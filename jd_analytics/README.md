# RADIX Talent Match — Role 1: JD Analytics

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/Tests-Pytest-green.svg)](https://docs.pytest.org/)

Production-grade, integration-ready Python backend module for **Role 1: Job Description (JD) Analytics** in the RADIX Talent Match system.

> ⚠️ **Important for Developers and Coding Agents**:
> Before integrating this backend with the React frontend or other RADIX roles, consult **[`INTEGRATION_MAP.md`](../INTEGRATION_MAP.md)** (or `./INTEGRATION_MAP.md`). That document contains the authoritative machine-readable specifications, component file maps, data flow sequences, and inter-role integration contracts.

---

## What the Module Does

The JD Analytics service ingests recruiter and employer Job Descriptions, analyzes requirements, and returns structured data:
- **Document Support**: Parses text-based `.pdf` and `.docx` files up to 10 MB (configurable).
- **Structure Extraction**: Extracts multi-paragraph text and tabular requirement data.
- **Scanned Detection**: Identifies image-only scanned PDFs without embedded text layers and returns descriptive errors (`SCANNED_PDF_UNSUPPORTED`).
- **Semantic Skill Analysis**: Identifies explicit technologies and strongly implied engineering capabilities with attached quotation evidence.
- **Taxonomy Normalization**: Standardizes all extracted skills into the **13 authorized RADIX category codes** (`COD`, `DSA`, `OOD`, `APTI`, `COMM`, `AI`, `CLOUD`, `SQL`, `SWE`, `SYSD`, `NETW`, `OS`, `OTHER`).
- **Metadata Detection**: Detects employer company name and job title if stated, otherwise returning `null`.
- **Contract Enforcement**: Enforces strict Pydantic v2 validation conforming to the shared team JSON contract.
- **Dual Execution Engine**: Supports semantic extraction via Google Gemini API alongside a hermetic deterministic fallback engine for offline or fallback execution.

---

## Installation & Running

### Prerequisites
- Python 3.11 or newer
- pip

### Setup (Linux / macOS)
```bash
# 1. Navigate to directory
cd jd_analytics

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env

# 5. Start development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Setup (Windows)
```cmd
cd jd_analytics
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

API documentation is accessible at: **`http://127.0.0.1:8000/docs`**

---

## Environment Variables

Configured via `.env` or system environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `development` | Application runtime environment (`development`, `production`, `test`) |
| `HOST` | `127.0.0.1` | Binding host address |
| `PORT` | `8000` | Binding port |
| `MAX_UPLOAD_SIZE_MB` | `10` | Maximum allowed file upload size in MB |
| `MAX_EXTRACTED_TEXT_LENGTH`| `50000` | Maximum character length of text to analyze |
| `LLM_ENABLED` | `false` | Enable LLM semantic extraction provider |
| `LLM_PROVIDER` | `gemini` | LLM provider identifier (`gemini`, `mock`) |
| `LLM_MODEL` | `gemini-2.5-flash`| Gemini model alias |
| `LLM_API_KEY` | *(empty)* | Google Gemini API key (optional; fallback handles extraction if absent) |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout in seconds for LLM provider HTTP requests |
| `ALLOW_DETERMINISTIC_FALLBACK` | `true` | Allows offline deterministic extraction when LLM is disabled or unavailable |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Automated Testing

All tests use in-memory synthetic documents and mocked network calls. No external credentials or paid API keys are required:

```bash
# Run pytest test suite
pytest tests/ -v

# Run with test coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Basic API Usage

### 1. Health Probe
```bash
curl http://127.0.0.1:8000/health
# Response: {"status":"healthy","version":"1.0.0","service":"jd-analytics"}
```

### 2. Analyze a Job Description
Upload a `.pdf` or `.docx` file using the multipart form field `file`:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jd-analytics/analyze" \
     -F "file=@sample_data/backend_engineer_jd.pdf"
```

**Example Successful Response (`200 OK`)**:
```json
{
  "source_type": "jd",
  "source_file": "backend_engineer_jd.pdf",
  "company": "NovaScale Technologies",
  "role": "Senior Backend Engineer",
  "skills": [
    {
      "skill_name": "Python",
      "category_code": "COD",
      "evidence": "High proficiency with Python or Go",
      "confidence": "high",
      "requirement_type": "required",
      "requirement_strength": "explicit"
    },
    {
      "skill_name": "SQL",
      "category_code": "SQL",
      "evidence": "Work with relational data and write complex queries against PostgreSQL databases",
      "confidence": "high",
      "requirement_type": "required",
      "requirement_strength": "explicit"
    },
    {
      "skill_name": "System Design",
      "category_code": "SYSD",
      "evidence": "Design and implement scalable services that communicate over HTTP using REST APIs and gRPC",
      "confidence": "high",
      "requirement_type": "required",
      "requirement_strength": "implied"
    }
  ]
}
```

### 3. Validate a Payload
Verify that a candidate JSON payload complies with the team specification:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jd-analytics/validate" \
     -H "Content-Type: application/json" \
     -d '{"source_type":"jd","source_file":"test.pdf","company":null,"role":null,"skills":[]}'
```

---

## Integration Handoff

For React integration examples, inter-role specifications (Role 2, Role 3, Role 4, Role 5), and file maps, see:
👉 **[`INTEGRATION_MAP.md`](../INTEGRATION_MAP.md)**
