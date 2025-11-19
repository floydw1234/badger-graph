import * as vscode from 'vscode';
import { Parser, Language } from 'web-tree-sitter';
import * as path from 'path';

let pythonParser: Parser | null = null;

// Parse a Python file and return AST information
async function parsePythonFile(filePath: string): Promise<any> {
    if (!pythonParser) {
        throw new Error('Python parser not initialized');
    }

    try {
        const document = await vscode.workspace.openTextDocument(filePath);
        const sourceCode = document.getText();

        const tree = pythonParser.parse(sourceCode);
        if (!tree) {
            throw new Error('Failed to parse source code');
        }

        // Extract useful information from the AST
        const functions: any[] = [];
        const classes: any[] = [];
        const imports: any[] = [];

        // Walk the tree to find interesting nodes
        const walkTree = (node: any, depth = 0) => {
            if (node.type === 'function_definition') {
                const functionName = node.childForFieldName('name')?.text;
                functions.push({
                    name: functionName,
                    start: node.startPosition,
                    end: node.endPosition
                });
            } else if (node.type === 'class_definition') {
                const className = node.childForFieldName('name')?.text;
                classes.push({
                    name: className,
                    start: node.startPosition,
                    end: node.endPosition
                });
            } else if (node.type === 'import_statement' || node.type === 'import_from_statement') {
                imports.push({
                    text: node.text,
                    start: node.startPosition,
                    end: node.endPosition
                });
            }

            // Recursively walk children
            for (let i = 0; i < node.childCount; i++) {
                walkTree(node.child(i), depth + 1);
            }
        };

        walkTree(tree.rootNode);

        return {
            filePath,
            tree: tree.rootNode.toString(),
            functions,
            classes,
            imports,
            totalNodes: countNodes(tree.rootNode)
        };
    } catch (error) {
        console.error('Error parsing Python file:', error);
        throw error;
    }
}

// Helper function to count total nodes in tree
function countNodes(node: any): number {
    let count = 1; // count this node
    for (let i = 0; i < node.childCount; i++) {
        count += countNodes(node.child(i));
    }
    return count;
}

// Parse all Python files in workspace
async function parseAllPythonFiles(): Promise<any[]> {
    const pythonFiles = await vscode.workspace.findFiles('**/*.py', '**/node_modules/**');
    const results: any[] = [];

    for (const file of pythonFiles) {
        try {
            const result = await parsePythonFile(file.fsPath);
            results.push(result);
        } catch (error) {
            console.error(`Failed to parse ${file.fsPath}:`, error);
        }
    }

    return results;
}

// Save parsing results to output files
async function saveParsingResults(results: any[]): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        throw new Error('No workspace folder found');
    }

    // Create output directory
    const outputDir = vscode.Uri.joinPath(workspaceFolder.uri, '.badger-index');
    await vscode.workspace.fs.createDirectory(outputDir);

    // Save individual file results
    const filesDir = vscode.Uri.joinPath(outputDir, 'files');
    await vscode.workspace.fs.createDirectory(filesDir);

    for (const result of results) {
        const fileName = path.basename(result.filePath, '.py') + '.json';
        const fileUri = vscode.Uri.joinPath(filesDir, fileName);
        const content = JSON.stringify(result, null, 2);
        await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));
    }

    // Save summary index
    const summary = {
        generatedAt: new Date().toISOString(),
        totalFiles: results.length,
        totalFunctions: results.reduce((sum, r) => sum + r.functions.length, 0),
        totalClasses: results.reduce((sum, r) => sum + r.classes.length, 0),
        totalImports: results.reduce((sum, r) => sum + r.imports.length, 0),
        files: results.map(r => ({
            path: r.filePath,
            functions: r.functions.length,
            classes: r.classes.length,
            imports: r.imports.length,
            astNodes: r.totalNodes
        }))
    };

    const summaryUri = vscode.Uri.joinPath(outputDir, 'index.json');
    await vscode.workspace.fs.writeFile(summaryUri, Buffer.from(JSON.stringify(summary, null, 2), 'utf8'));

    // Save semantic relationships
    const relationships = extractSemanticRelationships(results);
    const relationshipsUri = vscode.Uri.joinPath(outputDir, 'relationships.json');
    await vscode.workspace.fs.writeFile(relationshipsUri, Buffer.from(JSON.stringify(relationships, null, 2), 'utf8'));
}

// Extract semantic relationships from parsed files
function extractSemanticRelationships(results: any[]): any {
    const relationships = {
        generatedAt: new Date().toISOString(),
        functions: [] as any[],
        classes: [] as any[],
        imports: [] as any[],
        calls: [] as any[]
    };

    for (const result of results) {
        const filePath = result.filePath;

        // Collect functions
        for (const func of result.functions) {
            relationships.functions.push({
                name: func.name,
                file: filePath,
                line: func.start.row + 1,
                column: func.start.column
            });
        }

        // Collect classes
        for (const cls of result.classes) {
            relationships.classes.push({
                name: cls.name,
                file: filePath,
                line: cls.start.row + 1,
                column: cls.start.column
            });
        }

        // Collect imports
        for (const imp of result.imports) {
            relationships.imports.push({
                module: imp.text.trim(),
                file: filePath,
                line: imp.start.row + 1
            });
        }
    }

    return relationships;
}

export async function activate(context: vscode.ExtensionContext) {
    console.log('🔥 Badger extension activation started');

    try {
        // Initialize tree-sitter parser
        console.log('Initializing tree-sitter parser...');

        // For VSCode extensions, we need to read the WASM files as Uint8Array
        const treeSitterWasmUri = vscode.Uri.joinPath(context.extensionUri, 'out', 'tree-sitter.wasm');
        const pythonWasmUri = vscode.Uri.joinPath(context.extensionUri, 'out', 'tree-sitter-python.wasm');

        console.log(`Tree-sitter WASM URI: ${treeSitterWasmUri.toString()}`);
        console.log(`Python WASM URI: ${pythonWasmUri.toString()}`);

        // Read the WASM files
        const treeSitterWasmData = await vscode.workspace.fs.readFile(treeSitterWasmUri);
        const pythonWasmData = await vscode.workspace.fs.readFile(pythonWasmUri);

        console.log(`Tree-sitter WASM loaded: ${treeSitterWasmData.length} bytes`);
        console.log(`Python WASM loaded: ${pythonWasmData.length} bytes`);

        await Parser.init({
            locateFile(scriptName: string, scriptDirectory: string) {
                console.log(`locateFile called for: ${scriptName}`);
                // Return the URI as string - web-tree-sitter will handle the conversion
                if (scriptName === 'tree-sitter.wasm') {
                    return treeSitterWasmUri.toString();
                }
                return scriptName;
            }
        });

        // Load Python language using the data directly
        console.log('Loading Python language...');
        const Python = await Language.load(pythonWasmData);

        pythonParser = new Parser();
        pythonParser.setLanguage(Python);

        console.log('✅ Tree-sitter Python parser initialized successfully');
    } catch (error) {
        console.error('❌ Failed to initialize tree-sitter parser:', error);
        vscode.window.showErrorMessage('Failed to initialize tree-sitter parser: ' + error);
        // Continue with activation even if parser fails
    }

    console.log('📝 Registering Badger commands...');

    // Register the index workspace command
    const indexWorkspaceCommand = vscode.commands.registerCommand('badger.indexWorkspace', async () => {
        if (!pythonParser) {
            vscode.window.showErrorMessage('Tree-sitter parser not initialized');
            return;
        }

        vscode.window.showInformationMessage('Indexing workspace with tree-sitter...');

        try {
            const results = await parseAllPythonFiles();
            console.log('Parsed files:', results);

            // Save results to files
            await saveParsingResults(results);

            const totalFiles = results.length;
            const totalFunctions = results.reduce((sum, r) => sum + r.functions.length, 0);
            const totalClasses = results.reduce((sum, r) => sum + r.classes.length, 0);

            vscode.window.showInformationMessage(
                `Indexed ${totalFiles} Python files: ${totalFunctions} functions, ${totalClasses} classes. Results saved to .badger-index/`
            );

            // TODO: Store in Dgraph database
        } catch (error) {
            vscode.window.showErrorMessage('Failed to index workspace: ' + error);
        }
    });

    // Register the parse current file command
    const parseCurrentFileCommand = vscode.commands.registerCommand('badger.parseCurrentFile', async () => {
        if (!pythonParser) {
            vscode.window.showErrorMessage('Tree-sitter parser not initialized');
            return;
        }

        const activeEditor = vscode.window.activeTextEditor;
        if (!activeEditor || !activeEditor.document.fileName.endsWith('.py')) {
            vscode.window.showErrorMessage('Please open a Python file to parse');
            return;
        }

        try {
            vscode.window.showInformationMessage('Parsing current Python file...');

            const result = await parsePythonFile(activeEditor.document.fileName);
            console.log('Parsed file:', result);

            // Show results in a new document
            const outputChannel = vscode.window.createOutputChannel('Badger Parser');
            outputChannel.clear();
            outputChannel.appendLine(`=== Parsed: ${result.filePath} ===`);
            outputChannel.appendLine(`Total AST nodes: ${result.totalNodes}`);
            outputChannel.appendLine(`Functions found: ${result.functions.length}`);
            outputChannel.appendLine(`Classes found: ${result.classes.length}`);
            outputChannel.appendLine(`Imports found: ${result.imports.length}`);
            outputChannel.appendLine('');

            if (result.functions.length > 0) {
                outputChannel.appendLine('Functions:');
                result.functions.forEach((fn: any) => {
                    outputChannel.appendLine(`  - ${fn.name} (line ${fn.start.row + 1})`);
                });
                outputChannel.appendLine('');
            }

            if (result.classes.length > 0) {
                outputChannel.appendLine('Classes:');
                result.classes.forEach((cls: any) => {
                    outputChannel.appendLine(`  - ${cls.name} (line ${cls.start.row + 1})`);
                });
                outputChannel.appendLine('');
            }

            if (result.imports.length > 0) {
                outputChannel.appendLine('Imports:');
                result.imports.forEach((imp: any) => {
                    outputChannel.appendLine(`  - ${imp.text.trim()}`);
                });
            }

            outputChannel.show();

            vscode.window.showInformationMessage(
                `Parsed ${result.functions.length} functions, ${result.classes.length} classes`
            );
        } catch (error) {
            vscode.window.showErrorMessage('Failed to parse current file: ' + error);
        }
    });

    // Register the query context command
    const queryContextCommand = vscode.commands.registerCommand('badger.queryContext', async () => {
        const query = await vscode.window.showInputBox({
            prompt: 'Enter code elements to find context for',
            placeHolder: 'functionName, ClassName, variableName'
        });

        if (query) {
            vscode.window.showInformationMessage(`Querying context for: ${query}`);

            // TODO: Implement context querying logic
            // - Parse user query to identify code elements
            // - Query Dgraph graph database
            // - Return relevant context
        }
    });

    // Register the update graph command
    const updateGraphCommand = vscode.commands.registerCommand('badger.updateGraph', () => {
        vscode.window.showInformationMessage('Updating code graph...');

        // TODO: Implement graph update logic
        // - Detect changed files
        // - Re-parse with tree-sitter
        // - Update Dgraph with changes
    });

    // Register file save listener for automatic updates
    const fileSaveListener = vscode.workspace.onDidSaveTextDocument((document) => {
        // TODO: Implement automatic graph updates on file save
        console.log(`File saved: ${document.fileName}`);
    });

    // Add all disposables to context
    context.subscriptions.push(
        indexWorkspaceCommand,
        parseCurrentFileCommand,
        queryContextCommand,
        updateGraphCommand,
        fileSaveListener
    );

    console.log('🎉 Badger extension activation completed successfully!');
}

export function deactivate() {
    console.log('Badger extension deactivated');
}
