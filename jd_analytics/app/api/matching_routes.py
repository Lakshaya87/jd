import logging
from fastapi import APIRouter, status

from app.services.matching_engine import (
    MatchRequest,
    MatchResultResponse,
    SkillMatchingEngine,
)

logger = logging.getLogger("jd_analytics.matching_api")

matching_router = APIRouter(
    prefix="/api/v1/skill-matching",
    tags=["Skill Matching"]
)


@matching_router.get(
    "/health",
    summary="Skill Matching service health and capability probe",
    status_code=status.HTTP_200_OK
)
async def matching_health():
    """
    Returns the readiness status of the Role 5 Skill Matching engine.
    """
    return {
        "status": "ready",
        "service": "skill-matching",
        "version": "1.0.0",
        "description": "RADIX Role 5 Skill Matching and Compatibility Engine"
    }


@matching_router.post(
    "/match",
    response_model=MatchResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate skill compatibility and gap analysis between JD and Candidate",
    description=(
        "Consumes Role 1 JobDescriptionResponse and a CandidateProfile, "
        "calculates weighted compatibility scores (factoring required vs preferred skills "
        "and extraction confidence), preserves JD evidence, and returns category breakdown."
    )
)
async def match_skills(payload: MatchRequest) -> MatchResultResponse:
    """
    Executes skill matching and returns a detailed gap analysis report.
    """
    logger.info(
        f"Evaluating match for candidate '{payload.candidate_profile.candidate_id}' "
        f"against JD '{payload.job_description.source_file}' with {len(payload.job_description.skills)} skills."
    )
    result = SkillMatchingEngine.match(
        job_description=payload.job_description,
        candidate_profile=payload.candidate_profile
    )
    return result
