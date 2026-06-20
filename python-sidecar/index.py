"""SQLite-backed symbol index with fuzzy search and ranking."""
import os
import sqlite3
from typing import List, Dict, Optional


class SymbolIndex:
    """Persistent symbol index backed by SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS packages (
                name TEXT PRIMARY KEY,
                version TEXT,
                source TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_indexed BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                module TEXT NOT NULL,
                type TEXT NOT NULL,
                source TEXT NOT NULL,
                package_name TEXT REFERENCES packages(name)
            );

            CREATE TABLE IF NOT EXISTS search_history (
                symbol TEXT NOT NULL,
                module TEXT NOT NULL,
                selection_count INTEGER DEFAULT 0,
                last_selected TIMESTAMP,
                PRIMARY KEY (symbol, module)
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(symbol);
            CREATE INDEX IF NOT EXISTS idx_symbols_module ON symbols(module);
            CREATE INDEX IF NOT EXISTS idx_symbols_package ON symbols(package_name);
        ''')
        self.conn.commit()

    def add_symbols(
        self,
        package_name: str,
        version: str,
        source: str,
        symbols: List[Dict],
    ):
        """Add or replace symbols for a package."""
        cursor = self.conn.cursor()
        # Remove old entries for this package
        cursor.execute('DELETE FROM symbols WHERE package_name = ?', (package_name,))
        cursor.execute(
            'INSERT OR REPLACE INTO packages (name, version, source, is_indexed) '
            'VALUES (?, ?, ?, 1)',
            (package_name, version, source),
        )
        # Insert new symbols
        for sym in symbols:
            cursor.execute(
                'INSERT INTO symbols (symbol, module, type, source, package_name) '
                'VALUES (?, ?, ?, ?, ?)',
                (sym['symbol'], sym['module'], sym['type'], source, package_name),
            )
        self.conn.commit()

    def remove_package(self, package_name: str):
        """Remove all symbols for a package."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM symbols WHERE package_name = ?', (package_name,))
        cursor.execute('DELETE FROM packages WHERE name = ?', (package_name,))
        self.conn.commit()

    def is_package_indexed(self, package_name: str) -> bool:
        """Check if a package has been indexed."""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT is_indexed FROM packages WHERE name = ?', (package_name,)
        )
        row = cursor.fetchone()
        return bool(row and row['is_indexed'])

    def get_package_version(self, package_name: str) -> Optional[str]:
        """Get the indexed version of a package."""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT version FROM packages WHERE name = ?', (package_name,)
        )
        row = cursor.fetchone()
        return row['version'] if row else None

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for symbols matching query with ranked results."""
        if not query:
            return []

        # Get all symbols
        cursor = self.conn.cursor()
        cursor.execute('SELECT symbol, module, type, source FROM symbols')
        all_symbols = [dict(row) for row in cursor.fetchall()]

        # Get search history
        cursor.execute('SELECT symbol, module, selection_count FROM search_history')
        history = {
            (row['symbol'], row['module']): row['selection_count']
            for row in cursor.fetchall()
        }

        # Score and rank
        scored = []
        query_lower = query.lower()
        for sym in all_symbols:
            score = self._compute_score(query_lower, sym, history)
            if score > 0:
                sym['score'] = score
                scored.append(sym)

        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:limit]

    def _compute_score(
        self, query: str, sym: Dict, history: Dict
    ) -> float:
        """Compute relevance score for a symbol."""
        name = sym['symbol']
        name_lower = name.lower()
        score = 0.0

        # Exact match
        if name_lower == query:
            score += 100

        # Prefix match
        elif name_lower.startswith(query):
            score += 50

        # Fuzzy match
        else:
            fuzzy_score = self._fuzzy_score(query, name_lower)
            if fuzzy_score <= 0:
                return 0
            score += fuzzy_score

        # Stdlib boost
        if sym['source'] == 'stdlib':
            score += 20

        # History boost
        history_key = (sym['symbol'], sym['module'])
        if history_key in history:
            score += 5 * history[history_key]

        return score

    def _fuzzy_score(self, query: str, target: str) -> float:
        """Simple fuzzy matching score. Returns 0 if no match."""
        qi = 0
        consecutive = 0
        max_consecutive = 0
        score = 0.0

        for char in target:
            if qi < len(query) and char == query[qi]:
                qi += 1
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
                score += 1 + consecutive  # bonus for consecutive chars
            else:
                consecutive = 0

        if qi < len(query):
            return 0  # not all query chars matched

        # Normalize by query length
        return min(40, score * (10 / max(len(target), 1)))

    def record_selection(self, symbol: str, module: str):
        """Record that user selected a symbol for history-based ranking."""
        self.conn.execute(
            'INSERT INTO search_history (symbol, module, selection_count, last_selected) '
            'VALUES (?, ?, 1, CURRENT_TIMESTAMP) '
            'ON CONFLICT(symbol, module) DO UPDATE SET '
            'selection_count = selection_count + 1, '
            'last_selected = CURRENT_TIMESTAMP',
            (symbol, module),
        )
        self.conn.commit()

    def get_stats(self) -> Dict:
        """Get index statistics."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as c FROM packages WHERE is_indexed = 1')
        pkg_count = cursor.fetchone()['c']
        cursor.execute('SELECT COUNT(*) as c FROM symbols')
        sym_count = cursor.fetchone()['c']
        cursor.execute('SELECT COUNT(*) as c FROM packages')
        total_packages = cursor.fetchone()['c']
        return {
            'packages': total_packages,
            'indexedPackages': pkg_count,
            'symbols': sym_count,
        }

    def close(self):
        self.conn.close()
