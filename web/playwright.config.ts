import { defineConfig } from '@playwright/test';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..');
export default defineConfig({
  testDir: './tests', workers: 1, timeout: 60000, fullyParallel: false,
  use: {baseURL: 'http://127.0.0.1:5177', viewport: {width: 1440, height: 1000}},
  reporter: [['list'], ['json', {outputFile: '../var/browser-results.json'}]],
  webServer: [
    {command: `${root}/.venv/bin/python -m server`, cwd: root,
      env: {FACE_DATA_DIR: path.join(root, 'var/browser-tests')},
      url: 'http://127.0.0.1:8017/api/health', timeout: 30000, reuseExistingServer: false},
    {command: 'npm run dev', url: 'http://127.0.0.1:5177', timeout: 30000, reuseExistingServer: false}
  ]
});
