import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/** Unit and component tests (npm test). The API and Server Actions are mocked; nothing is sent anywhere. */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", ".next-preview/**"],
    setupFiles: ["./vitest.setup.ts"],
    restoreMocks: true,
  },
});
