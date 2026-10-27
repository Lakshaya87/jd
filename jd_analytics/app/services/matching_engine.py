import logging
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.schemas import (
    ConfidenceLevel,
    JobDescriptionResponse,
    RADIX_CATEGORY_DESCRIPTIONS,
    RadixCategoryCode,
    RequirementType,
    SkillItem,
)
from app.services.normalization import CANONICAL_SKILL_MAP

logger = logging.getLogger("jd_analytics.matching")

# Base weights for requirement types
REQUIREMENT_WEIGHTS: Dict[RequirementType, float] = {
    RequirementType.REQUIRED: 3.0,
    RequirementType.UNSPECIFIED: 2.0,
    RequirementType.PREFERRED: 1.0,
}

# Multipliers for confidence levels
CONFIDENCE_MULTIPLIERS: Dict[ConfidenceLevel, float] = {
    ConfidenceLevel.HIGH: 1.0,
    ConfidenceLevel.MEDIUM: 0.8,
    ConfidenceLevel.LOW: 0.5,
}


def normalize_skill_string(raw_name: str) -> str:
    """
    Normalizes a skill string to its canonical representation using CANONICAL_SKILL_MAP.
    Falls back to lowercased trimmed string if not found in dictionary.
    """
    cleaned = raw_name.strip().lower()
    if cleaned in CANONICAL_SKILL_MAP:
        return CANONICAL_SKILL_MAP[cleaned][0].strip().lower()
    return cleaned


# ============================================================================
# Candidate Profile Schemas (Role 3 Boundary)
#
# Assumptions:
# 1. Role 3 (Profile Builder) is pending team implementation.
# 2. We keep the candidate model minimal and resilient (extra="ignore")
#    so future fields from Role 3 (e.g., certifications, education, source)
#    do not break validation.
# ============================================================================

class CandidateSkill(BaseModel):
    """
    Skill possessed by a candidate.
    """
    skill_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Name of the skill possessed by the candidate."
    )
    category_code: Optional[RadixCategoryCode] = Field(
        default=None,
        description="Optional RADIX category code; inferred if omitted."
    )
    proficiency: Optional[str] = Field(
        default=None,
        description="Optional proficiency rating (e.g. beginner, intermediate, advanced)."
    )
    years_of_experience: Optional[float] = Field(
        default=None,
        ge=0,
        description="Optional years of verified or self-reported experience."
    )

    model_config = ConfigDict(
        use_enum_values=True,
        extra="ignore"
    )


class CandidateProfile(BaseModel):
    """
    Minimal candidate representation consumed by Role 5.
    """
    candidate_id: Optional[str] = Field(
        default="candidate_1",
        description="Unique identifier for the candidate."
    )
    candidate_name: Optional[str] = Field(
        default=None,
        description="Full name of the candidate, if available."
    )
    skills: List[CandidateSkill] = Field(
        default_factory=list,
        description="List of skills possessed by the candidate."
    )

    model_config = ConfigDict(
        use_enum_values=True,
        extra="ignore"
    )


# ============================================================================
# Match Output Schemas
# ============================================================================

class MatchedSkillDetail(BaseModel):
    skill_name: str
    category_code: str
    requirement_type: str
    confidence: str
    jd_evidence: str
    candidate_matched_name: str
    weight: float
    earned_score: float


class MissingSkillDetail(BaseModel):
    skill_name: str
    category_code: str
    requirement_type: str
    confidence: str
    jd_evidence: str
    penalty_weight: float
    is_required: bool


class CategoryMatchScore(BaseModel):
    category_code: str
    category_name: str
    total_skills: int
    matched_skills: int
    score_percentage: float


class MatchResultResponse(BaseModel):
    """
    Comprehensive match result returned by Role 5: Skill Matching.
    """
    match_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall match percentage from 0.0 to 100.0"
    )
    total_jd_skills: int = Field(..., description="Total skills specified in the job description")
    matched_count: int = Field(..., description="Number of required/preferred skills matched")
    missing_count: int = Field(..., description="Number of required/preferred skills missing")
    matched_skills: List[MatchedSkillDetail] = Field(default_factory=list)
    missing_skills: List[MissingSkillDetail] = Field(default_factory=list)
    category_breakdown: List[CategoryMatchScore] = Field(default_factory=list)
    additional_candidate_skills: List[str] = Field(
        default_factory=list,
        description="Candidate skills not explicitly requested by the job description"
    )
    summary: str = Field(..., description="Human-readable summary of the match evaluation")


class MatchRequest(BaseModel):
    """
    Payload required to execute a skill match evaluation.
    """
    job_description: JobDescriptionResponse
    candidate_profile: CandidateProfile


# ============================================================================
# Core Scoring Engine
# ============================================================================

class SkillMatchingEngine:
    """
    Deterministic scoring and gap analysis engine for Role 5.
    """

    @staticmethod
    def calculate_skill_weight(skill: SkillItem) -> float:
        """
        Calculates effective weight for a JD skill based on requirement_type and confidence.
        """
        base_weight = REQUIREMENT_WEIGHTS.get(skill.requirement_type, 2.0)
        multiplier = CONFIDENCE_MULTIPLIERS.get(skill.confidence, 1.0)
        return round(base_weight * multiplier, 3)

    @classmethod
    def match(
        cls,
        job_description: JobDescriptionResponse,
        candidate_profile: CandidateProfile
    ) -> MatchResultResponse:
        """
        Performs skill matching and scoring between a JD and a candidate profile.
        """
        jd_skills = job_description.skills

        # Guard: Empty Job Description should NOT return 100% match
        if not jd_skills:
            return MatchResultResponse(
                match_score=0.0,
                total_jd_skills=0,
                matched_count=0,
                missing_count=0,
                matched_skills=[],
                missing_skills=[],
                category_breakdown=[],
                additional_candidate_skills=[s.skill_name for s in candidate_profile.skills],
                summary="The job description contains no extractable skills to evaluate against."
            )

        # Build candidate lookup index: normalized_name -> CandidateSkill
        candidate_lookup: Dict[str, CandidateSkill] = {}
        for c_skill in candidate_profile.skills:
            norm_c = normalize_skill_string(c_skill.skill_name)
            if norm_c not in candidate_lookup:
                candidate_lookup[norm_c] = c_skill

        matched_skills: List[MatchedSkillDetail] = []
        missing_skills: List[MissingSkillDetail] = []
        matched_candidate_keys: Set[str] = set()

        total_weight = 0.0
        earned_weight = 0.0

        # Per-category accumulators: category_code -> (total_w, earned_w, total_cnt, match_cnt)
        cat_stats: Dict[str, Dict[str, float]] = {}

        for jd_skill in jd_skills:
            weight = cls.calculate_skill_weight(jd_skill)
            total_weight += weight

            cat_code = (
                jd_skill.category_code
                if isinstance(jd_skill.category_code, str)
                else jd_skill.category_code.value
            )

            if cat_code not in cat_stats:
                cat_stats[cat_code] = {
                    "total_weight": 0.0,
                    "earned_weight": 0.0,
                    "total_count": 0,
                    "matched_count": 0,
                }
            cat_stats[cat_code]["total_weight"] += weight
            cat_stats[cat_code]["total_count"] += 1

            norm_jd = normalize_skill_string(jd_skill.skill_name)

            # Check for direct match on normalized name
            matched_c_skill: Optional[CandidateSkill] = None
            matched_key: Optional[str] = None

            if norm_jd in candidate_lookup:
                matched_c_skill = candidate_lookup[norm_jd]
                matched_key = norm_jd
            else:
                # Fallback: Check if raw lowercase names match directly
                raw_jd = jd_skill.skill_name.strip().lower()
                for c_norm, c_sk in candidate_lookup.items():
                    if c_sk.skill_name.strip().lower() == raw_jd:
                        matched_c_skill = c_sk
                        matched_key = c_norm
                        break

            if matched_c_skill is not None:
                earned_weight += weight
                cat_stats[cat_code]["earned_weight"] += weight
                cat_stats[cat_code]["matched_count"] += 1
                if matched_key:
                    matched_candidate_keys.add(matched_key)

                matched_skills.append(
                    MatchedSkillDetail(
                        skill_name=jd_skill.skill_name,
                        category_code=cat_code,
                        requirement_type=(
                            jd_skill.requirement_type
                            if isinstance(jd_skill.requirement_type, str)
                            else jd_skill.requirement_type.value
                        ),
                        confidence=(
                            jd_skill.confidence
                            if isinstance(jd_skill.confidence, str)
                            else jd_skill.confidence.value
                        ),
                        jd_evidence=jd_skill.evidence,
                        candidate_matched_name=matched_c_skill.skill_name,
                        weight=weight,
                        earned_score=weight
                    )
                )
            else:
                is_req = (jd_skill.requirement_type == RequirementType.REQUIRED)
                missing_skills.append(
                    MissingSkillDetail(
                        skill_name=jd_skill.skill_name,
                        category_code=cat_code,
                        requirement_type=(
                            jd_skill.requirement_type
                            if isinstance(jd_skill.requirement_type, str)
                            else jd_skill.requirement_type.value
                        ),
                        confidence=(
                            jd_skill.confidence
                            if isinstance(jd_skill.confidence, str)
                            else jd_skill.confidence.value
                        ),
                        jd_evidence=jd_skill.evidence,
                        penalty_weight=weight,
                        is_required=is_req
                    )
                )

        # Calculate final overall score
        if total_weight > 0:
            raw_score = (earned_weight / total_weight) * 100.0
            match_score = round(min(100.0, max(0.0, raw_score)), 2)
        else:
            match_score = 0.0

        # Calculate per-category breakdown
        category_breakdown: List[CategoryMatchScore] = []
        for c_code, stats in sorted(cat_stats.items()):
            c_tot_w = stats["total_weight"]
            c_ear_w = stats["earned_weight"]
            pct = round((c_ear_w / c_tot_w) * 100.0, 2) if c_tot_w > 0 else 0.0

            # Friendly name lookup
            try:
                radix_enum = RadixCategoryCode(c_code)
                friendly_desc = RADIX_CATEGORY_DESCRIPTIONS.get(radix_enum, c_code)
            except ValueError:
                friendly_desc = c_code

            category_breakdown.append(
                CategoryMatchScore(
                    category_code=c_code,
                    category_name=friendly_desc,
                    total_skills=int(stats["total_count"]),
                    matched_skills=int(stats["matched_count"]),
                    score_percentage=pct
                )
            )

        # Additional candidate skills not matched to JD
        additional_skills: List[str] = [
            c_skill.skill_name
            for norm_key, c_skill in candidate_lookup.items()
            if norm_key not in matched_candidate_keys
        ]

        # Generate summary
        matched_cnt = len(matched_skills)
        missing_cnt = len(missing_skills)
        cand_name = candidate_profile.candidate_name or candidate_profile.candidate_id or "Candidate"
        summary = (
            f"{cand_name} matches {matched_cnt} of {len(jd_skills)} required/preferred skills "
            f"with an overall compatibility score of {match_score:.1f}%."
        )

        return MatchResultResponse(
            match_score=match_score,
            total_jd_skills=len(jd_skills),
            matched_count=matched_cnt,
            missing_count=missing_cnt,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            category_breakdown=category_breakdown,
            additional_candidate_skills=additional_skills,
            summary=summary
        )
