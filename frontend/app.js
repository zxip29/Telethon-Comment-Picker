import {
  applyFilters,
  formatComments,
  joinFormatted,
} from "./filters.js";

const form = document.getElementById("fetch-form");
const linkInput = document.getElementById("link-input");
const fetchBtn = document.getElementById("fetch-btn");
const stopFetchBtn = document.getElementById("stop-fetch-btn");
const copyBtn = document.getElementById("copy-btn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const filtersPanel = document.getElementById("filters-panel");
const countValue = document.getElementById("count-value");
const countFetched = document.getElementById("count-fetched");
const latencyValue = document.getElementById("latency-value");
const lineCountBadge = document.getElementById("line-count-badge");
const sessionBadge = document.getElementById("session-badge");
const commentsPre = document.getElementById("comments-pre");

const filterDedupe = document.getElementById("filter-dedupe");
const filterHideMedia = document.getElementById("filter-hide-media");
const filterTextOnly = document.getElementById("filter-text-only");

let allComments = [];
let copyText = "";
let activeController = null;

const API_BASE =
  window.location.port === "8000" || window.location.hostname === "127.0.0.1"
    ? ""
    : "http://127.0.0.1:8000";

async function loadSessionInfo() {
  try {
    const res = await fetch(`${API_BASE}/auth/status`);
    const data = await res.json();
    if (data.authorized && sessionBadge) {
      sessionBadge.textContent = `MTProto · ${data.name || "USER"}`;
    }
  } catch {
    // ignore
  }
}
loadSessionInfo();

function setStatus(message, type) {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  statusEl.classList.remove("hidden");
}

function clearStatus() {
  statusEl.classList.add("hidden");
  statusEl.textContent = "";
}

function getFilterOptions() {
  return {
    removeDuplicates: filterDedupe.checked,
    hideMedia: filterHideMedia.checked,
    textOnly: filterTextOnly.checked,
  };
}

function setLoading(loading) {
  fetchBtn.disabled = loading;
  linkInput.disabled = loading;
  if (stopFetchBtn) {
    stopFetchBtn.classList.toggle("hidden", !loading);
  }
  if (loading) {
    setStatus("[EXEC] Fetching paginated comments from Telegram MTProto…", "loading");
    resultsEl.classList.add("hidden");
    allComments = [];
    copyText = "";
  }
}

function applyFiltersAndRender() {
  const filtered = applyFilters(allComments, getFilterOptions());
  const lines = formatComments(filtered);
  copyText = joinFormatted(lines);

  countValue.textContent = String(filtered.length);
  countFetched.textContent = String(allComments.length);
  if (lineCountBadge) {
    lineCountBadge.textContent = `${filtered.length} lines`;
  }
  commentsPre.textContent = copyText || "// 0 comments match active filter pipeline";

  copyBtn.disabled = !copyText;
  resultsEl.classList.remove("hidden");
}

function onDataLoaded(data, elapsedMs) {
  allComments = data.comments || [];
  const total = data.total_fetched ?? allComments.length;

  countFetched.textContent = String(total);
  if (latencyValue) {
    latencyValue.textContent = `${elapsedMs}ms`;
  }

  if (total === 0) {
    countValue.textContent = "0";
    if (lineCountBadge) lineCountBadge.textContent = "0 lines";
    commentsPre.textContent = "// empty result set";
    copyBtn.disabled = true;
    resultsEl.classList.remove("hidden");
    filtersPanel.classList.add("hidden");
    if (data.message) {
      setStatus(`[INFO] ${data.message}`, "info");
    }
    return;
  }

  filtersPanel.classList.remove("hidden");
  clearStatus();
  applyFiltersAndRender();
}

[filterDedupe, filterHideMedia, filterTextOnly].forEach((el) => {
  el.addEventListener("change", () => {
    if (allComments.length) {
      applyFiltersAndRender();
    }
  });
});

async function copyAll() {
  if (!copyText) return;
  try {
    if (window.AndroidBridge && typeof window.AndroidBridge.copyToClipboard === "function") {
      window.AndroidBridge.copyToClipboard(copyText);
    } else {
      await navigator.clipboard.writeText(copyText);
    }
    setStatus(`[OK] Copied ${copyText.split("\n").length} lines to clipboard.`, "info");
    setTimeout(clearStatus, 2000);
  } catch {
    const range = document.createRange();
    range.selectNodeContents(commentsPre);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    setStatus("[INFO] Selected text — press Copy.", "info");
  }
}

copyBtn.addEventListener("click", copyAll);

if (stopFetchBtn) {
  stopFetchBtn.addEventListener("click", () => {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
  });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const link = linkInput.value.trim();
  if (!link) return;

  if (activeController) {
    activeController.abort();
  }
  activeController = new AbortController();

  setLoading(true);
  const t0 = performance.now();

  try {
    const url = `${API_BASE}/comments?link=${encodeURIComponent(link)}`;
    const res = await fetch(url, { signal: activeController.signal });
    const data = await res.json();
    const elapsedMs = Math.round(performance.now() - t0);

    if (!res.ok) {
      const msg = data.detail
        ? `[HTTP ${res.status}] ${data.error || "Error"}: ${data.detail}`
        : `[HTTP ${res.status}] ${data.error || "Request failed"}`;
      setStatus(msg, "error");
      resultsEl.classList.add("hidden");
      return;
    }

    onDataLoaded(data, elapsedMs);
  } catch (err) {
    if (err && err.name === "AbortError") {
      setStatus("[ABORTED] Fetch request cancelled by user.", "error");
    } else {
      setStatus(
        "[ERR] Connection refused on 127.0.0.1:8000 — check if daemon is RUNNING.",
        "error"
      );
    }
    resultsEl.classList.add("hidden");
  } finally {
    activeController = null;
    setLoading(false);
  }
});
