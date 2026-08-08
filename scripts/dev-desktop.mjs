/**
 * 一键开发：本地引擎 + Vite UI。
 * 用户无需手动记 uvicorn / 端口。
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const children = [];

function run(label, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    stdio: "inherit",
    shell: true,
    env: {
      ...process.env,
      PLANSEED_HOST: process.env.PLANSEED_HOST || "127.0.0.1",
      PLANSEED_PORT: process.env.PLANSEED_PORT || "8787",
    },
  });
  child.on("exit", (code, signal) => {
    if (signal) return;
    if (code && code !== 0) {
      console.error(`[${label}] exited with code ${code}`);
      shutdown(code);
    }
  });
  children.push(child);
  return child;
}

function shutdown(code = 0) {
  for (const c of children) {
    if (!c.killed) {
      try {
        c.kill("SIGTERM");
      } catch {
        /* ignore */
      }
    }
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

console.log("[planseed] starting local engine + UI…");
run("engine", "uv", ["run", "python", "-m", "backend"], root);
run("ui", "pnpm", ["--dir", "desktop", "dev"], root);
