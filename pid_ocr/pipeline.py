from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz
from PIL import Image
from pypdf import PdfReader

from .config import Settings
from .models import ExtractionResult, PageText, TagRecord
from .tag_patterns import PID_NUMBER_PATTERNS, TAG_PATTERNS, is_false_positive, normalize_tag

LOGGER = logging.getLogger(__name__)


class PIDExtractionPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def extract(self, pdf_path: Path) -> ExtractionResult:
        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)

        result = ExtractionResult(source_pdf=pdf_path, pid_number=None)
        embedded_pages = self._extract_embedded_text(pdf_path)
        result.raw_pages.extend(embedded_pages)

        pages_with_embedded_text = {page.page for page in embedded_pages}
        ocr_pages, ocr_tags, warnings = self._extract_ocr(pdf_path, pages_with_embedded_text)
        result.raw_pages.extend(ocr_pages)
        result.warnings.extend(warnings)

        pid_number = self._detect_pid_number(result.raw_pages, pdf_path)
        result.pid_number = pid_number

        text_tags = self._extract_tags_from_text(result.raw_pages, pid_number)
        combined = text_tags + ocr_tags
        for tag in combined:
            tag.pid_number = tag.pid_number or pid_number

        result.tags = self._deduplicate_tags(combined)
        return result

    def _extract_embedded_text(self, pdf_path: Path) -> list[PageText]:
        pages: list[PageText] = []
        try:
            reader = PdfReader(str(pdf_path))
            for index, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(PageText(page=index, text=text, source="embedded_pdf_text"))
        except Exception as exc:
            LOGGER.warning("Embedded text extraction failed: %s", exc)
        return pages

    def _extract_ocr(
        self, pdf_path: Path, pages_with_embedded_text: set[int]
    ) -> tuple[list[PageText], list[TagRecord], list[str]]:
        pages: list[PageText] = []
        tags: list[TagRecord] = []
        warnings: list[str] = []

        try:
            import pytesseract
        except ImportError:
            warnings.append("pytesseract is not installed; scanned PDF OCR was skipped.")
            return pages, tags, warnings

        try:
            document = fitz.open(str(pdf_path))
        except Exception as exc:
            warnings.append(f"PDF rendering failed: {exc}")
            return pages, tags, warnings

        zoom = self.settings.render_dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        page_limit = min(document.page_count, self.settings.max_pages)
        for page_index in range(page_limit):
            page_number = page_index + 1
            if page_number in pages_with_embedded_text and not self.settings.ocr_pages_with_embedded_text:
                continue
            try:
                pixmap = document[page_index].get_pixmap(matrix=matrix, alpha=False)
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                image = self._preprocess_image(image)
                text = pytesseract.image_to_string(
                    image,
                    lang=self.settings.ocr_language,
                    timeout=self.settings.ocr_timeout_seconds,
                )
                if text.strip():
                    pages.append(PageText(page=page_number, text=text, source="ocr"))
                tags.extend(self._extract_tags_from_ocr_data(pytesseract, image, page_number))
            except Exception as exc:
                warnings.append(f"OCR failed on page {page_number}: {exc}")

        document.close()
        return pages, tags, warnings

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        try:
            import cv2
            import numpy as np

            gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
            gray = cv2.fastNlMeansDenoising(gray, h=12)
            threshold = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                35,
                11,
            )
            return Image.fromarray(threshold)
        except Exception:
            return image.convert("L")

    def _extract_tags_from_ocr_data(self, pytesseract_module, image: Image.Image, page: int) -> list[TagRecord]:
        extracted: list[TagRecord] = []
        try:
            data = pytesseract_module.image_to_data(
                image,
                lang=self.settings.ocr_language,
                output_type=pytesseract_module.Output.DICT,
                timeout=self.settings.ocr_timeout_seconds,
            )
        except Exception:
            return extracted

        words = data.get("text", [])
        for index, raw_word in enumerate(words):
            word = normalize_tag(raw_word or "")
            confidence_text = str(data.get("conf", ["-1"])[index])
            try:
                confidence = float(confidence_text)
            except ValueError:
                confidence = -1.0
            if confidence < self.settings.min_confidence or is_false_positive(word):
                continue

            for tag_type, pattern in TAG_PATTERNS:
                if pattern.fullmatch(word):
                    bbox = "{x},{y},{w},{h}".format(
                        x=data["left"][index],
                        y=data["top"][index],
                        w=data["width"][index],
                        h=data["height"][index],
                    )
                    extracted.append(
                        TagRecord(
                            tag=raw_word,
                            normalized_tag=word,
                            tag_type=tag_type,
                            page=page,
                            source="ocr_bbox",
                            confidence=confidence,
                            bbox=bbox,
                        )
                    )
                    break
        return extracted

    def _detect_pid_number(self, pages: list[PageText], pdf_path: Path) -> str | None:
        candidates = [pdf_path.stem]
        candidates.extend(page.text for page in pages[:3])
        for text in candidates:
            for pattern in PID_NUMBER_PATTERNS:
                match = pattern.search(text)
                if match:
                    return normalize_tag(match.group(1))
        return None

    def _extract_tags_from_text(self, pages: list[PageText], pid_number: str | None) -> list[TagRecord]:
        records: list[TagRecord] = []
        for page in pages:
            normalized_text = page.text.replace("\n", " ")
            occupied_spans: list[tuple[int, int]] = []
            for tag_type, pattern in TAG_PATTERNS:
                for match in pattern.finditer(normalized_text):
                    if tag_type != "line_number" and self._inside_existing_span(match.start(), match.end(), occupied_spans):
                        continue
                    value = match.group(0)
                    normalized = normalize_tag(value)
                    if is_false_positive(normalized):
                        continue
                    if tag_type == "line_number":
                        occupied_spans.append((match.start(), match.end()))
                    records.append(
                        TagRecord(
                            tag=value,
                            normalized_tag=normalized,
                            tag_type=tag_type,
                            pid_number=pid_number,
                            page=page.page,
                            source=page.source,
                            context=self._context(normalized_text, match.start(), match.end()),
                        )
                    )
        return records

    def _inside_existing_span(self, start: int, end: int, spans: list[tuple[int, int]]) -> bool:
        return any(start >= span_start and end <= span_end for span_start, span_end in spans)

    def _context(self, text: str, start: int, end: int, radius: int = 60) -> str:
        snippet = text[max(0, start - radius) : min(len(text), end + radius)]
        return re.sub(r"\s+", " ", snippet).strip()

    def _deduplicate_tags(self, tags: list[TagRecord]) -> list[TagRecord]:
        best: dict[tuple[str, int], TagRecord] = {}
        for tag in tags:
            key = (tag.normalized_tag, tag.page)
            current = best.get(key)
            if current is None:
                best[key] = tag
                continue
            current_score = current.confidence if current.confidence is not None else 0
            new_score = tag.confidence if tag.confidence is not None else 0
            if new_score > current_score or current.source == "embedded_pdf_text":
                best[key] = tag
        return sorted(best.values(), key=lambda item: (item.page, item.tag_type, item.normalized_tag))
