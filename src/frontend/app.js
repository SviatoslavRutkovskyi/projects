// ── State ──
let state = {
  jobPosting: "",
  parsedJob: null,
  coverLetterText: null,
  coverLetterPdfFilename: null,
  resumePdfFilename: null,
  lastResumeJson: null,
};

let activeRequests = new Set();
let parsePromise = null;

// ── Tab switching ──
function switchTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".tab-panel")
    .forEach((p) => p.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  document.getElementById("panel-" + name).classList.add("active");
}

// ── Job posting change ──
function onJobPostingChange() {
  const val = document.getElementById("job-posting").value;
  state.jobPosting = val;
  // Clear cached parse if job text changed
  state.parsedJob = null;
  updateStatus("idle");
}

// ── Status indicator ──
function updateStatus(mode, text) {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-text");
  dot.className = "status-dot";
  if (mode === "parsing") {
    dot.classList.add("parsing");
    label.textContent = text || "parsing...";
  } else if (mode === "ready") {
    dot.classList.add("ready");
    label.textContent = text || "ready";
  } else if (mode === "error") {
    dot.classList.add("error");
    label.textContent = text || "error";
  } else {
    label.textContent = text || "no job loaded";
  }
}

// ── Action buttons ──
const ACTION_LABELS = {
  "cover-letter": "Generate Cover Letter",
  resume: "Tailor Resume",
  answer: "Answer Question",
};

const ACTION_BTN_IDS = {
  "cover-letter": "btn-cover-letter",
  resume: "btn-resume",
  answer: "btn-answer",
};

function setActionLoading(action, phase) {
  const btn = document.getElementById(ACTION_BTN_IDS[action]);
  if (!btn) return;
  btn.disabled = true;
  btn.classList.add("loading");
  btn.querySelector(".btn-label").textContent = phase;
}

function clearActionLoading(action) {
  const btn = document.getElementById(ACTION_BTN_IDS[action]);
  if (!btn) return;
  btn.disabled = false;
  btn.classList.remove("loading");
  btn.querySelector(".btn-label").textContent = ACTION_LABELS[action];
}

// ── Job parse deduplication ──
async function getOrParseJob(jobText) {
  if (state.parsedJob) return state.parsedJob;

  if (!parsePromise) {
    parsePromise = apiCall("POST", "/api/v1/job/parse", {
      job_posting: jobText,
    })
      .then((result) => {
        state.parsedJob = result;
        const label =
          [result.job_title, result.company_name]
            .filter(Boolean)
            .join(" at ") || "parsed";
        updateStatus("ready", label);
        return result;
      })
      .finally(() => {
        parsePromise = null;
      });
  }

  return parsePromise;
}

// ── Main action runner ──
async function runAction(action) {
  if (activeRequests.has(action)) return;
  activeRequests.add(action);

  const jobText = document.getElementById("job-posting").value.trim();
  if (!jobText) {
    toast("Paste a job description first.", "error");
    switchTab("job");
    activeRequests.delete(action);
    return;
  }

  try {
    // Step 1: Parse if needed
    let jobDesc = state.parsedJob;
    if (!jobDesc) {
      setActionLoading(action, "Parsing job...");
      updateStatus("parsing");
      jobDesc = await getOrParseJob(jobText);
    }

    // Step 2: Run action
    if (action === "cover-letter") {
      setActionLoading(action, "Generating...");
      const result = await apiCall("POST", "/api/v1/cover-letter", {
        job_description: jobDesc,
      });
      state.coverLetterText = result.cover_letter;
      state.parsedJob = result.job_description;
      renderCoverLetter(result.cover_letter);
      document.getElementById("btn-pdf").disabled = false;
      state.coverLetterPdfFilename = null;
      document.getElementById("pdf-download-cl").style.display = "none";
      switchTab("cover-letter");
      toast("Cover letter generated.", "success");
    } else if (action === "resume") {
      setActionLoading(action, "Tailoring...");
      const feedback = document.getElementById("resume-feedback").value;
      const useLast = document.getElementById("use-last-resume").checked;
      const body = {
        job_description: jobDesc,
        resume_feedback: feedback,
        last_resume_json: useLast ? state.lastResumeJson : null,
      };
      const result = await apiCall("POST", "/api/v1/resume/tailor", body);
      state.parsedJob = result.job_description;
      state.lastResumeJson = result.last_resume_json;
      state.resumePdfFilename = result.pdf_filename;
      renderResumePdf(result.pdf_filename);
      switchTab("resume");
      toast("Resume tailored.", "success");
    } else if (action === "answer") {
      switchTab("questions");
      const pairs = document.querySelectorAll(".qa-pair");
      if (pairs.length === 0) {
        addQuestion();
        toast("Enter a question then click Answer Question.", "info");
        clearActionLoading(action);
        activeRequests.delete(action);
        return;
      }
      setActionLoading(action, "Answering...");
      for (const pair of pairs) {
        const input = pair.querySelector("textarea");
        const answerBox = pair.querySelector(".answer-box");
        if (!input.value.trim() || answerBox.dataset.answered === "true")
          continue;
        answerBox.textContent = "Answering...";
        answerBox.classList.add("empty");
        try {
          const res = await apiCall("POST", "/api/v1/questions/answer", {
            job_description: jobDesc,
            question: input.value.trim(),
          });
          answerBox.textContent = res.answer;
          answerBox.classList.remove("empty");
          answerBox.dataset.answered = "true";
          state.parsedJob = res.job_description;
        } catch (e) {
          answerBox.textContent = "Error: " + e.message;
        }
      }
      toast("Questions answered.", "success");
    }
  } catch (err) {
    updateStatus("error", "error");
    toast(err.message || "Something went wrong.", "error");
  } finally {
    clearActionLoading(action);
    activeRequests.delete(action);
  }
}

// ── Cover letter PDF ──
async function convertToPdf() {
  if (!state.coverLetterText) return;
  const btn = document.getElementById("btn-pdf");
  btn.disabled = true;
  btn.classList.add("loading");
  btn.querySelector(".btn-label").textContent = "Converting...";
  try {
    const body = { cover_letter_text: state.coverLetterText };
    if (state.parsedJob) body.job_description = state.parsedJob;
    const response = await fetch("/api/v1/cover-letter/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.getElementById("pdf-link-cl");
    link.href = url;
    link.download = "cover_letter.pdf";
    link.textContent = "Download PDF";
    document.getElementById("pdf-download-cl").style.display = "block";
    toast("PDF ready.", "success");
  } catch (e) {
    toast("PDF generation failed: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.classList.remove("loading");
    btn.querySelector(".btn-label").textContent = "Convert to PDF";
  }
}

// ── Render cover letter ──
function renderCoverLetter(text) {
  const out = document.getElementById("cover-letter-output");
  out.innerHTML = "";
  const pre = document.createElement("pre");
  pre.id = "cover-letter-text";
  pre.style.cssText =
    "white-space:pre-wrap; font-family:var(--mono); font-size:12.5px; line-height:1.8; color:var(--text);";
  pre.textContent = text;
  out.appendChild(pre);
}

// ── Render resume PDF ──
function renderResumePdf(filename) {
  const iframe = document.getElementById("resume-iframe");
  const placeholder = document.getElementById("resume-placeholder");
  const downloadRow = document.getElementById("resume-download-row");
  const downloadLink = document.getElementById("resume-download-link");

  const url = "/api/v1/outputs/" + encodeURIComponent(filename);
  iframe.src = url;
  iframe.style.display = "block";
  placeholder.style.display = "none";
  downloadRow.style.display = "flex";
  downloadLink.href = url;
  downloadLink.download = filename;
  downloadLink.textContent = "Download PDF";

  document.getElementById("use-last-resume-row").style.display = "flex";
  document.getElementById("no-last-resume-msg").style.display = "none";
}

// ── Questions ──
let qaCounter = 0;

function addQuestion() {
  const list = document.getElementById("qa-list");
  const id = ++qaCounter;
  const div = document.createElement("div");
  div.className = "qa-pair";
  div.id = "qa-" + id;
  div.innerHTML = `
    <div>
      <div class="qa-label">Question</div>
      <textarea rows="4" placeholder="Enter interview question..." oninput="markUnanswered(${id})"></textarea>
      <div class="qa-row-actions">
        <button class="btn btn-sm" onclick="answerOne(${id})">
          <div class="spinner"></div>
          <span class="btn-label">Answer</span>
        </button>
        <button class="btn btn-sm" onclick="removeQuestion(${id})">Remove</button>
      </div>
    </div>
    <div>
      <div class="qa-label">Answer</div>
      <div class="answer-box empty" id="answer-${id}" data-answered="false">Answer will appear here.</div>
    </div>
  `;
  list.appendChild(div);
}

function removeQuestion(id) {
  const el = document.getElementById("qa-" + id);
  if (el) el.remove();
}

function markUnanswered(id) {
  const box = document.getElementById("answer-" + id);
  if (box) box.dataset.answered = "false";
}

async function answerOne(id) {
  const pair = document.getElementById("qa-" + id);
  const input = pair.querySelector("textarea");
  const answerBox = document.getElementById("answer-" + id);
  const btn = pair.querySelector("button");

  if (!input.value.trim()) {
    toast("Enter a question first.", "error");
    return;
  }

  const jobText = document.getElementById("job-posting").value.trim();
  if (!jobText) {
    toast("Paste a job description first.", "error");
    switchTab("job");
    return;
  }

  btn.disabled = true;
  btn.classList.add("loading");
  answerBox.textContent = "Answering...";
  answerBox.classList.add("empty");

  try {
    let jobDesc = state.parsedJob;
    if (!jobDesc) {
      updateStatus("parsing");
      jobDesc = await getOrParseJob(jobText);
    }
    const res = await apiCall("POST", "/api/v1/questions/answer", {
      job_description: jobDesc,
      question: input.value.trim(),
    });
    answerBox.textContent = res.answer;
    answerBox.classList.remove("empty");
    answerBox.dataset.answered = "true";
    state.parsedJob = res.job_description;
  } catch (e) {
    answerBox.textContent = "Error: " + e.message;
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.classList.remove("loading");
    btn.querySelector(".btn-label").textContent = "Answer";
  }
}

// ── API helper ──
async function apiCall(method, path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        detail = j.detail || detail;
      } catch {}
      throw new Error(detail);
    }
    return await res.json();
  } catch (e) {
    if (e.name === "AbortError")
      throw new Error("Request timed out. Please try again.");
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

// ── Copy helper ──
function copyText(id) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard
    .writeText(el.textContent)
    .then(() => toast("Copied.", "success"));
}

// ── Toast ──
function toast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Init ──
addQuestion();
