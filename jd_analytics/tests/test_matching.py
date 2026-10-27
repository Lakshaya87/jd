import sys
from unittest.mock import MagicMock
import pytest

# Ensure missing document extraction dependencies (used only by Role 1 file ingestion)
# do not prevent Role 5 matching service from running hermetically in environments without fitz/docx
for mod_name in ["fitz", "pymupdf", "docx"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from starlette.testclient import TestClient

from app.main import app
from app.schemas import (
    ConfidenceLevel,
    JobDescriptionResponse,
    RadixCategoryCode,
    RequirementStrength,
    RequirementType,
    SkillItem,
)
from app.services.matching_engine import (
    CandidateProfile,
    CandidateSkill,
    MatchRequest,
    SkillMatchingEngine,
)


def create_sample_jd(skills: list[SkillItem]) -> JobDescriptionResponse:
    """Helper to construct a valid JobDescriptionResponse."""
    return JobDescriptionResponse(
        source_type="jd",
        source_file="test_sample_jd.pdf",
        company="RADIX Corp",
        role="Full Stack Engineer",
        skills=skills
    )


# ============================================================================
# Unit Tests for Scoring Engine
# ============================================================================

def test_exact_match_returns_100_percent():
    """When a candidate possesses all required skills, match score should be 100%."""
    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Must write clean backend services in Python",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="PostgreSQL",
            category_code=RadixCategoryCode.SQL,
            evidence="Experience designing tables in PostgreSQL",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    cand = CandidateProfile(
        candidate_id="cand_101",
        candidate_name="Alice Developer",
        skills=[
            CandidateSkill(skill_name="Python", category_code=RadixCategoryCode.COD),
            CandidateSkill(skill_name="PostgreSQL", category_code=RadixCategoryCode.SQL),
        ]
    )

    result = SkillMatchingEngine.match(jd, cand)

    assert result.match_score == 100.0
    assert result.total_jd_skills == 2
    assert result.matched_count == 2
    assert result.missing_count == 0
    assert len(result.missing_skills) == 0
    assert len(result.matched_skills) == 2


def test_zero_match_returns_zero_percent():
    """When candidate has completely unrelated skills, match score should be 0%."""
    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Develop Python services",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="Docker",
            category_code=RadixCategoryCode.CLOUD,
            evidence="Deploy using Docker containers",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    cand = CandidateProfile(
        candidate_id="cand_102",
        candidate_name="Bob Designer",
        skills=[
            CandidateSkill(skill_name="Photoshop"),
            CandidateSkill(skill_name="Figma"),
        ]
    )

    result = SkillMatchingEngine.match(jd, cand)

    assert result.match_score == 0.0
    assert result.matched_count == 0
    assert result.missing_count == 2
    assert len(result.matched_skills) == 0
    assert len(result.missing_skills) == 2
    assert len(result.additional_candidate_skills) == 2


def test_partial_match():
    """Partial skill overlap should yield a proportional score."""
    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Write Python code",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="Docker",
            category_code=RadixCategoryCode.CLOUD,
            evidence="Deploy Docker containers",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    cand = CandidateProfile(
        skills=[CandidateSkill(skill_name="Python")]
    )

    result = SkillMatchingEngine.match(jd, cand)

    assert result.match_score == 50.0
    assert result.matched_count == 1
    assert result.missing_count == 1
    assert result.matched_skills[0].skill_name == "Python"
    assert result.missing_skills[0].skill_name == "Docker"


def test_required_versus_preferred_weighting():
    """
    Required skills carry higher weight (3.0) than preferred skills (1.0).
    A candidate matching a required skill should score significantly higher
    than a candidate matching only a preferred skill.
    """
    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Python is required for all backend tasks",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="Docker",
            category_code=RadixCategoryCode.CLOUD,
            evidence="Docker knowledge is nice to have",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.PREFERRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    # Candidate A matches ONLY the REQUIRED skill
    cand_a = CandidateProfile(skills=[CandidateSkill(skill_name="Python")])
    result_a = SkillMatchingEngine.match(jd, cand_a)

    # Candidate B matches ONLY the PREFERRED skill
    cand_b = CandidateProfile(skills=[CandidateSkill(skill_name="Docker")])
    result_b = SkillMatchingEngine.match(jd, cand_b)

    # Required weight = 3.0, Preferred weight = 1.0, Total = 4.0
    # Candidate A score: (3.0 / 4.0) * 100 = 75.0%
    # Candidate B score: (1.0 / 4.0) * 100 = 25.0%
    assert result_a.match_score == 75.0
    assert result_b.match_score == 25.0
    assert result_a.match_score > result_b.match_score


def test_canonical_alias_matching():
    """
    Verifies that canonical aliases in CANONICAL_SKILL_MAP are matched correctly.
    E.g., candidate specifying 'py', 'postgres', and 'k8s' should match
    JD requirements for 'Python', 'PostgreSQL', and 'Kubernetes'.
    """
    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Python 3.11+",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="PostgreSQL",
            category_code=RadixCategoryCode.SQL,
            evidence="PostgreSQL database queries",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="Kubernetes",
            category_code=RadixCategoryCode.CLOUD,
            evidence="Orchestration with Kubernetes",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    # Candidate provides lowercase aliases
    cand = CandidateProfile(
        skills=[
            CandidateSkill(skill_name="python3"),
            CandidateSkill(skill_name="postgres"),
            CandidateSkill(skill_name="k8s"),
        ]
    )

    result = SkillMatchingEngine.match(jd, cand)

    assert result.match_score == 100.0
    assert result.matched_count == 3
    assert result.missing_count == 0


def test_case_and_whitespace_insensitivity():
    """Ensure skills match regardless of surrounding whitespace or case variations."""
    jd = create_sample_jd([
        SkillItem(
            skill_name="TypeScript",
            category_code=RadixCategoryCode.COD,
            evidence="Frontend written in TypeScript",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        )
    ])

    cand = CandidateProfile(
        skills=[CandidateSkill(skill_name="  typeSCRIPT  ")]
    )

    result = SkillMatchingEngine.match(jd, cand)
    assert result.match_score == 100.0
    assert result.matched_count == 1


def test_empty_job_description_does_not_return_100_percent():
    """
    Guard: An empty job description MUST NOT return a 100% match score.
    It should return 0.0% with an informative summary message.
    """
    jd = create_sample_jd([])
    cand = CandidateProfile(
        skills=[
            CandidateSkill(skill_name="Python"),
            CandidateSkill(skill_name="FastAPI"),
        ]
    )

    result = SkillMatchingEngine.match(jd, cand)

    assert result.match_score == 0.0
    assert result.total_jd_skills == 0
    assert result.matched_count == 0
    assert result.missing_count == 0
    assert "no extractable skills" in result.summary.lower()
    assert len(result.additional_candidate_skills) == 2


def test_empty_candidate_profile_returns_zero():
    """When a candidate has no skills listed, score must be 0%."""
    jd = create_sample_jd([
        SkillItem(
            skill_name="Java",
            category_code=RadixCategoryCode.COD,
            evidence="Core Java development",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        )
    ])
    cand = CandidateProfile(skills=[])

    result = SkillMatchingEngine.match(jd, cand)

    assert result.match_score == 0.0
    assert result.matched_count == 0
    assert result.missing_count == 1
    assert result.missing_skills[0].is_required is True


def test_evidence_preservation():
    """JD evidence quotes must be preserved in both matched and missing skill reports."""
    python_evidence = "Develop microservices in Python 3.11"
    aws_evidence = "Deploy services to AWS ECS"

    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence=python_evidence,
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="AWS",
            category_code=RadixCategoryCode.CLOUD,
            evidence=aws_evidence,
            confidence=ConfidenceLevel.MEDIUM,
            requirement_type=RequirementType.PREFERRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    cand = CandidateProfile(skills=[CandidateSkill(skill_name="Python")])
    result = SkillMatchingEngine.match(jd, cand)

    # Matched skill retains evidence
    assert len(result.matched_skills) == 1
    assert result.matched_skills[0].jd_evidence == python_evidence

    # Missing skill retains evidence
    assert len(result.missing_skills) == 1
    assert result.missing_skills[0].jd_evidence == aws_evidence


def test_category_breakdown_calculation():
    """Verify category scores accurately compute per-category percentages."""
    jd = create_sample_jd([
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Python backend",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="Go",
            category_code=RadixCategoryCode.COD,
            evidence="Go concurrency",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
        SkillItem(
            skill_name="Docker",
            category_code=RadixCategoryCode.CLOUD,
            evidence="Docker containers",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        ),
    ])

    # Candidate has Python (COD) and Docker (CLOUD), but lacks Go (COD)
    cand = CandidateProfile(
        skills=[
            CandidateSkill(skill_name="Python"),
            CandidateSkill(skill_name="Docker"),
        ]
    )

    result = SkillMatchingEngine.match(jd, cand)

    # COD: 1 of 2 matched -> 50.0%
    # CLOUD: 1 of 1 matched -> 100.0%
    cat_map = {c.category_code: c for c in result.category_breakdown}
    assert "COD" in cat_map
    assert "CLOUD" in cat_map
    assert cat_map["COD"].score_percentage == 50.0
    assert cat_map["CLOUD"].score_percentage == 100.0


# ============================================================================
# API Integration Tests
# ============================================================================

def test_matching_health_endpoint():
    """GET /api/v1/skill-matching/health should return 200 ready."""
    client = TestClient(app)
    response = client.get("/api/v1/skill-matching/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["service"] == "skill-matching"


def test_match_api_endpoint_success():
    """POST /api/v1/skill-matching/match should calculate and return matching result."""
    client = TestClient(app)

    payload = {
        "job_description": {
            "source_type": "jd",
            "source_file": "backend_dev.pdf",
            "company": "TechStart Inc",
            "role": "Senior Engineer",
            "skills": [
                {
                    "skill_name": "Python",
                    "category_code": "COD",
                    "evidence": "High proficiency with Python",
                    "confidence": "high",
                    "requirement_type": "required",
                    "requirement_strength": "explicit"
                },
                {
                    "skill_name": "PostgreSQL",
                    "category_code": "SQL",
                    "evidence": "Write complex SQL queries",
                    "confidence": "high",
                    "requirement_type": "preferred",
                    "requirement_strength": "explicit"
                }
            ]
        },
        "candidate_profile": {
            "candidate_id": "cand_999",
            "candidate_name": "Sarah Connor",
            "skills": [
                {"skill_name": "python", "category_code": "COD"},
                {"skill_name": "react", "category_code": "COD"}
            ]
        }
    }

    response = client.post("/api/v1/skill-matching/match", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "match_score" in data
    # Python is required (3.0), SQL is preferred (1.0). Total 4.0.
    # Candidate matches Python -> 3.0 / 4.0 = 75.0%
    assert data["match_score"] == 75.0
    assert data["matched_count"] == 1
    assert data["missing_count"] == 1
    assert data["matched_skills"][0]["skill_name"] == "Python"
    assert data["missing_skills"][0]["skill_name"] == "PostgreSQL"
    assert "react" in [s.lower() for s in data["additional_candidate_skills"]]


def test_match_api_validation_error():
    """POST /api/v1/skill-matching/match with invalid structure returns 422."""
    client = TestClient(app)
    # Missing candidate_profile
    invalid_payload = {
        "job_description": {
            "source_type": "jd",
            "source_file": "test.pdf",
            "skills": []
        }
    }
    response = client.post("/api/v1/skill-matching/match", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
