import * as vscode from 'vscode';
import { LanguageProvider, SymbolMatch } from '../providers/provider';
import { ProviderManager } from '../providers/manager';

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

    private getIcon(type: string): string {
        switch (type) {
            case 'class':
                return 'class';
            case 'function':
                return 'method';
            case 'variable':
                return 'variable';
            case 'module':
                return 'namespace';
            default:
                return 'field';
        }
    }
}

export async function showSearchPicker(
    manager: ProviderManager,
    prefilledQuery?: string,
): Promise<SymbolMatch | undefined> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('ModulePath: No active editor');
        return undefined;
    }

    const provider = manager.getProvider(editor.document.languageId);
    if (!provider) {
        vscode.window.showWarningMessage(
            `ModulePath: No provider for ${editor.document.languageId}`,
        );
        return undefined;
    }

    if (!provider.isReady()) {
        vscode.window.showInformationMessage(
            'ModulePath: Still indexing, please wait...',
        );
        return undefined;
    }

    const quickPick = vscode.window.createQuickPick<SymbolQuickPickItem>();
    quickPick.placeholder = 'Search symbol to import...';
    quickPick.matchOnDescription = true;
    quickPick.matchOnDetail = true;

    if (prefilledQuery) {
        quickPick.value = prefilledQuery;
    }

    let debounceTimer: ReturnType<typeof setTimeout> | undefined;

    quickPick.onDidChangeValue(async (value) => {
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }

        if (value.length < 2) {
            quickPick.items = [];
            return;
        }

        debounceTimer = setTimeout(async () => {
            quickPick.busy = true;
            try {
                const results = await provider.search(value, 20);
                quickPick.items = results.map((r) => new SymbolQuickPickItem(r, provider));
            } catch {
                quickPick.items = [];
            }
            quickPick.busy = false;
        }, 150); // 150ms debounce
    });

    // If prefilled, trigger initial search
    if (prefilledQuery && prefilledQuery.length >= 2) {
        quickPick.busy = true;
        try {
            const results = await provider.search(prefilledQuery, 20);
            quickPick.items = results.map((r) => new SymbolQuickPickItem(r, provider));
        } catch {
            quickPick.items = [];
        }
        quickPick.busy = false;
    }

    return new Promise<SymbolMatch | undefined>((resolve) => {
        quickPick.onDidAccept(() => {
            const selected = quickPick.selectedItems[0];
            quickPick.dispose();
            resolve(selected?.match);
        });

        quickPick.onDidHide(() => {
            quickPick.dispose();
            resolve(undefined);
        });

        quickPick.show();
    });
}
