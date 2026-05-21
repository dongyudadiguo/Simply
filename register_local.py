import socket
import struct
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "124.221.146.23"
PORT = 9000
WEB_PORT = 7071

REGISTER = 1

SITEKEY = "0x4AAAAAADNgS66XXyfkgQMZ"

def recvn(s, n):
    b = b""

    while len(b) < n:
        x = s.recv(n - len(b))

        if not x:
            raise RuntimeError("closed")

        b += x

    return b

def register(token):
    data = token.encode("utf8")

    s = socket.create_connection((HOST, PORT))

    s.sendall(bytes([REGISTER]))
    s.sendall(struct.pack(">I", len(data)))
    s.sendall(data)

    st = recvn(s, 1)[0]

    if st:
        s.close()
        raise RuntimeError("register failed")

    id = recvn(s, 32)

    s.close()

    with open("id.bin", "wb") as f:
        f.write(id)

    return id

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
    let out = document.querySelector("#out");

    out.textContent = "registering...";

    try {{
        let r = await fetch("/api/register", {{
            method: "POST",
            body: JSON.stringify({{ token }}),
            headers: {{
                "Content-Type": "application/json"
            }}
        }});

        let j = await r.json();

        if (j.ok) {{
            out.textContent =
                "ok\\n" +
                "id = " + j.id + "\\n" +
                "id.bin saved";
        }} else {{
            out.textContent =
                "failed\\n" +
                j.error;
        }}
    }} catch (e) {{
        out.textContent = "error\\n" + e;
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
        data = json.dumps(obj).encode("utf8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()

        self.wfile.write(data)

    def send_html(self, html):
        data = html.encode("utf8")

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

            obj = json.loads(raw.decode("utf8"))
            token = obj["token"]

            id = register(token)

            self.send_json({
                "ok": True,
                "id": id.hex()
            })

        except Exception as e:
            self.send_json({
                "ok": False,
                "error": str(e)
            })

def main():
    print()
    print("open:")
    print(f"http://localhost:{WEB_PORT}")
    print()
    print("注意：Cloudflare Turnstile 后台 Hostname 至少要有 localhost")
    print()

    HTTPServer(("localhost", WEB_PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()