import * as vscode from 'vscode';
import * as fs from 'fs';
import { execSync } from 'child_process';

export function findPythonInterpreter(): string {
    // 1. Check modulepath setting
    const config = vscode.workspace.getConfiguration('modulepath');
    const configuredPath = config.get<string>('pythonPath', 'auto');

    if (configuredPath !== 'auto') {
        if (fs.existsSync(configuredPath)) {
            return configuredPath;
        }
    }

    // 2. Check VS Code Python extension setting
    const pythonConfig = vscode.workspace.getConfiguration('python');
    const pythonPath = pythonConfig.get<string>('defaultInterpreterPath');
    if (pythonPath && fs.existsSync(pythonPath)) {
        return pythonPath;
    }

    // 3. Try python3 / python on PATH
    for (const cmd of ['python3', 'python']) {
        try {
            const result = execSync(`${cmd} --version`, { timeout: 5000 })
                .toString()
                .trim();
            if (result.startsWith('Python 3')) {
                return cmd;
            }
        } catch {
            continue;
        }
    }

    throw new Error(
        'Python interpreter not found. Configure modulepath.pythonPath or install Python 3.'
    );
}
