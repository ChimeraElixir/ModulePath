"""Safe runtime import fallback with timeout and blacklist."""
import importlib
import inspect
import signal
import types
from typing import List, Dict, Optional

BLACKLISTED_PACKAGES = frozenset({
    'tensorflow', 'torch', 'jax', 'cv2',
    'scipy', 'matplotlib', 'sklearn',
    'transformers', 'datasets', 'keras',
    'theano', 'caffe', 'mxnet',
})


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError('Import timed out')


class RuntimeFallback:
    """Extract symbols by actually importing a package.

    Used only when static analysis fails. Protected by timeout and blacklist.
    """

    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout

    def extract_symbols(self, package_name: str) -> Optional[List[Dict]]:
        """Import a package and extract its public symbols.

        Returns:
            List of symbol dicts, or None if refused/failed.
        """
        if package_name in BLACKLISTED_PACKAGES:
            return None

        try:
            module = self._safe_import(package_name)
            if module is None:
                return None
            return self._extract_from_module(module, package_name)
        except Exception:
            return None

    def _safe_import(self, package_name: str) -> Optional[types.ModuleType]:
        """Import with timeout protection."""
        # Use signal-based timeout on Unix
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self.timeout)
            try:
                module = importlib.import_module(package_name)
                return module
            except _TimeoutError:
                return None
            except ImportError:
                return None
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            # Windows fallback — no timeout protection
            try:
                module = importlib.import_module(package_name)
                return module
            except ImportError:
                return None

    def _extract_from_module(
        self, module: types.ModuleType, package_name: str
    ) -> List[Dict]:
        """Extract public symbols from an imported module."""
        symbols = []

        # Respect __all__ if defined
        names = getattr(module, '__all__', None)
        if names is None:
            names = [n for n in dir(module) if not n.startswith('_')]

        for name in names:
            if name.startswith('_'):
                continue
            try:
                obj = getattr(module, name)
            except AttributeError:
                continue

            sym_type = self._classify(obj)
            symbols.append({
                'symbol': name,
                'module': package_name,
                'type': sym_type,
            })

        return symbols

    def _classify(self, obj) -> str:
        """Classify an object as class, function, variable, or module."""
        if inspect.isclass(obj):
            return 'class'
        elif inspect.isfunction(obj) or inspect.isbuiltin(obj):
            return 'function'
        elif inspect.ismodule(obj):
            return 'module'
        else:
            return 'variable'
