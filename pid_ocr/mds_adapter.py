from __future__ import annotations

import csv
import importlib
import logging
from pathlib import Path
from typing import Any

from .models import TagRecord

LOGGER = logging.getLogger(__name__)


class MDSAdapter:
    def __init__(
        self,
        reference_path: Path,
        module_name: str | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.reference_path = reference_path
        self.client = self._load_external_client(module_name, endpoint, api_key) if module_name else None
        self.reference = self._load_reference(reference_path)

    def validate_and_enrich(self, tags: list[TagRecord]) -> list[TagRecord]:
        for tag in tags:
            payload = self._lookup_external(tag.normalized_tag) if self.client else None
            if payload is None:
                payload = self.reference.get(tag.normalized_tag)
            self._apply_payload(tag, payload)
        return tags

    def _load_external_client(self, module_name: str, endpoint: str | None, api_key: str | None) -> Any:
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "MDSClient"):
                return module.MDSClient(endpoint=endpoint, api_key=api_key)
            if hasattr(module, "Client"):
                return module.Client(endpoint=endpoint, api_key=api_key)
            return module
        except Exception as exc:
            LOGGER.warning("Unable to load MDS library %s: %s", module_name, exc)
            return None

    def _lookup_external(self, tag: str) -> dict[str, Any] | None:
        if self.client is None:
            return None
        try:
            if hasattr(self.client, "validate_tag"):
                response = self.client.validate_tag(tag)
            elif hasattr(self.client, "get_tag"):
                response = self.client.get_tag(tag)
            else:
                return None
            if response is None:
                return None
            if isinstance(response, dict):
                return response
            if hasattr(response, "model_dump"):
                return response.model_dump()
            return vars(response)
        except Exception as exc:
            LOGGER.warning("MDS lookup failed for %s: %s", tag, exc)
            return None

    def _load_reference(self, path: Path) -> dict[str, dict[str, str]]:
        if not path.exists():
            return {}
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            return {row["tag"].strip().upper(): row for row in csv.DictReader(handle) if row.get("tag")}

    def _apply_payload(self, tag: TagRecord, payload: dict[str, Any] | None) -> None:
        if not payload:
            tag.mds_status = "not_found"
            tag.mds_message = "No matching MDS record found."
            return

        status = str(payload.get("status") or payload.get("validation_status") or "valid").lower()
        tag.mds_status = "valid" if status in {"active", "valid", "approved"} else status
        tag.mds_asset_id = self._first(payload, "asset_id", "id", "mds_id")
        tag.mds_description = self._first(payload, "description", "asset_description", "name")
        tag.mds_discipline = self._first(payload, "discipline")
        tag.mds_system = self._first(payload, "system", "process_system")
        tag.mds_criticality = self._first(payload, "criticality", "risk_class")
        tag.mds_message = "Matched in MDS."

    def _first(self, payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return None

