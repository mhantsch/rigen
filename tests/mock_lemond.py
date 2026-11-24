#!/usr/bin/env python3
"""Mock lemond for rigen tests.

Usage: mock_lemond.py [port] [request_log_file]
  port 0 => bind an ephemeral port and print it on stdout (first line).

Behavior:
  GET  /v1/models -> 200 (reachable signal)
  POST /api/v1/images/generations ->
     unknown model          -> 400 {"error": {"message": "unknown model: ...", ...}}
     empty prompt           -> 400
     control file contains FAIL  -> 500
     control file contains SHORT -> return only 1 image even if n > 1
     otherwise              -> 200 with n entries; each b64_json is a real 1x1 PNG
                               whose pixel is a deterministic function of
                               (model, prompt, index) so tests can detect duplicates.
Every request body is appended to the log file (one JSON per line).
Control file: optional third argument; re-read on every request, so tests can
flip behavior mid-run.
"""

import base64
import json
import os
import struct
import sys
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KNOWN_MODELS = [
    "SD-1.5",
    "SD-Turbo",
    "AmazingRender\u2011XL\u2011v14",  # U+2011, as produced by `lemonade list`
    "Qwen-Image-2.1-Turbo",
    "bad/name",  # exotic name: exercises filename sanitization
]


def _control_flags(control_path):
    if not control_path:
        return ""
    try:
        with open(control_path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def png1x1(r: int, g: int, b: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00" + bytes((r, g, b))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Handler(BaseHTTPRequestHandler):
    log_path = None
    control_path = None

    def log_message(self, fmt, *args):  # silence request logging
        pass

    def _send(self, code: int, obj) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            self._send(200, {"object": "list",
                             "data": [{"id": "mock", "object": "model"}]})
        else:
            self._send(404, {"error": {"message": "not found",
                                       "type": "invalid_request_error", "code": "404"}})

    def do_POST(self):
        if not self.path.startswith("/api/v1/images/generations"):
            self._send(404, {"error": {"message": "not found",
                                       "type": "invalid_request_error", "code": "404"}})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"error": {"message": "invalid JSON body",
                                       "type": "invalid_request_error", "code": "bad_json"}})
            return
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(body, ensure_ascii=False) + "\n")

        model = body.get("model")
        prompt = body.get("prompt")
        if model not in KNOWN_MODELS:
            self._send(400, {"error": {"message": f"unknown model: {model!r}",
                                       "type": "invalid_request_error",
                                       "code": "model_not_found"}})
            return
        if not isinstance(prompt, str) or not prompt.strip():
            self._send(400, {"error": {"message": "prompt must be non-empty",
                                       "type": "invalid_request_error",
                                       "code": "empty_prompt"}})
            return
        if os.environ.get("RIGEN_MOCK_FAIL") == "1" or "FAIL" in _control_flags(Handler.control_path):
            self._send(500, {"error": {"message": "mock backend failure",
                                       "type": "server_error", "code": "mock_fail"}})
            return

        n = max(1, int(body.get("n", 1)))
        if "SHORT" in _control_flags(Handler.control_path):
            n = 1
        data = []
        for i in range(n):
            r = (10 + 37 * (i + 1) + sum(ord(c) for c in str(model))) % 256
            g = (20 + 53 * (i + 1) + sum(ord(c) for c in str(prompt))) % 256
            b = (30 + 71 * (i + 1)) % 256
            data.append({
                "index": i,
                "b64_json": base64.b64encode(png1x1(r, g, b)).decode("ascii"),
                "generation_info": {
                    "model": model, "prompt": prompt, "n": n,
                    "seed": body.get("seed"), "steps": body.get("steps"),
                    "cfg_scale": body.get("cfg_scale"), "size": body.get("size"),
                },
            })
        self._send(200, {"object": "list", "data": data})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if len(sys.argv) > 2:
        Handler.log_path = sys.argv[2]
    if len(sys.argv) > 3:
        Handler.control_path = sys.argv[3]
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(srv.server_address[1], flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
