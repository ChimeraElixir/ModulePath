import * as vscode from 'vscode';
import { LanguageProvider, SymbolMatch, InsertPosition } from '../provider';
import { SidecarClient } from './sidecar';
import {
    getImportInsertPosition,
    formatImportStatement,
    findExistingFromImport,
} from './insertPosition';

export class PythonProvider implements LanguageProvider {
    readonly languageId = 'python';
    private sidecar: SidecarClient | null = null;
    private progressResolve: (() => void) | undefined;
    private progressReporter: vscode.Progress<{ message?: string }> | undefined;
    private extensionPath: string;
    private storagePath: string;

    constructor(extensionPath: string, storagePath: string) {
        this.extensionPath = extensionPath;
        this.storagePath = storagePath;
    }

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

    async deactivate(): Promise<void> {
        await this.sidecar?.stop();
    }

    async search(query: string, limit?: number): Promise<SymbolMatch[]> {
        if (!this.sidecar) {
            return [];
        }
        return this.sidecar.search(query, limit);
    }

    getInsertPosition(
        document: vscode.TextDocument,
        match: SymbolMatch,
    ): InsertPosition {
        return getImportInsertPosition(document, match);
    }

    async refresh(): Promise<void> {
        await this.sidecar?.refresh();
    }

    isReady(): boolean {
        return this.sidecar?.isReady() ?? false;
    }

    formatImportStatement(match: SymbolMatch): string {
        return formatImportStatement(match);
    }

    async recordSelection(match: SymbolMatch): Promise<void> {
        await this.sidecar?.recordSelection(match.symbol, match.module);
    }

    findExistingFromImport(
        document: vscode.TextDocument,
        module: string,
    ): { line: number; symbols: string[] } | null {
        return findExistingFromImport(document, module);
    }
}
