const form = document.getElementById("compileForm");
const apiBaseInput = document.getElementById("apiBase");
const filenameInput = document.getElementById("filename");
const fileInput = document.getElementById("latexFile");
const latexInput = document.getElementById("latexInput");
const loadSampleButton = document.getElementById("loadSample");
const statusEl = document.getElementById("status");
const errorBox = document.getElementById("errorBox");
const pdfFrame = document.getElementById("pdfFrame");
const downloadLink = document.getElementById("downloadLink");

let currentObjectUrl = null;

const sampleLatex = String.raw`
\\documentclass[10pt,letterpaper]{article}
\\usepackage[margin=0.8in]{geometry}
\\usepackage{hyperref}
\\begin{document}
\\section*{Sample Resume}
This is a sample LaTeX document. Replace with your full resume.
\\end{document}
`;

function setStatus(message) {
  statusEl.textContent = message;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.textContent = "";
  errorBox.hidden = true;
}

function resetPreview() {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = null;
  }
  pdfFrame.src = "";
  downloadLink.hidden = true;
  downloadLink.href = "#";
}

loadSampleButton.addEventListener("click", () => {
  latexInput.value = sampleLatex.trim();
});

fileInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) {
    return;
  }

  const text = await file.text();
  latexInput.value = text;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  resetPreview();

  const latex = latexInput.value.trim();
  if (!latex) {
    showError("Paste LaTeX or load a .tex file before compiling.");
    return;
  }

  const filename = filenameInput.value.trim() || "resume";
  const apiBase = apiBaseInput.value.trim().replace(/\/$/, "");
  const url = `${apiBase}/compile`;

  setStatus("Compiling...");

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latex, filename }),
    });

    if (!response.ok) {
      let message = "Compilation failed.";
      try {
        const data = await response.json();
        message = JSON.stringify(data, null, 2);
      } catch (err) {
        const text = await response.text();
        message = text || message;
      }
      showError(message);
      setStatus("Failed");
      return;
    }

    const blob = await response.blob();
    currentObjectUrl = URL.createObjectURL(blob);
    pdfFrame.src = currentObjectUrl;
    downloadLink.href = currentObjectUrl;
    downloadLink.hidden = false;
    downloadLink.download = `${filename}.pdf`;
    setStatus("Done");
  } catch (err) {
    showError(`Request failed: ${err.message}`);
    setStatus("Failed");
  }
});
