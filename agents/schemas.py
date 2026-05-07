"""Pydantic schemas the agent calls return.

These are the contract between prompts/ and the orchestrator. The chunk agent
returns ChunkExtraction; the file orchestrator returns FileOrchestrationOutput.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


Cluster = Literal[
    "theme",
    "object_entity",
    "event_process",
    "time_relevance",
    "information_need",
]


class Tag(BaseModel):
    """One tag emitted by the chunk agent.

    Either canonical is set (the tag mapped to an existing canonical in the seed
    vocabulary) or propose is True (the tag is a candidate for a new canonical).
    """

    name: str = Field(min_length=1, description="Raw snake_case label, e.g. 'revenue_decline'.")
    cluster: Cluster
    canonical: str | None = Field(default=None, description="Canonical label if mapped; null when proposing.")
    weight_local: float = Field(ge=0.0, le=1.0, description="Saliency of this tag for this chunk.")
    propose: bool = False
    gloss: str | None = Field(default=None, description="One-line definition; required when propose=True.")
    rationale: str | None = Field(default=None, description="Why a new canonical is needed; optional.")

    @model_validator(mode="after")
    def _validate_propose_vs_canonical(self) -> "Tag":
        if self.propose:
            if self.canonical is not None:
                raise ValueError("propose=True is incompatible with a non-null canonical.")
            if not self.gloss:
                raise ValueError("propose=True requires a gloss.")
        else:
            if self.canonical is None:
                raise ValueError("Either set canonical or set propose=True with a gloss.")
        return self


class ChunkExtraction(BaseModel):
    """Output of the chunk agent for a single chunk.

    chunk_end_offset must echo the graph Chunk.end_offset for this row (the
    orchestrator rejects mismatches). The prompt has the model copy it verbatim
    from the user message.
    """

    chunk_end_offset: int = Field(ge=0)
    empty: bool = False
    empty_reason: str | None = None
    description: str | None = None
    tags: list[Tag] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_empty_vs_content(self) -> "ChunkExtraction":
        if self.empty:
            if not self.empty_reason:
                raise ValueError("empty=True requires empty_reason.")
        else:
            if not self.description:
                raise ValueError("empty=False requires a description.")
        return self


class FileOrchestrationOutput(BaseModel):
    """Output of the file orchestrator for a single file."""

    description: str = Field(min_length=1, description="3-5 sentence description of the file.")
    chunk_relevance: dict[str, float] = Field(
        default_factory=dict,
        description="chunk_id -> relevance_to_file in [0, 1]. Every chunk should appear.",
    )

    @model_validator(mode="after")
    def _validate_relevance_range(self) -> "FileOrchestrationOutput":
        for cid, value in self.chunk_relevance.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"chunk_relevance[{cid}] = {value} not in [0, 1].")
        return self
