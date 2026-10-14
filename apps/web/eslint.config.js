// Flat config (ESLint 9). Replaces the legacy .eslintrc.cjs.
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'coverage'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  // Accessibility lint for JSX (labels, roles, interactive elements).
  jsxA11y.flatConfigs.recommended,
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
      // Our list rows wrap a checkbox + the title text nested a few levels deep;
      // allow the rule to find that text (default depth is 2).
      'jsx-a11y/label-has-associated-control': ['error', { depth: 3 }],
    },
  },
  // Vite-tuned Fast Refresh rule (allows constant exports alongside components).
  reactRefresh.configs.vite,
  // Keep ESLint out of Prettier's lane — must be last.
  prettier,
);
