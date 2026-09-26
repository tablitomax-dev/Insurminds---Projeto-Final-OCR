"""Fakes compartilhados dos testes (nenhuma dependência externa)."""

from .document_processing import (
    FakeEmbedder,
    FakeOcrEngine,
    FakeTextExtractor,
    InMemoryVectorIndex,
    RecordingStatusSink,
)
from .policy_analysis import (
    FakeEvidenceRetriever,
    FakeExplanationGenerator,
    FakeLlmExtractor,
    InMemoryFactRepository,
    make_evidence,
    make_fact,
)

__all__ = [
    "FakeEmbedder",
    "FakeEvidenceRetriever",
    "FakeExplanationGenerator",
    "FakeLlmExtractor",
    "FakeOcrEngine",
    "FakeTextExtractor",
    "InMemoryFactRepository",
    "InMemoryVectorIndex",
    "RecordingStatusSink",
    "make_evidence",
    "make_fact",
]
