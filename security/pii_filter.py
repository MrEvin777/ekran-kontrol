
import re, json
from http.server import BaseHTTPRequestHandler, HTTPServer

PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone_tr": r"(?:\+90|0)?[\s-]?5[0-9]{2}[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2}",
    "tc_kimlik": r"\b[1-9][0-9]{9}[02468]\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ip_addr": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}

def filter_pii(text):
    findings = []
    for name, pat in PII_PATTERNS.items():
        matches = re.findall(pat, text)
        if matches:
            findings.append({"type": name, "count": len(matches)})
            text = re.sub(pat, f"[REDACTED_{name.upper()}]", text)
    return {"filtered": text, "findings": findings}

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(ln))
        out = filter_pii(data.get("text", ""))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    s = HTTPServer(("127.0.0.1", 20130), H)
    print("[PII-FILTER] http://localhost:20130")
    s.serve_forever()
