// Same-origin API: this page is served by the same FastAPI process that
// serves the API, so whatever host:port loaded this page is the right base
// URL — no configuration needed for local-network or mobile access.
const API_BASE = window.location.origin;
const TOKEN_KEY = "calorie_tracker_token";

// ---------- tiny DOM helpers ----------
const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}
function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------- API wrapper ----------
async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    showAuthView();
    throw new Error("__unauthorized__");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // no body / not JSON
  }

  if (!res.ok) {
    const message = (data && data.detail) || "Something went wrong.";
    throw new Error(message);
  }
  return data;
}

// ---------- view switching ----------
function showAuthView() {
  hide($("app-view"));
  show($("auth-view"));
}
function showAppView() {
  hide($("auth-view"));
  show($("app-view"));
  loadDashboard();
}

function setAuthError(message) {
  const el = $("auth-error");
  if (message) {
    el.textContent = message;
    show(el);
  } else {
    hide(el);
  }
}
function setAppError(message) {
  const el = $("app-error");
  if (message) {
    el.textContent = message;
    show(el);
  } else {
    hide(el);
  }
}

// ---------- auth: tab switching ----------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    setAuthError(null);
    if (btn.dataset.mode === "login") {
      show($("login-form"));
      hide($("signup-form"));
    } else {
      hide($("login-form"));
      show($("signup-form"));
    }
  });
});

// ---------- auth: login ----------
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setAuthError(null);
  const submitBtn = $("login-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Please wait…";
  try {
    const data = await api("/auth/login", {
      method: "POST",
      auth: false,
      body: {
        email: $("login-email").value.trim(),
        password: $("login-password").value,
      },
    });
    setToken(data.access_token);
    showAppView();
  } catch (err) {
    if (err.message !== "__unauthorized__") setAuthError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Log in";
  }
});

// ---------- auth: signup ----------
$("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setAuthError(null);
  const password = $("signup-password").value;
  if (password.length < 8) {
    setAuthError("Password must be at least 8 characters.");
    return;
  }
  const submitBtn = $("signup-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Please wait…";
  try {
    const data = await api("/auth/signup", {
      method: "POST",
      auth: false,
      body: {
        first_name: $("signup-first").value.trim(),
        last_name: $("signup-last").value.trim(),
        email: $("signup-email").value.trim(),
        password,
      },
    });
    setToken(data.access_token);
    showAppView();
  } catch (err) {
    if (err.message !== "__unauthorized__") setAuthError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create account";
  }
});

// ---------- logout ----------
$("logout-btn").addEventListener("click", () => {
  clearToken();
  showAuthView();
});

// ---------- dashboard ----------
async function loadDashboard() {
  setAppError(null);
  try {
    const tzOffsetMinutes = new Date().getTimezoneOffset();
    const summary = await api(`/dashboard/today?tz_offset_minutes=${tzOffsetMinutes}`);
    renderSummary(summary);
    renderFoodList(summary.foods);
  } catch (err) {
    if (err.message !== "__unauthorized__") {
      setAppError("Could not reach the server. Is the backend running?");
    }
  }
}

function renderSummary(summary) {
  $("calories-consumed").textContent = Math.round(summary.calories_consumed);
  $("calories-goal").textContent = Math.round(summary.daily_calorie_goal);

  const ratio = summary.daily_calorie_goal > 0
    ? Math.min(summary.calories_consumed / summary.daily_calorie_goal, 1)
    : 0;
  const fill = $("progress-fill");
  fill.style.width = `${ratio * 100}%`;
  fill.classList.toggle("over", summary.over_target);

  const remainingText = $("remaining-text");
  if (summary.over_target) {
    const over = Math.round(summary.calories_consumed - summary.daily_calorie_goal);
    remainingText.textContent = `${over} kcal over your daily target`;
    remainingText.classList.add("over");
  } else {
    const remaining = Math.round(summary.daily_calorie_goal - summary.calories_consumed);
    remainingText.textContent = `${remaining} kcal remaining`;
    remainingText.classList.remove("over");
  }
}

function renderFoodList(foods) {
  const list = $("food-list");
  list.innerHTML = "";
  if (!foods || foods.length === 0) {
    show($("food-empty"));
    return;
  }
  hide($("food-empty"));

  foods.forEach((entry) => {
    const li = document.createElement("li");
    li.className = "entry-row";
    li.innerHTML = `
      <span class="entry-name">${escapeHtml(entry.name)}</span>
      <span class="entry-meta">${Math.round(entry.weight_grams)} g</span>
      <span class="entry-calories">${Math.round(entry.calculated_calories)} kcal</span>
      <button type="button" class="delete-btn" aria-label="Delete" data-id="${entry.id}">×</button>
    `;
    list.appendChild(li);
  });

  list.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteEntry(btn.dataset.id));
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function deleteEntry(id) {
  try {
    await api(`/log/${id}`, { method: "DELETE" });
    await loadDashboard();
  } catch (err) {
    if (err.message !== "__unauthorized__") setAppError("Could not delete that entry.");
  }
}

// ---------- goal editing ----------
$("edit-goal-btn").addEventListener("click", () => {
  $("goal-input").value = $("calories-goal").textContent;
  hide($("goal-display"));
  show($("goal-form"));
});

$("cancel-goal-btn").addEventListener("click", () => {
  hide($("goal-form"));
  show($("goal-display"));
});

$("goal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const value = parseInt($("goal-input").value, 10);
  if (Number.isNaN(value) || value <= 0) return;
  try {
    await api("/profile/goal", {
      method: "PUT",
      body: { daily_calorie_goal: value },
    });
    hide($("goal-form"));
    show($("goal-display"));
    await loadDashboard();
  } catch (err) {
    if (err.message !== "__unauthorized__") setAppError("Could not update your goal.");
  }
});

// ---------- food logging with live calculation ----------
function updateFoodPreview() {
  const weight = parseFloat($("food-weight").value);
  const density = parseFloat($("food-density").value);
  const preview = $("food-preview");
  if (!Number.isNaN(weight) && !Number.isNaN(density) && weight > 0 && density >= 0) {
    preview.textContent = ((weight * density) / 100).toFixed(1);
  } else {
    preview.textContent = "0";
  }
}
$("food-weight").addEventListener("input", updateFoodPreview);
$("food-density").addEventListener("input", updateFoodPreview);

$("food-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setAppError(null);

  const name = $("food-name").value.trim();
  const weight = parseFloat($("food-weight").value);
  const density = parseFloat($("food-density").value);

  if (!name) return;
  if (Number.isNaN(weight) || weight <= 0 || weight > 10000) {
    setAppError("Enter a weight between 0 and 10,000 g.");
    return;
  }
  if (Number.isNaN(density) || density < 0) {
    setAppError("Enter a valid calorie density.");
    return;
  }

  const submitBtn = $("food-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Adding…";
  try {
    await api("/log/from_search", {
      method: "POST",
      body: {
        name,
        calories_per_100g: density,
        grams: weight,
      },
    });
    $("food-form").reset();
    updateFoodPreview();
    await loadDashboard();
  } catch (err) {
    if (err.message !== "__unauthorized__") setAppError(err.message || "Could not save that food.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Add Food";
  }
});

// ---------- startup ----------
(function init() {
  if (getToken()) {
    showAppView();
  } else {
    showAuthView();
  }
})();
