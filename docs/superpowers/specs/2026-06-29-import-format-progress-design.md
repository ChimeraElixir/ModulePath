# ModulePath: Progress Notification & Import Format Settings

## Overview
Adds two new features to the ModulePath extension:
1. A VS Code native progress indicator showing the current file/module being parsed by the sidecar.
2. A configuration setting to control the preferred import format (`import module` vs `from module import symbol`).

## Architecture & Components

### 1. Progress Notification
- **Sidecar (`main.py` & friends)**: Updates the Python sidecar to emit progress messages. 
  - Message format: `{"cmd": "progress", "file": "path/to/file.py", "message": "Parsing..."}`
- **SidecarClient (`sidecar.ts`)**: Parses `cmd: progress` messages and triggers a registered progress callback, similar to how it handles `status`.
- **Extension UI (`extension.ts` / `progress.ts`)**: Uses `vscode.window.withProgress` with `location: vscode.ProgressLocation.Window`.
  - Displays a spinning loader in the bottom right.
  - Updates the progress message with the current file being parsed.
  - Resolves the progress promise when the sidecar emits the `ready` command.

### 2. Import Format Setting
- **Configuration (`package.json`)**: Adds `modulepath.importStyle` setting with enum `['auto', 'direct', 'absolute']`.
  - `auto`: Uses sidecar's default classification (current behavior).
  - `direct`: Forces `from module import symbol`.
  - `absolute`: Forces `import module`.
- **Formatting Logic (`insertPosition.ts`)**: Updates `formatImportStatement` to read the `modulepath.importStyle` setting from the VS Code workspace configuration.
  - Overrides the `match.importStyle` if the setting is `direct` or `absolute`.
- **Quick Pick UI (`searchPicker.ts`)**: Reads the setting to ensure the detail string (e.g. `→ from typing import TypeDict`) matches the format that will actually be inserted.

## Data Flow
- **Progress**: `Python Sidecar` -> stdout -> `SidecarClient` -> Progress Callback -> `vscode.window.withProgress` -> VS Code UI.
- **Import Format**: `VS Code Settings` -> `insertPosition.ts / searchPicker.ts` -> format generation -> Editor Insertion.

## Testing & Verification
- Manually trigger a re-index or start the extension to verify the window progress indicator appears and updates with file names.
- Change the `modulepath.importStyle` setting to `absolute` and verify `TypeDict` inserts as `import typing`.
- Change to `direct` and verify it inserts as `from typing import TypeDict`.
