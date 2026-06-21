# tests/sidecar/test_runtime_fallback.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar'))

from runtime_fallback import RuntimeFallback


def test_import_stdlib_module():
    fb = RuntimeFallback(timeout=2)
    symbols = fb.extract_symbols('json')
    symbol_names = {s['symbol'] for s in symbols}
    assert 'dumps' in symbol_names
    assert 'loads' in symbol_names
    assert 'JSONDecodeError' in symbol_names


def test_blacklisted_package():
    fb = RuntimeFallback(timeout=2)
    symbols = fb.extract_symbols('tensorflow')
    assert symbols is None


def test_timeout_handling():
    fb = RuntimeFallback(timeout=0.001)
    result = fb.extract_symbols('os')
    # Should not crash


def test_nonexistent_package():
    fb = RuntimeFallback(timeout=2)
    symbols = fb.extract_symbols('nonexistent_pkg_xyz_123')
    assert symbols is None or symbols == []


def test_symbol_metadata():
    fb = RuntimeFallback(timeout=2)
    symbols = fb.extract_symbols('json')
    for s in symbols:
        assert 'symbol' in s
        assert 'type' in s
        assert s['type'] in ('class', 'function', 'variable', 'module')
