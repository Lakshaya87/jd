import pytest
from app.exceptions import ExtractionServiceUnavailableError
from app.schemas import (
    ConfidenceLevel,
    RadixCategoryCode,
    RequirementStrength,
    RequirementType,
    SkillItem,
)
from app.services.jd_analyzer import (
    DeterministicSkillExtractor,
    JobDescriptionAnalyzer,
)
from app.services.llm_extractor import MockLLMExtractor
from app.services.normalization import deduplicate_and_merge_skills


def test_implied_skill_extraction():
    text = (
        "In this role, you will work with relational data and write complex queries. "
        "You will design scalable services that communicate over HTTP. "
        "Additionally, you will build predictive models from large customer datasets "
        "and investigate algorithmic complexity to optimize data structures."
    )
    skills = DeterministicSkillExtractor.extract_skills(text)
    skill_names = {s.skill_name for s in skills}
    categories = {s.category_code for s in skills}

    assert "SQL" in skill_names
    assert RadixCategoryCode.SQL in categories
    assert "System Design" in skill_names
    assert RadixCategoryCode.SYSD in categories
    assert "Machine Learning" in skill_names
    assert RadixCategoryCode.AI in categories
    assert "Data Structures & Algorithms" in skill_names
    assert RadixCategoryCode.DSA in categories

    # Verify requirement_strength is implied
    for s in skills:
        if s.skill_name in ["SQL", "System Design", "Machine Learning"]:
            assert s.requirement_strength == RequirementStrength.IMPLIED
            assert len(s.evidence) > 0


def test_explicit_vs_implied_and_requirement_classification(sample_backend_jd_text):
    skills = DeterministicSkillExtractor.extract_skills(sample_backend_jd_text)
    skill_dict = {s.skill_name: s for s in skills}

    # Python is in Requirements section
    assert "Python" in skill_dict
    assert skill_dict["Python"].requirement_strength == RequirementStrength.EXPLICIT
    assert skill_dict["Python"].requirement_type == RequirementType.REQUIRED
    assert skill_dict["Python"].category_code == RadixCategoryCode.COD

    # Machine Learning is in Preferred section
    assert "Machine Learning" in skill_dict
    assert skill_dict["Machine Learning"].requirement_type == RequirementType.PREFERRED
    assert skill_dict["Machine Learning"].category_code == RadixCategoryCode.AI


def test_duplicate_skill_normalization():
    skills = [
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Short Python mention",
            confidence=ConfidenceLevel.LOW,
            requirement_type=RequirementType.UNSPECIFIED,
            requirement_strength=RequirementStrength.IMPLIED
        ),
        SkillItem(
            skill_name="Python",
            category_code=RadixCategoryCode.COD,
            evidence="Strong Python experience developing distributed microservices",
            confidence=ConfidenceLevel.HIGH,
            requirement_type=RequirementType.REQUIRED,
            requirement_strength=RequirementStrength.EXPLICIT
        )
    ]
    merged = deduplicate_and_merge_skills(skills)
    assert len(merged) == 1
    assert merged[0].confidence == ConfidenceLevel.HIGH
    assert merged[0].requirement_type == RequirementType.REQUIRED
    assert merged[0].requirement_strength == RequirementStrength.EXPLICIT
    assert "Strong Python experience" in merged[0].evidence


def test_company_and_role_extraction():
    text = (
        "Company: Acme Cloud Solutions\n"
        "Job Title: Senior Distributed Systems Architect\n\n"
        "About the role: Build global infrastructure."
    )
    company, role = DeterministicSkillExtractor.extract_company_and_role(text)
    assert company == "Acme Cloud Solutions"
    assert role == "Senior Distributed Systems Architect"


def test_null_company_and_role_when_unidentifiable():
    text = "We are seeking a developer who can write code and solve problems. No company or title stated."
    company, role = DeterministicSkillExtractor.extract_company_and_role(text)
    assert company is None
    assert role is None


@pytest.mark.asyncio
async def test_analyzer_with_mock_llm():
    mock_extractor = MockLLMExtractor()
    analyzer = JobDescriptionAnalyzer(llm_extractor=mock_extractor, allow_fallback=False)
    response = await analyzer.analyze(
        text="Any input text",
        filename="test_jd.pdf"
    )
    assert response.source_file == "test_jd.pdf"
    assert response.company == "TechCorp Global"
    assert response.role == "Senior Backend Engineer"
    assert len(response.skills) == 2


@pytest.mark.asyncio
async def test_analyzer_llm_failure_with_fallback_allowed(sample_backend_jd_text):
    mock_extractor = MockLLMExtractor(fail_with_timeout=True)
    analyzer = JobDescriptionAnalyzer(llm_extractor=mock_extractor, allow_fallback=True)
    response = await analyzer.analyze(
        text=sample_backend_jd_text,
        filename="backend_jd.pdf"
    )
    assert response.source_file == "backend_jd.pdf"
    assert response.company == "Acme Cloud Solutions"
    assert len(response.skills) > 0


@pytest.mark.asyncio
async def test_analyzer_llm_failure_with_fallback_disallowed():
    mock_extractor = MockLLMExtractor(fail_with_timeout=True)
    analyzer = JobDescriptionAnalyzer(llm_extractor=mock_extractor, allow_fallback=False)
    with pytest.raises(ExtractionServiceUnavailableError):
        await analyzer.analyze(
            text="Some input text",
            filename="backend_jd.pdf"
        )
