import * as vscode from 'vscode';
import { SymbolMatch } from '../providers/provider';
import { ProviderManager } from '../providers/manager';

export async function insertImport(
    manager: ProviderManager,
    match: SymbolMatch,
): Promise<boolean> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        return false;
    }

    const document = editor.document;
    const provider = manager.getProvider(document.languageId);
    if (!provider) {
        return false;
    }

    const importStmt = provider.formatImportStatement(match);

    // Check for duplicate
    const existingText = document.getText();
    if (existingText.includes(importStmt)) {
        vscode.window.showInformationMessage(
            `ModulePath: "${importStmt}" already exists`,
        );
        return false;
    }

    // Check if we can merge with existing from-import
    const mergeConfig = vscode.workspace
        .getConfiguration('modulepath')
        .get<boolean>('mergeImports', true);

    if (mergeConfig && match.importStyle === 'from') {
        // Check for existing from X import Y
        const existingImportPattern = new RegExp(
            `^from\\s+${match.module.replace(/\./g, '\\.')}\\s+import\\s+(.+)$`,
            'm',
        );
        const existingMatch = existingText.match(existingImportPattern);

        if (existingMatch) {
            const existingSymbols = existingMatch[1]
                .split(',')
                .map((s) => s.trim());
            if (existingSymbols.includes(match.symbol)) {
                vscode.window.showInformationMessage(
                    `ModulePath: ${match.symbol} already imported from ${match.module}`,
                );
                return false;
            }

            // Merge: add symbol to existing import line
            const lineIndex = existingText
                .substring(0, existingMatch.index)
                .split('\n').length - 1;
            const line = document.lineAt(lineIndex);
            const newSymbols = [...existingSymbols, match.symbol].sort();
            const newLine = `from ${match.module} import ${newSymbols.join(', ')}`;

            await editor.edit((editBuilder) => {
                editBuilder.replace(line.range, newLine);
            });

            vscode.window.showInformationMessage(
                `ModulePath: Added ${match.symbol} to existing import`,
            );
            return true;
        }
    }

    // Insert at correct position
    const insertPos = provider.getInsertPosition(document, match);
    let insertText = importStmt;

    if (insertPos.needsBlankLineBefore) {
        insertText = '\n' + insertText;
    }
    if (insertPos.needsBlankLineAfter) {
        insertText = insertText + '\n';
    }
    insertText += '\n';

    await editor.edit((editBuilder) => {
        editBuilder.insert(new vscode.Position(insertPos.line, 0), insertText);
    });

    return true;
}
