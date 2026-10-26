import re
from typing import Dict, List, Optional, Set, Tuple

from app.schemas import (
    ConfidenceLevel,
    RadixCategoryCode,
    RequirementStrength,
    RequirementType,
    SkillItem,
)


# Canonical mappings: lowercase skill alias -> (Canonical Name, RadixCategoryCode)
CANONICAL_SKILL_MAP: Dict[str, Tuple[str, RadixCategoryCode]] = {
    # COD: Coding
    "python": ("Python", RadixCategoryCode.COD),
    "python3": ("Python", RadixCategoryCode.COD),
    "javascript": ("JavaScript", RadixCategoryCode.COD),
    "typescript": ("TypeScript", RadixCategoryCode.COD),
    "java": ("Java", RadixCategoryCode.COD),
    "c++": ("C++", RadixCategoryCode.COD),
    "cpp": ("C++", RadixCategoryCode.COD),
    "c#": ("C#", RadixCategoryCode.COD),
    "csharp": ("C#", RadixCategoryCode.COD),
    "golang": ("Go", RadixCategoryCode.COD),
    "go": ("Go", RadixCategoryCode.COD),
    "rust": ("Rust", RadixCategoryCode.COD),
    "ruby": ("Ruby", RadixCategoryCode.COD),
    "php": ("PHP", RadixCategoryCode.COD),
    "kotlin": ("Kotlin", RadixCategoryCode.COD),
    "swift": ("Swift", RadixCategoryCode.COD),
    "scala": ("Scala", RadixCategoryCode.COD),
    "r": ("R", RadixCategoryCode.COD),
    "programming": ("Coding", RadixCategoryCode.COD),
    "software development": ("Coding", RadixCategoryCode.COD),

    # DSA: Data Structures & Algorithms
    "dsa": ("Data Structures & Algorithms", RadixCategoryCode.DSA),
    "data structures": ("Data Structures & Algorithms", RadixCategoryCode.DSA),
    "algorithms": ("Data Structures & Algorithms", RadixCategoryCode.DSA),
    "data structures & algorithms": ("Data Structures & Algorithms", RadixCategoryCode.DSA),
    "algorithmic complexity": ("Data Structures & Algorithms", RadixCategoryCode.DSA),
    "dynamic programming": ("Data Structures & Algorithms", RadixCategoryCode.DSA),
    "graph algorithms": ("Data Structures & Algorithms", RadixCategoryCode.DSA),

    # OOD: Object-Oriented Design
    "ood": ("Object-Oriented Design", RadixCategoryCode.OOD),
    "oop": ("Object-Oriented Programming", RadixCategoryCode.OOD),
    "object oriented programming": ("Object-Oriented Programming", RadixCategoryCode.OOD),
    "object-oriented design": ("Object-Oriented Design", RadixCategoryCode.OOD),
    "design patterns": ("Design Patterns", RadixCategoryCode.OOD),
    "solid principles": ("SOLID Principles", RadixCategoryCode.OOD),

    # APTI: Aptitude
    "aptitude": ("Aptitude", RadixCategoryCode.APTI),
    "problem solving": ("Problem Solving", RadixCategoryCode.APTI),
    "analytical skills": ("Analytical Thinking", RadixCategoryCode.APTI),
    "analytical thinking": ("Analytical Thinking", RadixCategoryCode.APTI),
    "critical thinking": ("Critical Thinking", RadixCategoryCode.APTI),
    "quantitative reasoning": ("Quantitative Reasoning", RadixCategoryCode.APTI),

    # COMM: Communication
    "communication": ("Communication", RadixCategoryCode.COMM),
    "written communication": ("Written Communication", RadixCategoryCode.COMM),
    "verbal communication": ("Verbal Communication", RadixCategoryCode.COMM),
    "collaboration": ("Cross-functional Collaboration", RadixCategoryCode.COMM),
    "team collaboration": ("Cross-functional Collaboration", RadixCategoryCode.COMM),
    "stakeholder management": ("Stakeholder Management", RadixCategoryCode.COMM),
    "technical writing": ("Technical Writing", RadixCategoryCode.COMM),
    "presentation skills": ("Presentation Skills", RadixCategoryCode.COMM),

    # AI: AI / Machine Learning
    "machine learning": ("Machine Learning", RadixCategoryCode.AI),
    "ml": ("Machine Learning", RadixCategoryCode.AI),
    "artificial intelligence": ("Artificial Intelligence", RadixCategoryCode.AI),
    "deep learning": ("Deep Learning", RadixCategoryCode.AI),
    "nlp": ("Natural Language Processing", RadixCategoryCode.AI),
    "natural language processing": ("Natural Language Processing", RadixCategoryCode.AI),
    "computer vision": ("Computer Vision", RadixCategoryCode.AI),
    "pytorch": ("PyTorch", RadixCategoryCode.AI),
    "tensorflow": ("TensorFlow", RadixCategoryCode.AI),
    "scikit-learn": ("Scikit-Learn", RadixCategoryCode.AI),
    "llm": ("Large Language Models", RadixCategoryCode.AI),
    "llms": ("Large Language Models", RadixCategoryCode.AI),
    "predictive modeling": ("Machine Learning", RadixCategoryCode.AI),
    "data science": ("Data Science", RadixCategoryCode.AI),

    # CLOUD: Cloud
    "aws": ("AWS", RadixCategoryCode.CLOUD),
    "amazon web services": ("AWS", RadixCategoryCode.CLOUD),
    "gcp": ("Google Cloud Platform", RadixCategoryCode.CLOUD),
    "google cloud": ("Google Cloud Platform", RadixCategoryCode.CLOUD),
    "azure": ("Microsoft Azure", RadixCategoryCode.CLOUD),
    "microsoft azure": ("Microsoft Azure", RadixCategoryCode.CLOUD),
    "docker": ("Docker", RadixCategoryCode.CLOUD),
    "kubernetes": ("Kubernetes", RadixCategoryCode.CLOUD),
    "k8s": ("Kubernetes", RadixCategoryCode.CLOUD),
    "terraform": ("Terraform", RadixCategoryCode.CLOUD),
    "serverless": ("Serverless Architecture", RadixCategoryCode.CLOUD),
    "cloud infrastructure": ("Cloud Infrastructure", RadixCategoryCode.CLOUD),

    # SQL: SQL & Relational Databases
    "sql": ("SQL", RadixCategoryCode.SQL),
    "postgresql": ("PostgreSQL", RadixCategoryCode.SQL),
    "postgres": ("PostgreSQL", RadixCategoryCode.SQL),
    "mysql": ("MySQL", RadixCategoryCode.SQL),
    "rdbms": ("Relational Databases", RadixCategoryCode.SQL),
    "relational database": ("Relational Databases", RadixCategoryCode.SQL),
    "relational databases": ("Relational Databases", RadixCategoryCode.SQL),
    "database indexing": ("Database Indexing", RadixCategoryCode.SQL),
    "query optimization": ("SQL Query Optimization", RadixCategoryCode.SQL),
    "sqlite": ("SQLite", RadixCategoryCode.SQL),
    "oracle database": ("Oracle SQL", RadixCategoryCode.SQL),

    # SWE: Software Engineering
    "git": ("Git", RadixCategoryCode.SWE),
    "version control": ("Version Control (Git)", RadixCategoryCode.SWE),
    "ci/cd": ("CI/CD", RadixCategoryCode.SWE),
    "cicd": ("CI/CD", RadixCategoryCode.SWE),
    "unit testing": ("Unit Testing", RadixCategoryCode.SWE),
    "automated testing": ("Automated Testing", RadixCategoryCode.SWE),
    "agile": ("Agile / Scrum", RadixCategoryCode.SWE),
    "scrum": ("Agile / Scrum", RadixCategoryCode.SWE),
    "code review": ("Code Review", RadixCategoryCode.SWE),
    "refactoring": ("Code Refactoring", RadixCategoryCode.SWE),
    "devops": ("DevOps Practices", RadixCategoryCode.SWE),

    # SYSD: System Design
    "system design": ("System Design", RadixCategoryCode.SYSD),
    "distributed systems": ("Distributed Systems", RadixCategoryCode.SYSD),
    "microservices": ("Microservices Architecture", RadixCategoryCode.SYSD),
    "scalability": ("System Scalability", RadixCategoryCode.SYSD),
    "scalable architecture": ("System Scalability", RadixCategoryCode.SYSD),
    "load balancing": ("Load Balancing", RadixCategoryCode.SYSD),
    "caching": ("Caching Strategies", RadixCategoryCode.SYSD),
    "redis": ("Redis Caching", RadixCategoryCode.SYSD),
    "kafka": ("Apache Kafka", RadixCategoryCode.SYSD),
    "message queues": ("Message Queues", RadixCategoryCode.SYSD),
    "high availability": ("High Availability", RadixCategoryCode.SYSD),

    # NETW: Networking
    "networking": ("Networking", RadixCategoryCode.NETW),
    "rest": ("REST APIs", RadixCategoryCode.NETW),
    "rest api": ("REST APIs", RadixCategoryCode.NETW),
    "restful apis": ("REST APIs", RadixCategoryCode.NETW),
    "http": ("HTTP / HTTPS", RadixCategoryCode.NETW),
    "https": ("HTTP / HTTPS", RadixCategoryCode.NETW),
    "tcp/ip": ("TCP/IP", RadixCategoryCode.NETW),
    "grpc": ("gRPC", RadixCategoryCode.NETW),
    "graphql": ("GraphQL", RadixCategoryCode.NETW),
    "websockets": ("WebSockets", RadixCategoryCode.NETW),
    "dns": ("DNS", RadixCategoryCode.NETW),
    "ssl/tls": ("SSL / TLS", RadixCategoryCode.NETW),

    # OS: Operating Systems
    "linux": ("Linux", RadixCategoryCode.OS),
    "unix": ("Unix", RadixCategoryCode.OS),
    "operating systems": ("Operating Systems", RadixCategoryCode.OS),
    "bash": ("Bash Scripting", RadixCategoryCode.OS),
    "shell scripting": ("Shell Scripting", RadixCategoryCode.OS),
    "multithreading": ("Concurrency & Multithreading", RadixCategoryCode.OS),
    "concurrency": ("Concurrency & Multithreading", RadixCategoryCode.OS),
    "memory management": ("Memory Management", RadixCategoryCode.OS),
    "posix": ("POSIX Systems", RadixCategoryCode.OS),
}


CONFIDENCE_RANK = {
    ConfidenceLevel.HIGH: 3,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.LOW: 1,
}

REQUIREMENT_TYPE_RANK = {
    RequirementType.REQUIRED: 3,
    RequirementType.PREFERRED: 2,
    RequirementType.UNSPECIFIED: 1,
}

STRENGTH_RANK = {
    RequirementStrength.EXPLICIT: 2,
    RequirementStrength.IMPLIED: 1,
}


def normalize_category_code(raw_category: str) -> RadixCategoryCode:
    """
    Validates and normalizes category codes.
    If code matches one of the 12 RADIX categories, returns it.
    Otherwise maps to OTHER.
    """
    if not raw_category:
        return RadixCategoryCode.OTHER
    
    clean_cat = raw_category.strip().upper()
    try:
        return RadixCategoryCode(clean_cat)
    except ValueError:
        return RadixCategoryCode.OTHER


def deduplicate_and_merge_skills(skills: List[SkillItem]) -> List[SkillItem]:
    """
    Deduplicates synonymous skill mentions, merging duplicates while:
      - Keeping the highest confidence level
      - Keeping the strongest requirement type (required > preferred > unspecified)
      - Keeping explicit over implied strength
      - Keeping the most descriptive evidence quote
    """
    merged: Dict[str, SkillItem] = {}

    for skill in skills:
        key = skill.skill_name.strip().lower()

        if key not in merged:
            merged[key] = skill
        else:
            existing = merged[key]
            
            # 1. Highest confidence
            new_conf = (
                skill.confidence
                if CONFIDENCE_RANK[skill.confidence] > CONFIDENCE_RANK[existing.confidence]
                else existing.confidence
            )

            # 2. Strongest requirement type
            new_req_type = (
                skill.requirement_type
                if REQUIREMENT_TYPE_RANK[skill.requirement_type] > REQUIREMENT_TYPE_RANK[existing.requirement_type]
                else existing.requirement_type
            )

            # 3. Strongest requirement strength
            new_strength = (
                skill.requirement_strength
                if STRENGTH_RANK[skill.requirement_strength] > STRENGTH_RANK[existing.requirement_strength]
                else existing.requirement_strength
            )

            # 4. More informative evidence (longer / more detailed)
            new_evidence = (
                skill.evidence
                if len(skill.evidence) > len(existing.evidence)
                else existing.evidence
            )

            merged[key] = SkillItem(
                skill_name=existing.skill_name,
                category_code=existing.category_code,
                evidence=new_evidence,
                confidence=new_conf,
                requirement_type=new_req_type,
                requirement_strength=new_strength
            )

    return list(merged.values())
