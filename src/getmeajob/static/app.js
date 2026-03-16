const STORAGE_KEY = "getmeajob.ui.v2";

function readState() {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function writeState(nextState) {
  try {
    const current = readState();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...nextState }));
  } catch {
    // Ignore storage failures.
  }
}

function parseJsonNode(id, fallback) {
  const node = document.getElementById(id);
  if (!node) {
    return fallback;
  }
  try {
    return JSON.parse(node.textContent || "");
  } catch {
    return fallback;
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function page() {
  return document.body?.dataset.page || "";
}

function authStatus() {
  return parseJsonNode("page-auth-status", {});
}

function describeList(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return "none";
  }
  return items.slice(0, 4).join(", ");
}

function setupJobsPage() {
  const jobsGrid = document.getElementById("jobs-grid");
  if (!jobsGrid) {
    return;
  }

  const jobSearch = document.getElementById("job-search");
  const jobCompanyFilter = document.getElementById("job-company-filter");
  const jobLocationFilter = document.getElementById("job-location-filter");
  const jobDurationFilter = document.getElementById("job-duration-filter");
  const jobProviderFilter = document.getElementById("job-provider-filter");
  const jobRemoteFilter = document.getElementById("job-remote-filter");
  const jobFilterReset = document.getElementById("job-filter-reset");
  const jobsCount = document.getElementById("jobs-count");
  const jobsEmpty = document.getElementById("jobs-empty");
  const activeFilters = document.getElementById("active-filters");
  const authButtons = Array.from(document.querySelectorAll('.auth-button[href^="/auth/login/google"]'));

  authButtons.forEach((button) => {
    if (button instanceof HTMLAnchorElement) {
      button.href = `/auth/login/google?next=${encodeURIComponent(window.location.pathname)}`;
    }
  });

  const stored = readState();
  if (jobSearch && typeof stored.jobSearch === "string") {
    jobSearch.value = stored.jobSearch;
  }
  if (jobCompanyFilter && typeof stored.jobCompany === "string") {
    jobCompanyFilter.value = stored.jobCompany;
  }
  if (jobLocationFilter && typeof stored.jobLocation === "string") {
    jobLocationFilter.value = stored.jobLocation;
  }
  if (jobDurationFilter && typeof stored.jobDuration === "string") {
    jobDurationFilter.value = stored.jobDuration;
  }
  if (jobProviderFilter && typeof stored.jobProvider === "string") {
    jobProviderFilter.value = stored.jobProvider;
  }
  if (jobRemoteFilter) {
    jobRemoteFilter.checked = Boolean(stored.jobRemoteOnly);
  }

  function describeActiveFilters() {
    const labels = [];
    if (jobSearch?.value.trim()) {
      labels.push(`search: ${jobSearch.value.trim()}`);
    }
    if (jobCompanyFilter?.value) {
      labels.push(`company: ${jobCompanyFilter.value}`);
    }
    if (jobLocationFilter?.value) {
      labels.push(`location: ${jobLocationFilter.value}`);
    }
    if (jobDurationFilter?.value) {
      labels.push(`duration: ${jobDurationFilter.value}`);
    }
    if (jobProviderFilter?.value) {
      labels.push(`source: ${jobProviderFilter.value}`);
    }
    if (jobRemoteFilter?.checked) {
      labels.push("remote only");
    }
    return labels;
  }

  function applyJobFilters() {
    const cards = Array.from(jobsGrid.querySelectorAll(".job-card"));
    const search = (jobSearch?.value || "").trim().toLowerCase();
    const company = jobCompanyFilter?.value || "";
    const location = jobLocationFilter?.value || "";
    const duration = jobDurationFilter?.value || "";
    const provider = jobProviderFilter?.value || "";
    const remoteOnly = Boolean(jobRemoteFilter?.checked);

    let visibleCount = 0;
    cards.forEach((card) => {
      const matchesSearch = !search || String(card.dataset.search || "").includes(search);
      const matchesCompany = !company || card.dataset.company === company;
      const matchesLocation = !location || card.dataset.location === location;
      const matchesDuration = !duration || card.dataset.duration === duration;
      const matchesProvider = !provider || card.dataset.provider === provider;
      const matchesRemote = !remoteOnly || String(card.dataset.remote || "").toLowerCase() === "true";
      const visible = matchesSearch && matchesCompany && matchesLocation && matchesDuration && matchesProvider && matchesRemote;
      card.classList.toggle("hidden", !visible);
      if (visible) {
        visibleCount += 1;
      }
    });

    if (jobsCount) {
      jobsCount.textContent = `${visibleCount} role${visibleCount === 1 ? "" : "s"} shown`;
    }
    if (jobsEmpty) {
      jobsEmpty.hidden = visibleCount !== 0;
    }
    if (activeFilters) {
      const labels = describeActiveFilters();
      activeFilters.textContent = labels.length > 0 ? `${labels.length} active filter${labels.length === 1 ? "" : "s"}: ${labels.join(" | ")}` : "No active filters";
    }

    writeState({
      jobSearch: jobSearch?.value || "",
      jobCompany: company,
      jobLocation: location,
      jobDuration: duration,
      jobProvider: provider,
      jobRemoteOnly: remoteOnly,
    });
  }

  jobSearch?.addEventListener("input", applyJobFilters);
  jobCompanyFilter?.addEventListener("change", applyJobFilters);
  jobLocationFilter?.addEventListener("change", applyJobFilters);
  jobDurationFilter?.addEventListener("change", applyJobFilters);
  jobProviderFilter?.addEventListener("change", applyJobFilters);
  jobRemoteFilter?.addEventListener("change", applyJobFilters);

  jobFilterReset?.addEventListener("click", () => {
    if (jobSearch) {
      jobSearch.value = "";
    }
    if (jobCompanyFilter) {
      jobCompanyFilter.value = "";
    }
    if (jobLocationFilter) {
      jobLocationFilter.value = "";
    }
    if (jobDurationFilter) {
      jobDurationFilter.value = "";
    }
    if (jobProviderFilter) {
      jobProviderFilter.value = "";
    }
    if (jobRemoteFilter) {
      jobRemoteFilter.checked = false;
    }
    applyJobFilters();
  });

  jobsGrid.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.classList.contains("use-job")) {
      return;
    }
    const card = target.closest(".job-card");
    if (!card) {
      return;
    }
    writeState({
      pendingReviewJob: {
        url: card.dataset.jobUrl || "",
        description: card.dataset.jobDescription || "",
      },
    });
    window.location.href = "/review";
  });

  applyJobFilters();
}

function setupReviewPage() {
  const reviewForm = document.getElementById("review-form");
  const sets = document.getElementById("sets");
  const template = document.getElementById("application-set-template");
  if (!reviewForm || !sets || !(template instanceof HTMLTemplateElement)) {
    return;
  }

  const pageUser = parseJsonNode("page-user", {});
  const reviewData = parseJsonNode("review-data", []);
  const historyChartData = parseJsonNode("page-history-chart", []);
  const workspacePanel = document.getElementById("workspace-panel");
  const workspaceTabs = Array.from(document.querySelectorAll("[data-tab-trigger]"));
  const workspaceViews = Array.from(document.querySelectorAll("[data-tab-panel]"));
  const resultSwitches = Array.from(document.querySelectorAll("[data-result-target]"));
  const resultCards = Array.from(document.querySelectorAll(".result-card"));
  const jumpResultsButtons = Array.from(document.querySelectorAll("[data-open-tab]"));
  const chatbotForm = document.getElementById("chatbot-form");
  const chatbotMessages = document.getElementById("chatbot-messages");
  const chatbotApplication = document.getElementById("chatbot-application");
  const chatbotQuestion = document.getElementById("chatbot-question");
  const historyChart = document.getElementById("history-chart");
  const revisionViewer = document.getElementById("revision-viewer");
  const addButtons = Array.from(document.querySelectorAll("#add-set, #add-set-bottom"));
  const hasFeedback = reviewForm.dataset.hasFeedback === "true";
  const currentAuthStatus = authStatus();

  function readSetValue(container, selector) {
    const field = container.querySelector(selector);
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      return field.value;
    }
    return "";
  }

  function getActiveSet() {
    return document.querySelector(".set.active") || sets.querySelector(".set");
  }

  function setActiveSet(container) {
    Array.from(sets.querySelectorAll(".set")).forEach((set) => set.classList.remove("active"));
    if (container) {
      container.classList.add("active");
      writeState({ reviewActiveIndex: Number(container.dataset.index || "1") });
    }
  }

  function updateButtons() {
    const allSets = Array.from(sets.querySelectorAll(".set"));
    allSets.forEach((set, index) => {
      const removeButton = set.querySelector(".remove-set");
      if (removeButton instanceof HTMLButtonElement) {
        removeButton.disabled = index === 0 && allSets.length === 1;
      }
    });
  }

  function updateSetHeader(set, index) {
    set.dataset.index = String(index);
    const eyebrow = set.querySelector(".eyebrow");
    if (eyebrow) {
      eyebrow.textContent = `Application ${index}`;
    }
  }

  function renumberSets() {
    Array.from(sets.querySelectorAll(".set")).forEach((set, index) => updateSetHeader(set, index + 1));
  }

  function getSetState(container) {
    return {
      job_url: readSetValue(container, 'input[name="job_url"]'),
      job: readSetValue(container, 'textarea[name="job"]'),
      cv_text: readSetValue(container, 'textarea[name="cv_text"]'),
      cover_text: readSetValue(container, 'textarea[name="cover_text"]'),
      cv_draft_id: readSetValue(container, 'input[name="cv_draft_id"]'),
      cover_draft_id: readSetValue(container, 'input[name="cover_draft_id"]'),
      cv_draft_title: readSetValue(container, 'input[name="cv_draft_title"]'),
      cover_draft_title: readSetValue(container, 'input[name="cover_draft_title"]'),
      cv_file_name: container.querySelector('input[name="cv_file"]')?.getAttribute("data-loaded-name") || "",
      cover_letter_file_name: container.querySelector('input[name="cover_letter_file"]')?.getAttribute("data-loaded-name") || "",
    };
  }

  function persistReviewState() {
    const draftSets = Array.from(sets.querySelectorAll(".set")).map((set) => getSetState(set));
    const activeSet = getActiveSet();
    writeState({
      reviewDraftSets: draftSets,
      reviewActiveIndex: activeSet ? Number(activeSet.dataset.index || "1") : 1,
    });
  }

  function setFieldValue(container, selector, value) {
    const field = container.querySelector(selector);
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      field.value = value || "";
    }
  }

  function updateFileHint(container, inputName, message) {
    const input = container.querySelector(`input[name="${inputName}"]`);
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    const label = input.closest("label");
    const hint = label?.querySelector(".file-hint");
    if (hint) {
      hint.textContent = message;
    }
  }

  function setDraftStatus(container, kind, message, tone = "warning") {
    const status = container.querySelector(`[data-draft-status="${kind}"]`);
    if (!(status instanceof HTMLElement)) {
      return;
    }
    if (!message) {
      status.hidden = true;
      status.textContent = "";
      status.classList.remove("is-warning", "is-success");
      return;
    }
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle("is-warning", tone === "warning");
    status.classList.toggle("is-success", tone === "success");
  }

  function applyDocumentDraft(container, kind, draft) {
    const isCv = kind === "cv";
    const draftIdSelector = isCv ? 'input[name="cv_draft_id"]' : 'input[name="cover_draft_id"]';
    const titleSelector = isCv ? 'input[name="cv_draft_title"]' : 'input[name="cover_draft_title"]';
    const textSelector = isCv ? 'textarea[name="cv_text"]' : 'textarea[name="cover_text"]';
    const fileInputName = isCv ? "cv_file" : "cover_letter_file";

    setFieldValue(container, draftIdSelector, String(draft.id || ""));
    setFieldValue(container, titleSelector, draft.title || "");
    setFieldValue(container, textSelector, draft.content || "");

    const fileInput = container.querySelector(`input[name="${fileInputName}"]`);
    if (fileInput instanceof HTMLInputElement) {
      fileInput.value = "";
      fileInput.setAttribute("data-loaded-name", draft.title || "");
    }

    updateFileHint(container, fileInputName, `Loaded saved draft: ${draft.title || "Draft"}`);
    setDraftStatus(container, kind, "");
    persistReviewState();
  }

  function createSet(initialData = {}) {
    const index = sets.querySelectorAll(".set").length + 1;
    const fragment = template.content.cloneNode(true);
    const wrapper = document.createElement("div");
    wrapper.appendChild(fragment);
    const set = wrapper.querySelector(".set");
    if (!set) {
      throw new Error("Missing set template.");
    }

    updateSetHeader(set, index);
    setFieldValue(set, 'input[name="job_url"]', initialData.job_url || "");
    setFieldValue(set, 'textarea[name="job"]', initialData.job || "");
    setFieldValue(set, 'textarea[name="cv_text"]', initialData.cv_text || "");
    setFieldValue(set, 'textarea[name="cover_text"]', initialData.cover_text || "");
    setFieldValue(set, 'input[name="cv_draft_id"]', initialData.cv_draft_id || "");
    setFieldValue(set, 'input[name="cover_draft_id"]', initialData.cover_draft_id || "");
    setFieldValue(set, 'input[name="cv_draft_title"]', initialData.cv_draft_title || "Main CV");
    setFieldValue(set, 'input[name="cover_draft_title"]', initialData.cover_draft_title || "Main Cover Letter");

    const cvInput = set.querySelector('input[name="cv_file"]');
    if (cvInput instanceof HTMLInputElement && initialData.cv_file_name) {
      cvInput.setAttribute("data-loaded-name", initialData.cv_file_name);
      updateFileHint(set, "cv_file", `Loaded draft: ${initialData.cv_file_name}`);
    }

    const coverInput = set.querySelector('input[name="cover_letter_file"]');
    if (coverInput instanceof HTMLInputElement && initialData.cover_letter_file_name) {
      coverInput.setAttribute("data-loaded-name", initialData.cover_letter_file_name);
      updateFileHint(set, "cover_letter_file", `Loaded draft: ${initialData.cover_letter_file_name}`);
    }

    return set;
  }

  function resetSet(container) {
    [
      'input[name="job_url"]',
      'textarea[name="job"]',
      'textarea[name="cv_text"]',
      'textarea[name="cover_text"]',
      'input[name="cv_draft_id"]',
      'input[name="cover_draft_id"]',
    ].forEach((selector) => setFieldValue(container, selector, ""));

    setFieldValue(container, 'input[name="cv_draft_title"]', "Main CV");
    setFieldValue(container, 'input[name="cover_draft_title"]', "Main Cover Letter");

    ["cv_file", "cover_letter_file"].forEach((name) => {
      const input = container.querySelector(`input[name="${name}"]`);
      if (input instanceof HTMLInputElement) {
        input.value = "";
        input.setAttribute("data-loaded-name", "");
      }
      updateFileHint(
        container,
        name,
        name === "cv_file"
          ? "Upload .txt, .pdf, or .docx. The extracted text stays editable below."
          : "Upload .txt, .pdf, or .docx. The extracted text stays editable below."
      );
    });
    persistReviewState();
  }

  function isPristineSet(container) {
    const state = getSetState(container);
    return !state.job_url && !state.job && !state.cv_text && !state.cover_text;
  }

  function applyStoredReviewState() {
    if (hasFeedback) {
      return;
    }

    const stored = readState();
    if (!Array.isArray(stored.reviewDraftSets) || stored.reviewDraftSets.length === 0) {
      return;
    }

    const existingSets = Array.from(sets.querySelectorAll(".set"));
    if (existingSets.length !== 1 || !isPristineSet(existingSets[0])) {
      return;
    }

    sets.innerHTML = "";
    stored.reviewDraftSets.forEach((draftSet) => {
      sets.appendChild(createSet(draftSet));
    });
    const targetIndex = Number(stored.reviewActiveIndex || "1");
    const targetSet = Array.from(sets.querySelectorAll(".set")).find((set) => Number(set.dataset.index || "1") === targetIndex);
    setActiveSet(targetSet || sets.querySelector(".set"));
    updateButtons();
  }

  function consumePendingJob() {
    const stored = readState();
    const pendingJob = stored.pendingReviewJob;
    if (!pendingJob) {
      return;
    }

    const targetSet = getActiveSet();
    if (!targetSet) {
      return;
    }

    const urlInput = targetSet.querySelector('input[name="job_url"]');
    const jobTextarea = targetSet.querySelector('textarea[name="job"]');
    if (urlInput instanceof HTMLInputElement) {
      urlInput.value = pendingJob.url || "";
    }
    if (jobTextarea instanceof HTMLTextAreaElement) {
      jobTextarea.value = pendingJob.description || "";
    }

    const nextState = readState();
    writeState({ ...nextState, pendingReviewJob: null });
    setActiveSet(targetSet);
    targetSet.scrollIntoView({ behavior: "smooth", block: "nearest" });
    persistReviewState();
  }

  function activateWorkspaceTab(tabName) {
    workspaceTabs.forEach((button) => {
      const active = button.dataset.tabTrigger === tabName;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    workspaceViews.forEach((panel) => {
      panel.hidden = panel.dataset.tabPanel !== tabName;
    });
    writeState({ reviewWorkspaceTab: tabName });
  }

  function activateResultCard(index) {
    resultSwitches.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.resultTarget === String(index));
    });
    resultCards.forEach((card) => {
      card.classList.toggle("hidden", card.dataset.application !== String(index));
    });
    if (chatbotApplication) {
      chatbotApplication.value = String(index);
    }
    const selectedResult = reviewData.find((entry) => entry.index === Number(index));
    writeState({
      reviewSelectedResult: String(index),
      interviewPrepApplication: selectedResult || readState().interviewPrepApplication || null,
    });
  }

  function buildFallbackAssistantReply(result, question) {
    const lower = question.toLowerCase();
    const weakCategories = (result.categories || []).filter((category) => category.coverage < 60);
    const firstCvIssue = (result.tailored_advice || []).find((item) => item.source === "cv");
    const firstCoverIssue = (result.tailored_advice || []).find((item) => item.source === "cover_letter");
    const firstSuggestion = (result.role_suggestions || [])[0];

    if (lower.includes("role") || lower.includes("job")) {
      if (firstSuggestion) {
        return `${firstSuggestion.title} at ${firstSuggestion.company} is the closest current role for this CV. Strong overlap includes ${describeList(firstSuggestion.matched_keywords)}.`;
      }
      return "There is not enough CV evidence yet to suggest a stronger role match.";
    }
    if (lower.includes("first") || lower.includes("priority") || lower.includes("start")) {
      if (weakCategories.length > 0) {
        return `Start with ${weakCategories[0].label.toLowerCase()}. Missing evidence there includes ${describeList(weakCategories[0].missing_keywords)}.`;
      }
      if (firstCvIssue) {
        return `Start with this CV change first: ${firstCvIssue.suggestion}`;
      }
    }
    if (lower.includes("cover")) {
      if (firstCoverIssue) {
        return `The cover letter change to make first is: ${firstCoverIssue.suggestion}`;
      }
      return "The cover letter is mainly being scored on tailoring, clarity, and proof of impact.";
    }
    if (lower.includes("cv")) {
      if (firstCvIssue) {
        return `The CV change to make first is: ${firstCvIssue.suggestion}`;
      }
      return `Your CV should show stronger evidence for ${describeList(result.missing_keywords)} with measurable outcomes.`;
    }
    if (lower.includes("score") || lower.includes("low") || lower.includes("why")) {
      const weak = weakCategories.map((category) => `${category.label} (${category.coverage}%)`);
      return `Your score is being pulled down most by ${weak.slice(0, 3).join(", ") || "tailoring and evidence"}. Missing requirements include ${describeList(result.missing_keywords)}.`;
    }
    if (lower.includes("keyword") || lower.includes("requirement")) {
      return `The main missing requirements are ${describeList(result.missing_keywords)}. The strongest matched terms are ${describeList(result.keyword_overlap)}.`;
    }
    return `Focus on ${describeList(result.missing_keywords)}, the next improvements list, and the tailored advice cards that quote your wording.`;
  }

  async function fetchAssistantReply(result, question) {
    const response = await fetch("/api/review-assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application: result, question }),
    });
    if (!response.ok) {
      throw new Error("Assistant reply failed.");
    }
    const payload = await response.json();
    return String(payload.answer || "").trim();
  }

  function addChatMessage(role, text) {
    if (!chatbotMessages) {
      return;
    }
    const message = document.createElement("div");
    message.className = `chat-message ${role}`;
    message.textContent = text;
    chatbotMessages.appendChild(message);
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
  }

  async function extractUpload(target) {
    if (!(target instanceof HTMLInputElement) || !target.files || target.files.length === 0) {
      return;
    }

    const file = target.files[0];
    const set = target.closest(".set");
    if (!set) {
      return;
    }

    const isCv = target.name === "cv_file";
    const textareaSelector = isCv ? 'textarea[name="cv_text"]' : 'textarea[name="cover_text"]';
    const formData = new FormData();
    formData.append("file", file);
    updateFileHint(set, target.name, `Extracting text from ${file.name}...`);

    try {
      const response = await fetch("/api/extract-upload", { method: "POST", body: formData });
      if (!response.ok) {
        throw new Error("Upload extraction failed.");
      }
      const payload = await response.json();
      setFieldValue(set, textareaSelector, payload.text || "");
      target.setAttribute("data-loaded-name", payload.filename || file.name);
      updateFileHint(set, target.name, `Loaded from upload: ${payload.filename || file.name}`);
      persistReviewState();
    } catch (error) {
      updateFileHint(set, target.name, error instanceof Error ? error.message : "Upload extraction failed.");
    }
  }

  function upsertDraftCard(kind, draft) {
    const list = document.querySelector(`[data-draft-list="${kind}"]`);
    if (!list) {
      return;
    }
    const empty = list.querySelector(".sidebar-empty");
    if (empty) {
      empty.remove();
    }

    let card = list.querySelector(`[data-draft-id="${draft.id}"]`);
    if (!card) {
      card = document.createElement("article");
      card.className = "saved-draft";
      card.dataset.kind = kind;
      card.dataset.draftId = String(draft.id);
      card.innerHTML = `
        <div>
          <strong></strong>
          <span></span>
        </div>
        <div class="saved-draft-actions">
          <button type="button" class="ghost view-revisions" data-kind="${kind}" data-draft-id="${draft.id}">History</button>
          <button type="button" class="secondary load-draft" data-kind="${kind}" data-draft-id="${draft.id}">Use draft</button>
        </div>
      `;
      list.prepend(card);
    }

    card.dataset.draftTitle = draft.title || "";
    card.dataset.draftContent = draft.content || "";
    const strong = card.querySelector("strong");
    const span = card.querySelector("span");
    if (strong) {
      strong.textContent = draft.title || "Untitled draft";
    }
    if (span) {
      span.textContent = `Updated ${draft.updated_at || "just now"}`;
    }
  }

  async function saveDraft(button) {
    const kind = button.dataset.kind || "";
    const set = button.closest(".set");
    if (!set || (kind !== "cv" && kind !== "cover_letter")) {
      return;
    }

    const isCv = kind === "cv";
    const titleSelector = isCv ? 'input[name="cv_draft_title"]' : 'input[name="cover_draft_title"]';
    const textSelector = isCv ? 'textarea[name="cv_text"]' : 'textarea[name="cover_text"]';
    const idSelector = isCv ? 'input[name="cv_draft_id"]' : 'input[name="cover_draft_id"]';
    const title = readSetValue(set, titleSelector).trim();
    const content = readSetValue(set, textSelector).trim();
    const draftId = readSetValue(set, idSelector).trim();

    if (!content) {
      setDraftStatus(set, kind, "Add document text before saving this draft.", "warning");
      button.textContent = "Add text first";
      window.setTimeout(() => {
        button.textContent = kind === "cv" ? "Save CV draft" : "Save cover draft";
      }, 1400);
      return;
    }

    button.disabled = true;
    const originalLabel = button.textContent;
    button.textContent = "Saving...";

    try {
      const response = await fetch("/api/drafts/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, title, content, draft_id: draftId || null }),
      });
      if (response.status === 401) {
        persistReviewState();
        setDraftStatus(
          set,
          kind,
          "Sign in with Google to save drafts. Your current text is still available in the editor.",
          "warning"
        );
        button.textContent = "Sign in to save";
        return;
      }
      if (!response.ok) {
        throw new Error("Draft save failed.");
      }
      const saved = await response.json();
      setFieldValue(set, idSelector, String(saved.id || ""));
      setFieldValue(set, titleSelector, saved.title || title);
      upsertDraftCard(kind, saved);
      setDraftStatus(set, kind, "Draft saved.", "success");
      button.textContent = "Saved";
      persistReviewState();
    } catch (error) {
      setDraftStatus(set, kind, error instanceof Error ? error.message : "Draft save failed.", "warning");
      button.textContent = error instanceof Error ? error.message : "Draft save failed";
    } finally {
      window.setTimeout(() => {
        button.disabled = false;
        button.textContent = originalLabel;
      }, 1400);
    }
  }

  function renderHistoryChart() {
    if (!historyChart || !Array.isArray(historyChartData) || historyChartData.length === 0) {
      return;
    }

    const width = 320;
    const height = 150;
    const padding = 18;
    const minScore = Math.min(...historyChartData.map((item) => Number(item.score)));
    const maxScore = Math.max(...historyChartData.map((item) => Number(item.score)));
    const range = Math.max(maxScore - minScore, 10);

    const points = historyChartData.map((item, index) => {
      const x = padding + (index * (width - padding * 2)) / Math.max(historyChartData.length - 1, 1);
      const y = height - padding - ((Number(item.score) - minScore) * (height - padding * 2)) / range;
      return { ...item, x, y };
    });

    const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
    historyChart.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" class="history-chart-svg" role="img" aria-label="Review score trend">
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="history-axis"></line>
        <polyline points="${polyline}" class="history-line"></polyline>
        ${points
          .map(
            (point) => `
              <circle cx="${point.x}" cy="${point.y}" r="4" class="history-point"></circle>
              <text x="${point.x}" y="${point.y - 10}" text-anchor="middle" class="history-point-label">${point.score}</text>
            `
          )
          .join("")}
      </svg>
      <div class="history-chart-labels">
        <span>${escapeHtml(points[0]?.job_title || "First review")}</span>
        <span>${escapeHtml(points[points.length - 1]?.job_title || "Latest review")}</span>
      </div>
    `;
  }

  function renderRevisionViewer(payload) {
    if (!revisionViewer) {
      return;
    }

    const revisionOptions = (payload.revisions || [])
      .map(
        (revision) =>
          `<option value="${revision.id}" ${revision.id === payload.selected_revision?.id ? "selected" : ""}>${escapeHtml(revision.created_at)}</option>`
      )
      .join("");

    const diffBlocks = (payload.diff_blocks || [])
      .map(
        (block) =>
          `<div class="revision-line ${block.kind}"><span>${escapeHtml(block.text)}</span></div>`
      )
      .join("");

    revisionViewer.innerHTML = `
      <div class="revision-head">
        <div>
          <strong>${escapeHtml(payload.draft.title)}</strong>
          <span>${escapeHtml(payload.draft.kind === "cv" ? "CV draft history" : "Cover letter draft history")}</span>
        </div>
        <label class="revision-select-label">
          <span>Revision</span>
          <select id="revision-select" data-draft-id="${payload.draft.id}">
            ${revisionOptions}
          </select>
        </label>
      </div>
      <div class="revision-summary">
        <span class="revision-chip added">+${payload.summary?.added || 0} added</span>
        <span class="revision-chip removed">-${payload.summary?.removed || 0} removed</span>
        <span class="revision-chip same">${payload.summary?.unchanged || 0} unchanged</span>
      </div>
      <div class="revision-compare-note">
        ${payload.previous_revision ? `Comparing against ${escapeHtml(payload.previous_revision.created_at)}` : "This is the first saved revision for this draft."}
      </div>
      <div class="revision-lines">${diffBlocks || '<div class="revision-line same"><span>No textual changes to compare yet.</span></div>'}</div>
    `;
  }

  async function loadRevisionHistory(draftId, revisionId = "") {
    if (!revisionViewer) {
      return;
    }

    revisionViewer.innerHTML = `<p class="sidebar-empty">Loading revision history...</p>`;
    const suffix = revisionId ? `?revision_id=${encodeURIComponent(revisionId)}` : "";

    try {
      const response = await fetch(`/api/drafts/${draftId}/revisions${suffix}`);
      if (response.status === 401) {
        const authButton = document.querySelector('.site-auth a[href^="/auth/login/google"]');
        if (authButton instanceof HTMLAnchorElement) {
          window.location.href = authButton.href;
          return;
        }
        throw new Error("Sign in required.");
      }
      if (!response.ok) {
        throw new Error("Could not load revisions.");
      }
      const payload = await response.json();
      renderRevisionViewer(payload);
    } catch (error) {
      revisionViewer.innerHTML = `<p class="sidebar-empty">${escapeHtml(error instanceof Error ? error.message : "Could not load revisions.")}</p>`;
    }
  }

  async function saveOutcomeStatus(select) {
    const reviewId = select.dataset.reviewId || "";
    if (!reviewId) {
      return;
    }

    select.disabled = true;
    select.classList.remove("is-saved");
    select.classList.add("is-saving");

    try {
      const response = await fetch(`/api/review-runs/${encodeURIComponent(reviewId)}/outcome`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome_status: select.value }),
      });
      if (!response.ok) {
        throw new Error("Outcome update failed.");
      }
      select.classList.remove("is-saving");
      select.classList.add("is-saved");
      window.setTimeout(() => select.classList.remove("is-saved"), 1200);
    } catch (error) {
      select.classList.remove("is-saving");
      window.alert(error instanceof Error ? error.message : "Outcome update failed.");
    } finally {
      select.disabled = false;
    }
  }

  addButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const set = createSet();
      sets.appendChild(set);
      renumberSets();
      setActiveSet(set);
      updateButtons();
      persistReviewState();
      set.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  });

  sets.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const set = target.closest(".set");
    if (set) {
      setActiveSet(set);
    }

    if (target.classList.contains("remove-set")) {
      const allSets = Array.from(sets.querySelectorAll(".set"));
      if (allSets.length === 1) {
        return;
      }
      set?.remove();
      renumberSets();
      setActiveSet(sets.querySelector(".set"));
      updateButtons();
      persistReviewState();
      return;
    }

    if (target.classList.contains("reset-set") && set) {
      resetSet(set);
      return;
    }

    if (target.classList.contains("save-draft") && target instanceof HTMLButtonElement) {
      void saveDraft(target);
    }
  });

  sets.addEventListener("focusin", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const set = target.closest(".set");
    if (set) {
      setActiveSet(set);
    }
  });

  sets.addEventListener("input", () => {
    persistReviewState();
  });

  sets.addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && target.type === "file") {
      void extractUpload(target);
    }
    persistReviewState();
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const interviewLink = target.closest(".open-interview-prep");
    if (interviewLink instanceof HTMLAnchorElement) {
      const applicationIndex = Number(interviewLink.dataset.applicationIndex || "0");
      const result = reviewData.find((entry) => entry.index === applicationIndex);
      if (result) {
        writeState({ interviewPrepApplication: result });
      }
      event.preventDefault();
      window.location.href = interviewLink.href;
      return;
    }

    if (target.classList.contains("load-draft")) {
      const kind = target.dataset.kind || "";
      const card = target.closest(".saved-draft");
      const activeSet = getActiveSet();
      if (!card || !activeSet) {
        return;
      }
      applyDocumentDraft(activeSet, kind, {
        id: card.dataset.draftId || "",
        title: card.dataset.draftTitle || "",
        content: card.dataset.draftContent || "",
      });
      activeSet.scrollIntoView({ behavior: "smooth", block: "nearest" });
      activateWorkspaceTab("reviewer");
    }

    if (target.classList.contains("view-revisions")) {
      const draftId = target.dataset.draftId || "";
      if (draftId) {
        void loadRevisionHistory(draftId);
      }
    }

    if (target.classList.contains("use-suggestion")) {
      const activeSet = getActiveSet();
      if (!activeSet) {
        return;
      }
      setFieldValue(activeSet, 'input[name="job_url"]', target.dataset.jobUrl || "");
      setFieldValue(activeSet, 'textarea[name="job"]', target.dataset.jobDescription || "");
      activateWorkspaceTab("reviewer");
      activeSet.scrollIntoView({ behavior: "smooth", block: "nearest" });
      persistReviewState();
    }

  });

  workspaceTabs.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) {
        return;
      }
      activateWorkspaceTab(button.dataset.tabTrigger || "reviewer");
    });
  });

  jumpResultsButtons.forEach((button) => {
    button.addEventListener("click", () => activateWorkspaceTab(button.dataset.openTab || "results"));
  });

  resultSwitches.forEach((button) => {
    button.addEventListener("click", () => activateResultCard(button.dataset.resultTarget || "1"));
  });

  chatbotApplication?.addEventListener("change", () => {
    activateResultCard(chatbotApplication.value);
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) {
      return;
    }

    if (target.id === "revision-select") {
      const draftId = target.dataset.draftId || "";
      const revisionId = target.value || "";
      if (draftId) {
        void loadRevisionHistory(draftId, revisionId);
      }
      return;
    }

    if (target.classList.contains("history-outcome")) {
      void saveOutcomeStatus(target);
    }
  });

  if (chatbotForm && chatbotQuestion) {
    chatbotForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = chatbotQuestion.value.trim();
      if (!question) {
        return;
      }
      const applicationId = Number(chatbotApplication?.value || "1");
      const result = reviewData.find((entry) => entry.index === applicationId);
      addChatMessage("user", question);
      if (!result) {
        addChatMessage("bot", "I could not find review data for that application.");
        chatbotQuestion.value = "";
        return;
      }
      addChatMessage("bot", "Thinking through your CV, cover letter, and the role...");
      try {
        const reply = await fetchAssistantReply(result, question);
        const messages = chatbotMessages?.querySelectorAll(".chat-message.bot");
        const placeholder = messages && messages.length > 0 ? messages[messages.length - 1] : null;
        if (placeholder) {
          placeholder.textContent = reply || buildFallbackAssistantReply(result, question);
        } else {
          addChatMessage("bot", reply || buildFallbackAssistantReply(result, question));
        }
      } catch (error) {
        const fallback = buildFallbackAssistantReply(result, question);
        const messages = chatbotMessages?.querySelectorAll(".chat-message.bot");
        const placeholder = messages && messages.length > 0 ? messages[messages.length - 1] : null;
        if (placeholder && placeholder.textContent === "Thinking through your CV, cover letter, and the role...") {
          placeholder.textContent = fallback;
        } else {
          addChatMessage("bot", fallback);
        }
      }
      chatbotQuestion.value = "";
    });
  }

  if (workspacePanel) {
    const stored = readState();
    const serverPreferredTab = workspacePanel.dataset.initialTab || "reviewer";
    const initialTab = serverPreferredTab === "results" ? "results" : stored.reviewWorkspaceTab || serverPreferredTab;
    activateWorkspaceTab(initialTab);
  }

  if (resultSwitches.length > 0) {
    activateResultCard(readState().reviewSelectedResult || resultSwitches[0].dataset.resultTarget || "1");
  }

  applyStoredReviewState();
  setActiveSet(sets.querySelector(`.set[data-index="${readState().reviewActiveIndex || 1}"]`) || sets.querySelector(".set"));
  updateButtons();
  consumePendingJob();
  renderHistoryChart();

  if (!pageUser.id) {
    document.querySelectorAll(".save-draft").forEach((button) => {
      const title = currentAuthStatus.enabled
        ? "Sign in with Google to save drafts."
        : "Google login is not configured yet for this environment.";
      button.setAttribute("title", title);
    });
  }
}

function setupInterviewPrepPage() {
  const emptyState = document.getElementById("prep-empty");
  const loadingState = document.getElementById("prep-loading");
  const content = document.getElementById("prep-content");
  const sourcesList = document.getElementById("prep-sources-list");
  const roleTitle = document.getElementById("prep-role-title");
  const summary = document.getElementById("prep-summary");
  const metaChips = document.getElementById("prep-meta-chips");
  const priorities = document.getElementById("prep-priorities");
  const stageGrid = document.getElementById("prep-stage-grid");
  const signalGrid = document.getElementById("prep-signal-grid");
  const questionGroups = document.getElementById("prep-question-groups");
  const askList = document.getElementById("prep-ask-list");
  const statMode = document.getElementById("prep-stat-mode");
  const statCompany = document.getElementById("prep-stat-company");
  const statStages = document.getElementById("prep-stat-stages");
  const statQuestions = document.getElementById("prep-stat-questions");

  if (!emptyState || !loadingState || !content || !sourcesList || !roleTitle || !summary || !metaChips || !priorities || !stageGrid || !signalGrid || !questionGroups || !askList || !statMode || !statCompany || !statStages || !statQuestions) {
    return;
  }

  const stored = readState();
  const application = stored.interviewPrepApplication;
  if (!application || typeof application !== "object") {
    emptyState.hidden = false;
    loadingState.hidden = true;
    content.hidden = true;
    return;
  }

  function renderSources(items) {
    if (!Array.isArray(items) || items.length === 0) {
      sourcesList.innerHTML = '<p class="sidebar-empty">No public sources were captured for this pass.</p>';
      return;
    }
    sourcesList.innerHTML = items
      .map(
        (item) => `
          <article class="prep-source-card">
            <span class="prep-source-type">${escapeHtml(String(item.source_type || "").replaceAll("_", " "))}</span>
            <strong>${escapeHtml(item.title || "Source")}</strong>
            <p>${escapeHtml(item.domain || "")}</p>
            <a href="${escapeHtml(item.url || "#")}" target="_blank" rel="noopener noreferrer">Open source</a>
          </article>
        `
      )
      .join("");
  }

  function renderQuestionGroups(groups) {
    questionGroups.innerHTML = (Array.isArray(groups) ? groups : [])
      .map(
        (group) => `
          <article class="prep-question-group-card">
            <div class="section-heading">
              <div>
                <p class="eyebrow">${escapeHtml(group.title || "Question set")}</p>
                <h3>${escapeHtml(group.description || "")}</h3>
              </div>
            </div>
            <div class="prep-question-list">
              ${(Array.isArray(group.questions) ? group.questions : [])
                .map(
                  (question) => `
                    <article class="prep-question-card">
                      <strong>${escapeHtml(question.question || "")}</strong>
                      <p>${escapeHtml(question.why || "")}</p>
                      <span>${escapeHtml(question.anchor || "")}</span>
                    </article>
                  `
                )
                .join("")}
            </div>
          </article>
        `
      )
      .join("");
  }

  async function loadPrep() {
    emptyState.hidden = true;
    loadingState.hidden = false;
    content.hidden = true;

    try {
      const response = await fetch("/api/interview-prep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application }),
      });
      if (!response.ok) {
        throw new Error("Interview prep research failed.");
      }
      const prep = await response.json();
      const groups = Array.isArray(prep.question_groups) ? prep.question_groups : [];
      const totalQuestions = groups.reduce((sum, group) => sum + ((Array.isArray(group.questions) ? group.questions.length : 0)), 0);
      const prepCompany = String(prep.company || "Target company");
      const prepRoleTitle = String(prep.role_title || "Selected role");
      const displayTitle = prepRoleTitle.toLowerCase().includes(prepCompany.toLowerCase())
        ? prepRoleTitle
        : `${prepRoleTitle} at ${prepCompany}`;

      roleTitle.textContent = displayTitle;
      summary.textContent = prep.summary || "";
      metaChips.innerHTML = `
        <span>${escapeHtml(prep.research_mode || "fallback")} research</span>
        <span>${escapeHtml(prep.research_confidence || "Low")} confidence</span>
        <span>${escapeHtml(String((prep.sources || []).length))} sources</span>
      `;
      priorities.innerHTML = (prep.prep_priorities || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      stageGrid.innerHTML = (prep.process_stages || [])
        .map(
          (stage) => `
            <article class="prep-stage-card">
              <div class="prep-stage-head">
                <strong>${escapeHtml(stage.name || "")}</strong>
                <span>${escapeHtml(stage.confidence || "")}</span>
              </div>
              <p>${escapeHtml(stage.detail || "")}</p>
              <a href="${escapeHtml(stage.source_url || "#")}" ${stage.source_url ? 'target="_blank" rel="noopener noreferrer"' : 'aria-disabled="true"'}>${escapeHtml(stage.source_title || "Role inference")}</a>
            </article>
          `
        )
        .join("");
      signalGrid.innerHTML = (prep.company_signals || [])
        .map(
          (signal) => `
            <article class="prep-signal-card">
              <strong>${escapeHtml(signal.title || "")}</strong>
              <p>${escapeHtml(signal.detail || "")}</p>
              <a href="${escapeHtml(signal.source_url || "#")}" ${signal.source_url ? 'target="_blank" rel="noopener noreferrer"' : 'aria-disabled="true"'}>${escapeHtml(signal.source_title || "Job advert")}</a>
            </article>
          `
        )
        .join("");
      renderQuestionGroups(groups);
      askList.innerHTML = (prep.questions_to_ask || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      renderSources(prep.sources || []);

      statMode.textContent = String(prep.research_mode || "fallback").replaceAll("_", " ");
      statCompany.textContent = prepCompany;
      statStages.textContent = String((prep.process_stages || []).length);
      statQuestions.textContent = String(totalQuestions);

      loadingState.hidden = true;
      content.hidden = false;
    } catch (error) {
      loadingState.hidden = true;
      emptyState.hidden = false;
      content.hidden = true;
      emptyState.innerHTML = `
        <h3>Interview prep could not be loaded</h3>
        <p>${escapeHtml(error instanceof Error ? error.message : "The company research step failed.")}</p>
      `;
    }
  }

  void loadPrep();
}

if (page() === "jobs") {
  setupJobsPage();
}

if (page() === "review") {
  setupReviewPage();
}

if (page() === "interview-prep") {
  setupInterviewPrepPage();
}

