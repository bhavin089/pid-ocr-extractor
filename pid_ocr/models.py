from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field


class TagRecord(BaseModel):
    tag: str
    normalized_tag: str
    tag_type: str
    pid_number: str | None = None
    page: int
    source: str
    confidence: float | None = None
    bbox: str | None = None
    context: str | None = None
    mds_status: str = "not_checked"
    mds_asset_id: str | None = None
    mds_description: str | None = None
    mds_discipline: str | None = None
    mds_system: str | None = None
    mds_criticality: str | None = None
    mds_message: str | None = None


@dataclass
class PageText:
    page: int
    text: str
    source: str


@dataclass
class ExtractionResult:
    source_pdf: Path
    pid_number: str | None
    tags: list[TagRecord] = field(default_factory=list)
    raw_pages: list[PageText] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

