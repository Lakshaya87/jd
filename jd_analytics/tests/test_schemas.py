import pytest
from pydantic import ValidationError

from app.schemas import (
    ConfidenceLevel,
    JobDescriptionResponse,
    RadixCategoryCode,
    RequirementStrength,
    RequirementType,
    SkillItem,
)


def test_all_13_radix_categories_valid():
    """Verify that all 12 named categories + OTHER are strictly supported."""
    expected_codes = [
        "COD", "DSA", "OOD", "APTI", "COMM", "AI",
        "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS", "OTHER"
    ]
    for code in expected_codes:
        category = RadixCategoryCode(code)
        item = SkillItem(
            skill_name="Test Skill",
            category_code=category,
            evidence="Required experience with testing",
            confidence=ConfidenceLevel.HIGH
        )
        assert item.category_code == code


def test_reject_invalid_category_code():
    with pytest.raises(ValidationError):
        SkillItem(
            skill_name="Docker",
            category_code="DEVOPS_INVALID",  # Invalid category
            evidence="Docker experience",
            confidence="high"
        )


def test_reject_invalid_confidence():
    with pytest.raises(ValidationError):
        SkillItem(
            skill_name="Python",
            category_code="COD",
            evidence="5 years Python",
            confidence="super_high"  # Invalid confidence
        )


def test_missing_required_skill_fields():
    # Missing evidence
    with pytest.raises(ValidationError):
        SkillItem(
            skill_name="Python",
            category_code="COD",
            confidence="high"
        )

    # Missing skill_name
    with pytest.raises(ValidationError):
        SkillItem(
            category_code="COD",
            evidence="Evidence",
            confidence="high"
        )

    # Empty string skill_name
    with pytest.raises(ValidationError):
        SkillItem(
            skill_name="   ",
            category_code="COD",
            evidence="Evidence",
            confidence="high"
        )


def test_shared_contract_compliance():
    response = JobDescriptionResponse(
        source_type="jd",
        source_file="backend_developer_jd.pdf",
        company="Example Company",
        role="Backend Developer",
        skills=[
            SkillItem(
                skill_name="Python",
                category_code=RadixCategoryCode.COD,
                evidence="Develop backend services using Python",
                confidence=ConfidenceLevel.HIGH,
                requirement_type=RequirementType.REQUIRED,
                requirement_strength=RequirementStrength.EXPLICIT
            ),
            SkillItem(
                skill_name="SQL",
                category_code=RadixCategoryCode.SQL,
                evidence="Experience working with relational databases",
                confidence=ConfidenceLevel.MEDIUM,
                requirement_type=RequirementType.UNSPECIFIED,
                requirement_strength=RequirementStrength.IMPLIED
            )
        ]
    )

    data = response.model_dump()
    assert data["source_type"] == "jd"
    assert data["source_file"] == "backend_developer_jd.pdf"
    assert data["company"] == "Example Company"
    assert data["role"] == "Backend Developer"
    assert len(data["skills"]) == 2
    assert data["skills"][0]["skill_name"] == "Python"
    assert data["skills"][0]["category_code"] == "COD"
    assert data["skills"][0]["requirement_type"] == "required"
    assert data["skills"][1]["requirement_strength"] == "implied"


def test_nullable_company_and_role():
    response = JobDescriptionResponse(
        source_type="jd",
        source_file="anonymous_jd.pdf",
        company=None,
        role=None,
        skills=[]
    )
    data = response.model_dump()
    assert data["company"] is None
    assert data["role"] is None
    assert data["skills"] == []


def test_reject_invalid_source_type():
    with pytest.raises(ValidationError):
        JobDescriptionResponse(
            source_type="resume",  # Must be 'jd'
            source_file="file.pdf",
            skills=[]
        )
