const STORAGE_KEY = "getmeajob.ui.v1";

const workspacePanel = document.getElementById("workspace-panel");
const workspaceTabs = Array.from(document.querySelectorAll("[data-tab-trigger]"));
const workspaceViews = Array.from(document.querySelectorAll("[data-tab-panel]"));
const jumpResultsButtons = Array.from(document.querySelectorAll("[data-open-tab]"));

const reviewForm = document.getElementById("review-form");
const sets = document.getElementById("sets");
const addButton = document.getElementById("add-set");

const reviewDataNode = document.getElementById("review-data");
const resultSwitches = Array.from(document.querySelectorAll("[data-result-target]"));
const resultCards = Array.from(document.querySelectorAll(".result-card"));

const chatbotForm = document.getElementById("chatbot-form");
const chatbotMessages = document.getElementById("chatbot-messages");
const chatbotApplication = document.getElementById("chatbot-application");
const chatbotQuestion = document.getElementById("chatbot-question");

const jobsGrid = document.getElementById("jobs-grid");
const jobSearch = document.getElementById("job-search");
const jobCompanyFilter = document.getElementById("job-company-filter");
const jobLocationFilter = document.getElementById("job-location-filter");
const jobDurationFilter = document.getElementById("job-duration-filter");
const jobProviderFilter = document.getElementById("job-provider-filter");
const jobRemoteFilter = document.getElementById("job-remote-filter");
const jobFilterReset = document.getElementById("job-filter-reset");
const activeFilters = document.getElementById("active-filters");
const jobsCount = document.getElementById("jobs-count");
const jobsEmpty = document.getElementById("jobs-empty");

function readStoredState() {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function writeStoredState(nextState) {
  try {
    const current = readStoredState();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...nextState }));
  } catch {
    // Ignore storage failures.
  }
}

function clearDraftState() {
  try {
    const current = readStoredState();
    delete current.draftSets;
    delete current.activeSetIndex;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Ignore storage failures.
  }
}

function getSetState(container) {
  const readValue = (selector) => {
    const field = container.querySelector(selector);
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      return field.value;
    }
    return "";
  };

  return {
    job_url: readValue('input[name="job_url"]'),
    job: readValue('textarea[name="job"]'),
    cv_cached_text: readValue('input[name="cv_cached_text"]'),
    cover_cached_text: readValue('input[name="cover_cached_text"]'),
    cv_cached_name: readValue('input[name="cv_cached_name"]'),
    cover_cached_name: readValue('input[name="cover_cached_name"]'),
    cv_file_name: container.querySelector('input[name="cv_file"]')?.getAttribute("data-loaded-name") || "",
    cover_letter_file_name: container.querySelector('input[name="cover_letter_file"]')?.getAttribute("data-loaded-name") || "",
  };
}

function persistDraftState() {
  if (!sets) {
    return;
  }
  const draftSets = Array.from(sets.querySelectorAll(".set")).map((set) => getSetState(set));
  const activeSet = getActiveSet();
  writeStoredState({
    draftSets,
    activeSetIndex: activeSet ? Number(activeSet.dataset.index || "1") : 1,
  });
}

function activateWorkspaceTab(tabName) {
  if (!workspacePanel) {
    return;
  }

  workspaceTabs.forEach((button) => {
    const active = button.dataset.tabTrigger === tabName;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });

  workspaceViews.forEach((panel) => {
    const active = panel.dataset.tabPanel === tabName;
    panel.hidden = !active;
  });

  writeStoredState({ workspaceTab: tabName });
}

function activateResultCard(index) {
  resultSwitches.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.resultTarget === String(index));
  });

  resultCards.forEach((card) => {
    const active = card.dataset.application === String(index);
    card.classList.toggle("hidden", !active);
  });

  if (chatbotApplication) {
    chatbotApplication.value = String(index);
  }

  writeStoredState({ selectedResult: String(index) });
}

function getActiveSet() {
  return document.querySelector(".set.active") || document.querySelector(".set");
}

function setActiveSet(container) {
  const setsList = document.querySelectorAll(".set");
  setsList.forEach((set) => set.classList.remove("active"));
  if (container) {
    container.classList.add("active");
    writeStoredState({ activeSetIndex: Number(container.dataset.index || "1") });
  }
}

function updateButtons() {
  const removeButtons = document.querySelectorAll(".remove-set");
  removeButtons.forEach((button, index) => {
    button.disabled = index === 0;
  });
}

function createSet(index, initialData = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = "set";
  wrapper.dataset.index = String(index);
  wrapper.innerHTML = `
    <input type="hidden" name="cv_cached_text" value="${initialData.cv_cached_text || ""}" />
    <input type="hidden" name="cover_cached_text" value="${initialData.cover_cached_text || ""}" />
    <input type="hidden" name="cv_cached_name" value="${initialData.cv_cached_name || ""}" />
    <input type="hidden" name="cover_cached_name" value="${initialData.cover_cached_name || ""}" />
    <div class="set-header">
      <h3>Application ${index}</h3>
      <div class="set-controls">
        <button type="button" class="ghost reset-set">Reset</button>
        <button type="button" class="ghost remove-set">Remove</button>
      </div>
    </div>
    <label>
      Job advert URL
      <input type="url" name="job_url" placeholder="https://company.com/jobs/role" value="${initialData.job_url || ""}" />
    </label>
    <label>
      Job description
      <textarea name="job" rows="7" placeholder="Paste the job description here">${initialData.job || ""}</textarea>
    </label>
    <div class="upload-grid">
      <label>
        CV file
        <input type="file" name="cv_file" accept=".txt,.pdf,.docx" data-loaded-name="${initialData.cv_file_name || ""}" />
        ${initialData.cv_file_name ? `<span class="file-hint">Loaded and reusable: ${initialData.cv_file_name}</span>` : ""}
      </label>
      <label>
        Cover letter file
        <input type="file" name="cover_letter_file" accept=".txt,.pdf,.docx" data-loaded-name="${initialData.cover_letter_file_name || ""}" />
        ${initialData.cover_letter_file_name ? `<span class="file-hint">Loaded and reusable: ${initialData.cover_letter_file_name}</span>` : ""}
      </label>
    </div>
  `;
  return wrapper;
}

function renumberSets() {
  if (!sets) {
    return;
  }
  const remaining = sets.querySelectorAll(".set");
  remaining.forEach((set, idx) => {
    set.dataset.index = String(idx + 1);
    const title = set.querySelector("h3");
    if (title) {
      title.textContent = `Application ${idx + 1}`;
    }
  });
}

function resetSet(container) {
  const fields = [
    'input[name="job_url"]',
    'textarea[name="job"]',
    'input[name="cv_cached_text"]',
    'input[name="cover_cached_text"]',
    'input[name="cv_cached_name"]',
    'input[name="cover_cached_name"]',
  ];

  fields.forEach((selector) => {
    const field = container.querySelector(selector);
    if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      field.value = "";
    }
  });

  const fileInputs = container.querySelectorAll('input[type="file"]');
  fileInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.value = "";
      input.removeAttribute("data-loaded-name");
    }
  });

  const hints = container.querySelectorAll(".file-hint");
  hints.forEach((hint) => hint.remove());

  persistDraftState();
}

function applyDraftState() {
  const stored = readStoredState();
  if (!sets || !Array.isArray(stored.draftSets) || stored.draftSets.length === 0) {
    return;
  }

  const existingSets = sets.querySelectorAll(".set");
  const isPristine =
    existingSets.length === 1 &&
    !existingSets[0].querySelector('input[name="job_url"]')?.value &&
    !existingSets[0].querySelector('textarea[name="job"]')?.value &&
    !existingSets[0].querySelector('input[name="cv_cached_name"]')?.value &&
    !existingSets[0].querySelector('input[name="cover_cached_name"]')?.value;

  if (!isPristine) {
    return;
  }

  sets.innerHTML = "";
  stored.draftSets.forEach((draftSet, idx) => {
    sets.appendChild(createSet(idx + 1, draftSet));
  });

  const targetIndex = Number(stored.activeSetIndex || 1);
  const targetSet = Array.from(sets.querySelectorAll(".set")).find((set) => Number(set.dataset.index) === targetIndex);
  setActiveSet(targetSet || sets.querySelector(".set"));
  updateButtons();
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

function applyStoredUiState() {
  const stored = readStoredState();

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

  if (workspacePanel) {
    const serverPreferredTab = workspacePanel.dataset.initialTab || "reviewer";
    const initialTab = serverPreferredTab === "results" ? "results" : stored.workspaceTab || serverPreferredTab;
    activateWorkspaceTab(initialTab);
  }

  if (resultSwitches.length > 0) {
    const initialResult = stored.selectedResult || chatbotApplication?.value || resultSwitches[0].dataset.resultTarget || "1";
    activateResultCard(initialResult);
  }
}

function applyJobFilters() {
  if (!jobsGrid) {
    return;
  }

  const cards = jobsGrid.querySelectorAll(".job-card");
  const search = (jobSearch?.value || "").trim().toLowerCase();
  const company = jobCompanyFilter?.value || "";
  const location = jobLocationFilter?.value || "";
  const duration = jobDurationFilter?.value || "";
  const provider = jobProviderFilter?.value || "";
  const remoteOnly = jobRemoteFilter?.checked || false;

  let visibleCount = 0;
  cards.forEach((card) => {
    const matchesSearch = !search || card.dataset.search.includes(search);
    const matchesCompany = !company || card.dataset.company === company;
    const matchesLocation = !location || card.dataset.location === location;
    const matchesDuration = !duration || card.dataset.duration === duration;
    const matchesProvider = !provider || card.dataset.provider === provider;
    const matchesRemote = !remoteOnly || card.dataset.remote === "True" || card.dataset.remote === "true";
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
    activeFilters.textContent = labels.length > 0 ? `${labels.length} active filter${labels.length === 1 ? "" : "s"}: ${labels.join(" · ")}` : "No active filters";
  }

  writeStoredState({
    jobSearch: jobSearch?.value || "",
    jobCompany: company,
    jobLocation: location,
    jobDuration: duration,
    jobProvider: provider,
    jobRemoteOnly: remoteOnly,
  });
}

function loadJobIntoActiveSet(jobUrl, jobDescription) {
  const targetSet = getActiveSet();
  if (!targetSet) {
    return;
  }

  const urlInput = targetSet.querySelector('input[name="job_url"]');
  const jobTextarea = targetSet.querySelector('textarea[name="job"]');
  if (urlInput instanceof HTMLInputElement) {
    urlInput.value = jobUrl || "";
  }
  if (jobTextarea instanceof HTMLTextAreaElement) {
    jobTextarea.value = jobDescription || "";
    jobTextarea.focus();
  }

  setActiveSet(targetSet);
  activateWorkspaceTab("reviewer");
  targetSet.scrollIntoView({ behavior: "smooth", block: "nearest" });
  persistDraftState();
}

applyDraftState();
applyStoredUiState();
setActiveSet(document.querySelector(`.set[data-index="${readStoredState().activeSetIndex || 1}"]`) || document.querySelector(".set"));
updateButtons();
applyJobFilters();

workspaceTabs.forEach((button) => {
  button.addEventListener("click", () => {
    if (button.disabled) {
      return;
    }
    activateWorkspaceTab(button.dataset.tabTrigger || "reviewer");
  });
});

jumpResultsButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activateWorkspaceTab(button.dataset.openTab || "results");
  });
});

resultSwitches.forEach((button) => {
  button.addEventListener("click", () => activateResultCard(button.dataset.resultTarget || "1"));
});

chatbotApplication?.addEventListener("change", () => {
  activateResultCard(chatbotApplication.value);
});

addButton?.addEventListener("click", () => {
  if (!sets) {
    return;
  }
  const count = sets.querySelectorAll(".set").length;
  const next = createSet(count + 1);
  sets.appendChild(next);
  setActiveSet(next);
  activateWorkspaceTab("reviewer");
  next.scrollIntoView({ behavior: "smooth", block: "nearest" });
  updateButtons();
  persistDraftState();
});

sets?.addEventListener("click", (event) => {
  const target = event.target;

  if (target instanceof HTMLButtonElement && target.classList.contains("remove-set")) {
    const container = target.closest(".set");
    if (container) {
      container.remove();
      renumberSets();
      const remaining = sets.querySelectorAll(".set");
      setActiveSet(remaining[0] || null);
      updateButtons();
      persistDraftState();
      return;
    }
  }

  if (target instanceof HTMLButtonElement && target.classList.contains("reset-set")) {
    const container = target.closest(".set");
    if (container) {
      resetSet(container);
      setActiveSet(container);
    }
    return;
  }

  const setContainer = target instanceof Element ? target.closest(".set") : null;
  if (setContainer) {
    setActiveSet(setContainer);
  }
});

sets?.addEventListener("focusin", (event) => {
  const target = event.target;
  const setContainer = target instanceof Element ? target.closest(".set") : null;
  if (setContainer) {
    setActiveSet(setContainer);
  }
});

sets?.addEventListener("input", () => {
  persistDraftState();
});

sets?.addEventListener("change", (event) => {
  const target = event.target;
  if (target instanceof HTMLInputElement && target.type === "file") {
    const label = target.closest("label");
    const existingHint = label?.querySelector(".file-hint");
    if (existingHint) {
      existingHint.remove();
    }
    if (target.files && target.files.length > 0 && label) {
      target.setAttribute("data-loaded-name", target.files[0].name);
      const hint = document.createElement("span");
      hint.className = "file-hint";
      hint.textContent = `Selected for upload: ${target.files[0].name}`;
      label.appendChild(hint);
    }
  }
  persistDraftState();
});

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

jobsGrid?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement) || !target.classList.contains("use-job")) {
    return;
  }

  const card = target.closest(".job-card");
  if (!card) {
    return;
  }

  loadJobIntoActiveSet(card.dataset.jobUrl || "", card.dataset.jobDescription || "");
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement) || !target.classList.contains("use-suggestion")) {
    return;
  }

  loadJobIntoActiveSet(target.dataset.jobUrl || "", target.dataset.jobDescription || "");
});

reviewForm?.addEventListener("submit", () => {
  clearDraftState();
});

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

function formatList(items) {
  if (!items || items.length === 0) {
    return "none";
  }
  return items.slice(0, 4).join(", ");
}

function buildAssistantReply(result, question) {
  const lower = question.toLowerCase();
  const weakCategories = (result.categories || []).filter((category) => category.coverage < 60);
  const firstCvIssue = (result.cv_highlights || [])[0];
  const firstCoverIssue = (result.cover_highlights || [])[0];
  const firstSuggestion = (result.role_suggestions || [])[0];

  if (lower.includes("role") || lower.includes("job")) {
    if (firstSuggestion) {
      return `${firstSuggestion.title} at ${firstSuggestion.company} is the closest current role for this CV. Strong overlap includes ${formatList(firstSuggestion.matched_keywords)}.`;
    }
    return "There is not enough CV evidence yet to suggest a stronger role match.";
  }

  if (lower.includes("first") || lower.includes("priority") || lower.includes("start")) {
    if (weakCategories.length > 0) {
      return `Start with ${weakCategories[0].label.toLowerCase()}. Missing evidence there includes ${formatList(weakCategories[0].missing_keywords)}.`;
    }
    if (firstCvIssue) {
      return `Start with the CV issue marked ${firstCvIssue.issue_id}. ${firstCvIssue.suggestion}`;
    }
  }

  if (lower.includes("cover")) {
    if (firstCoverIssue) {
      return `Your cover letter is weakest at marker ${firstCoverIssue.issue_id}. ${firstCoverIssue.suggestion}`;
    }
    return "The cover letter is mainly being scored on tailoring, clarity, and proof of impact. Mention the company, the role, and a measurable outcome.";
  }

  if (lower.includes("cv")) {
    if (firstCvIssue) {
      return `Your CV issue to fix first is marker ${firstCvIssue.issue_id}. ${firstCvIssue.suggestion}`;
    }
    return `Your CV should show stronger evidence for ${formatList(result.missing_keywords)} with measurable outcomes.`;
  }

  if (lower.includes("score") || lower.includes("low") || lower.includes("why")) {
    const weak = weakCategories.map((category) => `${category.label} (${category.coverage}%)`);
    return `Your score is being pulled down most by ${weak.slice(0, 3).join(", ") || "tailoring and evidence"}. Missing requirements include ${formatList(result.missing_keywords)}.`;
  }

  if (lower.includes("keyword") || lower.includes("requirement")) {
    return `The main missing requirements are ${formatList(result.missing_keywords)}. The strongest matched terms are ${formatList(result.keyword_overlap)}.`;
  }

  if (lower.includes("improve") || lower.includes("better")) {
    const note = (result.notes || [])[0];
    if (note) {
      return `${note} After that, address ${formatList(result.missing_keywords)} in your evidence.`;
    }
  }

  return `Focus on ${formatList(result.missing_keywords)} and the red markers in the CV and cover letter sections. The weakest category right now is ${(weakCategories[0] && weakCategories[0].label.toLowerCase()) || "overall evidence"}.`;
}

if (chatbotForm && reviewDataNode) {
  const reviewData = JSON.parse(reviewDataNode.textContent || "[]");

  chatbotForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = chatbotQuestion?.value.trim() || "";
    if (!question) {
      return;
    }

    const applicationId = Number(chatbotApplication?.value || "1");
    const result = reviewData.find((entry) => entry.index === applicationId);
    addChatMessage("user", question);

    if (!result) {
      addChatMessage("bot", "I could not find review data for that application.");
      if (chatbotQuestion) {
        chatbotQuestion.value = "";
      }
      return;
    }

    const reply = buildAssistantReply(result, question);
    addChatMessage("bot", reply);
    if (chatbotQuestion) {
      chatbotQuestion.value = "";
    }
  });
}
