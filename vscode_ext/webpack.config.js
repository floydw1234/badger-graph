const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
    target: 'node',
    entry: './src/extension.ts',
    output: {
        path: path.resolve(__dirname, 'out'),
        filename: 'extension.js',
        libraryTarget: 'commonjs2',
        devtoolModuleFilenameTemplate: '../[resource-path]'
    },
    externals: {
        vscode: 'commonjs vscode'
    },
    resolve: {
        extensions: ['.ts', '.js']
    },
    module: {
        rules: [
            {
                test: /\.ts$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: 'ts-loader',
                        options: {
                            compilerOptions: {
                                sourceMap: true
                            }
                        }
                    }
                ]
            }
        ]
    },
    devtool: 'source-map',
    optimization: {
        minimize: false
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                {
                    from: 'tree-sitter-python.wasm',
                    to: 'tree-sitter-python.wasm'
                },
                {
                    from: 'node_modules/web-tree-sitter/tree-sitter.wasm',
                    to: 'tree-sitter.wasm'
                }
            ]
        })
    ]
};
