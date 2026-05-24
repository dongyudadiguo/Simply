import json
import os
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "124.221.146.23"
PORT = 9000
WEB_PORT = 7071

SITEKEY = "0x4AAAAAADNgS66XXyfkgQMZ"


def register(token):
    url = f"http://{HOST}:{PORT}/api/register"

    data = json.dumps({
        "token": token,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            j = json.loads(raw.decode("utf-8"))
            msg = j.get("error") or str(j)
        except Exception:
            msg = raw.decode("utf-8", "replace")
        raise RuntimeError(f"register failed: HTTP {e.code}: {msg}")

    j = json.loads(raw.decode("utf-8"))

    if not j.get("ok"):
        raise RuntimeError(j.get("error") or str(j))

    id_hex = j.get("data", {}).get("id")

    if not isinstance(id_hex, str) or len(id_hex) != 64:
        raise RuntimeError(f"bad register response: {j}")

    user_id = bytes.fromhex(id_hex)

    # 保存到脚本所在目录的 id.bin（避免权限问题）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    id_path = os.path.join(script_dir, "id.bin")

    with open(id_path, "wb") as f:
        f.write(user_id)

    return id_hex


HTML = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>CVM Register</title>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<style>
body {{
    margin: 0;
    background: #111;
    color: #ddd;
    font-family: Consolas, monospace;
    padding: 30px;
}}
pre {{
    background: #000;
    padding: 16px;
    border: 1px solid #333;
    white-space: pre-wrap;
}}
</style>
</head>
<body>
<h2>CVM Register</h2>

<p>请完成人机验证。</p>

<div
    class="cf-turnstile"
    data-sitekey="{SITEKEY}"
    data-callback="onToken">
</div>

<pre id="out">waiting...</pre>

<script>
async function onToken(token) {{
    const out = document.querySelector("#out");

    out.textContent = "registering...";

    try {{
        const r = await fetch("/api/register", {{
            method: "POST",
            body: JSON.stringify({{ token }}),
            headers: {{
                "Content-Type": "application/json"
            }}
        }});

        const j = await r.json();

        if (j.ok) {{
            localStorage.setItem("CVM.user", j.id);

            out.textContent =
                "ok\\n\\n" +
                "id = " + j.id + "\\n\\n" +
                "id.bin saved\\n\\n" +
                "localStorage also set:\\n" +
                "localStorage.setItem(\\"CVM.user\\", \\"" + j.id + "\\")";
        }} else {{
            out.textContent =
                "failed\\n\\n" +
                j.error;
        }}
    }} catch (e) {{
        out.textContent = "error\\n\\n" + e;
    }}
}}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, obj):
        data = json.dumps(obj).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        self.wfile.write(data)

    def send_html(self, html):
        data = html.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.send_html(HTML)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/register":
            self.send_response(404)
            self.end_headers()
            return

        try:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n)

            obj = json.loads(raw.decode("utf-8"))
            token = obj["token"]

            id_hex = register(token)

            self.send_json({
                "ok": True,
                "id": id_hex,
            })

        except Exception as e:
            self.send_json({
                "ok": False,
                "error": str(e),
            })


def main():
    print()
    print("open:")
    print(f"http://localhost:{WEB_PORT}")
    print()
    print("注意：Cloudflare Turnstile 后台 Hostname 至少要允许 localhost")
    print()

    HTTPServer(("localhost", WEB_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()