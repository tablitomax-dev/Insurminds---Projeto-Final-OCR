"""Fakes compartilhados dos testes (nenhuma dependência externa)."""

from .document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from .policy_analysis import (
    FailingExtractionAgent,
    FixtureExplanationAgent,
    FixtureExtractionAgent,
    InMemoryFactRepository,
    MockEvidenceSource,
    ScriptedExtractionAgent,
    make_evidence,
    make_fact,
)

__all__ = [
    "FailingExtractionAgent",
    "FakeEmbedder",
    "FakeOcrEngine",
    "FakeTextExtractor",
    "FixtureExplanationAgent",
    "FixtureExtractionAgent",
    "InMemoryFactRepository",
    "InMemoryVectorIndex",
    "MockEvidenceSource",
    "RecordingStatusSink",
    "ScriptedExtractionAgent",
    "make_evidence",
    "make_fact",
]
