Instructions for AI coding agents: Before modifying this repository or integrating it with another RADIX module, read this file first. Inspect the referenced source files and verify the current implementation before editing. Use the documented public APIs and shared JSON contract as the integration boundary. Do not guess filenames, symbols, endpoints, or schema fields. Preserve backward compatibility unless a coordinated schema change is explicitly approved. Update this integration map whenever a public interface, file responsibility, or dependency changes.

---

# RADIX Talent Match — Role 1: JD Analytics Integration Map

This document is the authoritative integration manual and machine-readable specification for **Role 1: Job Description (JD) Analytics**. It describes the current implementation, public interfaces, data flows, and inter-module contracts across the RADIX Talent Match platform.

---

## Section A — Project Purpose and Boundaries

### 1. What JD Analytics Does
Role 1 is a standalone Python backend service responsible for:
- Ingesting Job Description files uploaded by recruiters or hiring teams.
- Validating file integrity, size limits, and binary signatures (`%PDF-` and `PK\x03\x04`).
- Extracting raw text from `.pdf` and `.docx` documents, including tables and multi-page layouts.
- Identifying required and preferred technical skills, tools, and professional competencies.
- Classifying skills into the **13 authoritative RADIX category codes**.
- Generating grounded textual evidence and confidence ratings for every extracted skill.
- Detecting employer company name and job role/title when stated.
- Emitting validated structured JSON conforming strictly to the team's shared contract.

### 2. What It Accepts
- File formats: `.pdf` (text-based PDF) and `.docx` (Microsoft Word OpenXML).
- Transport: HTTP `POST` multipart/form-data using field name `file`.
- Size constraint: Configurable, defaults to 10 MB.

### 3. What It Returns
- A validated JSON payload conforming to `JobDescriptionResponse`:
  - `source_type`: Always `"jd"`
  - `source_file`: Sanitized display name of the uploaded document
  - `company`: Identified employer name or `null`
  - `role`: Identified job title or `null`
  - `skills`: Array of categorized skill objects with grounded evidence and confidence scores

### 4. What It Does NOT Do (Out of Scope)
- **No User Interface**: No HTML, CSS, or React components. (Frontend is implemented separately).
- **No Resume Parsing**: Handled by **Role 2: Resume Parsing**.
- **No Candidate Profile Management**: Handled by **Role 3: Profile Builder**.
- **No Candidate Verification / Assessment**: Handled by **Role 4: Talent Check**.
- **No Scoring / Matching Engine**: Handled by **Role 5: Skill Matching**.
- **No Database Persistence**: Stateless module; does not store resumes, job descriptions, or embeddings.

### 5. Runtime Dependencies
- Python 3.11+
- Web framework: `fastapi` (v0.110+), `uvicorn` (v0.28+)
- Data validation: `pydantic` (v2.6+), `pydantic-settings` (v2.2+)
- Document processing: `pymupdf` (v1.23+), `python-docx` (v1.1+)
- HTTP client & testing: `httpx`, `pytest`, `pytest-asyncio`

---

## Section B — Source-of-Truth File Map

| File / Path | Responsibility | Important Functions / Classes | Used By | Normally Modified During Integration? |
|---|---|---|---|---|
| `app/main.py` | Application entry point, CORS middleware, error handlers | `create_application()`, `app` | Uvicorn server, `tests/test_api.py` | **No** (modify only to add global middleware) |
| `app/config.py` | Environment variable parsing and system defaults | `Settings`, `settings` | All `app/` services, API routes | **Only** to adjust upload limits or env vars |
| `app/schemas.py` | Authoritative Pydantic models for RADIX contract | `RadixCategoryCode`, `SkillItem`, `JobDescriptionResponse`, `ErrorResponse` | `app/api/routes.py`, `app/services/jd_analyzer.py`, Downstream consumers | **NO** (Do not alter without cross-team consensus) |
| `app/exceptions.py` | Domain exceptions mapped to HTTP status codes | `FileSizeExceededError`, `UnsupportedFileTypeError`, `ScannedPDFError`, `MalformedDocumentError`, `ExtractionServiceUnavailableError` | `app/services/*`, `app/main.py` | **Rarely** (only to add new domain error types) |
| `app/api/routes.py` | HTTP endpoint controllers for health, analyze, validate | `service_health()`, `module_health()`, `analyze_job_description()`, `validate_jd_payload()` | `app/main.py` | **No** (preserve existing API endpoints) |
| `app/services/document_extractor.py` | Extraction of text and tables from PDF and DOCX | `DocumentExtractor.extract_from_bytes()`, `normalize_whitespace()` | `app/api/routes.py` | **Only** if improving document text parsers |
| `app/services/normalization.py` | Canonical dictionary, deduplication, category fallback | `CANONICAL_SKILL_MAP`, `normalize_category_code()`, `deduplicate_and_merge_skills()` | `app/services/jd_analyzer.py` | **YES** (to expand vocabulary or synonyms) |
| `app/services/llm_extractor.py` | LLM extraction interface and Gemini provider | `BaseLLMExtractor`, `GeminiLLMExtractor`, `MockLLMExtractor`, `get_llm_extractor()` | `app/services/jd_analyzer.py` | **YES** (to change or configure LLM providers) |
| `app/services/jd_analyzer.py` | Orchestrates skill extraction, implied rules, metadata | `DeterministicSkillExtractor`, `JobDescriptionAnalyzer`, `IMPLIED_SKILL_PATTERNS` | `app/api/routes.py` | **YES** (to refine implied skill heuristics) |
| `app/utils/security.py` | File validation, path sanitization, prompt isolation | `sanitize_filename()`, `validate_file_upload()`, `sanitize_prompt_text()` | `app/api/routes.py` | **No** (core security controls) |
| `app/utils/logging_config.py` | Privacy-preserving logging with credential scrubbing | `setup_logging()`, `SensitiveDataFilter` | `app/main.py`, services | **No** |

---

## Section C — Data Flow

The lifecycle of an analysis request proceeds in 7 deterministic stages:

```
[1. HTTP POST /api/v1/jd-analytics/analyze (multipart/form-data)]
    │
    ▼
[2. File Upload Validation]
    ├── Source: app/utils/security.py -> validate_file_upload()
    ├── Validates file size (max 10MB) -> FileSizeExceededError (413)
    ├── Validates extension (.pdf or .docx) -> UnsupportedFileTypeError (415)
    ├── Checks binary magic bytes (%PDF- or PK\x03\x04) -> UnsupportedFileTypeError (415)
    └── Sanitizes filename against path traversal -> sanitize_filename()
    │
    ▼
[3. Document Text & Structure Extraction]
    ├── Source: app/services/document_extractor.py -> DocumentExtractor.extract_from_bytes()
    ├── PDF (PyMuPDF): extracts pages, verifies character density -> ScannedPDFError (400) if image-only
    ├── DOCX (python-docx): extracts paragraphs and table rows/cells
    └── Normalizes spacing and line endings -> normalize_whitespace()
    │
    ▼
[4. Prompt Sanitization & Length Limiting]
    ├── Source: app/utils/security.py -> sanitize_prompt_text()
    └── Enforces MAX_EXTRACTED_TEXT_LENGTH (50,000 chars) and removes control bytes
    │
    ▼
[5. Semantic Skill Analysis & Categorization]
    ├── Source: app/services/jd_analyzer.py -> JobDescriptionAnalyzer.analyze()
    ├── Path A (LLM Enabled & Key Configured):
    │   └── app/services/llm_extractor.py -> GeminiLLMExtractor.extract_skills_and_metadata()
    └── Path B (LLM Disabled, Failed, or Offline):
        └── app/services/jd_analyzer.py -> DeterministicSkillExtractor
            ├── Company & Role header detection -> extract_company_and_role()
            ├── Implied capability rules -> IMPLIED_SKILL_PATTERNS
            └── Canonical technology dictionary -> CANONICAL_SKILL_MAP
    │
    ▼
[6. Normalization & Deduplication]
    ├── Source: app/services/normalization.py -> deduplicate_and_merge_skills()
    ├── Merges duplicate skill occurrences
    ├── Selects highest confidence level (high > medium > low)
    ├── Selects strongest requirement type (required > preferred > unspecified)
    └── Retains the most descriptive evidence quote
    │
    ▼
[7. Pydantic Contract Validation & Response]
    ├── Source: app/schemas.py -> JobDescriptionResponse
    ├── Validates category_code against 13 authorized RADIX categories
    └── Emits HTTP 200 OK with mandatory shared JSON contract
```

---

## Section D — Public API Contract

Base URL: `http://127.0.0.1:8000` (configurable via `HOST` and `PORT`).

### 1. `GET /health`
- **Purpose**: Liveness probe for containers and load balancers.
- **Request**: No headers or parameters required.
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "service": "jd-analytics"
  }
  ```

### 2. `GET /api/v1/jd-analytics/health`
- **Purpose**: Readiness probe detailing extraction capabilities and provider state.
- **Request**: No authentication or parameters required.
- **Response `200 OK`**:
  ```json
  {
    "status": "ready",
    "service": "jd-analytics",
    "version": "1.0.0",
    "llm_enabled": false,
    "llm_provider": "gemini",
    "llm_configured": false,
    "deterministic_fallback_enabled": true,
    "supported_formats": ["pdf", "docx"],
    "max_upload_size_mb": 10
  }
  ```

### 3. `POST /api/v1/jd-analytics/analyze`
- **Purpose**: Ingests a Job Description file, extracts text, categorizes skills, and outputs the shared contract JSON.
- **Content-Type**: `multipart/form-data`
- **Form Field**: `file` (binary PDF or DOCX file)
- **Supported Formats**: `.pdf`, `.docx`
- **Max File Size**: 10 MB (configurable)
- **Response `200 OK`**: Matches `JobDescriptionResponse` (see Section E).
- **HTTP Status Codes**:
  - `200`: Analysis succeeded.
  - `400`: Empty document, corrupt file, or scanned image PDF without OCR.
  - `413`: File exceeds upload size limit.
  - `415`: Unsupported file type (only `.pdf` and `.docx` supported).
  - `422`: Form field `file` is missing or invalid.
  - `500`: Unexpected internal error (stack traces redacted).
  - `503`: Extraction service unavailable and fallback is disabled.
- **Example cURL Request**:
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/jd-analytics/analyze" \
       -F "file=@sample_data/backend_engineer_jd.pdf"
  ```

### 4. `POST /api/v1/jd-analytics/validate`
- **Purpose**: Validates any candidate JSON payload against the shared RADIX contract.
- **Content-Type**: `application/json`
- **Request Body**: Arbitrary JSON payload.
- **Response `200 OK`**:
  ```json
  {
    "valid": true,
    "message": "Job description payload conforms strictly to the RADIX contract.",
    "skill_count": 5,
    "categories_present": ["COD", "CLOUD", "SQL"]
  }
  ```
- **Response `422 Unprocessable Entity`**:
  ```json
  {
    "valid": false,
    "message": "Job description payload failed validation against the shared contract.",
    "errors": [
      {
        "loc": ["skills", 0, "category_code"],
        "msg": "Input should be 'COD', 'DSA', 'OOD', ...",
        "type": "enum"
      }
    ]
  }
  ```

### 5. Standard Error Object Structure
Every non-200 failure returns a uniform machine-readable JSON structure:
```json
{
  "success": false,
  "error": {
    "code": "SCANNED_PDF_UNSUPPORTED",
    "message": "Document appears to be a scanned image-only PDF with no extractable text layer. OCR (Optical Character Recognition) is currently unsupported. Please upload a text-based PDF or DOCX file.",
    "field": "file"
  }
}
```

---

## Section E — Shared Data Contract

The JSON object returned by `POST /api/v1/jd-analytics/analyze` is the authoritative contract consumed by other RADIX modules:

```json
{
  "source_type": "jd",
  "source_file": "backend_developer_jd.pdf",
  "company": "Acme Cloud Solutions",
  "role": "Senior Backend Developer",
  "skills": [
    {
      "skill_name": "Python",
      "category_code": "COD",
      "evidence": "Develop backend services using Python 3",
      "confidence": "high",
      "requirement_type": "required",
      "requirement_strength": "explicit"
    },
    {
      "skill_name": "SQL",
      "category_code": "SQL",
      "evidence": "Work with relational data and write complex queries against PostgreSQL",
      "confidence": "high",
      "requirement_type": "required",
      "requirement_strength": "implied"
    }
  ]
}
```

### Field Definitions

| Field Path | Type | Required? | Nullable? | Description |
|---|---|---|---|---|
| `source_type` | `string` | **Yes** | No | Fixed literal: `"jd"`. Identifies the document origin for downstream modules. |
| `source_file` | `string` | **Yes** | No | Sanitized display name of the uploaded document (e.g. `"backend_developer_jd.pdf"`). |
| `company` | `string` | **Yes** | **Yes** | Employer company name if identified from headers/metadata; `null` if anonymous. |
| `role` | `string` | **Yes** | **Yes** | Job title/position name if identified; `null` if unstated. |
| `skills` | `array` | **Yes** | No | List of validated skill objects. May be empty (`[]`) if no technical skills were found. |
| `skills[].skill_name` | `string` | **Yes** | No | Clear canonical skill name (e.g. `"Python"`, `"Docker"`, `"Data Structures & Algorithms"`). |
| `skills[].category_code`| `string` | **Yes** | No | Exactly one of the 13 authorized RADIX category codes. |
| `skills[].evidence` | `string` | **Yes** | No | Grounded quote or excerpt from the job description supporting the extraction. |
| `skills[].confidence` | `string` | **Yes** | No | Value must be `"high"`, `"medium"`, or `"low"`. |
| `skills[].requirement_type` | `string` | Optional Ext | No | `"required"` (must-have), `"preferred"` (nice-to-have), or `"unspecified"`. |
| `skills[].requirement_strength`| `string` | Optional Ext | No | `"explicit"` (named directly) or `"implied"` (derived from task descriptions). |

### Authorized RADIX Category Codes

| Code | Domain | Primary Technical Scope |
|:---:|:---|:---|
| **`COD`** | Coding | Programming languages, scripting (Python, Go, Java, TypeScript, C++, Rust) |
| **`DSA`** | Data Structures & Algorithms | Trees, graphs, dynamic programming, algorithmic complexity, Big-O |
| **`OOD`** | Object-Oriented Design | Design patterns, SOLID principles, class architecture, encapsulation |
| **`APTI`** | Aptitude | Analytical reasoning, quantitative thinking, problem solving |
| **`COMM`** | Communication | Technical writing, cross-functional collaboration, stakeholder presentation |
| **`AI`** | Artificial Intelligence | Machine learning, deep learning, NLP, computer vision, PyTorch, LLMs |
| **`CLOUD`** | Cloud | AWS, GCP, Azure, Docker, Kubernetes, Terraform, Serverless architecture |
| **`SQL`** | SQL & Relational Databases | PostgreSQL, MySQL, database indexing, query optimization, schema design |
| **`SWE`** | Software Engineering | Git, CI/CD, unit testing, automated testing, Agile/Scrum, code review |
| **`SYSD`** | System Design | Distributed systems, microservices, scalability, caching, message queues |
| **`NETW`** | Networking | TCP/IP, HTTP/HTTPS, REST APIs, WebSockets, gRPC, DNS, SSL/TLS |
| **`OS`** | Operating Systems | Linux, shell scripting, concurrency, multithreading, memory management |
| **`OTHER`** | Other Competencies | Skills that do not fit into the 12 named categories above |

### Downstream Consumption Guidelines (Role 5: Skill Matching)
- **Primary Matching Keys**: `skill_name` (canonicalized) and `category_code`.
- **Weighting Factors**:
  - `requirement_type == "required"`: Higher match penalty if candidate lacks the skill.
  - `requirement_type == "preferred"`: Bonus match points if candidate possesses the skill.
  - `confidence`: Discount low-confidence extractions when computing compatibility scores.
- **Auditability / UI Display**: `evidence` should be rendered to the user as justification for why a skill was matched or flagged as missing.

---

## Section F — Integration with the React UI

The React frontend interacts with this module via standard HTTP calls. The frontend repository must not import Python modules directly.

### 1. Frontend Configuration
Set the backend endpoint in your React `.env`:
```env
VITE_JD_ANALYTICS_API_URL=http://127.0.0.1:8000
```
In production, point `VITE_JD_ANALYTICS_API_URL` to your deployed backend domain (e.g. `https://api.radix-talent.internal`).

### 2. React File Upload Implementation
```typescript
interface SkillItem {
  skill_name: string;
  category_code: string;
  evidence: string;
  confidence: 'high' | 'medium' | 'low';
  requirement_type: 'required' | 'preferred' | 'unspecified';
  requirement_strength: 'explicit' | 'implied';
}

interface JobDescriptionResponse {
  source_type: 'jd';
  source_file: string;
  company: string | null;
  role: string | null;
  skills: SkillItem[];
}

export async function uploadJobDescription(file: File): Promise<JobDescriptionResponse> {
  const baseUrl = import.meta.env.VITE_JD_ANALYTICS_API_URL || 'http://127.0.0.1:8000';
  
  // 1. Pack file into FormData with the mandatory field name 'file'
  const formData = new FormData();
  formData.append('file', file);

  // 2. Dispatch POST request
  // Note: Do NOT manually set the 'Content-Type' header; the browser will set multipart boundary
  const response = await fetch(`${baseUrl}/api/v1/jd-analytics/analyze`, {
    method: 'POST',
    body: formData,
  });

  const data = await response.json();

  // 3. Handle errors
  if (!response.ok) {
    const errorMsg = data.error?.message || `Extraction failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return data as JobDescriptionResponse;
}
```

### 3. UI Display Expectations
- **Displaying Metadata**: Handle `company` and `role` gracefully when `null`:
  ```jsx
  <h2>{data.role || 'Unspecified Role'}</h2>
  <p className="company-tag">{data.company || 'Anonymous Employer'}</p>
  ```
- **Empty States**: If `data.skills.length === 0`, display a state indicating that no technical requirements could be extracted.
- **CORS Handling**: `app/main.py` is configured with `CORSMiddleware(allow_origins=["*"])`, allowing local development on `http://localhost:3000` or `http://localhost:5173`.

---

## Section G — Integration with Other RADIX Roles

| RADIX Role | Module Responsibility | Data Flow Relationship with JD Analytics | Status | Integration Boundary |
|---|---|---|---|---|
| **Role 1: JD Analytics** *(This Module)* | Job description text extraction & skill categorization | Emits `JobDescriptionResponse` | **Implemented & Verified** | REST API (`POST /api/v1/jd-analytics/analyze`) |
| **Role 2: Resume Parsing** | Candidate resume ingestion & skill extraction | Parallel role; parses candidate resumes into structured skill schema | **Not Implemented** | Emits candidate skill schema (Target: `source_type: "resume"`) |
| **Role 3: Profile Builder** | Candidate profile aggregator and persistence | Independent; aggregates candidate work history, education, and links | **Not Implemented** | Downstream of Role 2; independent of Role 1 |
| **Role 4: Talent Check** | Verification of credentials, GitHub, or assessments | Independent; validates candidate claims | **Not Implemented** | Operates on candidate profile; independent of Role 1 |
| **Role 5: Skill Matching** | Computes match percentage between JD and Candidate | **Primary Consumer** of Role 1 output. Compares Role 1 `skills` with Role 2 `skills`. | **Pending team agreement** | Expects `JobDescriptionResponse` as input A and candidate profile as input B |

### Outstanding Inter-Role Decisions (Pending Team Agreement)
1. **Role 2 / Role 1 Skill Taxonomy Synchronization**: Role 2 (Resume Parsing) must adopt the identical `category_code` enum (`COD`, `DSA`, etc.) to allow direct matrix matching in Role 5.
2. **Role 5 Matching Algorithm**: The weighting formula for `requirement_type == "required"` vs. `requirement_type == "preferred"` needs team consensus.

---

## Section H — Extension and Modification Guide

| Task | Target File | Specific Target Symbol | Instructions |
|---|---|---|---|
| **Add a new skill or synonym** | `app/services/normalization.py` | `CANONICAL_SKILL_MAP` | Add key in lowercase: `"alias": ("Canonical Name", RadixCategoryCode.CATEGORY)` |
| **Add implied skill heuristic** | `app/services/jd_analyzer.py` | `IMPLIED_SKILL_PATTERNS` | Add `ImpliedPattern(regex, "Skill Name", RadixCategoryCode, ConfidenceLevel)` |
| **Refine company / role regex** | `app/services/jd_analyzer.py` | `DeterministicSkillExtractor.extract_company_and_role` | Update single-line header regex patterns |
| **Change or swap LLM provider** | `app/services/llm_extractor.py` | `BaseLLMExtractor`, `get_llm_extractor` | Subclass `BaseLLMExtractor` and register in factory function |
| **Modify upload limits** | `app/config.py` | `Settings.max_upload_size_mb` | Update setting default or configure via `.env` |
| **Improve table text extraction** | `app/services/document_extractor.py`| `DocumentExtractor._extract_docx` | Edit table parsing loop |
| **Add API route** | `app/api/routes.py` | `router` | Define route with standard `response_model` and register on `router` |
| **Modify shared response schema** | `app/schemas.py` | `JobDescriptionResponse`, `SkillItem` | ⚠️ **WARNING**: Modifying this schema will break downstream contracts! Requires cross-team agreement. |

---

## Section I — Setup and Verification

### 1. Requirements
- Python `3.11+`
- `pip`

### 2. Local Setup
```bash
# Navigate to directory
cd jd_analytics

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start backend server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Verification Commands
- **Check Health Probe**:
  ```bash
  curl http://127.0.0.1:8000/health
  # Expected: {"status":"healthy","version":"1.0.0","service":"jd-analytics"}
  ```
- **Check Module Readiness**:
  ```bash
  curl http://127.0.0.1:8000/api/v1/jd-analytics/health
  # Expected: {"status":"ready", ...}
  ```
- **Run Full Automated Test Suite**:
  ```bash
  PYTHONPATH=. pytest tests/ -v
  ```
- **Generate Test Files & Run Test Upload**:
  ```bash
  python sample_data/generate_samples.py
  curl -X POST "http://127.0.0.1:8000/api/v1/jd-analytics/analyze" \
       -F "file=@sample_data/backend_engineer_jd.pdf"
  ```

---

## Section J — Integration Status

| Integration Item | Status | Evidence or Next Action |
|---|---|---|
| **Python backend startup** | **Verified** | Verified with FastAPI and Uvicorn; `/health` endpoint responds with HTTP 200. |
| **PDF extraction** | **Verified** | PyMuPDF extraction verified with text, multi-page layout, and scanned PDF detection (`tests/test_document_extractor.py`). |
| **DOCX extraction** | **Verified** | python-docx extraction verified with paragraphs and table cells (`tests/test_document_extractor.py`). |
| **Skill extraction** | **Verified** | Explicit and implied extraction verified across all 13 RADIX categories (`tests/test_jd_analyzer.py`). |
| **Shared schema validation** | **Verified** | Strict Pydantic v2 validation enforced on all successful responses (`tests/test_schemas.py`). |
| **API availability** | **Verified** | Endpoints `/health`, `/api/v1/jd-analytics/health`, `/analyze`, `/validate` verified (`tests/test_api.py`). |
| **Automated tests** | **Verified** | 40/40 pytest tests passing hermetically without external network dependencies. |
| **React integration** | **Implemented, not verified** | Backend CORS enabled and API contract verified; awaiting React frontend connection. |
| **Role 2 (Resume Parsing)** | **Not implemented** | Out of scope for this role; pending Role 2 implementation by team. |
| **Role 3 (Profile Builder)** | **Not implemented** | Out of scope for this role; pending Role 3 implementation by team. |
| **Role 4 (Talent Check)** | **Not implemented** | Out of scope for this role; pending Role 4 implementation by team. |
| **Role 5 (Skill Matching)** | **Pending team agreement** | Role 1 contract is complete; awaiting team decision on match scoring algorithm. |
