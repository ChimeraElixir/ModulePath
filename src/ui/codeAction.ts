import * as vscode from 'vscode';
import { ProviderManager } from '../providers/manager';

export class ModulePathCodeActionProvider implements vscode.CodeActionProvider {
    private manager: ProviderManager;

    constructor(manager: ProviderManager) {
        this.manager = manager;
    }

    async provideCodeActions(
        document: vscode.TextDocument,
        _range: vscode.Range,
        context: vscode.CodeActionContext,
    ): Promise<vscode.CodeAction[]> {
        const provider = this.manager.getProvider(document.languageId);
        if (!provider || !provider.isReady()) {
            return [];
        }

        // Look for undefined name diagnostics
        const undefinedDiagnostics = context.diagnostics.filter(
            (d) =>
                d.message.includes('undefined') ||
                d.message.includes('is not defined') ||
                d.message.includes('Undefined') ||
                d.message.match(/name ['"]?\w+['"]? is not defined/i) !== null,
        );

        const actions: vscode.CodeAction[] = [];

        for (const diagnostic of undefinedDiagnostics) {
            // Extract the symbol name from the diagnostic
            const symbolMatch = diagnostic.message.match(
                /['"](\w+)['"]/,
            );
            if (!symbolMatch) {
                continue;
            }

            const symbolName = symbolMatch[1];
            const results = await provider.search(symbolName, 5);

            for (const result of results) {
                const importStmt = provider.formatImportStatement(result);
                const action = new vscode.CodeAction(
                    `Import: ${importStmt}`,
                    vscode.CodeActionKind.QuickFix,
                );
                action.command = {
                    command: 'modulepath.insertImport',
                    title: 'Insert Import',
                    arguments: [result],
                };
                action.diagnostics = [diagnostic];
                action.isPreferred = results.indexOf(result) === 0;
                actions.push(action);
            }
        }

        return actions;
    }
}
