const isServedByBackend = window.location.protocol.startsWith("http")
  && window.location.pathname.startsWith("/frontend");
const API_BASE_URL = isServedByBackend
  ? window.location.origin
  : "http://127.0.0.1:8000";

const state = {
  mode: "prompt",
  itinerary: null,
  links: null,
  currency: "INR",
  lastPayload: null,
};

const els = {
  promptTab: document.getElementById("promptTab"),
  manualTab: document.getElementById("manualTab"),
  promptSection: document.getElementById("promptSection"),
  manualSection: document.getElementById("manualSection"),
  tripForm: document.getElementById("tripForm"),
  apiStatus: document.getElementById("apiStatus"),
  loadingCard: document.getElementById("loadingCard"),
  emptyState: document.getElementById("emptyState"),
  resultContent: document.getElementById("resultContent"),
  downloadBtn: document.getElementById("downloadBtn"),
  generateBtn: document.getElementById("generateBtn"),
  tripSummary: document.getElementById("tripSummary"),
  summarySubtitle: document.getElementById("summarySubtitle"),
  summaryMetrics: document.getElementById("summaryMetrics"),
  budgetFit: document.getElementById("budgetFit"),
  budgetGrid: document.getElementById("budgetGrid"),
  dayList: document.getElementById("dayList"),
  travelOptions: document.getElementById("travelOptions"),
  stayOptions: document.getElementById("stayOptions"),
  bookingLinks: document.getElementById("bookingLinks"),
  tipsList: document.getElementById("tipsList"),
  prompt: document.getElementById("prompt"),
};

const CURRENCY_SYMBOLS = {
  INR: "₹",
  USD: "$",
  EUR: "EUR ",
  GBP: "GBP ",
  AED: "AED ",
  SGD: "S$",
};

const ICONS = {
  arrowUpRight: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 17 17 7"></path>
      <path d="M7 7h10v10"></path>
    </svg>
  `,
};

function setMode(mode) {
  state.mode = mode;
  const isPrompt = mode === "prompt";

  els.promptTab.classList.toggle("active", isPrompt);
  els.manualTab.classList.toggle("active", !isPrompt);
  els.promptTab.setAttribute("aria-selected", String(isPrompt));
  els.manualTab.setAttribute("aria-selected", String(!isPrompt));
  els.promptSection.classList.toggle("active", isPrompt);
  els.manualSection.classList.toggle("active", !isPrompt);
}

function setStatus(label, type = "") {
  els.apiStatus.textContent = label;
  els.apiStatus.className = `status-pill ${type}`.trim();
}

function setLoading(isLoading) {
  els.loadingCard.classList.toggle("hidden", !isLoading);
  els.emptyState.classList.add("hidden");
  els.resultContent.classList.toggle("hidden", isLoading || !state.itinerary);
  els.generateBtn.disabled = isLoading;
  els.downloadBtn.disabled = isLoading || !state.itinerary;
  setStatus(isLoading ? "Generating" : "Ready", isLoading ? "generating" : "");
}

function getManualPayload() {
  return {
    source: getInputValue("source"),
    destination: getInputValue("destination"),
    start_date: getInputValue("startDate"),
    end_date: getInputValue("endDate"),
    budget: Number(getInputValue("budget") || 0),
    people: Number(getInputValue("people") || 1),
    currency: getInputValue("currency"),
    travel_mode: getInputValue("travelMode"),
    stay_type: getInputValue("stayType"),
    estimate_mode: getInputValue("estimateMode"),
    interests: getInputValue("interests")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

function getInputValue(id) {
  return document.getElementById(id).value.trim();
}

async function postJson(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed. Please check the backend and try again.");
  }

  return data;
}

async function generateTrip(event) {
  event.preventDefault();
  state.itinerary = null;
  state.links = null;
  setLoading(true);

  try {
    let itinerary;
    let links;

    if (state.mode === "prompt") {
      const prompt = els.prompt.value.trim();
      if (!prompt) {
        throw new Error("Write a trip prompt first.");
      }

      const payload = {
        prompt,
        estimate_mode: getInputValue("estimateMode"),
      };
      state.lastPayload = payload;
      itinerary = await postJson("/trip/generate-from-prompt", payload);
      links = await postJson("/trip/booking-links-from-prompt", payload);
    } else {
      const payload = getManualPayload();
      validateManualPayload(payload);
      state.lastPayload = payload;
      itinerary = await postJson("/trip/generate", payload);
      links = await postJson("/trip/booking-links", payload);
    }

    state.itinerary = itinerary;
    state.links = links;
    state.currency = itinerary.estimated_budget?.currency || state.currency;

    renderResults();
    setStatus("Complete", "complete");
    els.downloadBtn.disabled = false;
    document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    state.itinerary = null;
    state.links = null;
    showError(error.message);
    setStatus("Error", "error");
  } finally {
    els.loadingCard.classList.add("hidden");
    els.generateBtn.disabled = false;
  }
}

function validateManualPayload(payload) {
  const requiredFields = ["source", "destination", "start_date", "end_date"];
  const missingField = requiredFields.find((field) => !payload[field]);

  if (missingField) {
    throw new Error(`${formatLabel(missingField)} is required.`);
  }

  if (payload.people < 1) {
    throw new Error("People must be at least 1.");
  }
}

function showError(message) {
  els.resultContent.classList.add("hidden");
  els.emptyState.classList.remove("hidden");
  els.emptyState.innerHTML = `
    <div class="empty-icon">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"></path>
        <path d="M12 9v4"></path>
        <path d="M12 17h.01"></path>
      </svg>
    </div>
    <p class="eyebrow">Something needs attention</p>
    <h2>Could not generate itinerary</h2>
    <p>${escapeHtml(message)}</p>
  `;
}

function renderResults() {
  const trip = state.itinerary || {};
  const links = state.links?.links || [];

  els.emptyState.classList.add("hidden");
  els.resultContent.classList.remove("hidden");

  renderSummaryHero(trip);
  renderBudget(trip.estimated_budget || {});
  renderDays(trip.day_wise_plan || []);
  renderTravelOptions(trip.travel_options || []);
  renderStayOptions(trip.stay_options || []);
  renderLinks(links);
  renderTips(trip.tips || []);
}

function renderSummaryHero(trip) {
  const payload = state.lastPayload || {};
  const days = trip.day_wise_plan?.length || calculatePayloadDays(payload) || 0;
  const budget = trip.estimated_budget || {};
  const total = budget.total ? formatCurrency(budget.total, budget.currency) : "TBD";
  const people = payload.people || extractPeople(trip.summary) || "TBD";
  const travelMode = payload.travel_mode || trip.travel_options?.[0]?.mode || "Travel";
  const stayType = payload.stay_type || trip.stay_options?.[0]?.type || "Stay";
  const estimateMode = payload.estimate_mode || trip.estimate_mode || "quick";

  els.tripSummary.textContent = buildSummaryTitle(trip, payload, days);
  els.summarySubtitle.textContent = buildSummarySubtitle(trip, payload, people, stayType);

  els.summaryMetrics.innerHTML = [
    metricTemplate(iconCalendar(), `${days || "TBD"} Days`),
    metricTemplate(iconWallet(), `${total} Budget`),
    metricTemplate(iconUsers(), `${people} Travelers`),
    metricTemplate(iconRoute(), formatLabel(travelMode)),
    metricTemplate(iconBed(), `${formatLabel(stayType)} Stay`),
    metricTemplate(iconSpark(), estimateMode === "agent" ? "Agent Plan" : "Quick Estimate"),
  ].join("");
}

function buildSummaryTitle(trip, payload, days) {
  if (payload.destination && payload.source) {
    return `${days || "Multi"}-Day ${payload.destination} Trip from ${payload.source}`;
  }

  if (payload.destination) {
    return `${days || "Multi"}-Day ${payload.destination} Trip`;
  }

  const summary = cleanSentence(trip.summary);
  return summary ? clampText(summary, 58) : `${days || "AI"}-Day Trip Itinerary`;
}

function buildSummarySubtitle(trip, payload, people, stayType) {
  if (payload.interests?.length) {
    const interests = payload.interests.slice(0, 2).join(" & ");
    return `${formatLabel(stayType)}-friendly ${interests} itinerary for ${people} travelers.`;
  }

  const summary = cleanSentence(trip.summary);
  if (summary) {
    return clampText(summary, 96);
  }

  return "Budget-friendly travel plan with routes, stays, food, and practical tips.";
}

function metricTemplate(icon, value) {
  return `
    <div class="metric">
      ${icon}
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function iconCalendar() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 2v4"></path>
      <path d="M16 2v4"></path>
      <path d="M3 10h18"></path>
      <path d="M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"></path>
    </svg>
  `;
}

function iconWallet() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 7H5a2 2 0 0 0 0 4h15v8H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14Z"></path>
      <path d="M16 14h.01"></path>
    </svg>
  `;
}

function iconUsers() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
      <path d="M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"></path>
      <path d="M22 21v-2a4 4 0 0 0-3-3.87"></path>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
    </svg>
  `;
}

function iconRoute() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 19a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"></path>
      <path d="M18 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"></path>
      <path d="M6 13V9a4 4 0 0 1 4-4h5"></path>
      <path d="M18 11v4a4 4 0 0 1-4 4H9"></path>
    </svg>
  `;
}

function iconBed() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 4v16"></path>
      <path d="M2 12h20"></path>
      <path d="M22 10v10"></path>
      <path d="M6 12V7a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v5"></path>
    </svg>
  `;
}

function iconSpark() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M13 2 3 14h8l-1 8 11-14h-8l1-6Z"></path>
    </svg>
  `;
}

function calculatePayloadDays(payload) {
  if (!payload.start_date || !payload.end_date) return 0;

  const start = new Date(payload.start_date);
  const end = new Date(payload.end_date);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;

  const msPerDay = 24 * 60 * 60 * 1000;
  return Math.max(Math.round((end - start) / msPerDay) + 1, 1);
}

function extractPeople(summary = "") {
  const match = String(summary).match(/(\d+)\s*(people|persons|travelers|travellers|guests)/i);
  return match ? Number(match[1]) : "";
}

function cleanSentence(value = "") {
  return String(value)
    .replace(/\s+/g, " ")
    .split(/[.!?]/)[0]
    .trim();
}

function clampText(value, maxLength) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;

  const clipped = text.slice(0, maxLength - 1);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${clipped.slice(0, lastSpace > 32 ? lastSpace : clipped.length).trim()}...`;
}

function renderBudget(budget) {
  state.currency = budget.currency || state.currency;

  const items = [
    ["Travel", budget.travel],
    ["Stay", budget.stay],
    ["Food", budget.food],
    ["Local Transport", budget.local_transport],
    ["Activities", budget.activities],
    ["Buffer", budget.buffer],
    ["Total", budget.total, "total"],
  ];

  els.budgetGrid.innerHTML = items
    .map(([label, value, className = ""]) => `
      <article class="budget-item ${className}">
        <span>${escapeHtml(label)}</span>
        <strong>${formatCurrency(value, budget.currency)}</strong>
      </article>
    `)
    .join("");

  const fitsBudget = budget.fits_budget !== false;
  els.budgetFit.textContent = fitsBudget ? "Fits budget" : "Over budget";
  els.budgetFit.classList.toggle("over", !fitsBudget);
}

function renderDays(days) {
  if (!days.length) {
    els.dayList.innerHTML = emptyCard("No day-wise plan returned yet.");
    return;
  }

  els.dayList.innerHTML = days
    .map((day, index) => `
      <article class="day-card">
        <div class="day-title">
          <div class="day-number">${escapeHtml(day.day || index + 1)}</div>
          <h4>${escapeHtml(day.title || `Day ${index + 1}`)}</h4>
        </div>

        <div class="time-grid">
          ${timeCard("Morning", day.morning)}
          ${timeCard("Afternoon", day.afternoon)}
          ${timeCard("Evening", day.evening || "Rest, explore nearby, or use this as a flexible travel window.")}
        </div>

        <div class="day-footer">
          <div>
            <span>Food & Travel Notes</span>
            <p>${escapeHtml(joinText([day.food_suggestion, day.travel_notes]))}</p>
          </div>
          <div class="cost-pill">${formatCurrency(day.estimated_cost)}</div>
        </div>
      </article>
    `)
    .join("");
}

function timeCard(label, value) {
  return `
    <div class="time-card">
      <span>${escapeHtml(label)}</span>
      <p>${escapeHtml(value || "Flexible time")}</p>
    </div>
  `;
}

function renderTravelOptions(items) {
  if (!items.length) {
    els.travelOptions.innerHTML = emptyCard("No travel options returned yet.");
    return;
  }

  els.travelOptions.innerHTML = items
    .map((item) => `
      <article class="option-card">
        <h4>${escapeHtml(item.mode || "Travel option")}</h4>
        <p>${escapeHtml(item.details || "Compare routes, timing, and comfort before booking.")}</p>
        <div class="option-meta">
          <span class="tag">${formatCurrency(item.estimated_cost)}</span>
        </div>
      </article>
    `)
    .join("");
}

function renderStayOptions(items) {
  if (!items.length) {
    els.stayOptions.innerHTML = emptyCard("No stay options returned yet.");
    return;
  }

  els.stayOptions.innerHTML = items
    .map((item) => `
      <article class="option-card">
        <h4>${escapeHtml(item.name || "Stay option")}</h4>
        <p>${escapeHtml(item.note || "Check reviews, cancellation terms, and distance from your planned areas.")}</p>
        <div class="option-meta">
          <span class="tag">${escapeHtml(item.type || "Stay")}</span>
          <span class="tag">${escapeHtml(item.location || "Good location")}</span>
          <span class="tag">${formatCurrency(item.estimated_price_per_night)} / night</span>
        </div>
      </article>
    `)
    .join("");
}

function renderLinks(links) {
  if (!links.length) {
    els.bookingLinks.innerHTML = emptyCard("No booking links returned yet.");
    return;
  }

  els.bookingLinks.innerHTML = links
    .map((link) => `
      <article class="link-card">
        <h4>
          <a href="${escapeAttribute(link.url)}" target="_blank" rel="noreferrer">
            <span>${escapeHtml(link.label || "Open link")}</span>
            ${ICONS.arrowUpRight}
          </a>
        </h4>
        <p><strong>${escapeHtml(formatLabel(link.type || "resource"))}</strong></p>
        <p>${escapeHtml(link.note || "Open this resource to continue planning.")}</p>
      </article>
    `)
    .join("");
}

function renderTips(tips) {
  if (!tips.length) {
    els.tipsList.innerHTML = "<li>Check weather, local rules, opening hours, and travel advisories before booking.</li>";
    return;
  }

  els.tipsList.innerHTML = tips
    .map((tip) => `<li>${escapeHtml(tip)}</li>`)
    .join("");
}

function emptyCard(message) {
  return `
    <article class="option-card">
      <p>${escapeHtml(message)}</p>
    </article>
  `;
}

function downloadItinerary() {
  if (!state.itinerary) return;

  const trip = state.itinerary;
  const links = state.links?.links || [];
  const budget = trip.estimated_budget || {};
  const days = trip.day_wise_plan || [];
  const travel = trip.travel_options || [];
  const stays = trip.stay_options || [];

  const lines = [
    trip.summary || "Trip itinerary",
    "",
    "Budget Breakdown",
    ...Object.entries(budget).map(([key, value]) => `${formatLabel(key)}: ${formatDownloadValue(key, value)}`),
    "",
    "Day-wise Itinerary",
    ...days.flatMap((day) => [
      `Day ${day.day}: ${day.title}`,
      `Morning: ${day.morning}`,
      `Afternoon: ${day.afternoon}`,
      `Evening: ${day.evening}`,
      `Food: ${day.food_suggestion}`,
      `Travel Notes: ${day.travel_notes}`,
      `Estimated Cost: ${formatCurrency(day.estimated_cost)}`,
      "",
    ]),
    "Travel Options",
    ...travel.map((item) => `${item.mode}: ${item.details} (${formatCurrency(item.estimated_cost)})`),
    "",
    "Stay Options",
    ...stays.map((item) => `${item.name}: ${item.type}, ${item.location}, ${formatCurrency(item.estimated_price_per_night)} per night. ${item.note}`),
    "",
    "Tips & Warnings",
    ...(trip.tips || []).map((tip) => `- ${tip}`),
    "",
    "Booking & Location Links",
    ...links.map((link) => `${link.label}: ${link.url}`),
  ];

  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "trip-itinerary.txt";
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatCurrency(value, currency = state.currency) {
  const amount = Number(value || 0);
  const normalizedCurrency = currency || "INR";
  const symbol = CURRENCY_SYMBOLS[normalizedCurrency] || `${normalizedCurrency} `;
  const locale = normalizedCurrency === "INR" ? "en-IN" : "en-US";

  return `${symbol}${amount.toLocaleString(locale)}`;
}

function formatDownloadValue(key, value) {
  if (key === "currency") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return formatCurrency(value);
  return String(value ?? "");
}

function formatLabel(key) {
  return String(key)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function joinText(parts) {
  return parts.filter(Boolean).join(" ");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

function setupPromptExamples() {
  document.querySelectorAll("[data-example]").forEach((button) => {
    button.addEventListener("click", () => {
      els.prompt.value = button.dataset.example;
      setMode("prompt");
      els.prompt.focus();
    });
  });
}

els.promptTab.addEventListener("click", () => setMode("prompt"));
els.manualTab.addEventListener("click", () => setMode("manual"));
els.tripForm.addEventListener("submit", generateTrip);
els.downloadBtn.addEventListener("click", downloadItinerary);
setupPromptExamples();
