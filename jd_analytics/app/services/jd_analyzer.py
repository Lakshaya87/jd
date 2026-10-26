import logging
import re
from typing import Dict, List, Optional, Tuple

from app.config import settings
from app.exceptions import ExtractionServiceUnavailableError
from app.schemas import (
    ConfidenceLevel,
    JobDescriptionResponse,
    RadixCategoryCode,
    RequirementStrength,
    RequirementType,
    SkillItem,
)
from app.services.llm_extractor import BaseLLMExtractor, get_llm_extractor
from app.services.normalization import (
    CANONICAL_SKILL_MAP,
    deduplicate_and_merge_skills,
    normalize_category_code,
)

logger = logging.getLogger("jd_analytics")


class ImpliedPattern:
    """
    Defines contextual phrases that strongly imply a specific technical skill.
    """
    def __init__(
        self,
        pattern: str,
        skill_name: str,
        category_code: RadixCategoryCode,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    ):
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.skill_name = skill_name
        self.category_code = category_code
        self.confidence = confidence


# Implied capability patterns (as specified in hackathon requirements)
IMPLIED_SKILL_PATTERNS = [
    ImpliedPattern(
        r"(?:write|compose|craft)\s+complex\s+queries|work\s+with\s+relational\s+data|relational\s+data\s+modeling|query\s+tuning|schema\s+migrations",
        "SQL",
        RadixCategoryCode.SQL,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"scalable\s+services(?:\s+that\s+communicate)?\s+over\s+http|design\s+(?:robust|scalable)\s+apis",
        "System Design",
        RadixCategoryCode.SYSD,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"communicate\s+over\s+http|http(?:\/https)?\s+endpoints|restful\s+endpoints",
        "HTTP / HTTPS",
        RadixCategoryCode.NETW,
        ConfidenceLevel.MEDIUM
    ),
    ImpliedPattern(
        r"build\s+predictive\s+models|train\s+(?:deep\s+learning|ml)\s+models|evaluate\s+model\s+performance",
        "Machine Learning",
        RadixCategoryCode.AI,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"investigate\s+algorithmic\s+complexity|optimize\s+(?:computational\s+complexity|runtime\s+complexity)|big-?o\s+analysis",
        "Data Structures & Algorithms",
        RadixCategoryCode.DSA,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"object[- ]oriented\s+(?:design|principles|programming)|apply\s+design\s+patterns|solid\s+principles",
        "Object-Oriented Design",
        RadixCategoryCode.OOD,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"break\s+down\s+complex\s+technical\s+concepts|present\s+to\s+stakeholders|strong\s+written\s+and\s+verbal\s+communication",
        "Communication",
        RadixCategoryCode.COMM,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"analytical\s+(?:mindset|thinking|reasoning)|strong\s+problem[- ]solving\s+aptitude",
        "Aptitude",
        RadixCategoryCode.APTI,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"deploy\s+(?:containerized|cloud)\s+applications|manage\s+cloud\s+resources|container\s+orchestration",
        "Cloud Infrastructure",
        RadixCategoryCode.CLOUD,
        ConfidenceLevel.MEDIUM
    ),
    ImpliedPattern(
        r"automate\s+build\s+and\s+deployment|write\s+unit\s+and\s+integration\s+tests|conduct\s+code\s+reviews",
        "Software Engineering",
        RadixCategoryCode.SWE,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"concurrent\s+programming|thread\s+safety|race\s+conditions|process\s+synchronization",
        "Concurrency & Multithreading",
        RadixCategoryCode.OS,
        ConfidenceLevel.HIGH
    ),
    ImpliedPattern(
        r"network\s+sockets|socket\s+programming|packet\s+analysis|ip\s+routing",
        "Networking",
        RadixCategoryCode.NETW,
        ConfidenceLevel.MEDIUM
    ),
]


class DeterministicSkillExtractor:
    """
    Robust, deterministic skill and metadata extractor for offline or fallback operation.
    Implements:
      - Contextual section parsing (Requirements vs Nice-to-Have)
      - Implied skill extraction using semantic capability patterns
      - Explicit technology identification with dictionary canonicalization
      - Grounded evidence quotation extraction
      - Company and Role identification
    """

    @classmethod
    def extract_company_and_role(
        cls,
        text: str,
        doc_metadata: Optional[Dict[str, Optional[str]]] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract employer company name and job title using explicit headers,
        document metadata, and strict pattern heuristics. Returns (None, None)
        if not reliably identifiable.
        """
        company: Optional[str] = None
        role: Optional[str] = None

        doc_metadata = doc_metadata or {}
        doc_title = doc_metadata.get("title")

        # 1. Look for explicit company patterns (single-line match)
        company_patterns = [
            r"^[ \t]*(?:Company|Employer|Organization|About\s+(?:the\s+)?Company)\s*[:\-–]\s*([A-Za-z0-9&.,' ]{2,50})",
            r"(?:At|About)\s+([A-Z][A-Za-z0-9&., ]{2,40}),\s+we\s+(?:are|build|create|innovate)",
            r"Welcome\s+to\s+([A-Z][A-Za-z0-9&., ]{2,40})[!.]"
        ]

        for pat in company_patterns:
            match = re.search(pat, text, re.MULTILINE)
            if match:
                candidate = match.group(1).strip().strip(".,:;-\n\r")
                # Filter out generic words
                if candidate.lower() not in ["the company", "us", "our team", "a fast-growing startup", "an exciting company"]:
                    company = candidate
                    break

        # 2. Look for explicit role / job title patterns (single-line match)
        role_patterns = [
            r"^[ \t]*(?:Job\s+Title|Position|Role|Opening)\s*[:\-–]\s*([A-Za-z0-9/,&.,\-\(\) ]{3,70})",
            r"(?:We\s+are\s+looking\s+for\s+(?:a|an)|Hiring)\s+([A-Z][A-Za-z0-9/,&.,\-\(\) ]{3,60})(?:\s+to\s+join|\.|\n|$)",
        ]

        for pat in role_patterns:
            match = re.search(pat, text, re.MULTILINE)
            if match:
                candidate = match.group(1).strip().strip(".,:;-\n")
                if len(candidate) >= 3 and "\n" not in candidate:
                    role = candidate
                    break

        # Check first line if it looks like a clean job title (e.g. "Senior Backend Developer")
        if not role:
            first_lines = [l.strip() for l in text.split("\n") if l.strip()][:3]
            for line in first_lines:
                if re.match(r"^(?:Senior |Junior |Lead |Staff |Principal )?(?:Backend|Frontend|Full[- ]?Stack|Software|Data|DevOps|Systems|Cloud|ML|AI)\s+(?:Engineer|Developer|Architect|Scientist)$", line, re.IGNORECASE):
                    role = line
                    break

        # Fallback to document title metadata if it matches a role pattern
        if not role and doc_title and len(doc_title.strip()) < 80:
            if any(term in doc_title.lower() for term in ["engineer", "developer", "architect", "analyst", "manager"]):
                role = doc_title.strip()

        return company, role

    @classmethod
    def _extract_sentence_evidence(cls, text: str, start_pos: int, end_pos: int) -> str:
        """
        Extracts the surrounding sentence or bullet point as grounded evidence.
        """
        # Look backwards for newline or sentence end
        left = max(0, start_pos - 120)
        prefix = text[left:start_pos]
        split_left = re.split(r"[\n\r•\-\*]|\.\s+", prefix)
        start_snippet = split_left[-1]

        # Look forwards for newline or sentence end
        right = min(len(text), end_pos + 120)
        suffix = text[end_pos:right]
        split_right = re.split(r"[\n\r•\-\*]|\.\s+", suffix)
        end_snippet = split_right[0]

        evidence = (start_snippet + text[start_pos:end_pos] + end_snippet).strip()
        # Clean up punctuation and whitespace
        evidence = re.sub(r"\s+", " ", evidence).strip("• -*#")
        return evidence[:300] if len(evidence) > 300 else evidence

    @classmethod
    def _detect_requirement_type(cls, text_before_match: str) -> RequirementType:
        """
        Inspects the nearest preceding section header to determine if a skill is
        'required', 'preferred', or 'unspecified'.
        """
        # Take the nearest preceding 500 characters
        context = text_before_match[-500:].lower()
        
        # Check for preferred headers
        preferred_markers = [
            "preferred qualifications",
            "nice to have",
            "bonus points",
            "bonus qualifications",
            "good to have",
            "plus if you have",
            "preferred skills",
            "desired qualifications",
            "bonus:"
        ]
        
        # Check for required headers
        required_markers = [
            "minimum qualifications",
            "basic qualifications",
            "required qualifications",
            "requirements",
            "must have",
            "what you need",
            "what you'll bring",
            "responsibilities",
            "required skills",
            "must-have"
        ]

        last_pref_pos = -1
        for marker in preferred_markers:
            pos = context.rfind(marker)
            if pos > last_pref_pos:
                last_pref_pos = pos

        last_req_pos = -1
        for marker in required_markers:
            pos = context.rfind(marker)
            if pos > last_req_pos:
                last_req_pos = pos

        if last_pref_pos > last_req_pos and last_pref_pos != -1:
            return RequirementType.PREFERRED
        elif last_req_pos > last_pref_pos and last_req_pos != -1:
            return RequirementType.REQUIRED
        
        # Default when section is unspecified
        return RequirementType.UNSPECIFIED

    @classmethod
    def extract_skills(cls, text: str) -> List[SkillItem]:
        """
        Deterministically extracts explicit and implied skills with evidence and confidence.
        """
        extracted_skills: List[SkillItem] = []
        lower_text = text.lower()

        # 1. Implied skills using semantic patterns
        for implied in IMPLIED_SKILL_PATTERNS:
            for match in implied.regex.finditer(text):
                start, end = match.span()
                evidence = cls._extract_sentence_evidence(text, start, end)
                req_type = cls._detect_requirement_type(text[:start])
                
                extracted_skills.append(
                    SkillItem(
                        skill_name=implied.skill_name,
                        category_code=implied.category_code,
                        evidence=evidence or match.group(0),
                        confidence=implied.confidence,
                        requirement_type=req_type,
                        requirement_strength=RequirementStrength.IMPLIED
                    )
                )

        # 2. Explicit technology and keyword skills from canonical dictionary
        for keyword, (canonical_name, category) in CANONICAL_SKILL_MAP.items():
            # Exact boundary matching for keywords (especially short words like Go, R, C++, AWS)
            # Escape regex characters
            escaped = re.escape(keyword)
            # Use negative lookbehind and lookahead to ensure whole word/token match
            pattern = rf"(?<![A-Za-z0-9#+]){escaped}(?![A-Za-z0-9#+])"
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.span()
                matched_token = text[start:end]
                
                # Special disambiguation for ambiguous words
                if keyword == "go" and matched_token != "Go" and matched_token != "Golang":
                    # skip regular verb 'go'
                    continue
                if keyword == "r" and matched_token != "R":
                    continue
                if keyword == "rest" and lower_text[start:end+4] != "rest api" and "api" not in text[max(0, start-15):min(len(text), end+15)].lower():
                    continue

                evidence = cls._extract_sentence_evidence(text, start, end)
                req_type = cls._detect_requirement_type(text[:start])

                extracted_skills.append(
                    SkillItem(
                        skill_name=canonical_name,
                        category_code=category,
                        evidence=evidence or f"Mentioned in job description: {matched_token}",
                        confidence=ConfidenceLevel.HIGH,
                        requirement_type=req_type,
                        requirement_strength=RequirementStrength.EXPLICIT
                    )
                )

        # Deduplicate and merge
        return deduplicate_and_merge_skills(extracted_skills)


class JobDescriptionAnalyzer:
    """
    Central analyzer service orchestrating document extraction, LLM analysis,
    deterministic fallback, schema validation, and contract assembly.
    """

    def __init__(
        self,
        llm_extractor: Optional[BaseLLMExtractor] = None,
        allow_fallback: Optional[bool] = None
    ):
        self.llm_extractor = llm_extractor
        self.allow_fallback = (
            allow_fallback if allow_fallback is not None else settings.allow_deterministic_fallback
        )

    async def analyze(
        self,
        text: str,
        filename: str,
        doc_metadata: Optional[Dict[str, Optional[str]]] = None
    ) -> JobDescriptionResponse:
        """
        Performs end-to-end analysis on extracted text and returns the validated
        shared JobDescriptionResponse contract.
        """
        extractor = self.llm_extractor or get_llm_extractor()
        llm_result: Optional[Dict] = None

        if extractor is not None:
            try:
                logger.info(f"Analyzing job description with LLM extractor for '{filename}'")
                llm_result = await extractor.extract_skills_and_metadata(text, filename)
            except Exception as e:
                logger.warning(f"LLM extraction failed: {str(e)}")
                if not self.allow_fallback:
                    raise ExtractionServiceUnavailableError(
                        f"LLM extraction failed and fallback is disabled: {str(e)}"
                    )

        if llm_result is not None:
            try:
                # Process LLM response
                company = llm_result.get("company")
                if isinstance(company, str) and not company.strip():
                    company = None
                role = llm_result.get("role")
                if isinstance(role, str) and not role.strip():
                    role = None

                raw_skills = llm_result.get("skills", [])
                validated_skills: List[SkillItem] = []

                for s in raw_skills:
                    if not isinstance(s, dict):
                        continue
                    skill_name = str(s.get("skill_name", "")).strip()
                    if not skill_name:
                        continue

                    # Validate category code
                    raw_cat = s.get("category_code", "OTHER")
                    cat_code = normalize_category_code(raw_cat)

                    # Evidence
                    evidence = str(s.get("evidence", "")).strip()
                    if not evidence:
                        evidence = f"Extracted from job description requirements for {skill_name}"

                    # Confidence
                    raw_conf = str(s.get("confidence", "medium")).lower().strip()
                    try:
                        conf = ConfidenceLevel(raw_conf)
                    except ValueError:
                        conf = ConfidenceLevel.MEDIUM

                    # Requirement type
                    raw_req = str(s.get("requirement_type", "unspecified")).lower().strip()
                    try:
                        req_type = RequirementType(raw_req)
                    except ValueError:
                        req_type = RequirementType.UNSPECIFIED

                    # Requirement strength
                    raw_strength = str(s.get("requirement_strength", "explicit")).lower().strip()
                    try:
                        req_strength = RequirementStrength(raw_strength)
                    except ValueError:
                        req_strength = RequirementStrength.EXPLICIT

                    validated_skills.append(
                        SkillItem(
                            skill_name=skill_name,
                            category_code=cat_code,
                            evidence=evidence,
                            confidence=conf,
                            requirement_type=req_type,
                            requirement_strength=req_strength
                        )
                    )

                merged_skills = deduplicate_and_merge_skills(validated_skills)

                return JobDescriptionResponse(
                    source_type="jd",
                    source_file=filename,
                    company=company,
                    role=role,
                    skills=merged_skills
                )

            except Exception as e:
                logger.warning(f"Error parsing LLM response: {str(e)}")
                if not self.allow_fallback:
                    raise ExtractionServiceUnavailableError(
                        f"Could not parse LLM output and fallback is disabled: {str(e)}"
                    )

        # Fallback to deterministic extraction
        if not self.allow_fallback:
            raise ExtractionServiceUnavailableError("No LLM provider configured and fallback is disabled.")

        logger.info(f"Using deterministic skill extractor fallback for '{filename}'")
        company, role = DeterministicSkillExtractor.extract_company_and_role(text, doc_metadata)
        skills = DeterministicSkillExtractor.extract_skills(text)

        return JobDescriptionResponse(
            source_type="jd",
            source_file=filename,
            company=company,
            role=role,
            skills=skills
        )
