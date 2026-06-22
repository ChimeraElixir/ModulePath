"""Scans local project files for importable symbols."""
import ast
import os
from typing import List, Dict


class ProjectScanner:
    """Discovers symbols defined in the local workspace project."""

    def __init__(self, project_root: str):
        self.project_root = project_root
        # Detect src layout
        src_dir = os.path.join(project_root, 'src')
        if os.path.isdir(src_dir):
            self.base_dir = src_dir
        else:
            self.base_dir = project_root

    def scan(self) -> List[Dict]:
        """Scan all .py files in the project and extract symbols."""
        symbols = []
        for dirpath, dirnames, filenames in os.walk(self.base_dir):
            # Skip hidden dirs, __pycache__, .venv, node_modules, etc.
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith('.')
                and d != '__pycache__'
                and d != 'node_modules'
                and d != '.venv'
                and d != 'venv'
            ]

            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                if filename.startswith('_') and filename != '__init__.py':
                    continue

                filepath = os.path.join(dirpath, filename)
                module_path = self._file_to_module(filepath)
                if module_path is None:
                    continue

                file_symbols = self._extract_symbols(filepath, module_path)
                symbols.extend(file_symbols)

        return symbols

    def _file_to_module(self, filepath: str) -> str:
        """Convert a file path to a Python module path."""
        rel_path = os.path.relpath(filepath, self.base_dir)

        # Skip files not in a package (no __init__.py in parent dirs)
        parts = rel_path.split(os.sep)
        # Check parent directories have __init__.py
        for i in range(len(parts) - 1):
            parent = os.path.join(self.base_dir, *parts[: i + 1])
            if os.path.isdir(parent):
                init_file = os.path.join(parent, '__init__.py')
                if not os.path.isfile(init_file):
                    return None

        # Convert path to module notation
        if parts[-1] == '__init__.py':
            if len(parts) == 1:
                return None  # root __init__.py
            module_parts = parts[:-1]
        else:
            module_parts = parts[:-1] + [parts[-1].replace('.py', '')]

        return '.'.join(module_parts)

    def _extract_symbols(
        self, filepath: str, module_path: str
    ) -> List[Dict]:
        """Extract public symbols from a Python file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except (SyntaxError, UnicodeDecodeError):
            return []

        symbols = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
                symbols.append({
                    'symbol': node.name,
                    'module': module_path,
                    'type': 'class',
                    'source': 'local',
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('_'):
                    symbols.append({
                        'symbol': node.name,
                        'module': module_path,
                        'type': 'function',
                        'source': 'local',
                    })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith('_'):
                        symbols.append({
                            'symbol': target.id,
                            'module': module_path,
                            'type': 'variable',
                            'source': 'local',
                        })
            # Handle re-exports in __init__.py
            elif isinstance(node, ast.ImportFrom) and os.path.basename(filepath) == '__init__.py':
                if node.module and node.module.startswith('.'):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if not name.startswith('_') and name != '*':
                            symbols.append({
                                'symbol': name,
                                'module': module_path,
                                'type': 'variable',  # approximate
                                'source': 'local',
                            })

        return symbols
