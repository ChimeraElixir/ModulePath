# ModulePath

**Python Symbol Discovery Tool for VS Code**

Know the symbol name but not the module? ModulePath searches across all installed packages, Python stdlib, and your local project to find where any symbol lives — then inserts the correct import with one click.

## Features

- 🔍 **Symbol Search** — Type a name, find all modules that export it
- ⚡ **Instant Results** — SQLite-cached index with fuzzy search
- 🎯 **Smart Placement** — Imports placed in correct PEP 8 group
- 🔀 **Import Merging** — Adds to existing `from X import ...` lines
- 💡 **Code Actions** — Lightbulb suggestions for undefined symbols
- ⌨️ **Keyboard Shortcut** — `Ctrl+Shift+I` (Cmd+Shift+I on Mac)
- 📦 **Auto-Refresh** — Detects `pip install/uninstall` automatically
- 📊 **Learning** — Boosts frequently used imports in results
- 📝 **Alias Support** — Search `np`, `pd`, `plt` and get correct alias imports
- 📁 **Local Project** — Indexes your workspace symbols too

## Usage

1. Press `Ctrl+Shift+I` (or `Cmd+Shift+I` on Mac)
2. Type the symbol name (e.g., `BaseModel`)
3. Select from results
4. Import is inserted automatically

### Alternative: Lightbulb

Write an undefined symbol in your code → lightbulb appears → click to import.

## How It Works

ModulePath runs a lightweight Python sidecar process that:
1. Scans your virtual environment and Python stdlib
2. Extracts public symbols using AST analysis (no code execution)
3. Stores results in a persistent SQLite cache
4. Responds to search queries with ranked results

No LLM, no API calls, no internet required. 100% offline and free.

## Requirements

- Python 3.8+
- VS Code 1.85+

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `modulepath.pythonPath` | `auto` | Python interpreter path |
| `modulepath.scanOnActivation` | `true` | Start indexing on activation |
| `modulepath.watchVenv` | `true` | Watch for package changes |
| `modulepath.mergeImports` | `true` | Merge imports from same module |
| `modulepath.runtimeFallbackTimeout` | `2` | Max seconds for runtime fallback |

## License

MIT
