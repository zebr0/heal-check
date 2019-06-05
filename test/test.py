#!/usr/bin/python3 -u

import pathlib
import subprocess
import sys
import threading
from datetime import datetime, timedelta

import dateutil.parser
import mock

first_error = pathlib.Path("first_error")


def run():
    return subprocess.Popen("../src/heal-check http://127.0.0.1:8000 first_error", shell=True, stdout=sys.stdout, stderr=sys.stderr).wait()


def test_ko():
    # test a: no first error timestamp
    just_before = datetime.utcnow()
    # then: exit code 0 + first error timestamp created at now
    assert run() == 0
    assert first_error.exists() and dateutil.parser.parse(first_error.read_text()) >= just_before

    # test b: first error 4 minutes ago
    four_minutes_ago = (datetime.utcnow() - timedelta(minutes=4)).isoformat()
    first_error.write_text(four_minutes_ago)
    # then: exit code 0 + first error timestamp unchanged
    assert run() == 0
    assert first_error.exists() and first_error.read_text() == four_minutes_ago

    # test c: first error 6 minutes ago
    six_minutes_ago = (datetime.utcnow() - timedelta(minutes=6)).isoformat()
    first_error.write_text(six_minutes_ago)
    # then: exit code 1 + first error timestamp unchanged
    assert run() == 1 and first_error.read_text() == six_minutes_ago


# cleans a potentially failed previous test run
if first_error.exists():
    first_error.unlink()

# test 1: server not responding
test_ko()
first_error.unlink()

# starting the mock server
server = mock.MockHealHTTPServer()
threading.Thread(target=server.serve_forever).start()

# test 2: 404
server.RequestHandlerClass = mock.NotFoundRH
test_ko()
first_error.unlink()

# test 3: 200 but 6 minutes old
server.RequestHandlerClass = mock.OkTooOldRH
test_ko()
first_error.unlink()

server.shutdown()
