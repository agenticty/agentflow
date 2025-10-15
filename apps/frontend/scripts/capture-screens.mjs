// apps/frontend/scripts/capture-screens.mjs
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";
import puppeteer from "puppeteer-core";

// --- Config ---
const API = process.env.API_BASE || "http://localhost:8000";
const WEB = process.env.WEB_BASE || "http://localhost:3000";
const CHROME_PATH =
  process.env.CHROME_PATH ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

// Resolve output dir relative to this file, not current shell folder
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const outDir = path.resolve(__dirname, "../../docs/images");

// --- Utils ---
async function ensureOutDir() {
  await fs.mkdir(outDir, { recursive: true });
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function clickButtonByText(page, text) {
  // Finds a <button> whose visible text includes `text` and clicks it
  const handle = await page.waitForFunction(
    (t) => {
      const buttons = Array.from(document.querySelectorAll("button"));
      return buttons.find((b) => b.textContent && b.textContent.includes(t)) || null;
    },
    { timeout: 15000 },
    text
  );
  const btn = await handle.asElement();
  if (!btn) throw new Error(`Button with text "${text}" not found`);
  await btn.click();
}

async function waitForText(page, text, { selector = "body", timeout = 15000 } = {}) {
  await page.waitForFunction(
    (t, sel) => {
      const el = document.querySelector(sel);
      return el && el.innerText && el.innerText.includes(t);
    },
    { timeout },
    text,
    selector
  );
}

// --- App-specific helpers ---
async function createViaUI(page, name) {
  await page.goto(`${WEB}/app`, { waitUntil: "networkidle0" });

  // Type into the workflow name input
  const inputSelector = 'input[placeholder="Inbound Lead → Research → Outreach"]';
  await page.waitForSelector(inputSelector, { timeout: 10000 });
  await page.click(inputSelector, { clickCount: 3 });
  await page.type(inputSelector, name);

  // Click the "Create" button (Puppeteer doesn't support :has-text)
  await clickButtonByText(page, "Create");

  // Wait for a success banner/snackbar/toast that contains "Success"
  await waitForText(page, "Success");
}

async function createViaAPI(name) {
  if (typeof fetch !== "function") {
    throw new Error(
      "Global fetch is not available in this Node version. Use Node 18+ or add a fetch polyfill."
    );
  }
  const res = await fetch(`${API}/api/workflows`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name,
      trigger: { type: "webhook", path: "/lead" },
      steps: [
        { id: randomUUID(), agent: "research", input_map: {} },
        { id: randomUUID(), agent: "qualify", input_map: {} },
        { id: randomUUID(), agent: "outreach", input_map: {} },
      ],
    }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST /api/workflows failed: ${res.status} ${text}`);
  }
}

// --- Main ---
async function main() {
  await ensureOutDir();

  // Sanity check: ensure Chrome exists
  try {
    await fs.access(CHROME_PATH);
  } catch {
    throw new Error(
      `Chrome not found at:\n${CHROME_PATH}\n` +
        `Set CHROME_PATH to your Chrome binary if it's in a different location.`
    );
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new", // if this ever errors on your setup, change to: true
    defaultViewport: { width: 1440, height: 900 },
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();

    // 1) Landing page
    await page.goto(`${WEB}/`, { waitUntil: "networkidle0" });
    await page.screenshot({ path: path.join(outDir, "landing.png") });

    // 2) Empty workflow state
    // Make sure you've cleared DB once before running:
    //   mongosh --eval 'use agentflow; db.workflows.deleteMany({})'
    await page.goto(`${WEB}/app`, { waitUntil: "networkidle0" });
    await wait(500); // let skeletons/animations settle
    await page.screenshot({ path: path.join(outDir, "workflows-empty.png") });

    // 3) Create workflow via UI to capture success state
    await createViaUI(page, "Inbound Lead → Research → Outreach");
    await page.screenshot({ path: path.join(outDir, "create-success.png") });

    // 4) Ensure list with items (add another via API, then refresh)
    await createViaAPI("Demo: Research → Qualify → Outreach");
    await page.goto(`${WEB}/app`, { waitUntil: "networkidle0" });
    await page.screenshot({ path: path.join(outDir, "workflows-list.png") });

    console.log(`✅ Screens saved to ${outDir}`);
  } finally {
    await browser.close().catch(() => {});
  }
}

main().catch((e) => {
  console.error("❌ capture-screens failed:\n", e);
  process.exit(1);
});
