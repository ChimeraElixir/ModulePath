# Import Format & Progress Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a window progress notification for background indexing and a setting to control the import format (direct vs absolute).

**Architecture:** Python sidecar will emit `progress` JSON messages. `SidecarClient` will pass these to `PythonProvider` via a new callback to drive a `vscode.window.withProgress` popup. `package.json` gets a new `importStyle` config string, which `formatImportStatement` will use to override the default style.

**Tech Stack:** TypeScript, VS Code API, Python

---

### Task 1: Python Sidecar Progress Events

**Files:**
- Modify: `python-sidecar/main.py:106-131`
- Test: `tests/sidecar/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/sidecar/test_main.py, add at the bottom:
def test_sidecar_emits_progress_events(capsys, tmp_path):
    from main import SidecarServer
    import json
    server = SidecarServer(db_path=str(tmp_path / "test.db"))
    
    # Fake package to index
    pkg = {"name": "testpkg", "version": "1.0", "source": "third-party"}
    server._index_package(pkg)
    
    captured = capsys.readouterr()
    found_progress = False
    for line in captured.out.splitlines():
        if not line.strip(): continue
        try:
            msg = json.loads(line)
            if msg.get("cmd") == "progress" and "testpkg" in msg.get("message", ""):
                found_progress = True
        except:
            pass
    assert found_progress, "No progress event emitted for testpkg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest python-sidecar/tests/test_main.py -v` (Adjust path as needed, or `cd python-sidecar && python3 -m pytest tests/test_main.py`)
Expected: FAIL with "No progress event emitted for testpkg"

- [ ] **Step 3: Write minimal implementation**

```python
# In python-sidecar/main.py
# Inside _index_package(self, pkg_info: dict):
# Before `symbols = []` add:
        name = pkg_info['name']
        version = pkg_info.get('version', '')
        source = pkg_info.get('source', 'third-party')
        path = pkg_info.get('path', '')

        # Check if already indexed with same version
        cached_version = self.index.get_package_version(name)
        if cached_version == version and self.index.is_package_indexed(name):
            return

        # Emit progress
        progress_msg = json.dumps({'cmd': 'progress', 'message': f'Parsing {name}'})
        sys.stdout.write(progress_msg + '\\n')
        sys.stdout.flush()

        symbols = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd python-sidecar && python3 -m pytest tests/test_main.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python-sidecar/main.py python-sidecar/tests/test_main.py
git commit -m "feat: sidecar emits progress events during indexing"
```

### Task 2: Handle Progress in SidecarClient

**Files:**
- Modify: `src/providers/python/sidecar.ts:31-45`, `src/providers/python/sidecar.ts:102-116`

- [ ] **Step 1: Add onProgress to constructor and SidecarResponse**

```typescript
// In src/providers/python/sidecar.ts
// Add to SidecarResponse interface:
    message?: string;
    // ...

// Update class fields and constructor:
    private onStatusChange: (status: string) => void;
    private onProgress: (message: string) => void;

    constructor(
        extensionPath: string,
        storagePath: string,
        projectRoot: string,
        onStatusChange: (status: string) => void,
        onProgress: (message: string) => void,
    ) {
        this.sidecarPath = path.join(extensionPath, 'python-sidecar', 'main.py');
        this.dbPath = path.join(storagePath, 'index.db');
        this.projectRoot = projectRoot;
        this.onStatusChange = onStatusChange;
        this.onProgress = onProgress;
    }
```

- [ ] **Step 2: Update handleResponse to route progress events**

```typescript
// In src/providers/python/sidecar.ts
// Inside handleResponse(response: SidecarResponse):
    private handleResponse(response: SidecarResponse): void {
        if (response.cmd === 'ready') {
            this.ready = true;
            this.restartAttempts = 0;
            const symCount = response.symbols || 0;
            this.onStatusChange(`✅ ${symCount} symbols`);
            return;
        }
        
        if (response.cmd === 'progress' && response.message) {
            this.onProgress(response.message);
            return; // Progress events don't have callbacks
        }

        // Route response to first waiting callback
```

- [ ] **Step 3: Compile and verify no errors**

Run: `npm run compile`
Expected: FAIL because `PythonProvider` in `src/providers/python/pythonProvider.ts` does not pass `onProgress` to `SidecarClient`.

- [ ] **Step 4: Commit**

```bash
git add src/providers/python/sidecar.ts
git commit -m "feat: SidecarClient handles progress events"
```

### Task 3: Display VS Code Progress

**Files:**
- Modify: `src/providers/python/pythonProvider.ts:25-35`

- [ ] **Step 1: Add progress state tracking and callback**

```typescript
// In src/providers/python/pythonProvider.ts
// Add these to PythonProvider class fields:
    private progressResolve: (() => void) | undefined;
    private progressReporter: vscode.Progress<{ message?: string }> | undefined;

// Update activate method:
    async activate(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        const projectRoot = workspaceFolders?.[0]?.uri.fsPath || '';

        this.sidecar = new SidecarClient(
            this.extensionPath,
            this.storagePath,
            projectRoot,
            (status) => {
                vscode.window.setStatusBarMessage(`ModulePath: ${status}`);
                if (status.includes('✅') && this.progressResolve) {
                    this.progressResolve();
                    this.progressResolve = undefined;
                    this.progressReporter = undefined;
                }
            },
            (message) => {
                if (!this.progressResolve) {
                    vscode.window.withProgress({
                        location: vscode.ProgressLocation.Window,
                        title: "ModulePath Indexing",
                    }, (progress) => {
                        this.progressReporter = progress;
                        return new Promise<void>(resolve => {
                            this.progressResolve = resolve;
                        });
                    });
                }
                this.progressReporter?.report({ message });
            }
        );

        await this.sidecar.start();
    }
```

- [ ] **Step 2: Compile to verify**

Run: `npm run compile`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/providers/python/pythonProvider.ts
git commit -m "feat: show parsing progress in VS Code window UI"
```

### Task 4: Add importStyle Configuration

**Files:**
- Modify: `package.json:52-57`

- [ ] **Step 1: Update package.json configuration**

```json
// Add to package.json inside properties:
        "modulepath.importStyle": {
          "type": "string",
          "enum": ["auto", "direct", "absolute"],
          "default": "auto",
          "description": "Preferred import style. 'auto' uses default, 'direct' uses 'from module import symbol', 'absolute' uses 'import module'."
        },
```

- [ ] **Step 2: Commit**

```bash
git add package.json
git commit -m "feat: add importStyle setting"
```

### Task 5: Use importStyle when Formatting

**Files:**
- Modify: `src/providers/python/insertPosition.ts:207-216`

- [ ] **Step 1: Read setting in formatImportStatement**

```typescript
// In src/providers/python/insertPosition.ts
// Update formatImportStatement:
export function formatImportStatement(match: SymbolMatch): string {
    const config = vscode.workspace.getConfiguration('modulepath');
    const styleSetting = config.get<string>('importStyle', 'auto');

    let effectiveStyle = match.importStyle;
    
    // Override if setting says so
    if (styleSetting === 'direct' && match.type !== 'module') {
        effectiveStyle = 'from';
    } else if (styleSetting === 'absolute' && match.type !== 'module') {
        effectiveStyle = 'import';
    }

    if (effectiveStyle === 'alias' && match.alias) {
        return `import ${match.module} as ${match.alias}`;
    }
    if (effectiveStyle === 'import') {
        return `import ${match.module}`;
    }
    return `from ${match.module} import ${match.symbol}`;
}
```

- [ ] **Step 2: Compile to verify**

Run: `npm run compile`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/providers/python/insertPosition.ts
git commit -m "feat: format imports based on importStyle setting"
```

### Task 6: Update Quick Pick Detail String

**Files:**
- Modify: `src/ui/searchPicker.ts:16-24`

- [ ] **Step 1: Use formatter in SymbolQuickPickItem**

```typescript
// In src/ui/searchPicker.ts
// Add import at top if needed, though formatImportStatement is usually inside a provider.
// Wait, the QuickPick item doesn't have access to the provider. 
// We should pass the format string, or pass the provider so it can call formatImportStatement.
// Currently it hardcodes:
//         const importStmt =
//             match.importStyle === 'alias' && match.alias
//                 ? `import ${match.module} as ${match.alias}`
//                 : match.importStyle === 'import'
//                     ? `import ${match.module}`
//                     : `from ${match.module} import ${match.symbol}`;

// Change SymbolQuickPickItem constructor to take the provider:
import { LanguageProvider, SymbolMatch } from '../providers/provider';

class SymbolQuickPickItem implements vscode.QuickPickItem {
    label: string;
    description: string;
    detail: string;
    match: SymbolMatch;

    constructor(match: SymbolMatch, provider: LanguageProvider) {
        this.match = match;
        this.label = `$(symbol-${this.getIcon(match.type)}) ${match.symbol}`;
        this.description = `${match.type}  ·  ${match.module}`;

        const importStmt = provider.formatImportStatement(match);
        this.detail = `→ ${importStmt}`;
    }
// ...
```

- [ ] **Step 2: Update showSearchPicker to pass provider**

```typescript
// Further down in showSearchPicker (src/ui/searchPicker.ts):
// Update where SymbolQuickPickItem is instantiated (2 places):
            try {
                const results = await provider.search(value, 20);
                quickPick.items = results.map((r) => new SymbolQuickPickItem(r, provider));
            } catch {
// ...
    if (prefilledQuery && prefilledQuery.length >= 2) {
        quickPick.busy = true;
        try {
            const results = await provider.search(prefilledQuery, 20);
            quickPick.items = results.map((r) => new SymbolQuickPickItem(r, provider));
        } catch {
```

- [ ] **Step 3: Compile to verify**

Run: `npm run compile`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/ui/searchPicker.ts
git commit -m "feat: sync search picker detail with formatting setting"
```
