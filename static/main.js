// Page plumbing only: tabs, copy buttons and starting Python.
// All IP maths lives in ipcalc/core.py and the page logic in static/app.py.

const PYTHON_FILES = {
  "ipcalc/__init__.py": "ipcalc/__init__.py",
  "ipcalc/core.py": "ipcalc/core.py",
  "static/app.py": "app.py",
};

// ---------- tabs ----------
const tabs = document.querySelectorAll("nav button");
function showTab(name) {
  tabs.forEach((t) => t.setAttribute("aria-selected", t.dataset.tab === name));
  document.querySelectorAll("[data-pane]").forEach((p) => (p.hidden = p.dataset.pane !== name));
}
tabs.forEach((t) =>
  t.addEventListener("click", () => {
    showTab(t.dataset.tab);
    history.replaceState(null, "", "#" + t.dataset.tab);
  })
);
const fromHash = location.hash.slice(1);
if ([...tabs].some((t) => t.dataset.tab === fromHash)) showTab(fromHash);

// ---------- theme: Auto (follow the device) -> Light -> Dark ----------
const themeButton = document.getElementById("theme");
const THEMES = ["auto", "light", "dark"];
const THEME_NAMES = { auto: "Auto", light: "Light", dark: "Dark" };
function setTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  themeButton.textContent = THEME_NAMES[theme];
  themeButton.setAttribute("aria-label", `Theme: ${theme === "auto" ? "automatic" : theme}. Click to change.`);
  try {
    if (theme === "auto") localStorage.removeItem("theme");
    else localStorage.setItem("theme", theme);
  } catch {}
}
setTheme(document.documentElement.dataset.theme || "auto");
themeButton.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme || "auto";
  setTheme(THEMES[(THEMES.indexOf(current) + 1) % THEMES.length]);
});

// ---------- copy ----------
async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
document.addEventListener("click", async (e) => {
  const button = e.target.closest(".copy");
  if (!button) return;
  button.textContent = (await copy(button.dataset.v)) ? "copied" : "select it";
  setTimeout(() => (button.textContent = "copy"), 1200);
});
const out = document.getElementById("b-out");
const msg = document.getElementById("b-msg");
document.getElementById("b-copy").addEventListener("click", async () => {
  msg.textContent = (await copy(out.dataset.tsv || "")) ? "Copied. Paste it into Word or Excel." : "Copy was blocked; select the table instead.";
});
document.getElementById("b-csv").addEventListener("click", async () => {
  msg.textContent = (await copy(out.dataset.csv || "")) ? "CSV copied." : "Copy was blocked; select the table instead.";
});

// ---------- Python ----------
async function startPython() {
  const status = document.getElementById("status");
  try {
    const pyodide = await loadPyodide();
    pyodide.FS.mkdirTree("/home/pyodide/ipcalc");
    for (const [url, path] of Object.entries(PYTHON_FILES)) {
      const response = await fetch(url, { cache: "no-cache" });
      if (!response.ok) throw new Error(`Could not load ${url}`);
      pyodide.FS.writeFile(`/home/pyodide/${path}`, await response.text());
    }
    pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide'); import app; app.start()");
    status.classList.add("ready");
  } catch (error) {
    console.error(error);
    status.textContent = "Python failed to load. Check your connection and reload the page.";
    status.classList.add("failed");
  }
}
startPython();
