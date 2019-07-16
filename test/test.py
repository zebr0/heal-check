#!/usr/bin/python3 -u

import pathlib
import subprocess
import sys
import threading
from datetime import datetime, timedelta

import dateutil.parser
import mock

file = pathlib.Path("heal-check-4411def9d576984c8d78253236b2a62f")


def run():
    return subprocess.Popen("../src/heal-check http://127.0.0.1:8000 -f heal-check- -d 5", shell=True, stdout=sys.stdout, stderr=sys.stderr).wait()


def test_warnings():
    if file.exists():
        file.unlink()

    # test a: no warning beforehand
    just_before = datetime.utcnow()
    # then: exit code 0 + warning created just now
    assert run() == 0
    assert file.exists()
    assert dateutil.parser.parse(file.read_text()) >= just_before

    # test b: warning 4 minutes ago
    four_minutes_ago = (datetime.utcnow() - timedelta(minutes=4)).isoformat()
    file.write_text(four_minutes_ago)
    # then: exit code 0 + warning unchanged
    assert run() == 0
    assert file.exists()
    assert file.read_text() == four_minutes_ago

    # test c: warning 6 minutes ago
    six_minutes_ago = (datetime.utcnow() - timedelta(minutes=6)).isoformat()
    file.write_text(six_minutes_ago)
    # then: exit code 1 + any warning is removed
    assert run() == 1
    assert not file.exists()


# test 1: server not responding
test_warnings()

# starting the mock server
server = mock.MockHealHTTPServer()
threading.Thread(target=server.serve_forever).start()

# test 2: 404
server.RequestHandlerClass = mock.NotFound
test_warnings()

# test 3: 200 but 6 minutes old
server.RequestHandlerClass = mock.OkTooOld
test_warnings()

# test 4: 200 but ko
server.RequestHandlerClass = mock.Ko
file.write_text((datetime.utcnow() - timedelta(minutes=1)).isoformat())
# then exit code 1 + any warning is removed
assert run() == 1
assert not file.exists()

# test 5: 200 but fixing
server.RequestHandlerClass = mock.Fixing
test_warnings()

# test 6: 200 and ok
server.RequestHandlerClass = mock.Ok
file.write_text((datetime.utcnow() - timedelta(minutes=1)).isoformat())
# then exit code 0 + any warning is removed
assert run() == 0
assert not file.exists()

# test 7: 200 but bad utc
server.RequestHandlerClass = mock.BadUtc
# then exit code 1 + any warning is removed
assert run() == 1
assert not file.exists()

# test 8: 200 but bad status
server.RequestHandlerClass = mock.BadStatus
# then exit code 1 + any warning is removed
assert run() == 1
assert not file.exists()

server.shutdown()  # todo: fix hang when assert fails (use unittest)
