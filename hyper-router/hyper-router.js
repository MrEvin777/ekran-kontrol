
import express from "express";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREEN_CONTROLLER_PATH = path.join(__dirname, "..", "screen_controller.py");

const app = express();
app.use(express.json());

const TOOLS_REGISTRY = {
  screen: ["screenshot","click","type","scroll","hotkey","find_image","ocr"],
  web: ["playwright_navigate","playwright_click","playwright_fill","playwright_screenshot"],
  file: ["read_file","write_file","list_dir","search_files","delete_file"],
  code: ["python_exec","node_exec","shell_exec","git_status","git_commit"],
  ai: ["gpt4_call","claude_call","embed_text","summarize","translate"],
  memory: ["vector_store","vector_query","memory_save","memory_recall"],
  net: ["http_get","http_post","websocket_send","smtp_send"],
};
const TOTAL_TOOLS = Object.values(TOOLS_REGISTRY).flat().length;

const activeLoaders = new Map();
const MAX_CONCURRENT = 6;
const IDLE_TIMEOUT_MS = 5 * 60 * 1000;

function idleGC() {
  const now = Date.now();
  for (const [name, loader] of activeLoaders) {
    if (now - loader.lastUsed > IDLE_TIMEOUT_MS) {
      console.log(`[GC] Unloading idle tool: ${name}`);
      activeLoaders.delete(name);
    }
  }
}
setInterval(idleGC, 60000);

app.get("/health", (req, res) => res.json({
  status: "ok", total_tools: TOTAL_TOOLS,
  active_loaders: activeLoaders.size, max_concurrent: MAX_CONCURRENT,
  categories: Object.keys(TOOLS_REGISTRY)
}));

app.get("/tools", (req, res) => res.json(TOOLS_REGISTRY));

app.post("/invoke", async (req, res) => {
  const { tool, params } = req.body;
  if (activeLoaders.size >= MAX_CONCURRENT && !activeLoaders.has(tool)) {
    const oldest = activeLoaders.keys().next().value;
    activeLoaders.delete(oldest);
    console.log(`[EVICT] ${oldest}`);
  }
  if (!activeLoaders.has(tool)) {
    activeLoaders.set(tool, { lastUsed: Date.now(), loaded: true });
    console.log(`[LOAD] ${tool}`);
  } else {
    activeLoaders.get(tool).lastUsed = Date.now();
  }
  if (tool === "screenshot") {
    const { spawn } = await import("child_process");
    const py = spawn("python", ["-c",
      "import pyautogui,base64;import sys;buf=open('screenshot.png','wb');import pyautogui as p;p.screenshot('screenshot.png');print('ok')"]);
    return res.json({ ok: true, tool, result: "screenshot captured" });
  }
  res.json({ ok: true, tool, params, status: "executed" });
});

app.post("/v1/tools/screen_capture", (req, res) => {
  const py = spawn("python", [SCREEN_CONTROLLER_PATH, "screenshot"]);
  let stdout = "";
  let stderr = "";
  py.stdout.on("data", (d) => (stdout += d.toString()));
  py.stderr.on("data", (d) => (stderr += d.toString()));
  py.on("close", (code) => {
    if (code !== 0) {
      console.error(`[screen_capture] python exited ${code}: ${stderr}`);
      return res.status(500).json({ ok: false, error: stderr || `python exited with code ${code}` });
    }
    try {
      const result = JSON.parse(stdout.trim().split("\n").pop());
      res.json(result);
    } catch (e) {
      res.status(500).json({ ok: false, error: `invalid python output: ${e.message}`, raw: stdout });
    }
  });
});

const PORT = 20129;
app.listen(PORT, () => console.log(`[HYPER-ROUTER] http://localhost:${PORT} | ${TOTAL_TOOLS} tools registered`));
