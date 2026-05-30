from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os

PORT = int(os.environ.get("PORT", "8002"))

if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SimpleHTTPRequestHandler)
    print(f"Test UI running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
