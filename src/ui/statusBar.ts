import * as vscode from 'vscode';

export class StatusBar {
    private item: vscode.StatusBarItem;

    constructor() {
        this.item = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100,
        );
        this.item.command = 'modulepath.refreshIndex';
        this.item.tooltip = 'ModulePath — Click to refresh index';
        this.item.show();
    }

    update(status: string): void {
        this.item.text = `$(search) ModulePath: ${status}`;
    }

    dispose(): void {
        this.item.dispose();
    }
}
