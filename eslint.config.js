// ESLint for the site's browser modules and the JS tests.
import js from '@eslint/js';
import globals from 'globals';

export default [
  {ignores: ['node_modules/', 'coverage/', 'htmlcov/', '.venv/']},
  js.configs.recommended,
  {
    files: ['ahflip/web/static/js/**/*.js'],
    languageOptions: {ecmaVersion: 2023, sourceType: 'module', globals: globals.browser},
  },
  {
    files: ['tests/js/**/*.js', '*.config.js'],
    languageOptions: {ecmaVersion: 2023, sourceType: 'module', globals: {...globals.node, ...globals.browser}},
  },
];
