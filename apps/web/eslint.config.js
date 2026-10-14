// Flat config (ESLint 9). Replaces the legacy .eslintrc.cjs.
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module',
      globals: { ...globals.browser },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      // TypeScript already resolves identifiers; the core rule double-reports.
      'no-undef': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
  // Vite-tuned Fast Refresh rule (allows constant exports alongside components).
  reactRefresh.configs.vite,
  // Keep ESLint out of Prettier's lane — must be last.
  prettier,
);
