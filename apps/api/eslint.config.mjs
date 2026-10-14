// Flat config (ESLint 9). Replaces the legacy .eslintrc.cjs.
// `.mjs` because this package is CommonJS (no "type": "module").
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.ts'],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module',
      globals: { ...globals.node },
    },
    rules: {
      // TypeScript already resolves identifiers; the core rule double-reports.
      'no-undef': 'off',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
  {
    files: ['**/*.spec.ts', 'test/**/*.ts'],
    languageOptions: { globals: { ...globals.jest } },
  },
  // Keep ESLint out of Prettier's lane — must be last.
  prettier,
);
