"use strict";

const state = { result: null, filter: "ALL", toastTimer: null };
const byId = (id) => document.getElementById(id);

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function clearError() {
  const error = byId("package-error");
  error.hidden = true;
  error.textContent = "";
}

function showError(message) {
  const error = byId("package-error");
  error.textContent = message;
  error.hidden = false;
  showToast(message);
}

function replayGuideMotion() {
  const guide = byId("orientation-guide");
  guide.classList.remove("motion-cue");
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => guide.classList.add("motion-cue"));
  });
}

function displayValue(value) {
  return typeof value === "string" ? value : JSON.stringify(value);
}

function setText(id, value) {
  byId(id).textContent = value == null ? "—" : String(value);
}

function goalFrom(checkpoint) {
  const lamp = checkpoint.active_lamps.find((item) => item.type === "GOAL");
  return lamp ? displayValue(lamp.value) : "UNKNOWN";
}

function formatSuccessCondition(condition) {
  return Object.entries(condition)
    .map(([name, value]) => `${name.replaceAll("_", " ")}=${displayValue(value)}`)
    .join(" · ");
}

function renderIntake() {
  const list = byId("intake-list");
  list.replaceChildren();
  const items = state.result.intake.filter((item) => state.filter === "ALL" || item.status === state.filter);
  const total = state.result.intake.length;
  const count = state.filter === "ALL" ? `${total} ${total === 1 ? "item" : "items"}` : `${items.length} of ${total} items`;
  setText("intake-count", count);
  items.forEach((item) => {
    const row = node("li", "intake-item");
    row.dataset.status = item.status;
    const header = node("header");
    header.append(node("strong", "", item.subject));
    header.append(node("span", "status-label", item.status));
    row.append(header);
    row.append(node("p", "", item.reason));
    row.append(node("p", "", `${item.change_id} · ${item.source_ids.join(", ") || "no source"}`));
    list.append(row);
  });
}

function renderCurrent(result) {
  const checkpoint = result.checkpoint;
  const guideState = {
    FLOWING: "Direction is clear",
    WEAK: "Mitigation comes first",
    BLOCKED: "Holding at the blocker",
    BROKEN: "Correct the course",
    UNKNOWN: "Waiting for evidence",
  };
  setText("package-name", result.package_id);
  setText("checkpoint-hash", `checkpoint ${checkpoint.integrity.value.slice(0, 18)}…`);
  setText("voltage", checkpoint.voltage);
  byId("voltage").dataset.voltage = checkpoint.voltage;
  setText("position-statement", checkpoint.city_position);
  setText("goal", goalFrom(checkpoint));
  setText("base-status", result.base_checkpoint.status);
  setText("execution-mode", result.execution_mode.replaceAll("_", " "));
  byId("orientation-guide").dataset.voltage = checkpoint.voltage;
  setText("assistant-state", guideState[checkpoint.voltage] || guideState.UNKNOWN);
  setText("assistant-cue", checkpoint.primary_next_step.instruction);
  setText("next-step-reason", checkpoint.primary_next_step.reason);
  setText("next-step-sources", `Sources ${checkpoint.primary_next_step.source_ids.join(" · ")}`);
  const successCondition = checkpoint.primary_next_step.success_condition;
  setText("success-condition", `success · ${formatSuccessCondition(successCondition)}`);
  byId("success-condition").dataset.machineValue = JSON.stringify(successCondition);
  setText("orientation-status", `${checkpoint.voltage}. Next action: ${checkpoint.primary_next_step.instruction}`);
  replayGuideMotion();
}

function renderBlockers(result) {
  const conflicts = result.checkpoint.conflicts.filter((item) => item.status === "DISPUTED");
  const materialConflicts = conflicts.filter((item) => item.material);
  const unknowns = result.checkpoint.unknowns.filter((item) => item.critical);
  setText("blocker-count", `${materialConflicts.length + unknowns.length} blockers`);
  const conflictList = byId("conflict-list");
  const unknownList = byId("unknown-list");
  conflictList.replaceChildren();
  unknownList.replaceChildren();
  if (!conflicts.length) conflictList.append(node("p", "empty-state", "No open material conflict."));
  conflicts.forEach((conflict) => {
    const item = node("article", "ruled-item");
    item.append(node("strong", "", conflict.subject));
    item.append(node("p", "", conflict.reason));
    conflict.claims.forEach((claim) => item.append(node("p", "", `${displayValue(claim.value)} — ${claim.source_ids.join(", ")}`)));
    conflictList.append(item);
  });
  if (!unknowns.length) unknownList.append(node("p", "empty-state", "No critical unknown."));
  unknowns.forEach((unknown) => {
    const item = node("article", "ruled-item");
    item.append(node("strong", "", unknown.subject));
    item.append(node("p", "", unknown.statement));
    item.append(node("p", "", `Sources ${unknown.source_ids.join(", ")}`));
    unknownList.append(item);
  });
}

function renderRecovery(result) {
  const card = result.recovery_card;
  setText("card-position", card.city_position);
  setText("card-goal", card.goal);
  setText("card-voltage", card.voltage);
  setText("card-next", card.primary_next_step.instruction);
  setText("card-provenance", `Derived from ${card.derived_from_checkpoint_id} · ${card.derived_from_integrity.slice(0, 14)}…`);
}

function renderSources(result) {
  const table = byId("source-table");
  table.replaceChildren();
  setText("source-count", `${result.source_evidence.length} sources`);
  result.source_evidence.forEach((source) => {
    const row = node("tr");
    const idCell = node("td");
    idCell.append(node("code", "", source.source_id));
    row.append(idCell);
    row.append(node("td", "", source.kind));
    const authorityCell = node("td");
    const authority = node("span", "authority", source.authority);
    authority.dataset.authority = source.authority;
    authorityCell.append(authority);
    row.append(authorityCell);
    row.append(node("td", "", source.captured_at));
    row.append(node("td", "", source.excerpt));
    table.append(row);
  });
}

function renderReceipts(result) {
  const imported = byId("imported-receipts");
  imported.replaceChildren();
  result.validation_receipts.forEach((receipt) => {
    const card = node("article", "receipt-card");
    const header = node("header");
    header.append(node("h3", "", receipt.subject));
    const status = node("span", "receipt-status", receipt.status);
    status.dataset.status = receipt.status;
    header.append(status);
    card.append(header);
    card.append(node("p", "", receipt.summary));
    card.append(node("p", "", `${receipt.validator_id} · ${receipt.receipt_id}`));
    const checks = node("ul", "check-list");
    receipt.checks.forEach((check) => {
      const item = node("li");
      item.append(node("span", "", check.id));
      item.append(node("strong", "", check.status));
      checks.append(item);
    });
    card.append(checks);
    imported.append(card);
  });

  const run = result.run_receipt;
  const runBox = byId("run-receipt");
  runBox.replaceChildren();
  runBox.append(node("h3", "", `${run.status} · ${run.scope}`));
  runBox.append(node("p", "", run.claim_limit));
  const checks = node("ul", "check-list");
  Object.entries(run.checks).forEach(([name, passed]) => {
    const item = node("li");
    item.append(node("span", "", name.replaceAll("_", " ")));
    item.append(node("strong", "", passed ? "PASS" : "FAIL"));
    checks.append(item);
  });
  runBox.append(checks);
  setText("run-status", `${run.status} · transform only`);
}

function render(result) {
  state.result = result;
  renderCurrent(result);
  renderIntake();
  renderBlockers(result);
  renderRecovery(result);
  renderSources(result);
  renderReceipts(result);
}

async function requestResult(url, options, announce = true) {
  byId("rerun").disabled = true;
  byId("choose-package").disabled = true;
  document.querySelector("main").setAttribute("aria-busy", "true");
  clearError();
  try {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || body.error || `HTTP ${response.status}`);
    render(body);
    if (announce) showToast(`Orientation updated: ${body.checkpoint.voltage}. One next action selected.`);
  } catch (error) {
    showError(`Orientation failed: ${error.message}`);
  } finally {
    byId("rerun").disabled = false;
    byId("choose-package").disabled = false;
    document.querySelector("main").removeAttribute("aria-busy");
  }
}

byId("rerun").addEventListener("click", () => requestResult("/api/demo"));
byId("choose-package").addEventListener("click", () => byId("package-file").click());
byId("package-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  if (file.size > 1_000_000) {
    showError("Package rejected: the local JSON limit is 1 MB.");
    event.target.value = "";
    return;
  }
  await requestResult("/api/orient", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await file.text(),
  });
  event.target.value = "";
});
document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    document.querySelectorAll(".filter").forEach((item) => {
      const selected = item === button;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    if (state.result) renderIntake();
  });
});
byId("copy-card").addEventListener("click", async () => {
  if (!state.result) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(state.result.recovery_card, null, 2));
    showToast("Recovery Card copied. It remains derived, never authoritative.");
  } catch (_error) {
    showToast("Clipboard access is unavailable in this browser.");
  }
});

requestResult("/api/demo", undefined, false);
