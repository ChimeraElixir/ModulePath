"""Watches virtual environment site-packages for changes."""
import os
import threading
import time
from typing import Callable, Dict, Set


class VenvWatcher:
    """Polls a directory for added/removed subdirectories."""

    def __init__(
        self,
        watch_path: str,
        on_change: Callable[[Dict], None],
        poll_interval: float = 5.0,
    ):
        self.watch_path = watch_path
        self.on_change = on_change
        self.poll_interval = poll_interval
        self._known_entries: Set[str] = set()
        self._running = False
        self._thread = None

        # Initialize known entries
        if os.path.isdir(watch_path):
            self._known_entries = self._list_dirs()

    def _list_dirs(self) -> Set[str]:
        """List directory names in watched path."""
        try:
            return {
                entry
                for entry in os.listdir(self.watch_path)
                if os.path.isdir(os.path.join(self.watch_path, entry))
                and not entry.startswith('.')
                and not entry.startswith('_')
                and not entry.endswith('.dist-info')
                and not entry.endswith('.egg-info')
            }
        except OSError:
            return set()

    def poll_once(self):
        """Check for changes once."""
        current = self._list_dirs()

        added = current - self._known_entries
        removed = self._known_entries - current

        for name in added:
            self.on_change({'type': 'added', 'name': name})

        for name in removed:
            self.on_change({'type': 'removed', 'name': name})

        self._known_entries = current

    def start(self):
        """Start polling in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop polling."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _poll_loop(self):
        """Background polling loop."""
        while self._running:
            self.poll_once()
            time.sleep(self.poll_interval)
