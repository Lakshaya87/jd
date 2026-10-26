from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RadixCategoryCode(str, Enum):
    """
    Exact RADIX skill category codes as required by the shared specification.
    Do not rename or alter these codes.
    """
    COD = "COD"      # Coding
    DSA = "DSA"      # Data Structures & Algorithms
    OOD = "OOD"      # Object-Oriented Design
    APTI = "APTI"    # Aptitude
    COMM = "COMM"    # Communication
    AI = "AI"        # AI / Machine Learning
    CLOUD = "CLOUD"  # Cloud
    SQL = "SQL"      # SQL & Relational Databases
    SWE = "SWE"      # Software Engineering & Tooling
    SYSD = "SYSD"    # System Design & Architecture
    NETW = "NETW"    # Networking & Protocols
    OS = "OS"        # Operating Systems & Systems Programming
    OTHER = "OTHER"  # Skills that do not fit the categories above


RADIX_CATEGORY_DESCRIPTIONS = {
    RadixCategoryCode.COD: "Coding (Programming Languages, Scripting)",
    RadixCategoryCode.DSA: "Data Structures & Algorithms",
    RadixCategoryCode.OOD: "Object-Oriented Design & Patterns",
    RadixCategoryCode.APTI: "Aptitude & Problem Solving",
    RadixCategoryCode.COMM: "Communication & Collaboration",
    RadixCategoryCode.AI: "AI, Machine Learning, Data Science",
    RadixCategoryCode.CLOUD: "Cloud Platforms & Infrastructure (AWS, GCP, Azure, Docker, K8s)",
    RadixCategoryCode.SQL: "SQL & Relational Databases (PostgreSQL, MySQL, RDBMS)",
    RadixCategoryCode.SWE: "Software Engineering, CI/CD, Git, Testing",
    RadixCategoryCode.SYSD: "System Design, Microservices, Scalability, Distributed Systems",
    RadixCategoryCode.NETW: "Networking, HTTP/HTTPS, WebSockets, TCP/IP, REST/gRPC",
    RadixCategoryCode.OS: "Operating Systems, Linux, Concurrency, Threads, Memory",
    RadixCategoryCode.OTHER: "Skills that do not fit the categories above"
}


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementType(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    UNSPECIFIED = "unspecified"


class RequirementStrength(str, Enum):
    EXPLICIT = "explicit"
    IMPLIED = "implied"


class SkillItem(BaseModel):
    """
    Standardized skill object complying with the RADIX shared specification.
    Required fields:
      - skill_name
      - category_code
      - evidence
      - confidence
    Documented extension fields:
      - requirement_type
      - requirement_strength
    """
    skill_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Clear, concise skill name."
    )
    category_code: RadixCategoryCode = Field(
        ...,
        description="One of the 13 authorized RADIX category codes."
    )
    evidence: str = Field(
        ...,
        min_length=1,
        max_length=600,
        description="Short quotation or explanation grounded directly in the job description."
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level: high, medium, or low."
    )
    requirement_type: RequirementType = Field(
        default=RequirementType.UNSPECIFIED,
        description="Extension field: required, preferred, or unspecified."
    )
    requirement_strength: RequirementStrength = Field(
        default=RequirementStrength.EXPLICIT,
        description="Extension field: explicit or implied."
    )

    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid"
    )

    @field_validator("skill_name")
    @classmethod
    def clean_skill_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("skill_name cannot be empty or only whitespace")
        return cleaned

    @field_validator("evidence")
    @classmethod
    def clean_evidence(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("evidence cannot be empty or only whitespace")
        return cleaned


class JobDescriptionResponse(BaseModel):
    """
    Mandatory shared JSON contract for Role 1: JD Analytics.
    source_type is always 'jd'.
    company and role may be null if not reliably identified.
    skills is always an array of SkillItem.
    """
    source_type: Literal["jd"] = Field(
        default="jd",
        description="Must always be 'jd'."
    )
    source_file: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Sanitized display name of the uploaded job description file."
    )
    company: Optional[str] = Field(
        default=None,
        description="Employer company name if reliably identifiable, otherwise null."
    )
    role: Optional[str] = Field(
        default=None,
        description="Job title/role name if reliably identifiable, otherwise null."
    )
    skills: List[SkillItem] = Field(
        default_factory=list,
        description="List of extracted, validated skills categorized with RADIX codes."
    )

    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid"
    )

    @field_validator("source_file")
    @classmethod
    def clean_source_file(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("source_file cannot be empty")
        return cleaned


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation")
    field: Optional[str] = Field(default=None, description="Request field causing the error, if applicable")


class ErrorResponse(BaseModel):
    """
    Consistent, machine-readable error response format.
    """
    success: Literal[False] = False
    error: ErrorDetail

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    version: str
    service: Literal["jd-analytics"] = "jd-analytics"


class ModuleReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    service: Literal["jd-analytics"] = "jd-analytics"
    version: str
    llm_enabled: bool
    llm_provider: str
    llm_configured: bool
    deterministic_fallback_enabled: bool
    supported_formats: List[str] = ["pdf", "docx"]
    max_upload_size_mb: int


class ValidationSuccessResponse(BaseModel):
    valid: Literal[True] = True
    message: str = "Job description payload conforms to the RADIX contract."
    skill_count: int
    categories_present: List[str]


class ValidationFailureResponse(BaseModel):
    valid: Literal[False] = False
    message: str = "Job description payload failed validation."
    errors: List[dict]
