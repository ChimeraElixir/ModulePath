# tests/sidecar/test_main.py
import json
import subprocess
import sys
import os

SIDECAR_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar', 'main.py')

def run_sidecar_command(cmd: dict) -> dict:
    """Send a single command to sidecar and get response."""
    proc = subprocess.Popen(
        [sys.executable, SIDECAR_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate(json.dumps(cmd) + '\n', timeout=10)
    lines = [l for l in stdout.strip().split('\n') if l]
    assert len(lines) >= 1, f"No output from sidecar. stderr: {stderr}"
    return json.loads(lines[-1])


def test_status_command():
    result = run_sidecar_command({"cmd": "status"})
    assert result["cmd"] == "status"
    assert "ready" in result


def test_unknown_command():
    result = run_sidecar_command({"cmd": "unknown_xyz"})
    assert result["cmd"] == "error"
    assert "unknown" in result.get("message", "").lower()


def test_search_returns_results_format():
    result = run_sidecar_command({"cmd": "search", "query": "path", "limit": 5})
    assert result["cmd"] == "search"
    assert "results" in result
    assert isinstance(result["results"], list)
