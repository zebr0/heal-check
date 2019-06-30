import http.server
import json
import socketserver
from datetime import datetime, timedelta


class MockHealHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    def __init__(self):
        super().__init__(("0.0.0.0", 8000), None)


class NotFound(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()


class OkTooOld(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": (datetime.utcnow() - timedelta(minutes=6)).isoformat(),
            "status": "ok"
        }).encode("utf-8"))


class Ko(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": datetime.utcnow().isoformat(),
            "status": "ko"
        }).encode("utf-8"))


class Fixing(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": datetime.utcnow().isoformat(),
            "status": "fixing"
        }).encode("utf-8"))


class Ok(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": datetime.utcnow().isoformat(),
            "status": "ok"
        }).encode("utf-8"))


class BadUtc(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": "MCMLXXXIV",
            "status": "ok"
        }).encode("utf-8"))


class BadStatus(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": datetime.utcnow().isoformat(),
            "status": "sudo rm -rf /"
        }).encode("utf-8"))

# TODO: rework
