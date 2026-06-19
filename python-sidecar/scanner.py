"""Discovers installed Python packages and stdlib modules."""
import importlib.metadata
import os
import sys
import sysconfig
from typing import List, Dict


class PackageScanner:
    """Discovers packages available for symbol extraction."""

    def discover_stdlib(self) -> List[Dict]:
        """List all Python stdlib modules."""
        modules = []

        # Python 3.10+ has sys.stdlib_module_names
        if hasattr(sys, 'stdlib_module_names'):
            for name in sorted(sys.stdlib_module_names):
                if name.startswith('_'):
                    continue
                modules.append({
                    'name': name,
                    'source': 'stdlib',
                    'path': self._find_stdlib_path(name),
                    'version': f'{sys.version_info.major}.{sys.version_info.minor}',
                })
        else:
            # Fallback for Python < 3.10
            stdlib_path = sysconfig.get_paths()['stdlib']
            if os.path.isdir(stdlib_path):
                for entry in sorted(os.listdir(stdlib_path)):
                    name = entry.replace('.py', '')
                    if name.startswith('_') or name.startswith('.'):
                        continue
                    if entry.endswith('.py') or os.path.isdir(
                        os.path.join(stdlib_path, entry)
                    ):
                        modules.append({
                            'name': name,
                            'source': 'stdlib',
                            'path': os.path.join(stdlib_path, entry),
                            'version': f'{sys.version_info.major}.{sys.version_info.minor}',
                        })

        return modules

    def discover_installed(self) -> List[Dict]:
        """List all installed third-party packages."""
        packages = []
        seen = set()

        for dist in importlib.metadata.distributions():
            name = dist.metadata['Name']
            if name in seen:
                continue
            seen.add(name)

            # Find the actual package directory
            top_level = self._get_top_level_packages(dist)
            version = dist.metadata['Version']

            for pkg_name in top_level:
                if pkg_name.startswith('_'):
                    continue
                path = self._find_package_path(pkg_name)
                if path:
                    packages.append({
                        'name': pkg_name,
                        'dist_name': name,
                        'version': version,
                        'path': path,
                        'source': 'third-party',
                    })

        return packages

    def _get_top_level_packages(self, dist) -> List[str]:
        """Get top-level importable package names from a distribution."""
        # Try top_level.txt first
        try:
            top_level_text = dist.read_text('top_level.txt')
            if top_level_text:
                return [
                    line.strip()
                    for line in top_level_text.strip().split('\n')
                    if line.strip() and not line.strip().startswith('#')
                ]
        except (FileNotFoundError, TypeError):
            pass

        # Fallback: use distribution name as package name
        name = dist.metadata['Name']
        return [name.replace('-', '_').lower()]

    def _find_package_path(self, package_name: str) -> str:
        """Find filesystem path for a package."""
        for path in sys.path:
            pkg_dir = os.path.join(path, package_name)
            if os.path.isdir(pkg_dir):
                return pkg_dir
            pkg_file = os.path.join(path, package_name + '.py')
            if os.path.isfile(pkg_file):
                return pkg_file
        return ''

    def _find_stdlib_path(self, module_name: str) -> str:
        """Find filesystem path for a stdlib module."""
        paths = sysconfig.get_paths()
        stdlib_path = paths.get('stdlib', '')
        if stdlib_path:
            pkg_dir = os.path.join(stdlib_path, module_name)
            if os.path.isdir(pkg_dir):
                return pkg_dir
            pkg_file = os.path.join(stdlib_path, module_name + '.py')
            if os.path.isfile(pkg_file):
                return pkg_file
        return ''
