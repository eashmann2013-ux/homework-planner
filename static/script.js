const SUBJECT_LABEL = {
  math: "Math",
  science: "Science",
  language_arts: "Language Arts",
  google_classroom: "Google Classroom",
};

const state = {
  subject: "all",
  homework: { math: [], science: [], language_arts: [], google_classroom: [] },
  today: null,
  classroomConnected: false,
  classroomConfigured: true,
};

const els = {
  status: document.getElementById("statusLine"),
  tabs: document.getElementById("tabs"),
  refreshBtn: document.getElementById("refreshBtn"),
  todaySection: document.getElementById("todaySection"),
  todayList: document.getElementById("todayList"),
  upcomingHeading: document.getElementById("upcomingHeading"),
  upcomingList: document.getElementById("upcomingList"),
  emptyMsg: document.getElementById("emptyMsg"),
  lastChecked: document.getElementById("lastChecked"),
  classroomConnect: document.getElementById("classroomConnect"),
  classroomConnectMsg: document.getElementById("classroomConnectMsg"),
  disconnectBtn: document.getElementById("disconnectBtn"),
};

function formatDayLabel(isoDate, todayIso) {
  if (!isoDate) return "No date";
  const d = new Date(isoDate + "T00:00:00");
  const today = new Date(todayIso + "T00:00:00");
  const diffDays = Math.round((d - today) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays === -1) return "Yesterday";
  const opts = { weekday: "short", month: "short", day: "numeric" };
  return d.toLocaleDateString(undefined, opts);
}

function allEntries() {
  const subjects = state.subject === "all"
    ? ["math", "science", "language_arts", "google_classroom"]
    : [state.subject];
  let entries = [];
  subjects.forEach((s) => {
    entries = entries.concat(state.homework[s] || []);
  });
  return entries;
}

function entryRow(entry, { showTag }) {
  const li = document.createElement("li");
  li.className = "entry";

  const dateCol = document.createElement("div");
  dateCol.className = "entry-date";
  dateCol.textContent = formatDayLabel(entry.date || entry.posted, state.today);

  const body = document.createElement("div");
  body.className = "entry-body";

  if (showTag) {
    const tag = document.createElement("span");
    tag.className = `entry-tag ${entry.subject}`;
    tag.textContent = SUBJECT_LABEL[entry.subject];
    body.appendChild(tag);
  }

  const text = document.createElement("span");
  text.className = "entry-text";
  text.textContent = entry.text;
  body.appendChild(text);

  li.appendChild(dateCol);
  li.appendChild(body);
  return li;
}

function render() {
  const onClassroomTab = state.subject === "google_classroom";
  const needsConnect = onClassroomTab && !state.classroomConnected;

  if (needsConnect) {
    els.classroomConnect.hidden = false;
    els.classroomConnectMsg.textContent = state.classroomConfigured
      ? "See homework from Google Classroom here too, alongside your teacher sites."
      : "Google Classroom isn't set up on this server yet.";
    document.getElementById("connectBtn").style.display = state.classroomConfigured ? "inline-block" : "none";
    els.todaySection.hidden = true;
    els.upcomingList.innerHTML = "";
    els.emptyMsg.hidden = true;
    els.disconnectBtn.hidden = true;
    return;
  }
  els.classroomConnect.hidden = true;
  els.disconnectBtn.hidden = !onClassroomTab || !state.classroomConnected;

  const showTag = state.subject === "all";
  const entries = allEntries();

  const dueToday = entries.filter((e) => e.date === state.today);
  const rest = entries.filter((e) => e.date !== state.today);

  // Sort newest-posted first, so the most recently added homework shows at the top
  // (falls back to due date if an entry has no posted date)
  rest.sort((a, b) => {
    const aKey = a.posted || a.date || "";
    const bKey = b.posted || b.date || "";
    return bKey.localeCompare(aKey);
  });

  els.todayList.innerHTML = "";
  if (dueToday.length) {
    els.todaySection.hidden = false;
    dueToday.forEach((e) => els.todayList.appendChild(entryRow(e, { showTag })));
  } else {
    els.todaySection.hidden = true;
  }

  els.upcomingHeading.textContent = state.subject === "all" ? "Everything" : SUBJECT_LABEL[state.subject];
  els.upcomingList.innerHTML = "";
  if (rest.length === 0) {
    els.emptyMsg.hidden = false;
  } else {
    els.emptyMsg.hidden = true;
    rest.forEach((e) => els.upcomingList.appendChild(entryRow(e, { showTag })));
  }
}

async function loadData(force) {
  els.status.textContent = force ? "Checking your teachers' sites again…" : "Checking your teachers' sites…";
  els.refreshBtn.disabled = true;
  try {
    const res = await fetch(force ? "/api/refresh" : "/api/homework", {
      method: force ? "POST" : "GET",
    });
    const data = await res.json();
    state.homework = data.homework;
    state.today = data.today;
    state.classroomConnected = data.classroom_connected;
    state.classroomConfigured = data.classroom_configured;
    if (data.classroom_error) {
      console.warn("Classroom error:", data.classroom_error);
    }
    const fetchedAt = new Date(data.fetched_at);
    els.lastChecked.textContent = "Last checked " + fetchedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    els.status.textContent = "Here's what's due.";
    render();
  } catch (err) {
    els.status.textContent = "Couldn't load homework right now — try Refresh.";
  } finally {
    els.refreshBtn.disabled = false;
  }
}

els.tabs.addEventListener("click", (evt) => {
  const btn = evt.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  btn.classList.add("active");
  state.subject = btn.dataset.subject;
  render();
});

els.refreshBtn.addEventListener("click", () => loadData(true));

els.disconnectBtn.addEventListener("click", async () => {
  await fetch("/disconnect-classroom", { method: "POST" });
  state.classroomConnected = false;
  render();
});

function applyInitialTab() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("tab");
  const valid = ["all", "math", "science", "language_arts", "google_classroom"];
  if (!requested || !valid.includes(requested)) return;

  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  const btn = document.querySelector(`.tab[data-subject="${requested}"]`);
  if (btn) btn.classList.add("active");
  state.subject = requested;

  // clean the URL so refreshing later doesn't keep forcing this tab
  const cleanUrl = window.location.pathname;
  window.history.replaceState({}, "", cleanUrl);
}

applyInitialTab();
loadData(false);
