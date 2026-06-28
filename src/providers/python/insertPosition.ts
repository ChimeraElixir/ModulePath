import * as vscode from 'vscode';
import { InsertPosition, SymbolMatch } from '../provider';

interface ImportBlock {
    startLine: number;
    endLine: number;
    group: 'stdlib' | 'third-party' | 'local';
}

// Known stdlib module names (subset for classification)
const STDLIB_MODULES = new Set([
    'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections',
    'concurrent', 'configparser', 'contextlib', 'copy', 'csv',
    'dataclasses', 'datetime', 'decimal', 'enum', 'email',
    'functools', 'glob', 'hashlib', 'http', 'importlib', 'inspect',
    'io', 'itertools', 'json', 'logging', 'math', 'multiprocessing',
    'operator', 'os', 'pathlib', 'pickle', 'platform', 'pprint',
    're', 'secrets', 'shutil', 'signal', 'socket', 'sqlite3',
    'string', 'struct', 'subprocess', 'sys', 'tempfile', 'textwrap',
    'threading', 'time', 'traceback', 'types', 'typing', 'unittest',
    'urllib', 'uuid', 'warnings', 'weakref', 'xml', 'zipfile',
]);

export function getImportInsertPosition(
    document: vscode.TextDocument,
    match: SymbolMatch,
): InsertPosition {
    const text = document.getText();
    const lines = text.split('\n');

    const importBlocks = parseImportBlocks(lines);
    const targetGroup = match.source;

    // Find the block matching our group
    const existingBlock = importBlocks.find((b) => b.group === targetGroup);

    if (existingBlock) {
        // Append after existing block
        return {
            line: existingBlock.endLine + 1,
            group: targetGroup,
            needsBlankLineBefore: false,
            needsBlankLineAfter: false,
        };
    }

    // Group doesn't exist — find where to create it
    if (importBlocks.length === 0) {
        // No imports at all — find position after docstring and __future__
        const insertLine = findFirstCodeLine(lines);
        return {
            line: insertLine,
            group: targetGroup,
            needsBlankLineBefore: insertLine > 0,
            needsBlankLineAfter: true,
        };
    }

    // Insert in correct order: stdlib < third-party < local
    const groupOrder: Record<string, number> = {
        'stdlib': 0,
        'third-party': 1,
        'local': 2,
    };
    const targetOrder = groupOrder[targetGroup] ?? 1;

    // Find the right position between existing blocks
    let insertLine = importBlocks[0].startLine;
    let needsBefore = false;
    let needsAfter = true;

    for (const block of importBlocks) {
        const blockOrder = groupOrder[block.group] ?? 1;
        if (blockOrder < targetOrder) {
            insertLine = block.endLine + 1;
            needsBefore = true;
        } else if (blockOrder > targetOrder) {
            insertLine = block.startLine;
            needsAfter = true;
            break;
        }
    }

    // If no block with higher order found, append after last block
    if (!importBlocks.some((b) => (groupOrder[b.group] ?? 1) > targetOrder)) {
        insertLine = importBlocks[importBlocks.length - 1].endLine + 1;
        needsBefore = true;
        needsAfter = false;
    }

    return {
        line: insertLine,
        group: targetGroup,
        needsBlankLineBefore: needsBefore,
        needsBlankLineAfter: needsAfter,
    };
}

function parseImportBlocks(lines: string[]): ImportBlock[] {
    const blocks: ImportBlock[] = [];
    let currentBlock: ImportBlock | null = null;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        if (isImportLine(line)) {
            const group = classifyImportLine(line);
            if (currentBlock && currentBlock.group === group) {
                currentBlock.endLine = i;
            } else {
                if (currentBlock) {
                    blocks.push(currentBlock);
                }
                currentBlock = { startLine: i, endLine: i, group };
            }
        } else if (line === '' && currentBlock) {
            // Blank line — might be group separator
            blocks.push(currentBlock);
            currentBlock = null;
        } else if (line !== '' && !line.startsWith('#') && !isImportLine(line)) {
            // Non-import, non-comment line — end of import section
            if (currentBlock) {
                blocks.push(currentBlock);
            }
            break;
        }
    }

    if (currentBlock) {
        blocks.push(currentBlock);
    }

    return blocks;
}

function isImportLine(line: string): boolean {
    return line.startsWith('import ') || line.startsWith('from ');
}

function classifyImportLine(line: string): 'stdlib' | 'third-party' | 'local' {
    let moduleName = '';

    if (line.startsWith('from ')) {
        const match = line.match(/^from\s+(\S+)/);
        if (match) {
            moduleName = match[1];
        }
    } else if (line.startsWith('import ')) {
        const match = line.match(/^import\s+(\S+)/);
        if (match) {
            moduleName = match[1];
        }
    }

    if (moduleName.startsWith('.')) {
        return 'local';
    }

    const topLevel = moduleName.split('.')[0];
    if (STDLIB_MODULES.has(topLevel)) {
        return 'stdlib';
    }

    return 'third-party';
}

function findFirstCodeLine(lines: string[]): number {
    let i = 0;

    // Skip shebang
    if (lines[i]?.startsWith('#!')) {
        i++;
    }

    // Skip encoding declaration
    if (lines[i]?.match(/^#.*coding[=:]/)) {
        i++;
    }

    // Skip docstring
    if (lines[i]?.trim().startsWith('"""') || lines[i]?.trim().startsWith("'''")) {
        const quote = lines[i].trim().substring(0, 3);
        if (lines[i].trim().endsWith(quote) && lines[i].trim().length > 6) {
            i++; // single-line docstring
        } else {
            i++;
            while (i < lines.length && !lines[i].includes(quote)) {
                i++;
            }
            i++; // skip closing quote line
        }
    }

    // Skip __future__ imports
    while (i < lines.length && lines[i]?.trim().startsWith('from __future__')) {
        i++;
    }

    // Skip blank lines
    while (i < lines.length && lines[i]?.trim() === '') {
        i++;
    }

    return i;
}

export function formatImportStatement(match: SymbolMatch): string {
    if (match.importStyle === 'alias' && match.alias) {
        return `import ${match.module} as ${match.alias}`;
    }
    if (match.importStyle === 'import') {
        return `import ${match.module}`;
    }
    return `from ${match.module} import ${match.symbol}`;
}

export function findExistingFromImport(
    document: vscode.TextDocument,
    module: string,
): { line: number; symbols: string[] } | null {
    for (let i = 0; i < document.lineCount; i++) {
        const lineText = document.lineAt(i).text.trim();
        const match = lineText.match(
            new RegExp(`^from\\s+${module.replace(/\./g, '\\.')}\\s+import\\s+(.+)$`),
        );
        if (match) {
            const symbols = match[1]
                .split(',')
                .map((s) => s.trim())
                .filter((s) => s);
            return { line: i, symbols };
        }
    }
    return null;
}
