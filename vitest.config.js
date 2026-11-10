// JS unit tests (tests/js) run in a simulated browser DOM (jsdom).
import {defineConfig} from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['tests/js/**/*.test.js'],
    coverage: {
      provider: 'v8', include: ['ahflip/web/static/js/**'], reporter: ['text', 'html'],
      thresholds: {100: true}, // the check fails if any file drops below 100%
    },
  },
});
