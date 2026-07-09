# P&ID OCR Tag Extractor

A production-oriented FastAPI application for extracting engineering tags from P&ID PDF drawings, associating them with P&ID / drawing numbers, validating and enriching them through an MDS adapter, and exporting the results to Excel.

## What It Does

- Upload one P&ID PDF from the browser.
- Extract embedded PDF text when available.
- Render pages and run OCR for scanned drawings.
- Detect common engineering tags such as instruments, valves, pumps, equipment, line numbers, and drawing numbers.
- Associate every detected tag with a P&ID number, page, source, and optional OCR location.
- Validate and enrich extracted tags with an MDS integration layer.
- Generate a structured `.xlsx` workbook with Tags, Summary, MDS Validation, and Raw Text sheets.

## Requirements

Python 3.10+ is recommended.

Install Python dependencies:

```bash
pip install -r requirements.txt
```

For scanned PDFs, install the Tesseract OCR engine:

- Windows: install from `https://github.com/UB-Mannheim/tesseract/wiki`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- macOS: `brew install tesseract`

The app uses PyMuPDF for PDF rendering, so Poppler is not required.

## Run

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:8000
```

## MDS Integration

The adapter first tries to use an external MDS library if one is available. You can configure it with:

```text
MDS_LIBRARY_MODULE=your_mds_library
MDS_ENDPOINT=https://mds.example.internal
MDS_API_KEY=...
```

The library module may expose one of these shapes:

- `MDSClient(endpoint=..., api_key=...)`
- `Client(endpoint=..., api_key=...)`
- `validate_tag(tag)` and/or `get_tag(tag)` functions

If no external library is installed, the app falls back to `data/mds_reference.csv`.

## Output Workbook

Each extraction creates:

- `Tags`: normalized extraction results and MDS enrichment.
- `Summary`: counts by tag type and validation status.
- `MDS Validation`: validation details per unique tag.
- `Raw Text`: page-level text used by the extraction pipeline.

Generated uploads and outputs are stored under `storage/`.

## Free Hosting On Render

This project includes `render.yaml` and a Dockerfile, so Render can build it with Tesseract OCR installed.

1. Push this folder to a GitHub repository.
2. Open Render and choose **New > Blueprint**.
3. Connect the repository.
4. Select the repository containing this app.
5. Render will detect `render.yaml` and create the free web service.
6. After deployment, open the Render service URL.

For manual Render setup, create a **Web Service** with:

```text
Environment: Docker
Health Check Path: /api/health
```

No build or start command is needed when using Docker.
