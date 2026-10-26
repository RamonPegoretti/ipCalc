// Page plumbing only: tabs, copy buttons and starting Python.
// All IP maths lives in ipcalc/core.py and the page logic in static/app.py.

const PYTHON_FILES = {
  "ipcalc/__init__.py": "ipcalc/__init__.py",
  "ipcalc/core.py": "ipcalc/core.py",
  "ipcalc/ipv6.py": "ipcalc/ipv6.py",
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
  themeButton.innerHTML = `Theme <b>${THEME_NAMES[theme]}</b>`;
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

// ---------- the slash on the Subnet info bit ruler ----------
// Dragging (or arrow keys) picks a prefix length; app.py writes it into the mask box.
const ruler = document.getElementById("c-ruler");
function sendPrefix(prefix) {
  const now = Number(ruler.getAttribute("aria-valuenow"));
  prefix = Math.max(0, Math.min(32, prefix));
  if (Number.isNaN(now) || prefix === now) return;
  ruler.dispatchEvent(new CustomEvent("setprefix", { detail: prefix }));
}
function prefixAt(x, y) {
  // The slash goes to the cell edge nearest the pointer, so it also works when octets wrap on phones.
  let best = null;
  let bestDistance = Infinity;
  ruler.querySelectorAll(".cell").forEach((cell) => {
    const r = cell.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const distance = Math.hypot(x - cx, (y - (r.top + r.height / 2)) * 1.5);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = { index: Number(cell.dataset.i), cx };
    }
  });
  return best && (x < best.cx ? best.index : best.index + 1);
}
ruler.addEventListener("pointerdown", (e) => {
  ruler.setPointerCapture(e.pointerId);
  ruler.classList.add("drag");
  const p = prefixAt(e.clientX, e.clientY);
  if (p !== null) sendPrefix(p);
});
ruler.addEventListener("pointermove", (e) => {
  if (!ruler.classList.contains("drag")) return;
  const p = prefixAt(e.clientX, e.clientY);
  if (p !== null) sendPrefix(p);
});
["pointerup", "pointercancel"].forEach((type) => ruler.addEventListener(type, () => ruler.classList.remove("drag")));
ruler.addEventListener("keydown", (e) => {
  const now = Number(ruler.getAttribute("aria-valuenow"));
  const moves = { ArrowLeft: now - 1, ArrowDown: now - 1, ArrowRight: now + 1, ArrowUp: now + 1, Home: 0, End: 32 };
  if (!(e.key in moves)) return;
  e.preventDefault();
  sendPrefix(moves[e.key]);
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
  button.textContent = (await copy(button.dataset.v)) ? "Copied" : "Select it";
  setTimeout(() => (button.textContent = "Copy"), 1200);
});
// Buttons with data-table="<id>" copy that table as tab-separated text (pastes
// into Word/Excel as a table) or, with data-format="csv", as CSV.
document.addEventListener("click", async (e) => {
  const button = e.target.closest("[data-table]");
  if (!button) return;
  const out = document.getElementById(button.dataset.table);
  const csv = button.dataset.format === "csv";
  const ok = await copy((csv ? out.dataset.csv : out.dataset.tsv) || "");
  button.parentElement.querySelector(".copy-msg").textContent = ok
    ? csv ? "CSV copied." : "Copied. Paste it into Word or Excel."
    : "Copy was blocked; select the table instead.";
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
