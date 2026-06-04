#!/usr/bin/env python3
"""
씬 무드보드 서버 — static 파일 제공 + Claude API 프록시
"""
import json, os, urllib.request, urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
PORT = int(os.environ.get("PORT", 7788))
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = """You are a color palette expert for scene backgrounds in illustration and animation.
Given a mood/keyword, generate a 4-layer background color palette (sky, far background, mid background, foreground).
Apply atmospheric perspective: sky is brightest/least saturated, foreground is darkest/most saturated.
Respond ONLY with valid JSON, no explanation."""

USER_TMPL = """Keyword: "{keyword}"

Return exactly this JSON shape (HSB values, integers):
{{
  "name": "<scene name in Korean, 2-5 chars>",
  "mood": "<mood tags in Korean, comma-separated, max 3>",
  "layers": [
    {{"h": 0-360, "s": 0-100, "b": 0-100}},
    {{"h": 0-360, "s": 0-100, "b": 0-100}},
    {{"h": 0-360, "s": 0-100, "b": 0-100}},
    {{"h": 0-360, "s": 0-100, "b": 0-100}}
  ]
}}
layers[0]=sky, layers[1]=far BG, layers[2]=mid BG, layers[3]=foreground."""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass  # silence default logs

    def do_GET(self):
        # 루트 → index.html 리다이렉트
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        else:
            super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/generate-palette":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        keyword = body.get("keyword", "").strip()
        api_key = body.get("apiKey", "").strip()

        if not keyword:
            self._json(400, {"error": "keyword required"})
            return
        if not api_key:
            self._json(400, {"error": "apiKey required"})
            return

        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": USER_TMPL.format(keyword=keyword)}],
        }).encode()

        req = urllib.request.Request(
            ANTHROPIC_API,
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            text = data["content"][0]["text"].strip()
            # strip markdown code fences if present
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            result = json.loads(text)
            self._json(200, result)
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            self._json(e.code, {"error": err})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("", PORT), Handler)
    print(f"🎨 씬 무드보드 서버 → http://localhost:{PORT}/")
    server.serve_forever()
