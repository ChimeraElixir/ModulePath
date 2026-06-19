# tests/sidecar/test_export_resolver.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar'))

from export_resolver import ExportResolver

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def test_extract_definitions():
    resolver = ExportResolver()
    pkg_path = os.path.join(FIXTURES_DIR, 'fake_pkg')
    symbols = resolver.resolve(pkg_path, 'fake_pkg')
    symbol_names = {s['symbol'] for s in symbols}
    assert 'MyClass' in symbol_names
    assert 'my_function' in symbol_names
    assert 'MY_CONSTANT' in symbol_names


def test_respects_all():
    resolver = ExportResolver()
    pkg_path = os.path.join(FIXTURES_DIR, 'fake_pkg_all')
    symbols = resolver.resolve(pkg_path, 'fake_pkg_all')
    symbol_names = {s['symbol'] for s in symbols}
    assert 'PublicClass' in symbol_names
    assert 'public_func' in symbol_names
    assert '_PrivateClass' not in symbol_names
    assert '_private_func' not in symbol_names


def test_reexports():
    resolver = ExportResolver()
    pkg_path = os.path.join(FIXTURES_DIR, 'fake_pkg_reexport')
    symbols = resolver.resolve(pkg_path, 'fake_pkg_reexport')
    symbol_names = {s['symbol'] for s in symbols}
    assert 'BaseModel' in symbol_names
    assert 'Field' in symbol_names
    for s in symbols:
        if s['symbol'] == 'BaseModel':
            assert s['module'] == 'fake_pkg_reexport'


def test_symbol_metadata():
    resolver = ExportResolver()
    pkg_path = os.path.join(FIXTURES_DIR, 'fake_pkg')
    symbols = resolver.resolve(pkg_path, 'fake_pkg')
    for s in symbols:
        assert 'symbol' in s
        assert 'module' in s
        assert 'type' in s
        assert s['type'] in ('class', 'function', 'variable', 'module')


def test_skips_private_symbols():
    resolver = ExportResolver()
    pkg_path = os.path.join(FIXTURES_DIR, 'fake_pkg')
    symbols = resolver.resolve(pkg_path, 'fake_pkg')
    for s in symbols:
        assert not s['symbol'].startswith('_')
