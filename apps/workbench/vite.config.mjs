import { defineConfig } from "vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const workbenchStaticRoot = path.join(repoRoot, "examples", "workbench");

export default defineConfig({
  root: workbenchStaticRoot,
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: false
  },
  preview: {
    host: "127.0.0.1",
    port: 4174,
    strictPort: false
  }
});
