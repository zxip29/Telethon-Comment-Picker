import {
  applyFilters,
  formatComments,
  joinFormatted,
} from "./filters.js";

const form = document.getElementById("fetch-form");
const linkInput = document.getElementById("link-input");
const fetchBtn = document.getElementById("fetch-btn");
const copyBtn = document.getElementById("copy-btn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const filtersPanel = document.getElementById("filters-panel");
const countValue = document.getElementById("count-value");
const countFetched = document.getElementById("count-fetched");
const commentsPre = document.getElementById("comments-pre");

const filterDedupe = document.getElementById("filter-dedupe");
const filterHideMedia = document.getElementById("filter-hide-media");
const filterTextOnly = document.getElementById("filter-text-only");

let allComments = [];
let copyText = "";

const API_BASE =
  window.location.port === "8000" || window.location.hostname === "127.0.0.1"
    ? ""
    : "http://127.0.0.1:8000";

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
  if (loading) {
    setStatus("Fetching comments from Telegram…", "loading");
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
  commentsPre.textContent = copyText || "(no comments match filters)";

  copyBtn.disabled = !copyText;
  resultsEl.classList.remove("hidden");
}

function onDataLoaded(data) {
  allComments = data.comments || [];
  const total = data.total_fetched ?? allComments.length;

  countFetched.textContent = String(total);

  if (total === 0) {
    countValue.textContent = "0";
    commentsPre.textContent = "";
    copyBtn.disabled = true;
    resultsEl.classList.remove("hidden");
    filtersPanel.classList.add("hidden");
    if (data.message) {
      setStatus(data.message, "info");
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
    await navigator.clipboard.writeText(copyText);
    setStatus("Copied to clipboard.", "info");
    setTimeout(clearStatus, 2000);
  } catch {
    const range = document.createRange();
    range.selectNodeContents(commentsPre);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    setStatus("Press Ctrl+C to copy the selected text.", "info");
  }
}

copyBtn.addEventListener("click", copyAll);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const link = linkInput.value.trim();
  if (!link) return;

  setLoading(true);

  try {
    const url = `${API_BASE}/comments?link=${encodeURIComponent(link)}`;
    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok) {
      const msg = data.detail
        ? `${data.error || "Error"}: ${data.detail}`
        : data.error || `Request failed (${res.status})`;
      setStatus(msg, "error");
      resultsEl.classList.add("hidden");
      return;
    }

    onDataLoaded(data);
  } catch {
    setStatus(
      "Could not reach the API. Is the backend running on http://127.0.0.1:8000?",
      "error"
    );
    resultsEl.classList.add("hidden");
  } finally {
    fetchBtn.disabled = false;
    linkInput.disabled = false;
  }
});
