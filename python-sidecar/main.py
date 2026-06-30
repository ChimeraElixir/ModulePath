"""ModulePath Python Sidecar — JSON Lines protocol over stdin/stdout."""
import json
import os
import sys
import tempfile
import threading
import traceback

from scanner import PackageScanner
from export_resolver import ExportResolver
from index import SymbolIndex
from runtime_fallback import RuntimeFallback
from project_scanner import ProjectScanner
from watcher import VenvWatcher


class SidecarServer:
    """Handles JSON commands from the VS Code extension."""

    def __init__(self, db_path: str, project_root: str = None):
        self.scanner = PackageScanner()
        self.resolver = ExportResolver()
        self.index = SymbolIndex(db_path)
        self.fallback = RuntimeFallback(timeout=2.0)
        self.project_root = project_root
        self.project_scanner = ProjectScanner(project_root) if project_root else None
        self.watcher = None

        self.ready = False
        self._packages_cache = {}  # name → {version, path, source}
        self._aliases = self._load_aliases()

        self.handlers = {
            'status': self.handle_status,
            'search': self.handle_search,
            'refresh': self.handle_refresh,
            'index_package': self.handle_index_package,
            'record_selection': self.handle_record_selection,
            'set_project_root': self.handle_set_project_root,
        }

    def _load_aliases(self) -> dict:
        aliases_path = os.path.join(os.path.dirname(__file__), 'aliases.json')
        if os.path.isfile(aliases_path):
            with open(aliases_path, 'r') as f:
                return json.load(f)
        return {}

    def initialize(self):
        """Phase 1+2: Discover packages and index stdlib."""
        # Discover all packages (fast, no scanning)
        stdlib_modules = self.scanner.discover_stdlib()
        installed_packages = self.scanner.discover_installed()

        # Cache package info
        for mod in stdlib_modules:
            self._packages_cache[mod['name']] = mod
        for pkg in installed_packages:
            self._packages_cache[pkg['name']] = pkg

        # Phase 2: Index stdlib immediately (small, fast)
        for mod in stdlib_modules:
            if not self.index.is_package_indexed(mod['name']):
                self._index_package(mod)

        # Index aliases
        self._index_aliases()

        # Index local project if available
        if self.project_scanner:
            self._index_project()

        self.ready = True

        # Start venv watcher
        site_packages = self._find_site_packages()
        if site_packages:
            self.watcher = VenvWatcher(
                site_packages,
                on_change=self._on_venv_change,
                poll_interval=5.0,
            )
            self.watcher.start()

        # Phase 4: Background idle indexing of remaining packages
        bg_thread = threading.Thread(target=self._background_index, daemon=True)
        bg_thread.start()

    def _find_site_packages(self) -> str:
        """Find the site-packages directory."""
        for path in sys.path:
            if 'site-packages' in path and os.path.isdir(path):
                return path
        return ''

    def _on_venv_change(self, event: dict):
        """Handle venv package changes."""
        name = event['name']
        if event['type'] == 'added':
            pkg_info = self._packages_cache.get(name)
            if pkg_info:
                self._index_package(pkg_info)
        elif event['type'] == 'removed':
            self.index.remove_package(name)

    def _index_package(self, pkg_info: dict):
        """Index a single package."""
        name = pkg_info['name']
        version = pkg_info.get('version', '')
        source = pkg_info.get('source', 'third-party')
        path = pkg_info.get('path', '')

        # Check if already indexed with same version
        cached_version = self.index.get_package_version(name)
        if cached_version == version and self.index.is_package_indexed(name):
            return

        # Emit progress
        progress_msg = json.dumps({'cmd': 'progress', 'message': f'Parsing {name}'})
        sys.stdout.write(progress_msg + '\n')
        sys.stdout.flush()

        symbols = []
        if path:
            symbols = self.resolver.resolve(path, name)

        # Runtime fallback if static found nothing
        if not symbols:
            fb_symbols = self.fallback.extract_symbols(name)
            if fb_symbols:
                symbols = fb_symbols

        if symbols:
            self.index.add_symbols(name, version, source, symbols)

    def _index_aliases(self):
        """Add alias entries to the index."""
        alias_symbols = []
        for alias, info in self._aliases.items():
            alias_symbols.append({
                'symbol': alias,
                'module': info['module'],
                'type': 'module',
            })
        if alias_symbols:
            self.index.add_symbols(
                '__aliases__', '1.0', 'third-party', alias_symbols
            )

    def _index_project(self):
        """Index local project symbols."""
        if self.project_scanner:
            symbols = self.project_scanner.scan()
            if symbols:
                self.index.add_symbols(
                    '__project__', '0.0.0', 'local', symbols
                )

    def _background_index(self):
        """Phase 4: Index remaining packages in background."""
        for name, pkg_info in self._packages_cache.items():
            if pkg_info.get('source') == 'stdlib':
                continue  # already indexed
            if self.index.is_package_indexed(name):
                continue
            try:
                self._index_package(pkg_info)
            except Exception:
                pass  # skip problematic packages

    def handle_status(self, cmd: dict) -> dict:
        stats = self.index.get_stats()
        return {
            'cmd': 'status',
            'ready': self.ready,
            **stats,
        }

    def handle_search(self, cmd: dict) -> dict:
        query = cmd.get('query', '')
        limit = cmd.get('limit', 20)

        # Phase 3: On-demand indexing
        for name, pkg_info in self._packages_cache.items():
            if query.lower() in name.lower() and not self.index.is_package_indexed(name):
                self._index_package(pkg_info)

        results = self.index.search(query, limit=limit)

        # Check for alias matches
        if query.lower() in self._aliases:
            alias_info = self._aliases[query.lower()]
            alias_result = {
                'symbol': query.lower(),
                'module': alias_info['module'],
                'type': 'module',
                'source': 'third-party',
                'importStyle': alias_info['importStyle'],
                'alias': query.lower(),
                'score': 200,  # high priority for exact alias match
            }
            results.insert(0, alias_result)

        return {
            'cmd': 'search',
            'indexed': True,
            'results': results,
        }

    def handle_refresh(self, cmd: dict) -> dict:
        self._packages_cache.clear()
        self.initialize()
        stats = self.index.get_stats()
        return {
            'cmd': 'refresh',
            'status': 'ok',
            'symbolCount': stats['symbols'],
        }

    def handle_index_package(self, cmd: dict) -> dict:
        package = cmd.get('package', '')
        pkg_info = self._packages_cache.get(package)
        if pkg_info:
            self._index_package(pkg_info)
            return {
                'cmd': 'index_package',
                'status': 'ok',
                'package': package,
            }
        return {
            'cmd': 'index_package',
            'status': 'error',
            'message': f'Package not found: {package}',
        }

    def handle_record_selection(self, cmd: dict) -> dict:
        symbol = cmd.get('symbol', '')
        module = cmd.get('module', '')
        self.index.record_selection(symbol, module)
        return {'cmd': 'record_selection', 'status': 'ok'}

    def handle_set_project_root(self, cmd: dict) -> dict:
        root = cmd.get('root', '')
        if root and os.path.isdir(root):
            self.project_root = root
            self.project_scanner = ProjectScanner(root)
            self._index_project()
            return {'cmd': 'set_project_root', 'status': 'ok'}
        return {'cmd': 'set_project_root', 'status': 'error', 'message': 'Invalid path'}

    def handle_command(self, line: str) -> str:
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError as e:
            return json.dumps({'cmd': 'error', 'message': f'Invalid JSON: {e}'})

        cmd_name = cmd.get('cmd', '')
        handler = self.handlers.get(cmd_name)
        if handler is None:
            return json.dumps({
                'cmd': 'error',
                'message': f'Unknown command: {cmd_name}',
            })

        try:
            result = handler(cmd)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({
                'cmd': 'error',
                'message': str(e),
                'traceback': traceback.format_exc(),
            })

    def run(self):
        """Main loop: read JSON lines from stdin, write responses to stdout."""
        # Initialize and send ready signal
        self.initialize()
        ready_msg = json.dumps({'cmd': 'ready', **self.index.get_stats()})
        sys.stdout.write(ready_msg + '\n')
        sys.stdout.flush()

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            response = self.handle_command(line)
            sys.stdout.write(response + '\n')
            sys.stdout.flush()


def main():
    # Parse args
    db_path = None
    project_root = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--db' and i + 1 < len(args):
            db_path = args[i + 1]
            i += 2
        elif args[i] == '--project' and i + 1 < len(args):
            project_root = args[i + 1]
            i += 2
        else:
            i += 1

    if db_path is None:
        cache_dir = os.path.join(tempfile.gettempdir(), 'modulepath')
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, 'index.db')

    server = SidecarServer(db_path=db_path, project_root=project_root)
    server.run()


if __name__ == '__main__':
    main()
