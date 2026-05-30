# LaTeX Compiler Test UI

This is a lightweight browser UI for the local LaTeX compiler service.

## Run the compiler service

```powershell
cd "c:\Users\shahn\Desktop\desktop dump\research assistance\resume"
docker run --rm -p 8001:8001 resume-compiler
```

## Run the UI

```powershell
cd "c:\Users\shahn\Desktop\desktop dump\research assistance\resume\test_ui"
python .\serve.py
```

Open http://localhost:8002 in a browser and paste LaTeX or load a .tex file.

If you change the UI port, set the allowed origins in the service:

```powershell
$env:ALLOWED_ORIGINS = "http://localhost:8002,http://127.0.0.1:8002"
```

## Postman alternative

- Method: POST
- URL: http://localhost:8001/compile
- Headers: Content-Type: application/json
- Body (raw JSON):

```json
{
  "latex": "\\\\documentclass{article}\\\\begin{document}Hello\\\\end{document}",
  "filename": "resume"
}
```

Use "Send and Download" to save the PDF.
