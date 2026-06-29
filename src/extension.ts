import * as vscode from 'vscode';
import { ProviderManager } from './providers/manager';
import { PythonProvider } from './providers/python/pythonProvider';
import { showSearchPicker } from './ui/searchPicker';
import { ModulePathCodeActionProvider } from './ui/codeAction';
import { insertImport } from './ui/importInserter';
import { StatusBar } from './ui/statusBar';
import { SymbolMatch } from './providers/provider';

let statusBar: StatusBar;
let providerManager: ProviderManager;

export async function activate(context: vscode.ExtensionContext) {
    console.log('ModulePath: Activating...');

    // Initialize components
    statusBar = new StatusBar();
    providerManager = new ProviderManager();

    // Storage path for SQLite DB
    const storagePath =
        context.globalStorageUri?.fsPath ||
        context.storageUri?.fsPath ||
        '';

    // Register Python provider
    const pythonProvider = new PythonProvider(
        context.extensionPath,
        storagePath,
    );
    providerManager.register(pythonProvider);

    // Status bar updates from sidecar
    statusBar.update('Starting...');

    // Activate providers
    try {
        await providerManager.activateAll();
    } catch (e: any) {
        statusBar.update(`❌ ${e.message}`);
    }

    // Register commands
    const searchCommand = vscode.commands.registerCommand(
        'modulepath.searchImport',
        async () => {
            // Get word under cursor if any
            const editor = vscode.window.activeTextEditor;
            let prefilledQuery: string | undefined;

            if (editor) {
                const position = editor.selection.active;
                const wordRange = editor.document.getWordRangeAtPosition(position);
                if (wordRange) {
                    prefilledQuery = editor.document.getText(wordRange);
                }
            }

            const match = await showSearchPicker(providerManager, prefilledQuery);
            if (match) {
                const success = await insertImport(providerManager, match);
                if (success) {
                    // Record selection for history-based ranking
                    const provider = providerManager.getProvider('python') as PythonProvider;
                    await provider?.recordSelection(match);
                }
            }
        },
    );

    const refreshCommand = vscode.commands.registerCommand(
        'modulepath.refreshIndex',
        async () => {
            const provider = providerManager.getProvider('python');
            if (provider) {
                await provider.refresh();
            }
        },
    );

    const insertCommand = vscode.commands.registerCommand(
        'modulepath.insertImport',
        async (match: SymbolMatch) => {
            await insertImport(providerManager, match);
            // Record selection
            const provider = providerManager.getProvider('python') as PythonProvider;
            await provider?.recordSelection(match);
        },
    );

    // Register code action provider for Python files
    const codeActionProvider = vscode.languages.registerCodeActionsProvider(
        { language: 'python', scheme: 'file' },
        new ModulePathCodeActionProvider(providerManager),
        {
            providedCodeActionKinds: [vscode.CodeActionKind.QuickFix],
        },
    );

    context.subscriptions.push(
        searchCommand,
        refreshCommand,
        insertCommand,
        codeActionProvider,
        statusBar,
    );

    console.log('ModulePath: Activated successfully');
}

export function deactivate() {
    console.log('ModulePath: Deactivating...');
    providerManager?.deactivateAll();
    statusBar?.dispose();
}
