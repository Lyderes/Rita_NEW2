import json; from http.server import BaseHTTPRequestHandler, HTTPServer;
class MockLLM(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self.end_headers()
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())
    def do_POST(self):
        if self.path == "/v1/chat/completions":
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": "Hola, soy el simulador de RITA."}}]}).encode())
HTTPServer(("", 8001), MockLLM).serve_forever()
