"""A tiny webhook receiver for OpenMetadata alerts (chapter 09). Standard library only.

Runs in the om-tutorial-webhook container on port 8000 (host 18090).
POST /<anything>  stores the JSON body; GET /events lists everything received;
DELETE /events clears the list. Inside Docker the server reaches it at
http://webhook:8000/om.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {"raw": raw.decode(errors="replace")}
        EVENTS.append({"path": self.path, "body": body})
        print(f"received {self.path} ({len(raw)} bytes)")
        self._send(200, {"ok": True})

    def do_GET(self):
        if self.path.startswith("/events"):
            self._send(200, EVENTS)
        else:
            self._send(200, {"status": "up", "events": len(EVENTS)})

    def do_DELETE(self):
        EVENTS.clear()
        self._send(200, {"cleared": True})

    def log_message(self, *args):  # keep container logs to our own prints
        pass


if __name__ == "__main__":
    print("webhook receiver listening on :8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
