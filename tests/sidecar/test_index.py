# tests/sidecar/test_index.py
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar'))

from index import SymbolIndex


def make_index(db_path=None):
    if db_path is None:
        db_path = os.path.join(tempfile.mkdtemp(), 'test.db')
    idx = SymbolIndex(db_path)
    return idx


def test_add_and_search():
    idx = make_index()
    idx.add_symbols('pathlib', '3.12', 'stdlib', [
        {'symbol': 'Path', 'module': 'pathlib', 'type': 'class'},
        {'symbol': 'PurePath', 'module': 'pathlib', 'type': 'class'},
    ])
    results = idx.search('Path')
    symbols = [r['symbol'] for r in results]
    assert 'Path' in symbols


def test_exact_match_ranks_higher():
    idx = make_index()
    idx.add_symbols('pathlib', '3.12', 'stdlib', [
        {'symbol': 'Path', 'module': 'pathlib', 'type': 'class'},
        {'symbol': 'PurePath', 'module': 'pathlib', 'type': 'class'},
        {'symbol': 'PureWindowsPath', 'module': 'pathlib', 'type': 'class'},
    ])
    results = idx.search('Path')
    assert results[0]['symbol'] == 'Path'


def test_stdlib_boost():
    idx = make_index()
    idx.add_symbols('pathlib', '3.12', 'stdlib', [
        {'symbol': 'Path', 'module': 'pathlib', 'type': 'class'},
    ])
    idx.add_symbols('click', '8.0', 'third-party', [
        {'symbol': 'Path', 'module': 'click', 'type': 'class'},
    ])
    results = idx.search('Path')
    assert results[0]['module'] == 'pathlib'


def test_search_history_boost():
    idx = make_index()
    idx.add_symbols('pathlib', '3.12', 'stdlib', [
        {'symbol': 'Path', 'module': 'pathlib', 'type': 'class'},
    ])
    idx.add_symbols('click', '8.0', 'third-party', [
        {'symbol': 'Path', 'module': 'click', 'type': 'class'},
    ])
    for _ in range(10):
        idx.record_selection('Path', 'click')
    results = idx.search('Path')
    assert results[0]['module'] == 'click'


def test_fuzzy_search():
    idx = make_index()
    idx.add_symbols('pydantic', '2.0', 'third-party', [
        {'symbol': 'BaseModel', 'module': 'pydantic', 'type': 'class'},
    ])
    results = idx.search('bsmdl')
    symbols = [r['symbol'] for r in results]
    assert 'BaseModel' in symbols


def test_limit():
    idx = make_index()
    symbols = [
        {'symbol': f'Func{i}', 'module': 'pkg', 'type': 'function'}
        for i in range(50)
    ]
    idx.add_symbols('pkg', '1.0', 'third-party', symbols)
    results = idx.search('Func', limit=5)
    assert len(results) <= 5


def test_package_version_change_reindex():
    idx = make_index()
    idx.add_symbols('pkg', '1.0', 'third-party', [
        {'symbol': 'OldFunc', 'module': 'pkg', 'type': 'function'},
    ])
    idx.add_symbols('pkg', '2.0', 'third-party', [
        {'symbol': 'NewFunc', 'module': 'pkg', 'type': 'function'},
    ])
    results = idx.search('OldFunc')
    old_syms = [r['symbol'] for r in results]
    assert 'OldFunc' not in old_syms
    results = idx.search('NewFunc')
    new_syms = [r['symbol'] for r in results]
    assert 'NewFunc' in new_syms


def test_remove_package():
    idx = make_index()
    idx.add_symbols('pkg', '1.0', 'third-party', [
        {'symbol': 'MyFunc', 'module': 'pkg', 'type': 'function'},
    ])
    idx.remove_package('pkg')
    results = idx.search('MyFunc')
    assert len(results) == 0


def test_is_indexed():
    idx = make_index()
    assert not idx.is_package_indexed('pkg')
    idx.add_symbols('pkg', '1.0', 'third-party', [
        {'symbol': 'X', 'module': 'pkg', 'type': 'variable'},
    ])
    assert idx.is_package_indexed('pkg')
