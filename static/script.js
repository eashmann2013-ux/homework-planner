const SUBJECT_LABEL = {
  math: "Math",
  science: "Science",
  language_arts: "Language Arts",
  google_classroom: "Google Classroom",
};

const STORAGE_KEY = "homeworkPlannerTeachers"; // { math: "id", science: "id", language_arts: "id" }

const state = {
  subject: "all",
  homework: { math: [], science: [], language_arts: [], google_classroom: [] },
  today: null,
  classroomConnected: false,
  classroomConfigured: true,
  teacherOptions: { math: [], science: [], language_arts: [] },
  selectedTeachers: { math: "", science: "", language_arts: "" },
};

const els = {
  status: document.getElementById("statusLine"),
  changeTeachersBtn: document.getElementById("changeTeachersBtn"),
  pickerSection: document.getElementById("pickerSection"),
  mathPicker: document.getElementById("mathPicker"),
  sciencePicker: document.getElementById("sciencePicker"),
  laPicker: document.getElementById("laPicker"),
  savePickerBtn: document.getElementById("savePickerBtn"),
  pickerMsg: document.getElementById("pickerMsg"),
  appContent: document.getElementById("appContent"),
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

// ---------------------------------------------------------------------------
// Teacher selection (localStorage)
// ---------------------------------------------------------------------------
function loadSavedTeachers() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && (parsed.math || parsed.science || parsed.language_arts)) return parsed;
    return null;
  } catch (e) {
    return null;
  }
}

function saveTeachers(selection) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selection));
}

function populatePicker(select, options, selectedId) {
  const placeholder = select.querySelector("option[value='']");
  select.innerHTML = "";
  if (placeholder) select.appendChild(placeholder);
  options.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.name} — ${t.course}`;
    if (t.id === selectedId) opt.selected = true;
    select.appendChild(opt);
  });
}

async function showPicker() {
  els.appContent.hidden = true;
  els.pickerSection.hidden = false;
  els.changeTeachersBtn.hidden = true;
  els.status.textContent = "Pick your teachers to get started.";

  if (!state.teacherOptions.math.length && !state.teacherOptions.science.length) {
    try {
      const res = await fetch("/api/teachers");
      state.teacherOptions = await res.json();
    } catch (e) {
      els.status.textContent = "Couldn't load the teacher list — try refreshing the page.";
      return;
    }
  }

  const saved = loadSavedTeachers() || {};
  populatePicker(els.mathPicker, state.teacherOptions.math, saved.math);
  populatePicker(els.sciencePicker, state.teacherOptions.science, saved.science);
  populatePicker(els.laPicker, state.teacherOptions.language_arts, saved.language_arts);
}

function hidePicker() {
  els.pickerSection.hidden = true;
  els.appContent.hidden = false;
  els.changeTeachersBtn.hidden = false;
}

els.savePickerBtn.addEventListener("click", () => {
  const selection = {
    math: els.mathPicker.value,
    science: els.sciencePicker.value,
    language_arts: els.laPicker.value,
  };
  if (!selection.math && !selection.science && !selection.language_arts) {
    els.pickerMsg.hidden = false;
    return;
  }
  els.pickerMsg.hidden = true;
  saveTeachers(selection);
  state.selectedTeachers = selection;
  hidePicker();
  loadData(false);
});

els.changeTeachersBtn.addEventListener("click", () => {
  showPicker();
});

// ---------------------------------------------------------------------------
// Homework display (same as before, now driven by selectedTeachers)
// ---------------------------------------------------------------------------
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
  const onGamesTab = state.subject === "games";
  const onMusicTab = state.subject === "music";
  const needsConnect = onClassroomTab && !state.classroomConnected;

  document.getElementById("gamesSection").hidden = !onGamesTab;
  document.getElementById("musicSection").hidden = !onMusicTab;

  if (!onGamesTab && window.TetrisGame) {
    window.TetrisGame.stop();
  }

  if (onMusicTab) {
    updateMusicEmbed();
  }

  if (onGamesTab || onMusicTab) {
    els.todaySection.hidden = true;
    els.upcomingList.innerHTML = "";
    els.emptyMsg.hidden = true;
    els.classroomConnect.hidden = true;
    els.disconnectBtn.hidden = true;
    document.getElementById("upcomingSection").hidden = true;
    return;
  }
  document.getElementById("upcomingSection").hidden = false;

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

function buildQuery(extra) {
  const params = new URLSearchParams();
  if (state.selectedTeachers.math) params.set("math_teacher", state.selectedTeachers.math);
  if (state.selectedTeachers.science) params.set("science_teacher", state.selectedTeachers.science);
  if (state.selectedTeachers.language_arts) params.set("language_arts_teacher", state.selectedTeachers.language_arts);
  if (extra) Object.entries(extra).forEach(([k, v]) => params.set(k, v));
  return params.toString();
}

async function loadData(force) {
  els.status.textContent = force ? "Checking your teachers' sites again…" : "Checking your teachers' sites…";
  els.refreshBtn.disabled = true;
  try {
    const query = buildQuery();
    const url = (force ? "/api/refresh" : "/api/homework") + (query ? "?" + query : "");
    const res = await fetch(url, { method: force ? "POST" : "GET" });
    const data = await res.json();
    state.homework = data.homework;
    state.today = data.today;
    state.classroomConnected = data.classroom_connected;
    state.classroomConfigured = data.classroom_configured;
    if (data.fetched_at) {
      const fetchedAt = new Date(data.fetched_at);
      els.lastChecked.textContent = "Last checked " + fetchedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    els.status.textContent = "Here's what's due.";
    render();
  } catch (err) {
    els.status.textContent = "Couldn't load homework right now — try Refresh.";
  } finally {
    els.refreshBtn.disabled = false;
  }
}

function updateMusicEmbed() {
  const stationSelect = document.getElementById("musicStation");
  const frame = document.getElementById("musicFrame");
  const videoId = stationSelect.value;
  const desiredSrc = `https://www.youtube.com/embed/${videoId}?autoplay=1`;
  if (!frame.src.includes(videoId)) {
    frame.src = desiredSrc;
  }
}

document.getElementById("musicStation").addEventListener("change", updateMusicEmbed);

document.getElementById("tetrisStartBtn").addEventListener("click", () => {
  if (window.TetrisGame) window.TetrisGame.start();
});

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
  const valid = ["all", "math", "science", "language_arts", "google_classroom", "games", "music"];
  if (!requested || !valid.includes(requested)) return;

  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  const btn = document.querySelector(`.tab[data-subject="${requested}"]`);
  if (btn) btn.classList.add("active");
  state.subject = requested;

  const cleanUrl = window.location.pathname;
  window.history.replaceState({}, "", cleanUrl);
}

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------
(async function start() {
  const saved = loadSavedTeachers();
  if (!saved) {
    await showPicker();
    return;
  }
  state.selectedTeachers = { math: saved.math || "", science: saved.science || "", language_arts: saved.language_arts || "" };
  hidePicker();
  applyInitialTab();
  loadData(false);
})();
