import { ChildProcess, spawn } from 'child_process';
import * as path from 'path';
import { SymbolMatch } from '../provider';
import { findPythonInterpreter } from '../../utils/pythonFinder';

interface SidecarResponse {
    cmd: string;
    results?: any[];
    ready?: boolean;
    status?: string;
    packages?: number;
    symbols?: number;
    indexedPackages?: number;
    indexed?: boolean;
    message?: string;
    symbolCount?: number;
    [key: string]: any;
}

export class SidecarClient {
    private process: ChildProcess | null = null;
    private pythonPath: string = '';
    private sidecarPath: string;
    private dbPath: string;
    private projectRoot: string;
    private pendingCallbacks: Array<(response: SidecarResponse) => void> = [];
    private buffer = '';
    private ready = false;
    private restartAttempts = 0;
    private maxRestartAttempts = 3;
    private onStatusChange: (status: string) => void;

    constructor(
        extensionPath: string,
        storagePath: string,
        projectRoot: string,
        onStatusChange: (status: string) => void,
    ) {
        this.sidecarPath = path.join(extensionPath, 'python-sidecar', 'main.py');
        this.dbPath = path.join(storagePath, 'index.db');
        this.projectRoot = projectRoot;
        this.onStatusChange = onStatusChange;
    }

    async start(): Promise<void> {
        try {
            this.pythonPath = findPythonInterpreter();
        } catch (e: any) {
            this.onStatusChange(`❌ ${e.message}`);
            throw e;
        }

        this.onStatusChange('Indexing... 🔄');
        this.spawnProcess();
    }

    private spawnProcess(): void {
        const args = [
            this.sidecarPath,
            '--db',
            this.dbPath,
            '--project',
            this.projectRoot,
        ];

        this.process = spawn(this.pythonPath, args, {
            stdio: ['pipe', 'pipe', 'pipe'],
        });

        this.process.stdout?.on('data', (data: Buffer) => {
            this.buffer += data.toString();
            const lines = this.buffer.split('\n');
            this.buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.trim()) { continue; }
                try {
                    const response: SidecarResponse = JSON.parse(line);
                    this.handleResponse(response);
                } catch {
                    console.error('ModulePath: Invalid JSON from sidecar:', line);
                }
            }
        });

        this.process.stderr?.on('data', (data: Buffer) => {
            console.error('ModulePath sidecar stderr:', data.toString());
        });

        this.process.on('exit', (code) => {
            console.log(`ModulePath sidecar exited with code ${code}`);
            this.ready = false;
            if (code !== 0 && this.restartAttempts < this.maxRestartAttempts) {
                this.restartAttempts++;
                const delay = Math.pow(2, this.restartAttempts) * 1000;
                this.onStatusChange(`❌ Restarting in ${delay / 1000}s...`);
                setTimeout(() => this.spawnProcess(), delay);
            }
        });
    }

    private handleResponse(response: SidecarResponse): void {
        if (response.cmd === 'ready') {
            this.ready = true;
            this.restartAttempts = 0;
            const symCount = response.symbols || 0;
            this.onStatusChange(`✅ ${symCount} symbols`);
            return;
        }

        // Route response to first waiting callback
        const callback = this.pendingCallbacks.shift();
        if (callback) {
            callback(response);
        }
    }

    private sendCommand(cmd: object): Promise<SidecarResponse> {
        return new Promise((resolve, reject) => {
            if (!this.process?.stdin?.writable) {
                reject(new Error('Sidecar not running'));
                return;
            }

            const timeout = setTimeout(() => {
                // Remove this callback from pending
                const idx = this.pendingCallbacks.indexOf(resolveCallback);
                if (idx >= 0) { this.pendingCallbacks.splice(idx, 1); }
                reject(new Error('Sidecar command timed out'));
            }, 30000);

            const resolveCallback = (response: SidecarResponse) => {
                clearTimeout(timeout);
                resolve(response);
            };

            this.pendingCallbacks.push(resolveCallback);

            const line = JSON.stringify(cmd) + '\n';
            this.process!.stdin!.write(line);
        });
    }

    async search(query: string, limit: number = 20): Promise<SymbolMatch[]> {
        const response = await this.sendCommand({
            cmd: 'search',
            query,
            limit,
        });

        if (!response.results) {
            return [];
        }

        return response.results.map((r: any) => ({
            symbol: r.symbol,
            module: r.module,
            type: r.type || 'variable',
            source: r.source || 'third-party',
            importStyle: r.importStyle || 'from',
            alias: r.alias,
            score: r.score,
        }));
    }

    async recordSelection(symbol: string, module: string): Promise<void> {
        await this.sendCommand({
            cmd: 'record_selection',
            symbol,
            module,
        });
    }

    async refresh(): Promise<void> {
        this.onStatusChange('Refreshing... 🔄');
        const response = await this.sendCommand({ cmd: 'refresh' });
        const symCount = response.symbolCount || 0;
        this.onStatusChange(`✅ ${symCount} symbols`);
    }

    async getStatus(): Promise<SidecarResponse> {
        return await this.sendCommand({ cmd: 'status' });
    }

    isReady(): boolean {
        return this.ready;
    }

    async stop(): Promise<void> {
        if (this.process) {
            this.process.kill();
            this.process = null;
        }
        this.ready = false;
    }
}
