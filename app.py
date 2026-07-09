from __future__ import annotations

import logging
import os
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pid_ocr.config import Settings
from pid_ocr.excel_exporter import export_results_to_excel
from pid_ocr.mds_adapter import MDSAdapter
from pid_ocr.pipeline import PIDExtractionPipeline


BASE_DIR = Path(__file__).resolve().parent
SETTINGS = Settings()
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="P&ID OCR Tag Extractor",
    version="1.0.0",
    description="Extract engineering tags from P&ID PDFs and export validated results to Excel.",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/extract")
async def extract_pid_tags(file: UploadFile = File(...)) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    request_id = uuid4().hex
    safe_name = Path(file.filename).name.replace(" ", "_")
    pdf_path = UPLOAD_DIR / f"{request_id}_{safe_name}"
    xlsx_path = OUTPUT_DIR / f"{request_id}_pid_ocr_results.xlsx"

    try:
        with pdf_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)

        pipeline = PIDExtractionPipeline(settings=SETTINGS)
        extraction = pipeline.extract(pdf_path)

        mds = MDSAdapter(
            reference_path=BASE_DIR / "data" / "mds_reference.csv",
            module_name=SETTINGS.mds_library_module,
            endpoint=SETTINGS.mds_endpoint,
            api_key=SETTINGS.mds_api_key,
        )
        enriched = mds.validate_and_enrich(extraction.tags)
        extraction.tags = enriched

        export_results_to_excel(extraction, xlsx_path)

        return {
            "request_id": request_id,
            "pid_number": extraction.pid_number,
            "tag_count": len(extraction.tags),
            "validated_count": sum(1 for tag in extraction.tags if tag.mds_status == "valid"),
            "review_count": sum(1 for tag in extraction.tags if tag.mds_status != "valid"),
            "download_url": f"/api/download/{request_id}",
            "preview": [tag.model_dump() for tag in extraction.tags[:50]],
            "warnings": extraction.warnings,
        }
    except Exception as exc:
        logging.exception("Extraction failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/download/{request_id}")
def download_results(request_id: str) -> FileResponse:
    if not request_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid request id.")

    matches = list(OUTPUT_DIR.glob(f"{request_id}_pid_ocr_results.xlsx"))
    if not matches:
        raise HTTPException(status_code=404, detail="Result file not found.")

    return FileResponse(
        matches[0],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="pid_ocr_results.xlsx",
    )


app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("app:app", host=SETTINGS.host, port=SETTINGS.port, reload=SETTINGS.reload)

