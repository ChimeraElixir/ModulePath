"""Resolves public exports from Python packages using AST analysis."""
import ast
import os
from typing import List, Dict, Optional


class ExportResolver:
    """Extracts public symbols from a Python package using static analysis.

    Resolution priority:
    1. __all__ (if defined, this IS the public API)
    2. Re-exports (from .x import y in __init__.py)
    3. Class definitions
    4. Function definitions
    5. Variable assignments
    """

    def resolve(self, package_path: str, package_name: str) -> List[Dict]:
        """Extract all public symbols from a package.

        Args:
            package_path: Filesystem path to the package directory or .py file.
            package_name: The importable package name.

        Returns:
            List of symbol dicts with keys: symbol, module, type.
        """
        if os.path.isfile(package_path) and package_path.endswith('.py'):
            return self._resolve_module_file(package_path, package_name)

        init_path = os.path.join(package_path, '__init__.py')
        if not os.path.isfile(init_path):
            return []

        return self._resolve_init(init_path, package_name)

    def _resolve_init(self, init_path: str, package_name: str) -> List[Dict]:
        """Resolve symbols from __init__.py."""
        try:
            with open(init_path, 'r', encoding='utf-8', errors='replace') as f:
                source = f.read()
            tree = ast.parse(source, filename=init_path)
        except (SyntaxError, UnicodeDecodeError):
            return []

        # Check for __all__ first (highest priority)
        all_list = self._extract_all(tree)
        if all_list is not None:
            return self._symbols_from_all(all_list, tree, package_name)

        # No __all__ — collect all public symbols
        symbols = []
        symbols.extend(self._extract_reexports(tree, package_name))
        symbols.extend(self._extract_definitions(tree, package_name))

        # Deduplicate by symbol name (re-exports take priority)
        seen = set()
        deduped = []
        for s in symbols:
            if s['symbol'] not in seen:
                seen.add(s['symbol'])
                deduped.append(s)

        return deduped

    def _resolve_module_file(
        self, file_path: str, module_name: str
    ) -> List[Dict]:
        """Resolve symbols from a single .py file (not a package)."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                source = f.read()
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return []

        all_list = self._extract_all(tree)
        if all_list is not None:
            return self._symbols_from_all(all_list, tree, module_name)

        return self._extract_definitions(tree, module_name)

    def _extract_all(self, tree: ast.Module) -> Optional[List[str]]:
        """Extract __all__ list if defined."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            return [
                                elt.value
                                for elt in node.value.elts
                                if isinstance(elt, ast.Constant)
                                and isinstance(elt.value, str)
                            ]
        return None

    def _symbols_from_all(
        self, all_names: List[str], tree: ast.Module, package_name: str
    ) -> List[Dict]:
        """Build symbol list from __all__ entries with type info."""
        type_map = self._build_type_map(tree)
        symbols = []
        for name in all_names:
            sym_type = type_map.get(name, 'variable')
            symbols.append({
                'symbol': name,
                'module': package_name,
                'type': sym_type,
            })
        return symbols

    def _extract_reexports(
        self, tree: ast.Module, package_name: str
    ) -> List[Dict]:
        """Extract re-exported symbols (from .x import y)."""
        symbols = []
        type_map = self._build_type_map(tree)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                if node.names:
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if name.startswith('_'):
                            continue
                        if name == '*':
                            continue
                        sym_type = type_map.get(name, 'variable')
                        symbols.append({
                            'symbol': name,
                            'module': package_name,
                            'type': sym_type,
                        })
        return symbols

    def _extract_definitions(
        self, tree: ast.Module, package_name: str
    ) -> List[Dict]:
        """Extract class, function, and variable definitions."""
        symbols = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
                symbols.append({
                    'symbol': node.name,
                    'module': package_name,
                    'type': 'class',
                })
            elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                symbols.append({
                    'symbol': node.name,
                    'module': package_name,
                    'type': 'function',
                })
            elif isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith('_'):
                symbols.append({
                    'symbol': node.name,
                    'module': package_name,
                    'type': 'function',
                })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith('_'):
                        if target.id == '__all__':
                            continue
                        symbols.append({
                            'symbol': target.id,
                            'module': package_name,
                            'type': 'variable',
                        })
        return symbols

    def _build_type_map(self, tree: ast.Module) -> Dict[str, str]:
        """Build a name→type mapping from definitions in the AST."""
        type_map = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                type_map[node.name] = 'class'
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                type_map[node.name] = 'function'
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        type_map[target.id] = 'variable'
        return type_map
