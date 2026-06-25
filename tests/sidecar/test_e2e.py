# tests/sidecar/test_e2e.py
import json
import subprocess
import sys
import os
import tempfile

SIDECAR_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'python-sidecar', 'main.py'
)


def run_sidecar_session(commands: list, timeout: int = 30) -> list:
    db_dir = tempfile.mkdtemp()
    db_path = os.path.join(db_dir, 'test.db')

    input_text = '\n'.join(json.dumps(c) for c in commands) + '\n'

    proc = subprocess.Popen(
        [sys.executable, SIDECAR_PATH, '--db', db_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(input_text, timeout=timeout)

    responses = []
    for line in stdout.strip().split('\n'):
        if line.strip():
            responses.append(json.loads(line))
    return responses


def test_e2e_search_path():
    responses = run_sidecar_session([
        {'cmd': 'search', 'query': 'Path', 'limit': 10},
    ])
    assert responses[0]['cmd'] == 'ready'
    search_response = responses[1]
    assert search_response['cmd'] == 'search'
    symbols = [r['symbol'] for r in search_response['results']]
    assert 'Path' in symbols


def test_e2e_status():
    responses = run_sidecar_session([{'cmd': 'status'}])
    status = responses[1]
    assert status['cmd'] == 'status'
    assert status['ready'] is True
    assert status['symbols'] > 0


def test_e2e_search_no_crash():
    responses = run_sidecar_session([
        {'cmd': 'search', 'query': 'BaseModel', 'limit': 10},
    ])
    search_response = responses[1]
    assert search_response['cmd'] == 'search'
    assert isinstance(search_response['results'], list)
