import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  reporter: [['list']],
  use: {
    actionTimeout: 45000,
    navigationTimeout: 45000, // Render free-tier cold starts, same as Flaky Test Detector
  },
});
