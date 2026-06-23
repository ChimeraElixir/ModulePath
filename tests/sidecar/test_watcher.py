# tests/sidecar/test_watcher.py
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar'))

from watcher import VenvWatcher


def test_detect_new_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        events = []
        watcher = VenvWatcher(tmpdir, on_change=lambda e: events.append(e))
        watcher.poll_once()

        os.makedirs(os.path.join(tmpdir, 'new_package'))
        watcher.poll_once()

        assert any(e['type'] == 'added' and e['name'] == 'new_package' for e in events)


def test_detect_removed_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = os.path.join(tmpdir, 'old_package')
        os.makedirs(pkg_dir)

        events = []
        watcher = VenvWatcher(tmpdir, on_change=lambda e: events.append(e))
        watcher.poll_once()

        os.rmdir(pkg_dir)
        watcher.poll_once()

        assert any(e['type'] == 'removed' and e['name'] == 'old_package' for e in events)
