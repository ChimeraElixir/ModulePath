# tests/sidecar/test_scanner.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'python-sidecar'))

from scanner import PackageScanner


def test_discover_stdlib_modules():
    scanner = PackageScanner()
    modules = scanner.discover_stdlib()
    module_names = {m['name'] for m in modules}
    assert 'os' in module_names
    assert 'sys' in module_names
    assert 'json' in module_names
    assert 'pathlib' in module_names
    assert 'collections' in module_names
    assert len(modules) > 100


def test_discover_installed_packages():
    scanner = PackageScanner()
    packages = scanner.discover_installed()
    assert len(packages) > 0
    pkg_names = {p['name'] for p in packages}
    assert 'pip' in pkg_names


def test_package_info_structure():
    scanner = PackageScanner()
    packages = scanner.discover_installed()
    for pkg in packages[:5]:
        assert 'name' in pkg
        assert 'version' in pkg
        assert 'path' in pkg


def test_stdlib_info_structure():
    scanner = PackageScanner()
    modules = scanner.discover_stdlib()
    for mod in modules[:5]:
        assert 'name' in mod
        assert 'source' in mod
        assert mod['source'] == 'stdlib'
