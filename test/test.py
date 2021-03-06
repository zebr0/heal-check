#!/usr/bin/python3 -u

import http.server
import json
import pathlib
import socketserver
import subprocess
import threading
import unittest
from datetime import datetime, timedelta

import dateutil.parser

uri = "http://127.0.0.1:8000"
file_prefix = "heal-check-"
filename = file_prefix + "4411def9d576984c8d78253236b2a62f"
file = pathlib.Path(filename)
command = "../src/heal-check " + uri + " -f " + file_prefix

base_stdout = {
    "delay": 30,
    "file_path": filename,
    "file_prefix": file_prefix,
    "uri": uri,
    "mode": None
}


def run(mode=None):
    sp = subprocess.Popen(command + " -m " + mode if mode else command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = sp.communicate()

    # clears the output of time-related values that are difficult to test and not really needed anyway
    stdout_json = json.loads(stdout or "{}")
    stdout_json.pop("utc_now", None)
    stdout_json.pop("utc_min", None)
    stdout_json.pop("utc_file", None)
    stdout_json.pop("utc_remote", None)
    stdout_json.pop("file_content", None)
    stdout_json.pop("response_text", None)
    stdout_json.get("response_json", {}).pop("utc", None)

    return sp.returncode, stdout_json


class TestCase(unittest.TestCase):
    def setUp(self):
        # starting the mock server
        self.server = MockHealHTTPServer()
        threading.Thread(target=self.server.serve_forever).start()

    def tearDown(self):
        # stopping the mock server
        self.server.shutdown()

    def _test_warnings(self, specific_stdout):
        if file.exists():
            file.unlink()

        # test a: no warning beforehand
        just_before = datetime.utcnow()
        # then: exit code 0 + warning created just now
        (rc, stdout) = run()
        self.assertEqual(rc, 0)
        self.assertTrue(file.exists())
        self.assertGreaterEqual(dateutil.parser.parse(file.read_text()), just_before)
        self.assertEqual(stdout, {
            **base_stdout,
            **specific_stdout,
            "exit_code": 0,
            "warning_file": "created"
        })

        # test b: warning 29 minutes ago
        four_minutes_ago = (datetime.utcnow() - timedelta(minutes=29)).isoformat()
        file.write_text(four_minutes_ago)
        # then: exit code 0 + warning unchanged
        (rc, stdout) = run()
        self.assertEqual(rc, 0)
        self.assertTrue(file.exists())
        self.assertEqual(file.read_text(), four_minutes_ago)
        self.assertEqual(stdout, {
            **base_stdout,
            **specific_stdout,
            "exit_code": 0,
            "warning_file": "unchanged"
        })

        # test c: warning 31 minutes ago
        six_minutes_ago = (datetime.utcnow() - timedelta(minutes=31)).isoformat()
        file.write_text(six_minutes_ago)
        # then: exit code 1 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            **base_stdout,
            **specific_stdout,
            "error_cause": "utc_file < utc_min",
            "exit_code": 1,
            "warning_file": "deleted"
        })

    def test_server_not_responding(self):
        self._test_warnings({
            "warning_cause": "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response',))"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_404(self):
        self.server.RequestHandlerClass = NotFound
        self._test_warnings({
            "response": "<Response [404]>",
            "warning_cause": "404"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_6_minutes_old(self):
        self.server.RequestHandlerClass = OkTooOld
        self._test_warnings({
            "response": "<Response [200]>",
            "response_json": {"status": "ok"},
            "warning_cause": "utc_remote < utc_min"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_ko(self):
        self.server.RequestHandlerClass = Ko
        file.touch()
        # then exit code 1 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            **base_stdout,
            "error_cause": "status ko",
            "exit_code": 1,
            "response": "<Response [200]>",
            "response_json": {"status": "ko"},
            "status": "ko",
            "warning_file": "deleted"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_fixing(self):
        self.server.RequestHandlerClass = Fixing
        self._test_warnings({
            "response": "<Response [200]>",
            "response_json": {"status": "fixing"},
            "status": "fixing",
            "warning_cause": "fixing"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_and_ok(self):
        self.server.RequestHandlerClass = Ok
        file.touch()
        # then exit code 0 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 0)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            **base_stdout,
            "modes": ["alpha"],
            "exit_code": 0,
            "response": "<Response [200]>",
            "response_json": {"modes": ["alpha"], "status": "ok"},
            "status": "ok",
            "warning_file": "deleted"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 0)
        (rc, stdout) = run("beta")
        self.assertEqual(rc, 1)

    def test_200_but_bad_utc(self):
        self.server.RequestHandlerClass = BadUtc
        self._test_warnings({
            "response": "<Response [200]>",
            "response_json": {"status": "ok"},
            "warning_cause": "Unknown string format"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_no_utc(self):
        self.server.RequestHandlerClass = NoUtc
        self._test_warnings({
            "response": "<Response [200]>",
            "response_json": {"status": "ok"},
            "warning_cause": "Parser must be a string or character stream, not NoneType"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_empty_response(self):
        self.server.RequestHandlerClass = EmptyResponse
        self._test_warnings({
            "response": "<Response [200]>",
            "warning_cause": "Expecting value: line 1 column 1 (char 0)"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_bad_status(self):
        self.server.RequestHandlerClass = BadStatus
        file.touch()
        # then exit code 1 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            **base_stdout,
            "error_cause": "status ko",
            "exit_code": 1,
            "response": "<Response [200]>",
            "response_json": {"status": "sudo rm -rf /"},
            "status": "sudo rm -rf /",
            "warning_file": "deleted"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)

    def test_200_but_no_status(self):
        self.server.RequestHandlerClass = NoStatus
        file.touch()
        # then exit code 1 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            **base_stdout,
            "error_cause": "status ko",
            "exit_code": 1,
            "response": "<Response [200]>",
            "response_json": {},
            "status": None,
            "warning_file": "deleted"
        })

        (rc, stdout) = run("alpha")
        self.assertEqual(rc, 1)


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
            "utc": (datetime.utcnow() - timedelta(minutes=31)).isoformat(),
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
            "status": "ok",
            "modes": ["alpha"]
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


class NoUtc(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
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


class NoStatus(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "utc": datetime.utcnow().isoformat()
        }).encode("utf-8"))


class EmptyResponse(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write("".encode("utf-8"))


unittest.main(verbosity=2)
