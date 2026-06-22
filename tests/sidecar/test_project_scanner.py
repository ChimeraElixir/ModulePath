# tests/sidecar/test_project_scanner.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar'))

from project_scanner import ProjectScanner

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_project')


def test_discover_project_symbols():
    scanner = ProjectScanner(FIXTURES_DIR)
    symbols = scanner.scan()
    symbol_names = {s['symbol'] for s in symbols}
    assert 'UserService' in symbol_names
    assert 'create_user' in symbol_names
    assert 'User' in symbol_names


def test_import_paths_are_correct():
    scanner = ProjectScanner(FIXTURES_DIR)
    symbols = scanner.scan()
    for s in symbols:
        if s['symbol'] == 'UserService':
            assert s['module'] == 'myapp.services.user'
        if s['symbol'] == 'User':
            assert s['module'] in ('myapp.models', 'myapp.models.user')


def test_source_is_local():
    scanner = ProjectScanner(FIXTURES_DIR)
    symbols = scanner.scan()
    for s in symbols:
        assert s['source'] == 'local'


def test_skips_private_symbols():
    scanner = ProjectScanner(FIXTURES_DIR)
    symbols = scanner.scan()
    for s in symbols:
        assert not s['symbol'].startswith('_')
