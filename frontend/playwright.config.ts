import { defineConfig, devices } from '@playwright/test'

const port = process.env.E2E_PORT ?? '5173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'on-first-retry',
  },
  webServer: {
    command: `pnpm dev --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.E2E_PORT,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
