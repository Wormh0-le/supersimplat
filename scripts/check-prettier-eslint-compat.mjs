/**
 * Ensure that formatting every TypeScript source file does not produce code
 * rejected by this repository's ESLint configuration.
 *
 * The pre-commit hook formats staged TypeScript before linting it. Keeping this
 * check in `npm run lint` prevents Prettier or ESLint configuration changes
 * from silently making those two steps incompatible again.
 */

import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { ESLint } from 'eslint';
import { format, resolveConfig } from 'prettier';

const findTypeScriptFiles = async (directory) => {
    const entries = await readdir(directory, { withFileTypes: true });
    const nestedFiles = await Promise.all(
        entries.map(async (entry) => {
            const path = join(directory, entry.name);
            if (entry.isDirectory()) {
                return findTypeScriptFiles(path);
            }
            return entry.isFile() && path.endsWith('.ts') ? [path] : [];
        })
    );
    return nestedFiles.flat();
};

const sourcePaths = (await findTypeScriptFiles('src')).sort();
const eslint = new ESLint();
let failures = 0;

for (const sourcePath of sourcePaths) {
    const source = await readFile(sourcePath, 'utf8');
    const prettierOptions = await resolveConfig(sourcePath);

    if (!prettierOptions) {
        throw new Error(
            `Unable to resolve Prettier configuration for ${sourcePath}.`
        );
    }

    const formatted = await format(source, {
        ...prettierOptions,
        filepath: sourcePath
    });
    const [result] = await eslint.lintText(formatted, { filePath: sourcePath });

    if (result.errorCount > 0) {
        failures += result.errorCount;
        console.error(
            `✖ Prettier output is rejected by ESLint for ${sourcePath}:`
        );
        for (const message of result.messages) {
            console.error(
                `  ${message.line}:${message.column} ${message.ruleId ?? 'syntax'} ${message.message}`
            );
        }
    }
}

if (failures > 0) {
    process.exit(1);
}

console.log(
    `✔ Prettier output passes ESLint for ${sourcePaths.length} TypeScript source files.`
);
