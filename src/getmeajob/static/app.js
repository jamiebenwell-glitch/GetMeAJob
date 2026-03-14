const workspacePanel = document.getElementById("workspace-panel");
const workspaceTabs = Array.from(document.querySelectorAll("[data-tab-trigger]"));
const workspaceViews = Array.from(document.querySelectorAll("[data-tab-panel]"));
const jumpResultsButtons = Array.from(document.querySelectorAll("[data-open-tab]"));

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
const jobsCount = document.getElementById("jobs-count");
const jobsEmpty = document.getElementById("jobs-empty");

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
}

if (workspacePanel) {
  const initialTab = workspacePanel.dataset.initialTab || "reviewer";
  activateWorkspaceTab(initialTab);

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
}

if (resultSwitches.length > 0) {
  const initialResult = chatbotApplication?.value || resultSwitches[0].dataset.resultTarget || "1";
  activateResultCard(initialResult);
  resultSwitches.forEach((button) => {
    button.addEventListener("click", () => activateResultCard(button.dataset.resultTarget || "1"));
  });
}

chatbotApplication?.addEventListener("change", () => {
  activateResultCard(chatbotApplication.value);
});

function getActiveSet() {
  return document.querySelector(".set.active") || document.querySelector(".set");
}

function setActiveSet(container) {
  const setsList = document.querySelectorAll(".set");
  setsList.forEach((set) => set.classList.remove("active"));
  if (container) {
    container.classList.add("active");
  }
}

function updateButtons() {
  const removeButtons = document.querySelectorAll(".remove-set");
  removeButtons.forEach((button, index) => {
    button.disabled = index === 0;
  });
}

function createSet(index) {
  const wrapper = document.createElement("div");
  wrapper.className = "set";
  wrapper.dataset.index = String(index);
  wrapper.innerHTML = `
    <input type="hidden" name="cv_cached_text" value="" />
    <input type="hidden" name="cover_cached_text" value="" />
    <input type="hidden" name="cv_cached_name" value="" />
    <input type="hidden" name="cover_cached_name" value="" />
    <div class="set-header">
      <h3>Application ${index}</h3>
      <button type="button" class="ghost remove-set">Remove</button>
    </div>
    <label>
      Job advert URL
      <input type="url" name="job_url" placeholder="https://company.com/jobs/role" />
    </label>
    <label>
      Job description
      <textarea name="job" rows="7" placeholder="Paste the job description here"></textarea>
    </label>
    <div class="upload-grid">
      <label>
        CV file
        <input type="file" name="cv_file" accept=".txt,.pdf,.docx" />
      </label>
      <label>
        Cover letter file
        <input type="file" name="cover_letter_file" accept=".txt,.pdf,.docx" />
      </label>
    </div>
  `;
  return wrapper;
}

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
});

sets?.addEventListener("click", (event) => {
  const target = event.target;
  if (target instanceof HTMLButtonElement && target.classList.contains("remove-set")) {
    const container = target.closest(".set");
    if (container) {
      container.remove();
      const remaining = sets.querySelectorAll(".set");
      remaining.forEach((set, idx) => {
        const title = set.querySelector("h3");
        if (title) {
          title.textContent = `Application ${idx + 1}`;
        }
      });
      setActiveSet(remaining[0] || null);
      updateButtons();
      return;
    }
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

setActiveSet(document.querySelector(".set"));
updateButtons();

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
}

jobSearch?.addEventListener("input", applyJobFilters);
jobCompanyFilter?.addEventListener("change", applyJobFilters);
jobLocationFilter?.addEventListener("change", applyJobFilters);
jobDurationFilter?.addEventListener("change", applyJobFilters);
jobProviderFilter?.addEventListener("change", applyJobFilters);
jobRemoteFilter?.addEventListener("change", applyJobFilters);

jobsGrid?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement) || !target.classList.contains("use-job")) {
    return;
  }

  const card = target.closest(".job-card");
  const targetSet = getActiveSet();
  if (!card || !targetSet) {
    return;
  }

  const urlInput = targetSet.querySelector('input[name="job_url"]');
  const jobTextarea = targetSet.querySelector('textarea[name="job"]');
  if (urlInput instanceof HTMLInputElement) {
    urlInput.value = card.dataset.jobUrl || "";
  }
  if (jobTextarea instanceof HTMLTextAreaElement) {
    jobTextarea.value = card.dataset.jobDescription || "";
    jobTextarea.focus();
  }

  setActiveSet(targetSet);
  activateWorkspaceTab("reviewer");
  targetSet.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

applyJobFilters();

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
