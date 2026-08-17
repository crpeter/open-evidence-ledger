const state = { token: null, config: null, candidates: [], currentId: null, detail: null };
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const init = { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } };
  if (options.body && typeof options.body !== "string") {
    init.body = JSON.stringify({ ...options.body, csrf_token: state.token });
  }
  const response = await fetch(path, init);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function setOptions(select, values) {
  select.replaceChildren();
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
}

function checkboxGroup(container, values, selected) {
  container.replaceChildren();
  const selectedSet = new Set(selected || []);
  for (const value of values) {
    const label = document.createElement("label");
    label.className = "check-pill";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = value;
    input.checked = selectedSet.has(value);
    const span = document.createElement("span");
    span.textContent = value;
    label.append(input, span);
    container.appendChild(label);
  }
}

function checkedValues(container) {
  return [...container.querySelectorAll('input[type="checkbox"]:checked')].map((input) => input.value);
}

function lines(value) {
  return Array.isArray(value) ? value.join("\n") : (value || "");
}

function draftKey(id) {
  return `oel-review-draft:${id}`;
}

function loadDraft(id) {
  try { return JSON.parse(localStorage.getItem(draftKey(id))) || null; }
  catch { return null; }
}

function saveDraft() {
  if (!state.currentId || !state.detail) return;
  const status = state.detail.candidate.review_status;
  if (status === "PUBLISHED") return;
  localStorage.setItem(draftKey(state.currentId), JSON.stringify(collectRecord()));
}

function showMessage(text, kind = "info") {
  const message = $("message");
  message.textContent = text;
  message.className = `message ${kind}`;
}

function clearMessage() {
  $("message").className = "message hidden";
  $("message").textContent = "";
}

function renderList() {
  const filter = $("search").value.trim().toLowerCase();
  const list = $("candidate-list");
  list.replaceChildren();
  const visible = state.candidates.filter((item) => {
    const haystack = `${item.id} ${item.claim} ${item.source_organization} ${item.source_document_id} ${item.status}`.toLowerCase();
    return !filter || haystack.includes(filter);
  });
  for (const item of visible) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `candidate-item${item.id === state.currentId ? " active" : ""}`;
    button.addEventListener("click", () => selectCandidate(item.id));

    const top = document.createElement("div");
    top.className = "candidate-item-top";
    const status = document.createElement("span");
    status.className = `status status-${item.status.toLowerCase().replaceAll("_", "-")}`;
    status.textContent = item.status.replaceAll("_", " ");
    const flag = document.createElement("span");
    flag.className = "flag-count";
    flag.textContent = item.flags.length ? `${item.flags.length} flag${item.flags.length === 1 ? "" : "s"}` : "no flags";
    top.append(status, flag);

    const claim = document.createElement("div");
    claim.className = "candidate-item-claim";
    claim.textContent = item.claim;
    const source = document.createElement("div");
    source.className = "candidate-item-source";
    source.textContent = `${item.source_organization} · ${item.source_document_id}`;
    button.append(top, claim, source);
    list.appendChild(button);
  }
  if (!visible.length) {
    const empty = document.createElement("div");
    empty.className = "sidebar-empty";
    empty.textContent = "No matching candidates.";
    list.appendChild(empty);
  }
}

async function loadCandidates(preferredId = state.currentId) {
  const result = await api("/api/candidates");
  state.candidates = result.candidates;
  renderList();
  const nextId = state.candidates.some((item) => item.id === preferredId) ? preferredId : state.candidates[0]?.id;
  if (nextId) await selectCandidate(nextId, false);
}

async function selectCandidate(id, preserveDraft = true) {
  if (preserveDraft && state.currentId && state.currentId !== id) saveDraft();
  clearMessage();
  state.detail = await api(`/api/candidates/${encodeURIComponent(id)}`);
  state.currentId = id;
  renderList();
  renderDetail();
}

function renderDetail() {
  const { candidate, related_records, record_fields } = state.detail;
  $("empty-state").classList.add("hidden");
  $("review-form").classList.remove("hidden");
  const index = state.candidates.findIndex((item) => item.id === candidate.id);
  $("position").textContent = `Candidate ${index + 1} of ${state.candidates.length} · ${candidate.id}`;
  $("candidate-title").textContent = candidate.proposed_claim;
  $("source-title").textContent = candidate.source_title;
  $("source-org").textContent = candidate.source_organization;
  $("source-doc").textContent = candidate.source_document_id;
  $("publication-date").textContent = candidate.publication_date;
  $("pinpoint-label").textContent = candidate.source_page || "Not specified";
  $("open-source").href = candidate.source_url;

  $("proposed-claim").value = candidate.proposed_claim;
  $("proposed-category").value = candidate.proposed_category;
  $("proposed-legal-status").value = candidate.proposed_legal_status;
  $("proposed-event-date").value = candidate.proposed_event_date || "";
  $("source-page").value = candidate.source_page || "";
  $("supporting-passage").value = candidate.supporting_passage || "";
  $("extraction-notes").value = candidate.extraction_notes || "";
  $("related-record-ids").value = lines(candidate.related_published_records);
  $("review-notes").value = candidate.review_notes || "";
  checkboxGroup($("review-flags"), state.config.review_flags, candidate.review_flags);

  const statusBadge = $("status-badge");
  statusBadge.className = `status status-${candidate.review_status.toLowerCase().replaceAll("_", "-")}`;
  statusBadge.textContent = candidate.review_status.replaceAll("_", " ");

  const relatedCard = $("overlap-card");
  const relatedList = $("related-records");
  relatedList.replaceChildren();
  if (related_records.length) {
    relatedCard.classList.remove("hidden");
    for (const record of related_records) {
      const item = document.createElement("div");
      item.className = "related-item";
      const title = document.createElement("strong");
      title.textContent = `${record.id} — ${record.title}`;
      const claim = document.createElement("p");
      claim.textContent = record.claim;
      item.append(title, claim);
      relatedList.appendChild(item);
    }
  } else {
    relatedCard.classList.add("hidden");
  }

  const draft = candidate.proposed_record ? record_fields : (loadDraft(candidate.id) || record_fields);
  fillRecord(draft);
  setLockedState(candidate.review_status);
  $("previous").disabled = index <= 0;
  $("next").disabled = index < 0 || index >= state.candidates.length - 1;
}

function fillRecord(record) {
  $("record-id").value = record.id || "";
  $("record-title").value = record.title || "";
  $("record-location").value = lines(record.location);
  $("record-actors").value = lines(record.actors);
  $("record-population").value = lines(record.affected_population);
  $("record-summary").value = record.summary || "";
  $("record-legal-characterization").value = record.legal_characterization || "";
  checkboxGroup($("evidence-types"), state.config.evidence_types, record.evidence_type || []);
  $("record-source-quote").value = record.source_quote || "";
  $("record-verification-notes").value = record.verification_notes || "";
  $("record-tags").value = lines(record.tags);
}

function setLockedState(status) {
  const locked = status === "VERIFIED" || status === "REJECTED" || status === "PUBLISHED";
  const editableIds = [
    "proposed-claim", "proposed-category", "proposed-legal-status", "proposed-event-date", "source-page",
    "supporting-passage", "extraction-notes", "related-record-ids", "review-notes", "record-id", "record-title",
    "record-location", "record-actors", "record-population", "record-summary", "record-legal-characterization",
    "record-source-quote", "record-verification-notes", "record-tags"
  ];
  for (const id of editableIds) $(id).disabled = locked;
  for (const container of [$("review-flags"), $("evidence-types")]) {
    for (const input of container.querySelectorAll("input")) input.disabled = locked;
  }
  $("save").disabled = locked;
  $("needs-review").disabled = locked;
  $("reject").disabled = locked;
  $("verify").disabled = locked;
  $("reopen").classList.toggle("hidden", status === "PUBLISHED" || !locked);
}

function collectCandidate() {
  return {
    proposed_claim: $("proposed-claim").value.trim(),
    proposed_category: $("proposed-category").value,
    proposed_legal_status: $("proposed-legal-status").value,
    proposed_event_date: $("proposed-event-date").value || null,
    source_page: $("source-page").value.trim() || null,
    supporting_passage: $("supporting-passage").value.trim() || null,
    extraction_notes: $("extraction-notes").value.trim(),
    related_published_records: $("related-record-ids").value,
    review_flags: checkedValues($("review-flags")),
    review_notes: $("review-notes").value.trim() || null,
  };
}

function collectRecord() {
  return {
    id: $("record-id").value.trim(),
    title: $("record-title").value.trim(),
    location: $("record-location").value,
    actors: $("record-actors").value,
    affected_population: $("record-population").value,
    summary: $("record-summary").value.trim(),
    legal_characterization: $("record-legal-characterization").value.trim(),
    evidence_type: checkedValues($("evidence-types")),
    source_quote: $("record-source-quote").value.trim() || null,
    verification_notes: $("record-verification-notes").value.trim(),
    tags: $("record-tags").value,
  };
}

async function submit(action) {
  if (!state.currentId) return;
  clearMessage();
  const oldId = state.currentId;
  try {
    const result = await api(`/api/candidates/${encodeURIComponent(oldId)}`, {
      method: "POST",
      body: {
        action,
        reviewer: $("reviewer").value.trim(),
        review_notes: $("review-notes").value.trim(),
        candidate: action === "reopen" ? {} : collectCandidate(),
        record: action === "verify" ? collectRecord() : undefined,
      },
    });
    const newId = result.candidate.id;
    if (newId !== oldId) {
      const draft = localStorage.getItem(draftKey(oldId));
      localStorage.removeItem(draftKey(oldId));
      if (draft) localStorage.setItem(draftKey(newId), draft);
    }
    if (action === "verify" || action === "reject") localStorage.removeItem(draftKey(newId));
    state.currentId = newId;
    state.detail = result;
    await loadCandidates(newId);
    showMessage(action === "verify" ? "Candidate verified. It is still not published." : action === "reject" ? "Candidate rejected." : "Review changes saved.", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function move(delta) {
  const index = state.candidates.findIndex((item) => item.id === state.currentId);
  const target = state.candidates[index + delta];
  if (target) selectCandidate(target.id);
}

async function init() {
  try {
    const session = await api("/api/session");
    state.token = session.csrf_token;
    state.config = await api("/api/config");
    setOptions($("proposed-category"), state.config.categories);
    setOptions($("proposed-legal-status"), state.config.legal_statuses);
    $("reviewer").value = localStorage.getItem("oel-reviewer") || "";
    $("reviewer").addEventListener("input", () => localStorage.setItem("oel-reviewer", $("reviewer").value));
    $("search").addEventListener("input", renderList);
    $("previous").addEventListener("click", () => move(-1));
    $("next").addEventListener("click", () => move(1));
    $("save").addEventListener("click", () => submit("save"));
    $("needs-review").addEventListener("click", () => submit("needs_review"));
    $("reopen").addEventListener("click", () => submit("reopen"));
    $("reject").addEventListener("click", () => submit("reject"));
    $("verify").addEventListener("click", () => submit("verify"));
    $("review-form").addEventListener("input", saveDraft);
    window.addEventListener("beforeunload", saveDraft);
    await loadCandidates();
  } catch (error) {
    $("empty-state").innerHTML = "";
    const title = document.createElement("h3");
    title.textContent = "Reviewer failed to load";
    const message = document.createElement("p");
    message.textContent = error.message;
    $("empty-state").append(title, message);
  }
}

init();
