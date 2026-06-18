import * as vscode from 'vscode';

export interface SymbolMatch {
    symbol: string;
    module: string;
    type: 'class' | 'function' | 'variable' | 'module';
    source: 'stdlib' | 'third-party' | 'local';
    importStyle: 'from' | 'import' | 'alias';
    alias?: string;
    score?: number;
}

export interface InsertPosition {
    line: number;
    group: 'stdlib' | 'third-party' | 'local';
    needsBlankLineBefore: boolean;
    needsBlankLineAfter: boolean;
}

export interface LanguageProvider {
    readonly languageId: string;
    activate(): Promise<void>;
    deactivate(): Promise<void>;
    search(query: string, limit?: number): Promise<SymbolMatch[]>;
    getInsertPosition(document: vscode.TextDocument, match: SymbolMatch): InsertPosition;
    refresh(): Promise<void>;
    isReady(): boolean;
    formatImportStatement(match: SymbolMatch): string;
}
