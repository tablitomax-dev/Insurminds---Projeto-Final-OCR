"""Fakes compartilhados dos testes (nenhuma dependência externa)."""

from .document_processing import (
    FakeEmbedder,
    FakeLayoutEngine,
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
    "FakeLayoutEngine",
    "FakeOcrEngine",
    "FakeTextExtractor",
    "FixtureExtractionAgent",
    "FixtureExplanationAgent",
    "InMemoryFactRepository",
    "InMemoryVectorIndex",
    "MockEvidenceSource",
    "RecordingStatusSink",
    "ScriptedExtractionAgent",
    "make_evidence",
    "make_fact",
]
