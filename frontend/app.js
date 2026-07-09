const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");
const extractButton = document.getElementById("extractButton");
const dropzone = document.getElementById("dropzone");
const health = document.getElementById("health");
const previewRows = document.getElementById("previewRows");
const downloadLink = document.getElementById("downloadLink");
const warnings = document.getElementById("warnings");

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("Backend unavailable");
    health.textContent = "Backend ready";
    health.classList.add("ok");
  } catch {
    health.textContent = "Backend offline";
    health.classList.remove("ok");
  }
}

function setFile(file) {
  if (!file) return;
  fileName.textContent = file.name;
  extractButton.disabled = false;
}

fileInput.addEventListener("change", () => setFile(fileInput.files[0]));

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragover");
  const file = event.dataTransfer.files[0];
  if (!file) return;
  fileInput.files = event.dataTransfer.files;
  setFile(file);
});

extractButton.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  extractButton.disabled = true;
  extractButton.textContent = "Extracting...";
  previewRows.innerHTML = `<tr><td colspan="5">Processing PDF. OCR can take a little while for scanned drawings.</td></tr>`;
  downloadLink.classList.add("hidden");
  warnings.classList.add("hidden");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/extract", { method: "POST", body: formData });
    const result = await readJsonResponse(response);
    if (!response.ok) throw new Error(result.detail || "Extraction failed");
    renderResult(result);
  } catch (error) {
    previewRows.innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
  } finally {
    extractButton.disabled = false;
    extractButton.textContent = "Run Extraction";
  }
});

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error(
      `Server returned an empty response (${response.status}). Check Render logs for the backend error.`
    );
  }

  try {
    return JSON.parse(text);
  } catch {
    const shortText = text.replace(/\s+/g, " ").slice(0, 220);
    throw new Error(
      `Server returned non-JSON response (${response.status}): ${shortText}`
    );
  }
}

function renderResult(result) {
  document.getElementById("pidNumber").textContent = result.pid_number || "Not detected";
  document.getElementById("tagCount").textContent = result.tag_count;
  document.getElementById("validCount").textContent = result.validated_count;
  document.getElementById("reviewCount").textContent = result.review_count;

  downloadLink.href = result.download_url;
  downloadLink.classList.remove("hidden");

  if (result.warnings && result.warnings.length) {
    warnings.textContent = result.warnings.join(" | ");
    warnings.classList.remove("hidden");
  }

  if (!result.preview.length) {
    previewRows.innerHTML = `<tr><td colspan="5">No tags were detected. Try a higher quality PDF or confirm Tesseract is installed.</td></tr>`;
    return;
  }

  previewRows.innerHTML = result.preview
    .map((tag) => {
      const description = tag.mds_description || tag.context || "";
      return `
        <tr>
          <td>${escapeHtml(tag.normalized_tag)}</td>
          <td>${escapeHtml(tag.tag_type)}</td>
          <td>${escapeHtml(String(tag.page))}</td>
          <td>${escapeHtml(tag.mds_status)}</td>
          <td>${escapeHtml(description)}</td>
        </tr>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

checkHealth();
