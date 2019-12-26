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

file = pathlib.Path("heal-check-4411def9d576984c8d78253236b2a62f")


def run():
    sp = subprocess.Popen("../src/heal-check http://127.0.0.1:8000 -f heal-check-", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = sp.communicate()
    stdout_json = json.loads(stdout)
    stdout_json.pop("utc_now", "")
    stdout_json.pop("utc_min", "")
    stdout_json.pop("utc_file", "")
    stdout_json.pop("utc_remote", "")
    stdout_json.pop("file_content", "")
    stdout_json.pop("response_text", "")
    stdout_json.get("response_json", {}).pop("utc", "")
    return sp.returncode, stdout_json


class TestCase(unittest.TestCase):
    def setUp(self):
        # starting the mock server
        self.server = MockHealHTTPServer()
        threading.Thread(target=self.server.serve_forever).start()

    def tearDown(self):
        # stopping the mock server
        self.server.shutdown()

    def warnings(self):
        if file.exists():
            file.unlink()

        # test a: no warning beforehand
        just_before = datetime.utcnow()
        # then: exit code 0 + warning created just now
        (rc, stdout0) = run()
        self.assertEqual(rc, 0)
        self.assertTrue(file.exists())
        self.assertGreaterEqual(dateutil.parser.parse(file.read_text()), just_before)

        # test b: warning 29 minutes ago
        four_minutes_ago = (datetime.utcnow() - timedelta(minutes=29)).isoformat()
        file.write_text(four_minutes_ago)
        # then: exit code 0 + warning unchanged
        (rc, stdout29) = run()
        self.assertEqual(rc, 0)
        self.assertTrue(file.exists())
        self.assertEqual(file.read_text(), four_minutes_ago)

        # test c: warning 31 minutes ago
        six_minutes_ago = (datetime.utcnow() - timedelta(minutes=31)).isoformat()
        file.write_text(six_minutes_ago)
        # then: exit code 1 + any warning is removed
        (rc, stdout31) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())

        return stdout0, stdout29, stdout31

    def test_server_not_responding(self):
        (stdout0, stdout29, stdout31) = self.warnings()
        self.assertEqual(stdout0, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response',))",
            'warning_file': 'created'
        })
        self.assertEqual(stdout29, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response',))",
            'warning_file': 'unchanged'
        })
        self.assertEqual(stdout31, {
            'delay': 30,
            'error_cause': 'utc_file < utc_min',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response',))",
            'warning_file': 'deleted'
        })

    def test_404(self):
        self.server.RequestHandlerClass = NotFound
        (stdout0, stdout29, stdout31) = self.warnings()
        self.assertEqual(stdout0, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [404]>',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 404,
            'warning_file': 'created'
        })
        self.assertEqual(stdout29, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [404]>',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 404,
            'warning_file': 'unchanged'
        })
        self.assertEqual(stdout31, {
            'delay': 30,
            'error_cause': 'utc_file < utc_min',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [404]>',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 404,
            'warning_file': 'deleted'
        })

    def test_200_but_6_minutes_old(self):
        self.server.RequestHandlerClass = OkTooOld
        (stdout0, stdout29, stdout31) = self.warnings()
        self.assertEqual(stdout0, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'utc_remote < utc_min',
            'warning_file': 'created'
        })
        self.assertEqual(stdout29, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'utc_remote < utc_min',
            'warning_file': 'unchanged'
        })
        self.assertEqual(stdout31, {
            'delay': 30,
            'error_cause': 'utc_file < utc_min',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'utc_remote < utc_min',
            'warning_file': 'deleted'
        })

    def test_200_but_ko(self):
        self.server.RequestHandlerClass = Ko
        file.touch()
        # then exit code 1 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            'delay': 30,
            'error_cause': 'status ko',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ko'},
            'status': 'ko',
            'uri': 'http://127.0.0.1:8000',
            'warning_file': 'deleted'
        })

    def test_200_but_fixing(self):
        self.server.RequestHandlerClass = Fixing
        (stdout0, stdout29, stdout31) = self.warnings()
        self.assertEqual(stdout0, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'fixing'},
            'status': 'fixing',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'fixing',
            'warning_file': 'created'
        })
        self.assertEqual(stdout29, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'fixing'},
            'status': 'fixing',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'fixing',
            'warning_file': 'unchanged'
        })
        self.assertEqual(stdout31, {
            'delay': 30,
            'error_cause': 'utc_file < utc_min',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'fixing'},
            'status': 'fixing',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'fixing',
            'warning_file': 'deleted'
        })

    def test_200_and_ok(self):
        self.server.RequestHandlerClass = Ok
        file.touch()
        # then exit code 0 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 0)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'status': 'ok',
            'uri': 'http://127.0.0.1:8000',
            'warning_file': 'deleted'
        })

    def test_200_but_bad_utc(self):
        self.server.RequestHandlerClass = BadUtc
        (stdout0, stdout29, stdout31) = self.warnings()
        self.assertEqual(stdout0, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'Unknown string format',
            'warning_file': 'created'
        })
        self.assertEqual(stdout29, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'Unknown string format',
            'warning_file': 'unchanged'
        })
        self.assertEqual(stdout31, {
            'delay': 30,
            'error_cause': 'utc_file < utc_min',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'ok'},
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'Unknown string format',
            'warning_file': 'deleted'
        })

    def test_200_but_empty_response(self):
        self.server.RequestHandlerClass = EmptyResponse
        (stdout0, stdout29, stdout31) = self.warnings()
        self.assertEqual(stdout0, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'Expecting value: line 1 column 1 (char 0)',
            'warning_file': 'created'
        })
        self.assertEqual(stdout29, {
            'delay': 30,
            'exit_code': 0,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'Expecting value: line 1 column 1 (char 0)',
            'warning_file': 'unchanged'
        })
        self.assertEqual(stdout31, {
            'delay': 30,
            'error_cause': 'utc_file < utc_min',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'uri': 'http://127.0.0.1:8000',
            'warning_cause': 'Expecting value: line 1 column 1 (char 0)',
            'warning_file': 'deleted'
        })

    def test_200_but_bad_status(self):
        self.server.RequestHandlerClass = BadStatus
        file.touch()
        # then exit code 1 + any warning is removed
        (rc, stdout) = run()
        self.assertEqual(rc, 1)
        self.assertFalse(file.exists())
        self.assertEqual(stdout, {
            'delay': 30,
            'error_cause': 'status ko',
            'exit_code': 1,
            'file_path': 'heal-check-4411def9d576984c8d78253236b2a62f',
            'file_prefix': 'heal-check-',
            'response': '<Response [200]>',
            'response_json': {'status': 'sudo rm -rf /'},
            'status': 'sudo rm -rf /',
            'uri': 'http://127.0.0.1:8000',
            'warning_file': 'deleted'
        })


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


class EmptyResponse(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write("".encode("utf-8"))


unittest.main(verbosity=2)
