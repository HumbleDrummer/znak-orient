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
const desktopScreenshotPath = path.resolve(
  process.env.ZNAK_ORIENT_DESKTOP_SCREENSHOT || "artifacts/ui-desktop-1440x900.png",
);
const mobileScreenshotPath = path.resolve(
  process.env.ZNAK_ORIENT_MOBILE_SCREENSHOT || "artifacts/ui-mobile-390x844.png",
);
const rawVideoDirectory = path.resolve("work/video-recordings");
const demoPackagePath = path.resolve("demo/evidence-package.json");
const executablePath = process.env.ZNAK_ORIENT_CHROMIUM;
const parsedUrl = new URL(baseUrl);
const loopbackHosts = new Set(["127.0.0.1", "::1", "localhost"]);

if (!loopbackHosts.has(parsedUrl.hostname)) {
  throw new Error("Demo recording is restricted to a loopback URL.");
}
if (!executablePath) {
  throw new Error("Set ZNAK_ORIENT_CHROMIUM to a local Chromium executable.");
}

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const ensureParentDirectory = (filePath) => fs.mkdirSync(path.dirname(filePath), { recursive: true });
const cloneJson = (value) => JSON.parse(JSON.stringify(value));
const demoPackage = JSON.parse(fs.readFileSync(demoPackagePath, "utf8"));
const expectedGuideStates = {
  FLOWING: { label: "Direction is clear", animation: "guide-step", color: "rgb(15, 109, 82)" },
  WEAK: { label: "Mitigation comes first", animation: "guide-lean", color: "rgb(154, 93, 0)" },
  BLOCKED: { label: "Holding at the blocker", animation: "guide-anchor", color: "rgb(169, 54, 42)" },
  BROKEN: { label: "Correct the course", animation: "guide-correct", color: "rgb(169, 54, 42)" },
  UNKNOWN: { label: "Waiting for evidence", animation: "guide-consider", color: "rgb(154, 93, 0)" },
};

function buildVoltagePackages() {
  const core = cloneJson(demoPackage);
  core.validation_receipts = core.validation_receipts.filter(
    (receipt) => receipt.receipt_id === "vr-core-001",
  );
  core.changes = [];

  const unknown = cloneJson(core);
  unknown.changes = [{
    change_id: "chg-ui-critical-unknown",
    object_type: "STATE_CHANGE",
    sequence: 5,
    observed_at: "2026-07-19T08:00:00+02:00",
    content_type: "UNKNOWN",
    operation: "CREATE",
    subject: "release.owner",
    value: "Release owner is not established.",
    epistemic: "UNKNOWN",
    authority: "NOT_APPLICABLE",
    material: true,
    expected_checkpoint_id: "cp-old-valid-001",
    source_ids: ["src-clean-validation"],
  }];

  const weak = cloneJson(core);
  weak.changes = [{
    change_id: "chg-ui-data-loss-risk",
    object_type: "STATE_CHANGE",
    sequence: 5,
    observed_at: "2026-07-19T08:00:00+02:00",
    content_type: "RISK",
    operation: "CREATE",
    subject: "storage.data_loss",
    value: "Unverified backup before migration.",
    epistemic: "SUPPORTED",
    authority: "NOT_APPLICABLE",
    material: true,
    expected_checkpoint_id: "cp-old-valid-001",
    source_ids: ["src-clean-validation"],
  }];

  const broken = cloneJson(core);
  broken.changes = [{
    change_id: "chg-ui-forbid-goal-validation",
    object_type: "STATE_CHANGE",
    sequence: 5,
    observed_at: "2026-07-19T08:00:00+02:00",
    content_type: "CONSTRAINT",
    operation: "CREATE",
    subject: "policy.forbidden-classes",
    value: { forbidden_policy_classes: ["GOAL_VALIDATION"] },
    epistemic: "VERIFIED",
    authority: "AUTHORIZED",
    material: true,
    expected_checkpoint_id: "cp-old-valid-001",
    source_ids: ["src-pin-001"],
  }];

  return {
    BLOCKED: cloneJson(demoPackage),
    FLOWING: core,
    WEAK: weak,
    BROKEN: broken,
    UNKNOWN: unknown,
  };
}
[
  outputPath,
  qaPath,
  desktopScreenshotPath,
  mobileScreenshotPath,
].forEach(ensureParentDirectory);
fs.mkdirSync(rawVideoDirectory, { recursive: true });

(async () => {
  let browser;
  try {
  browser = await chromium.launch({
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
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator("#position-statement").filter({ hasText: "not yet judge-ready" }).waitFor();
  await pause(3500);
  await page.screenshot({
    path: desktopScreenshotPath,
    fullPage: false,
    animations: "disabled",
  });

  await page.locator("#rerun").click();
  await page.locator("#toast").filter({ hasText: "Orientation updated" }).waitFor();
  await pause(3000);

  await page.locator('[data-filter="REJECTED"]').click();
  await page.locator("#intake-count").filter({ hasText: "5 of 8 items" }).waitFor();
  const rejectedFilterCountVerified = (await page.locator("#intake-count").textContent()) === "5 of 8 items";
  const rejectedFilterPressedVerified = (await page.locator('[data-filter="REJECTED"]').getAttribute("aria-pressed")) === "true";
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

  const apiDemo = await page.evaluate(async () => {
    const response = await fetch("/api/demo");
    if (!response.ok) throw new Error(`Demo API returned HTTP ${response.status}.`);
    return response.json();
  });
  const apiNextStep = apiDemo.checkpoint.primary_next_step.instruction;
  const successConditionAttribute = await page
    .locator("#success-condition")
    .getAttribute("data-machine-value");
  let successConditionMachineValue = null;
  try {
    successConditionMachineValue = JSON.parse(successConditionAttribute);
  } catch (_error) {
    successConditionMachineValue = null;
  }
  const visibleStateMarkers = await page.locator(".guide-marker").evaluateAll((markers) => (
    markers.filter((marker) => {
      const style = getComputedStyle(marker);
      return style.display !== "none"
        && style.visibility !== "hidden"
        && Number.parseFloat(style.opacity) > 0;
    }).map((marker) => marker.getAttribute("class"))
  ));
  const guideVoltage = await page.locator("#orientation-guide").getAttribute("data-voltage");
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  let choosePackageReachedByKeyboard = false;
  for (let index = 0; index < 6; index += 1) {
    await page.keyboard.press("Tab");
    choosePackageReachedByKeyboard = await page.locator("#choose-package").evaluate(
      (element) => document.activeElement === element,
    );
    if (choosePackageReachedByKeyboard) break;
  }

  const browserChecks = {
    six_required_sections: (await page.locator("#noise-intake, #current-position, #conflicts-unknowns, #recovery-card, #source-evidence, #validation-receipt").count()) === 6,
    source_backed_position: (await page.locator("#position-statement").textContent()).includes("not yet judge-ready"),
    exactly_one_visible_next_step: (await page.locator("#assistant-cue").count()) === 1,
    assistant_reacts_to_voltage: (await page.locator("#orientation-guide").getAttribute("data-voltage")) === "BLOCKED"
      && (await page.locator("#assistant-state").textContent()) === "Holding at the blocker",
    assistant_contains_exact_canonical_next_step: (await page.locator("#assistant-cue").textContent()) === apiNextStep,
    exactly_one_visible_state_marker: visibleStateMarkers.length === 1
      && visibleStateMarkers[0].includes(`guide-marker-${(guideVoltage || "").toLowerCase()}`),
    success_condition_matches_api_demo: JSON.stringify(successConditionMachineValue)
      === JSON.stringify(apiDemo.checkpoint.primary_next_step.success_condition),
    assistant_blocked_motion_is_finite: await page.locator(".guide-character").evaluate(
      (element) => getComputedStyle(element).animationName === "guide-anchor"
        && getComputedStyle(element).animationIterationCount === "1",
    ),
    rejected_filter_count: rejectedFilterCountVerified,
    rejected_filter_semantics: rejectedFilterPressedVerified,
    all_filter_restored: (await page.locator("#intake-count").textContent()) === "8 items",
    choose_json_keyboard_focus_visible: choosePackageReachedByKeyboard && await page.locator("#choose-package").evaluate(
      (element) => getComputedStyle(element).boxShadow !== "none",
    ),
    scoped_run_pass: (await page.locator("#run-status").textContent()).startsWith("PASS · transform only"),
    no_horizontal_overflow: await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
    clipboard_card_payload_non_authoritative: clipboardCardVerified,
    no_unexpected_console_or_page_errors: consoleErrors.length === 0 && pageErrors.length === 0,
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
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await mobilePage.goto(baseUrl, { waitUntil: "networkidle" });
  await mobilePage.locator("#position-statement").filter({ hasText: "not yet judge-ready" }).waitFor();
  await mobilePage.screenshot({
    path: mobileScreenshotPath,
    fullPage: false,
    animations: "disabled",
  });
  const mobileCurrentBox = await mobilePage.locator("#current-position").boundingBox();
  const mobileIntakeBox = await mobilePage.locator("#noise-intake").boundingBox();
  const mobileGuideBox = await mobilePage.locator("#orientation-guide").boundingBox();
  const mobileNextStepBox = await mobilePage.locator("#assistant-cue").boundingBox();
  browserChecks.mobile_no_horizontal_overflow = await mobilePage.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  browserChecks.mobile_position_precedes_intake = Boolean(
    mobileCurrentBox && mobileIntakeBox && mobileCurrentBox.y < mobileIntakeBox.y,
  );
  browserChecks.mobile_next_step_visible_in_opening_view = Boolean(
    mobileNextStepBox && mobileNextStepBox.y + mobileNextStepBox.height <= 844,
  );
  browserChecks.mobile_guide_visible_in_opening_view = Boolean(
    mobileGuideBox && mobileGuideBox.y + mobileGuideBox.height <= 844,
  );
  browserChecks.semantic_position_precedes_intake = await mobilePage.evaluate(
    () => Array.from(document.querySelectorAll("#current-position, #noise-intake"))[0]?.id === "current-position",
  );
  browserChecks.assistant_reduced_motion_respected = await mobilePage
    .locator(".guide-character, .guide-arm, .guide-marker")
    .evaluateAll(
      (elements) => elements.every((element) => getComputedStyle(element).animationName === "none"),
    );
  await mobileContext.close();

  const voltageContext = await browser.newContext({ viewport: { width: 900, height: 800 } });
  const voltagePage = await voltageContext.newPage();
  voltagePage.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      consoleErrors.push({ type: message.type(), text: message.text(), viewport: "voltage" });
    }
  });
  voltagePage.on("pageerror", (error) => pageErrors.push(`voltage: ${error.message}`));
  await voltagePage.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await voltagePage.goto(baseUrl, { waitUntil: "networkidle" });
  for (const [expectedVoltage, payload] of Object.entries(buildVoltagePackages())) {
    const rendered = await voltagePage.evaluate(async (testPackage) => {
      await requestResult("/api/orient", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(testPackage),
      }, false);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      await new Promise((resolve) => setTimeout(resolve, 220));
      const result = state.result;
      const visibleMarkerElements = Array.from(document.querySelectorAll(".guide-marker"))
        .filter((marker) => {
          const style = getComputedStyle(marker);
          return style.display !== "none"
            && style.visibility !== "hidden"
            && Number.parseFloat(style.opacity) > 0;
        });
      const visibleMarkers = visibleMarkerElements.map((marker) => marker.getAttribute("class"));
      const characterStyle = getComputedStyle(document.querySelector(".guide-character"));
      return {
        voltage: document.querySelector("#orientation-guide").dataset.voltage,
        stateLabel: document.querySelector("#assistant-state").textContent,
        cueMatches: document.querySelector("#assistant-cue").textContent
          === result.checkpoint.primary_next_step.instruction,
        successConditionMatches: document.querySelector("#success-condition").dataset.machineValue
          === JSON.stringify(result.checkpoint.primary_next_step.success_condition),
        visibleMarkers,
        badgeColor: getComputedStyle(document.querySelector("#voltage")).color,
        labelColor: getComputedStyle(document.querySelector(".guide-status-line .small-label")).color,
        markerStroke: visibleMarkerElements[0] ? getComputedStyle(visibleMarkerElements[0]).stroke : null,
        animationName: characterStyle.animationName,
        animationCount: characterStyle.animationIterationCount,
      };
    }, payload);
    const expected = expectedGuideStates[expectedVoltage];
    browserChecks[`assistant_${expectedVoltage.toLowerCase()}_runtime_state`] = (
      rendered.voltage === expectedVoltage
      && rendered.stateLabel === expected.label
      && rendered.cueMatches
      && rendered.successConditionMatches
      && rendered.visibleMarkers.length === 1
      && rendered.visibleMarkers[0].includes(`guide-marker-${expectedVoltage.toLowerCase()}`)
      && rendered.badgeColor === expected.color
      && rendered.labelColor === expected.color
      && rendered.markerStroke === expected.color
      && rendered.animationName === expected.animation
      && rendered.animationCount === "1"
    );
  }
  await voltageContext.close();

  const reducedVoltageContext = await browser.newContext({
    viewport: { width: 900, height: 800 },
    reducedMotion: "reduce",
  });
  const reducedVoltagePage = await reducedVoltageContext.newPage();
  reducedVoltagePage.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      consoleErrors.push({ type: message.type(), text: message.text(), viewport: "reduced-voltage" });
    }
  });
  reducedVoltagePage.on("pageerror", (error) => pageErrors.push(`reduced-voltage: ${error.message}`));
  await reducedVoltagePage.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await reducedVoltagePage.goto(baseUrl, { waitUntil: "networkidle" });
  let allReducedVoltageStatesVerified = true;
  for (const payload of Object.values(buildVoltagePackages())) {
    const reducedStateVerified = await reducedVoltagePage.evaluate(async (testPackage) => {
      await requestResult("/api/orient", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(testPackage),
      }, false);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return Array.from(document.querySelectorAll(".guide-character, .guide-arm, .guide-marker"))
        .every((element) => getComputedStyle(element).animationName === "none");
    }, payload);
    allReducedVoltageStatesVerified = allReducedVoltageStatesVerified && reducedStateVerified;
  }
  browserChecks.assistant_all_five_reduced_motion_states = allReducedVoltageStatesVerified;
  await reducedVoltageContext.close();

  const narrowContext = await browser.newContext({
    viewport: { width: 320, height: 640 },
    reducedMotion: "reduce",
  });
  const narrowPage = await narrowContext.newPage();
  narrowPage.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      consoleErrors.push({ type: message.type(), text: message.text(), viewport: "narrow" });
    }
  });
  narrowPage.on("pageerror", (error) => pageErrors.push(`narrow: ${error.message}`));
  await narrowPage.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await narrowPage.goto(baseUrl, { waitUntil: "networkidle" });
  await narrowPage.locator("#position-statement").filter({ hasText: "not yet judge-ready" }).waitFor();
  browserChecks.minimum_width_no_horizontal_overflow = await narrowPage.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  const longToken = "ORIENTATION".repeat(96);
  await narrowPage.evaluate((token) => {
    const selectors = [
      "#position-statement",
      "#package-name",
      "#goal",
      "#assistant-cue",
      "#next-step-reason",
      "#next-step-sources",
      "#success-condition",
      ".intake-item strong",
      ".intake-item p",
      ".ruled-item strong",
      ".ruled-item p",
      ".card-summary dd",
      ".receipt-card h3",
      ".package-error",
      "#source-table td",
    ];
    selectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((element) => {
        element.textContent = token;
        if (element.id === "package-error") element.hidden = false;
      });
    });
  }, longToken);
  browserChecks.long_dynamic_tokens_reflow = await narrowPage.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  const responsiveWidths = [320, 360, 390, 480, 600, 640, 720, 760, 761, 768, 800, 900, 1024, 1120, 1121, 1280, 1440];
  const responsiveResults = [];
  for (const width of responsiveWidths) {
    await narrowPage.setViewportSize({ width, height: 640 });
    responsiveResults.push(await narrowPage.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    })));
  }
  browserChecks.responsive_width_sweep_no_horizontal_overflow = responsiveResults.every(
    ({ clientWidth, scrollWidth }) => scrollWidth <= clientWidth,
  );
  await narrowContext.close();

  const forcedColorsContext = await browser.newContext({
    viewport: { width: 320, height: 640 },
    forcedColors: "active",
    reducedMotion: "reduce",
  });
  const forcedColorsPage = await forcedColorsContext.newPage();
  forcedColorsPage.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      consoleErrors.push({ type: message.type(), text: message.text(), viewport: "forced-colors" });
    }
  });
  forcedColorsPage.on("pageerror", (error) => pageErrors.push(`forced-colors: ${error.message}`));
  await forcedColorsPage.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await forcedColorsPage.goto(baseUrl, { waitUntil: "networkidle" });
  await forcedColorsPage.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
  });
  let forcedColorsFocusReached = false;
  for (let index = 0; index < 6; index += 1) {
    await forcedColorsPage.keyboard.press("Tab");
    forcedColorsFocusReached = await forcedColorsPage.locator("#choose-package").evaluate(
      (element) => document.activeElement === element,
    );
    if (forcedColorsFocusReached) break;
  }
  browserChecks.high_contrast_focus_visible = forcedColorsFocusReached
    && await forcedColorsPage.locator("#choose-package").evaluate((element) => {
      const style = getComputedStyle(element);
      return style.outlineStyle === "solid" && Number.parseFloat(style.outlineWidth) >= 3;
    });
  let forcedColorsTableFocusReached = false;
  for (let index = 0; index < 16; index += 1) {
    await forcedColorsPage.keyboard.press("Tab");
    forcedColorsTableFocusReached = await forcedColorsPage.locator(".table-wrap").evaluate(
      (element) => document.activeElement === element,
    );
    if (forcedColorsTableFocusReached) break;
  }
  browserChecks.high_contrast_table_keyboard_focus_visible = forcedColorsTableFocusReached
    && await forcedColorsPage.locator(".table-wrap").evaluate((element) => {
      const style = getComputedStyle(element);
      return style.outlineStyle === "solid" && Number.parseFloat(style.outlineWidth) >= 3;
    });
  browserChecks.high_contrast_assistant_strokes_visible = await forcedColorsPage.evaluate(() => {
    const bodyStroke = getComputedStyle(document.querySelector(".guide-body")).stroke;
    const armStroke = getComputedStyle(document.querySelector(".guide-arm")).stroke;
    const markerStroke = getComputedStyle(document.querySelector(".guide-marker-blocked")).stroke;
    const canvasText = getComputedStyle(document.body).color;
    const highlightProbe = document.createElement("span");
    highlightProbe.style.color = "Highlight";
    document.body.append(highlightProbe);
    const highlight = getComputedStyle(highlightProbe).color;
    highlightProbe.remove();
    return bodyStroke === canvasText && armStroke === canvasText && markerStroke === highlight;
  });
  browserChecks.high_contrast_no_horizontal_overflow = await forcedColorsPage.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  await forcedColorsContext.close();

  const importContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const importPage = await importContext.newPage();
  const importConsoleMessages = [];
  importPage.on("console", (message) => {
    if (new Set(["error", "warning"]).has(message.type())) {
      importConsoleMessages.push({ type: message.type(), text: message.text(), viewport: "import" });
    }
  });
  importPage.on("pageerror", (error) => pageErrors.push(`import: ${error.message}`));
  await importPage.route("**/*", async (route) => {
    const target = new URL(route.request().url());
    if (loopbackHosts.has(target.hostname)) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  await importPage.goto(baseUrl, { waitUntil: "networkidle" });
  await importPage.locator("#package-file").setInputFiles({
    name: "invalid.json",
    mimeType: "application/json",
    buffer: Buffer.from("{invalid", "utf8"),
  });
  await importPage.locator("#package-error").filter({ hasText: "Orientation failed" }).waitFor();
  await pause(2800);
  browserChecks.invalid_json_error_is_persistent_and_single = await importPage.evaluate(() => (
    !document.querySelector("#package-error").hidden
    && document.querySelector("#package-error").textContent.includes("Orientation failed")
    && !document.querySelector("#toast").classList.contains("visible")
  ));
  await importPage.locator("#package-file").setInputFiles(demoPackagePath);
  await importPage.locator("#position-statement").filter({ hasText: "not yet judge-ready" }).waitFor();
  browserChecks.valid_import_recovers_after_invalid_json = await importPage.evaluate(
    () => document.querySelector("#package-error").hidden
      && document.querySelector("#orientation-guide").dataset.voltage === "BLOCKED",
  );
  await importPage.locator("#package-file").setInputFiles({
    name: "oversized.json",
    mimeType: "application/json",
    buffer: Buffer.alloc(1_000_001, 32),
  });
  await importPage.locator("#package-error").filter({ hasText: "local JSON limit is 1 MB" }).waitFor();
  browserChecks.oversized_import_rejected_locally = await importPage.evaluate(
    () => !document.querySelector("#package-error").hidden
      && document.querySelector("#package-error").textContent.includes("local JSON limit is 1 MB"),
  );
  const expectedImportErrors = importConsoleMessages.filter(
    (message) => message.type === "error"
      && message.text.includes("Failed to load resource")
      && message.text.includes("status of 400"),
  );
  const unexpectedImportMessages = importConsoleMessages.filter(
    (message) => !expectedImportErrors.includes(message),
  );
  browserChecks.invalid_json_expected_http_error_isolated = expectedImportErrors.length === 1
    && unexpectedImportMessages.length === 0;
  consoleErrors.push(...unexpectedImportMessages);
  await importContext.close();
  browserChecks.no_unexpected_console_or_page_errors = consoleErrors.length === 0 && pageErrors.length === 0;

  const qaReceipt = {
    scope: "LOCAL_BROWSER_WORKFLOW_ONLY",
    status: Object.values(browserChecks).every(Boolean) ? "PASS" : "FAIL",
    base_url: baseUrl,
    execution: "LOCAL_HEADLESS_CHROMIUM_NO_EXTERNAL_HOSTS",
    artifacts: {
      desktop_screenshot: path.relative(process.cwd(), desktopScreenshotPath).split(path.sep).join("/"),
      mobile_screenshot: path.relative(process.cwd(), mobileScreenshotPath).split(path.sep).join("/"),
    },
    checks: browserChecks,
    expected_console_events: expectedImportErrors,
    console_errors: consoleErrors,
    page_errors: pageErrors,
    claim_limit: "This receipt proves only the tested local headless workflow; it does not prove publication, external source truth, clipboard support in other browsers, or production readiness.",
  };
  fs.writeFileSync(qaPath, `${JSON.stringify(qaReceipt, null, 2)}\n`, "utf8");

  const video = page.video();
  await page.close();
  await video.saveAs(outputPath);
  await context.close();
  process.stdout.write(
    `VIDEO_RECORDED ${outputPath}\n`
      + `DESKTOP_SCREENSHOT_RECORDED ${desktopScreenshotPath}\n`
      + `MOBILE_SCREENSHOT_RECORDED ${mobileScreenshotPath}\n`
      + `BROWSER_QA_${qaReceipt.status} ${qaPath}\n`,
  );
  if (qaReceipt.status !== "PASS") process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
})().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
