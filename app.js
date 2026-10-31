let token = "";
let selected = "";
let tabsSignature = "";
let lastSize = "";
let refreshing = false;

const $ = selector => document.querySelector(selector);
const tabs = $("#tabs");
const output = $("#output");
const message = $("#message");

async function init() {
  try {
    token = (await fetch("/api/session").then(response => response.json())).token;
    await refresh();
    setInterval(refresh, 700);
  } catch {
    say("Could not connect to the local service. Start server.py and reload.", true);
  }
}

function say(text, error = false) {
  message.textContent = text;
  message.classList.toggle("error", error);
}

function request(url, options = {}) {
  options.headers = { ...(options.headers || {}), "X-Console-Request": token };
  if (options.body && typeof options.body === "object") {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  return fetch(url, options);
}

function safe(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function viewTransition(update) {
  if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.startViewTransition(update);
  } else update();
}

async function refresh() {
  if (refreshing || !token) return;
  refreshing = true;
  try {
    const response = await request("/api/sessions");
    if (!response.ok) throw Error("Local session check failed");
    const data = await response.json();
    render(data.sessions);
    $("#slot-count").textContent = `${data.sessions.filter(session => session.state === "running").length} / ${data.limits.active} active`;
  } catch (error) {
    say(error.message, true);
  } finally {
    refreshing = false;
  }
}

function render(sessions) {
  if (!sessions.some(session => session.id === selected)) selected = sessions.at(-1)?.id || "";
  const signature = JSON.stringify([selected, sessions.map(session => [session.id, session.label, session.profile_name, session.state])]);
  if (signature !== tabsSignature) {
    const focusedId = document.activeElement?.dataset?.session || "";
    tabs.innerHTML = sessions.map(session => `<button class="tab ${session.id === selected ? "active" : ""}" type="button" role="tab" aria-selected="${session.id === selected}" data-session="${session.id}"><span class="tab-name">${safe(session.label)}</span><span class="tab-meta"><i class="dot ${session.state.replaceAll(" ", "-")}"></i>${safe(session.profile_name)} · ${safe(session.state)}</span></button>`).join("");
    tabs.querySelectorAll("[data-session]").forEach(button => {
      button.onclick = () => viewTransition(() => {
        selected = button.dataset.session;
        render(sessions);
        sendResize();
      });
    });
    tabsSignature = signature;
    if (focusedId) tabs.querySelector(`[data-session="${focusedId}"]`)?.focus();
  }
  const session = sessions.find(item => item.id === selected);
  $("#empty").classList.toggle("hidden", Boolean(session));
  $("#view").classList.toggle("hidden", !session);
  if (!session) return;
  $("#selected-profile").textContent = session.profile_name.toUpperCase();
  $("#selected-label").textContent = session.label;
  $("#pid").textContent = session.pid;
  $("#cwd").textContent = session.cwd;
  $("#state").textContent = session.state;
  $("#timeout").textContent = `${session.timeout}s`;
  $("#term-status").textContent = session.state.toUpperCase();
  $("#term-size").textContent = `${session.rows} × ${session.cols}`;
  if (output.textContent !== session.output) {
    output.textContent = session.output;
    output.scrollTop = output.scrollHeight;
  }
  $("#stop").disabled = session.state !== "running";
  $("#stop").textContent = session.state === "running" ? "Stop session" : "Session ended";
}

tabs.addEventListener("keydown", event => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const buttons = [...tabs.querySelectorAll("[role=tab]")];
  if (!buttons.length) return;
  const index = buttons.indexOf(document.activeElement);
  const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
  event.preventDefault();
  buttons[next].focus();
  buttons[next].click();
});

$("#launch-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    const response = await request("/api/sessions", {
      method: "POST",
      body: { profile: $("#profile").value, label: $("#label").value, timeout: Number($("#time-limit").value) }
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error);
    selected = result.session.id;
    tabsSignature = "";
    $("#label").value = "";
    say(`${result.session.profile_name} started in an isolated runtime.`);
    await refresh();
  } catch (error) {
    say(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("#stop").addEventListener("click", async () => {
  if (!selected) return;
  const button = $("#stop");
  button.disabled = true;
  try {
    const response = await request(`/api/sessions/${selected}/stop`, { method: "POST", body: {} });
    const result = await response.json();
    if (!response.ok) throw Error(result.error);
    say("Session stopped. Its output remains available in this workspace.");
    await refresh();
  } catch (error) {
    say(error.message, true);
  }
});

$("#settings-toggle").onclick = () => {
  const panel = $("#settings");
  panel.classList.toggle("hidden");
  $("#settings-toggle").setAttribute("aria-expanded", String(!panel.classList.contains("hidden")));
};
$("#settings-close").onclick = () => {
  $("#settings").classList.add("hidden");
  $("#settings-toggle").setAttribute("aria-expanded", "false");
};

function sendResize(rect = output.getBoundingClientRect()) {
  if (!selected || !rect.width || !rect.height) return;
  const cols = Math.max(30, Math.min(160, Math.floor(rect.width / 7.4)));
  const rows = Math.max(10, Math.min(80, Math.floor(rect.height / 20)));
  const key = `${selected}/${rows}/${cols}`;
  if (key === lastSize) return;
  lastSize = key;
  request(`/api/sessions/${selected}/resize`, { method: "POST", body: { rows, cols } }).catch(() => {});
}

new ResizeObserver(entries => sendResize(entries[0].contentRect)).observe(output);
init();
