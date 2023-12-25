const path = require('path');
const webpack = require('webpack');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const childProcess = require('child_process');


function gitVersion() {
    try {
        return childProcess
            .execSync('git describe --abbrev=8 --always --tags --dirty=" (modified)" 2>/dev/null')
            .toString().trim();
    } catch(error) { /* empty */ }
}


function buildDate() {
    return new Date().toLocaleString();
}


module.exports = {
    entry: './main.tsx',
    output: {
        path: path.resolve(__dirname, 'public'),
        filename: '[name].[contenthash].js',
        publicPath: '/',
    },
    optimization: {
        // Generate a single separate chunk with runtime webpack boilerplate
        // code to be shared by all other chunks.
        runtimeChunk: 'single',
        moduleIds: 'deterministic',
        // Generate a separate chunk with all external third-party libraries
        // from node_modules.
        splitChunks: {
            cacheGroups: {
                vendor: {
                    test: /[\\/]node_modules[\\/]/,
                    name: 'libs',
                    chunks: 'all',
                }
            }
        }
    },
    plugins: [
        new CleanWebpackPlugin(),
        new HtmlWebpackPlugin({
            template: path.resolve(__dirname, 'index.html'),
            templateParameters: { },
            minify: {
                minifyCSS: true,
                minifyJS: true,
                collapseWhitespace: true,
                keepClosingSlash: true,
                removeComments: true,
                removeRedundantAttributes: true,
                removeScriptTypeAttributes: true,
                removeStyleLinkTypeAttributes: true,
                useShortDoctype: true
            }
        }),
        new webpack.DefinePlugin({
            // The second parameter (true) marks any module that uses these defines as
            // non cacheable, i.e., they will be rebuilt every single time.
            // runtimeValue() recomputes the value of the variable on each build.
            BUILD_DATE: webpack.DefinePlugin.runtimeValue(() => `"${buildDate()}"`, true),
            NODE_ENV: webpack.DefinePlugin.runtimeValue(() => {
                const v = process.env.NODE_ENV;
                if (v) return `"${v}"`;
            }),
            GIT_VERSION: webpack.DefinePlugin.runtimeValue(() => {
                const v = gitVersion();
                if (v) return `"${v}"`;
            }, true),
            npm_package_name: webpack.DefinePlugin.runtimeValue(() => {
                const v = process.env.npm_package_name;
                if (v) return `"${v}"`;
            }, true),
            npm_package_version: webpack.DefinePlugin.runtimeValue(() => {
                const v = process.env.npm_package_version;
                if (v) return `"${v}"`;
            }, true),
        }),
        // Ignore node_modules when watching for file changes. Files in that folder
        // normally don't get edited during development.
        new webpack.WatchIgnorePlugin({
            paths: [ path.resolve(__dirname, "node_modules") ]
        })
    ],
    module: {
        rules: [{
            test: /\.(jsx?|tsx?)$/i,
            exclude: /node_modules/,
            use: 'ts-loader',
        }, {
            test: /\.css$/i,
            use: ['style-loader', 'css-loader']
        }, {
            test: /\.(woff|woff2|eot|ttf|otf)$/i,
            type: 'asset/resource'
        }, {
            test: /\.(png|svg|jpg|jpeg|gif|ico)$/i,
            type: 'asset/resource'
        }]
    },
    resolve: {
        extensions: [ '.tsx', '.ts', '.jsx', '.js']
    }
}
