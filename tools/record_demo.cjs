"use strict";

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const baseUrl = process.env.ZNAK_ORIENT_URL || "http://127.0.0.1:8765";
const outputPath = path.resolve(
  process.env.ZNAK_ORIENT_VIDEO || "artifacts/znak-orient-demo.webm",
);
const qaPath = path.resolve(
  process.env.ZNAK_ORIENT_BROWSER_QA || "artifacts/browser-qa.json",
);
const rawVideoDirectory = path.resolve("work/video-recordings");
const executablePath = process.env.ZNAK_ORIENT_CHROMIUM;
const parsedUrl = new URL(baseUrl);

if (!new Set(["127.0.0.1", "::1", "localhost"]).has(parsedUrl.hostname)) {
  throw new Error("Demo recording is restricted to a loopback URL.");
}
if (!executablePath) {
  throw new Error("Set ZNAK_ORIENT_CHROMIUM to a local Chromium executable.");
}

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.mkdirSync(path.dirname(qaPath), { recursive: true });
fs.mkdirSync(rawVideoDirectory, { recursive: true });

(async () => {
  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: [
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-default-apps",
      "--disable-sync",
      "--host-resolver-rules=MAP * 0.0.0.0, EXCLUDE 127.0.0.1",
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    permissions: ["clipboard-read", "clipboard-write"],
    recordVideo: {
      dir: rawVideoDirectory,
      size: { width: 1440, height: 900 },
    },
  });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      consoleErrors.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (new Set(["127.0.0.1", "::1", "localhost"]).has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("#position-statement").filter({ hasText: "not yet judge-ready" }).waitFor();
  await pause(3500);

  await page.locator("#rerun").click();
  await page.locator("#toast").filter({ hasText: "Orientation recovered" }).waitFor();
  await pause(3000);

  await page.locator('[data-filter="REJECTED"]').click();
  await page.locator("#intake-count").filter({ hasText: "5 items" }).waitFor();
  const rejectedFilterCountVerified = (await page.locator("#intake-count").textContent()) === "5 items";
  await pause(3000);

  await page.locator('[data-filter="ALL"]').click();
  await page.locator("#conflicts-unknowns").scrollIntoViewIfNeeded();
  await pause(4500);

  await page.locator("#recovery-card").scrollIntoViewIfNeeded();
  await page.locator("#copy-card").click();
  let clipboardCardVerified = false;
  try {
    const clipboardCard = JSON.parse(await page.evaluate(() => navigator.clipboard.readText()));
    clipboardCardVerified = clipboardCard.source_of_truth === false && clipboardCard.write_back_allowed === false;
  } catch (_error) {
    clipboardCardVerified = false;
  }
  await pause(3500);

  await page.locator("#source-evidence").scrollIntoViewIfNeeded();
  await pause(5000);

  await page.locator("#validation-receipt").scrollIntoViewIfNeeded();
  await pause(5000);

  await page.locator("#current-position").scrollIntoViewIfNeeded();
  await pause(3500);

  const browserChecks = {
    six_required_sections: (await page.locator("#noise-intake, #current-position, #conflicts-unknowns, #recovery-card, #source-evidence, #validation-receipt").count()) === 6,
    source_backed_position: (await page.locator("#position-statement").textContent()).includes("not yet judge-ready"),
    exactly_one_visible_next_step: (await page.locator("#next-step-title").count()) === 1,
    assistant_reacts_to_voltage: (await page.locator("#orientation-guide").getAttribute("data-voltage")) === "BLOCKED"
      && (await page.locator("#assistant-state").textContent()) === "Holding at the blocker",
    assistant_repeats_exact_next_step: (await page.locator("#assistant-cue").textContent())
      === (await page.locator("#next-step-title").textContent()),
    assistant_animation_active: await page.locator(".guide-character").evaluate(
      (element) => getComputedStyle(element).animationName === "guide-float",
    ),
    rejected_filter_count: rejectedFilterCountVerified,
    all_filter_restored: (await page.locator("#intake-count").textContent()) === "8 items",
    scoped_run_pass: (await page.locator("#run-status").textContent()).startsWith("PASS · transform only"),
    no_horizontal_overflow: await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
    clipboard_card_payload_non_authoritative: clipboardCardVerified,
    no_console_or_page_errors: consoleErrors.length === 0 && pageErrors.length === 0,
  };

  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const mobilePage = await mobileContext.newPage();
  mobilePage.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      consoleErrors.push({ type: message.type(), text: message.text(), viewport: "mobile" });
    }
  });
  mobilePage.on("pageerror", (error) => pageErrors.push(`mobile: ${error.message}`));
  await mobilePage.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (new Set(["127.0.0.1", "::1", "localhost"]).has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await mobilePage.goto(baseUrl, { waitUntil: "networkidle" });
  await mobilePage.locator("#position-statement").filter({ hasText: "not yet judge-ready" }).waitFor();
  const mobileCurrentBox = await mobilePage.locator("#current-position").boundingBox();
  const mobileIntakeBox = await mobilePage.locator("#noise-intake").boundingBox();
  browserChecks.mobile_no_horizontal_overflow = await mobilePage.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  browserChecks.mobile_position_precedes_intake = Boolean(
    mobileCurrentBox && mobileIntakeBox && mobileCurrentBox.y < mobileIntakeBox.y,
  );
  browserChecks.assistant_reduced_motion_respected = await mobilePage.locator(".guide-character").evaluate(
    (element) => getComputedStyle(element).animationName === "none",
  );
  await mobileContext.close();
  browserChecks.no_console_or_page_errors = consoleErrors.length === 0 && pageErrors.length === 0;

  const qaReceipt = {
    scope: "LOCAL_BROWSER_WORKFLOW_ONLY",
    status: Object.values(browserChecks).every(Boolean) ? "PASS" : "FAIL",
    base_url: baseUrl,
    execution: "LOCAL_HEADLESS_CHROMIUM_NO_EXTERNAL_HOSTS",
    checks: browserChecks,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    claim_limit: "This receipt proves only the tested local headless workflow; it does not prove publication, external source truth, clipboard support in other browsers, or production readiness.",
  };
  fs.writeFileSync(qaPath, `${JSON.stringify(qaReceipt, null, 2)}\n`, "utf8");

  const video = page.video();
  await page.close();
  await video.saveAs(outputPath);
  await context.close();
  await browser.close();
  process.stdout.write(`VIDEO_RECORDED ${outputPath}\nBROWSER_QA_${qaReceipt.status} ${qaPath}\n`);
  if (qaReceipt.status !== "PASS") process.exitCode = 1;
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
