"""Pydantic schemas the agent calls return.

These are the contract between prompts/ and the orchestrator. The chunk agent
returns ChunkExtraction; the file orchestrator returns FileOrchestrationOutput.
"""

from __future__ import annotations

from typing import Literal

from typing import Any

from pydantic import BaseModel, Field, model_validator


Cluster = Literal[
    "topic",
    "entities",
    "activity",
    "temporal",
    "evidence",
]


class Tag(BaseModel):
    """One tag emitted by the chunk agent.

    ``name`` is the raw, specific tag extracted from the chunk. ``canonical``
    maps that raw tag to the broad controlled vocabulary. ``canonical_missing``
    is only for the rare case where no broad canonical label fits.
    """

    name: str = Field(min_length=1, description="Raw snake_case label, e.g. 'revenue_decline'.")
    cluster: Cluster
    canonical: str | None = Field(
        default=None,
        description="Broad canonical label if mapped; null only when canonical_missing=True.",
    )
    weight_local: float = Field(ge=0.0, le=1.0, description="Saliency of this tag for this chunk.")
    canonical_missing: bool = False
    gloss: str | None = Field(default=None, description="One-line canonical proposal definition; required when canonical_missing=True.")
    rationale: str | None = Field(default=None, description="Why a new canonical is needed; optional.")

    @model_validator(mode="before")
    @classmethod
    def _normalise_legacy_propose(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "canonical_missing" not in data and "propose" in data:
            out = dict(data)
            # Legacy prompts used `propose` ambiguously. If the model also
            # supplied a canonical, it meant "new raw tag name", not "missing
            # canonical", so preserve the canonical mapping.
            out["canonical_missing"] = bool(out["propose"]) and out.get("canonical") is None
            return out
        return data

    @model_validator(mode="after")
    def _validate_missing_vs_canonical(self) -> "Tag":
        if self.canonical_missing:
            if self.canonical is not None:
                raise ValueError("canonical_missing=True is incompatible with a non-null canonical.")
            if not self.gloss:
                raise ValueError("canonical_missing=True requires a gloss.")
        else:
            if self.canonical is None:
                raise ValueError("Either set canonical or set canonical_missing=True with a gloss.")
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
