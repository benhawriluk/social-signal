"""SQLAlchemy models and Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


# --- SQLAlchemy ORM ---


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String(255), unique=True, nullable=False)
    subreddit = Column(String(100), nullable=False)
    author_hash = Column(String(64))
    title = Column(Text)
    body = Column(Text, nullable=False)
    body_cleaned = Column(Text)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    score = Column(Integer)
    num_comments = Column(Integer)
    permalink = Column(Text)
    published_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    word_count = Column(Integer)
    simhash = Column(BigInteger)

    classifications = relationship("Classification", back_populates="document")


class Classification(Base):
    __tablename__ = "classifications"
    __table_args__ = (UniqueConstraint("document_id", "classifier"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"))
    classifier = Column(String(50))
    # Full classifier output stored as JSONB for flexibility
    classifications = Column(JSONB, nullable=False)
    meta = Column(JSONB, nullable=False)
    # Denormalized for fast querying
    themes_detected_count = Column(Integer)
    confidence = Column(String(10))  # "high" | "medium" | "low"
    pass2_needed = Column(Boolean)
    classified_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    # Pass 2 extraction results
    extractions = Column(JSONB)
    extracted_at = Column(DateTime(timezone=True))

    document = relationship("Document", back_populates="classifications")
    audits = relationship("Audit", back_populates="classification")


class Audit(Base):
    __tablename__ = "audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classification_id = Column(UUID(as_uuid=True), ForeignKey("classifications.id"))
    auditor = Column(String(100))
    agrees = Column(Boolean)
    corrected_label = Column(String(100))
    notes = Column(Text)
    audited_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    classification = relationship("Classification", back_populates="audits")


# --- Pydantic schemas (for pipeline data flow) ---


class RawDocument(BaseModel):
    """Document as it comes from the scraper, before cleaning."""

    source_id: str
    subreddit: str
    author_hash: str | None = None
    title: str | None = None
    body: str
    parent_id: str | None = None
    score: int | None = None
    num_comments: int | None = None
    permalink: str | None = None
    published_at: datetime | None = None


# --- Classification output Pydantic models ---
# These mirror the structure in docs/classifier_prompt.md and data/classifier_schema_1.json.


class Q01ExistentialReflection(BaseModel):
    present: bool
    valence: Literal["positive", "negative", "mixed"] | None = None


class Q02FutureConfidence(BaseModel):
    present: bool
    direction: Literal["more_confident", "less_confident", "mixed"] | None = None


class Q03ParasocialAttachment(BaseModel):
    present: bool
    disposition: Literal["favorable", "negative", "mixed"] | None = None


class Q04ProblematicEngagement(BaseModel):
    present: bool
    engagement_patterns: bool | None = None
    addiction: bool | None = None


class Q05Anthropomorphization(BaseModel):
    present: bool
    disposition: Literal["favorable", "negative", "mixed"] | None = None


class Q06VulnerablePopulations(BaseModel):
    present: bool
    company_responsibility_mentioned: bool | None = None


class Q07ModelChangeHarm(BaseModel):
    present: bool
    user_proposes_remedy: bool | None = None


class Q08HumanRelationships(BaseModel):
    present: bool
    avoidance: bool | None = None
    loneliness: bool | None = None
    adjudication: bool | None = None
    adjudication_norms_proposed: bool | None = None


class Q09JudgmentSubstitution(BaseModel):
    present: bool


class Q10CognitiveOffloading(BaseModel):
    present: bool
    learning_impact: bool | None = None
    cheating: bool | None = None


class Q11DataProvenanceTrust(BaseModel):
    present: bool
    solutions_proposed: bool | None = None


class Q12UsageNorms(BaseModel):
    present: bool
    acceptability_discussed: bool | None = None
    actor_specific_norms: bool | None = None


class Q13AiValidation(BaseModel):
    present: bool
    unreasonable_validation: bool | None = None


class Q14EaseOfAccess(BaseModel):
    present: bool
    friction_view: Literal["wants_more_friction", "wants_less_friction", "neutral"] | None = None


class Q15PaceOfChange(BaseModel):
    present: bool
    emotional_reaction: Literal["anxious", "excited", "resigned", "angry", "mixed"] | None = None


class Q16InformationalEcosystem(BaseModel):
    present: bool
    direction: Literal["helpful", "polluting", "mixed"] | None = None


class Q17Disintermediation(BaseModel):
    present: bool
    mechanism_described: bool | None = None


class Classifications(BaseModel):
    q01_existential_reflection: Q01ExistentialReflection
    q02_future_confidence: Q02FutureConfidence
    q03_parasocial_attachment: Q03ParasocialAttachment
    q04_problematic_engagement: Q04ProblematicEngagement
    q05_anthropomorphization: Q05Anthropomorphization
    q06_vulnerable_populations: Q06VulnerablePopulations
    q07_model_change_harm: Q07ModelChangeHarm
    q08_human_relationships: Q08HumanRelationships
    q09_judgment_substitution: Q09JudgmentSubstitution
    q10_cognitive_offloading: Q10CognitiveOffloading
    q11_data_provenance_trust: Q11DataProvenanceTrust
    q12_usage_norms: Q12UsageNorms
    q13_ai_validation: Q13AiValidation
    q14_ease_of_access: Q14EaseOfAccess
    q15_pace_of_change: Q15PaceOfChange
    q16_informational_ecosystem: Q16InformationalEcosystem
    q17_disintermediation: Q17Disintermediation


class ClassificationMeta(BaseModel):
    themes_detected_count: int
    confidence: Literal["high", "medium", "low"]
    ambiguous_themes: list[str] = []
    pass2_needed: bool


class ClassificationResult(BaseModel):
    """Structured output from the LLM classifier."""

    post_id: str
    subreddit: str
    classifications: Classifications
    meta: ClassificationMeta


class ExtractionResult(BaseModel):
    """Structured output from the Pass 2 extractor."""

    post_id: str
    company_responsibility: str | None = None
    proposed_remedy: str | None = None
    adjudication_norms: str | None = None
    provenance_solutions: str | None = None
    disintermediation_mechanism: str | None = None
