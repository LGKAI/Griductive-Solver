/* Casebook GUI. The browser only ever sees the public state sent by the server. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const S = {
  puzzles: [],
  selectedFile: null,
  currentFile: null,
  view: null,          // latest public state from the server
  boardGame: null,     // game id the board DOM was built for
  cards: new Map(),    // cell -> card element
  known: new Set(),    // cells known at the last render
  selectedClue: null,  // clue id (owner cell) being highlighted
  hint: null,          // {cell, support, verdict, revealed}
  analysis: null,      // last entailment analysis (solver view)
  popCell: null,
  auto: false,
  busy: false,
  genSize: 4,
  epoch: 0,            // bumped on load/restart: responses from an older epoch are dropped
  celebrateTimer: null,
  modalMode: "won",    // "won" (case closed) or "lost" (game over)
};

/* ------------------------------------------------------------------ utils */
function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  let res;
  try {
    res = await fetch(path, opts);
  } catch (err) {
    throw new Error("Cannot reach the Casebook server. Is main.py still running?");
  }
  let data = null;
  try { data = await res.json(); } catch { /* ignore */ }
  if (!res.ok) throw new Error((data && data.error) || `${res.status} ${res.statusText}`);
  return data;
}

function nameOf(cell) {
  return (S.view && S.view.names[cell]) || cell;
}

/* Status words. The server and the logic always say criminal/innocent; a character
   theme may rename them for display (football: red card / fair play). */
const DEFAULT_TERMS = {
  criminal: { label: "Criminal", adj: "a criminal", one: "criminal", many: "criminals" },
  innocent: { label: "Innocent", adj: "innocent", one: "innocent", many: "innocents" },
};
const terms = () => (S.view && S.view.terms) || DEFAULT_TERMS;
/** Display word for a status/verdict ("criminal", "INNOCENT", …); form: label | adj | one | many. */
function term(status, form = "label") {
  const key = String(status).toLowerCase() === "criminal" ? "criminal" : "innocent";
  const t = terms()[key] || DEFAULT_TERMS[key];
  return t[form] || DEFAULT_TERMS[key][form];
}

const CLUE_WORDS = { "is a criminal": ["is ", "criminal", "adj"], "is innocent": ["is ", "innocent", "adj"],
  criminals: ["", "criminal", "many"], innocents: ["", "innocent", "many"], criminal: ["", "criminal", "one"], innocent: ["", "innocent", "one"] };

/** Clue text with theme words; `wrap(status, word)` styles each status word. */
function themeClue(text, wrap = (_, w) => w, plain = (x) => x) {
  return String(text).split(/(\bis a criminal\b|\bis innocent\b|\bcriminals\b|\binnocents\b|\bcriminal\b|\binnocent\b)/i).map((seg) => {
    const hit = CLUE_WORDS[seg.toLowerCase()];
    return hit ? plain(hit[0]) + wrap(hit[1], term(hit[1], hit[2])) : plain(seg);
  }).join("");
}

/** Render clue text: {B2} tokens become names; status words get colour and theme wording. */
function formatClue(text) {
  const parts = String(text).split(/(\{[A-J][0-9]{1,2}\})/);
  return parts.map((part) => {
    const m = /^\{([A-J][0-9]{1,2})\}$/.exec(part);
    if (m) return `<span class="ref" data-cell="${m[1]}">${esc(nameOf(m[1]))}</span>`;
    return themeClue(part, (s, w) => `<span class="${s === "criminal" ? "w-crim" : "w-inn"}">${esc(w)}</span>`, esc);
  }).join("");
}

/** Clue text as plain words (aria labels). */
function plainClue(text) {
  return themeClue(String(text).replace(/\{([A-J][0-9]{1,2})\}/g, (_, c) => nameOf(c)));
}

/* --------------------------------------------------------------- avatars */
const SKIN = ["#f6d3b3", "#eab98f", "#d39a6a", "#b57a4c", "#8d5a36", "#f1c8a4", "#c98c5e"];
const HAIR = ["#2b2220", "#4a3326", "#7a4b2a", "#b9773e", "#d8b06a", "#8c8c94", "#5a2d40", "#1f2b46"];
const BG = ["#c7d2fe", "#fde68a", "#bbf7d0", "#fecaca", "#bae6fd", "#ddd6fe", "#fed7aa", "#a7f3d0", "#fbcfe8"];
const SHIRT = ["#4f46e5", "#0f766e", "#b45309", "#be123c", "#334155", "#7c3aed", "#0369a1", "#15803d", "#a16207"];
/* skin tones used by the themed casts (index 0-6, light to deep) */
const TONE = ["#f8d9be", "#f0c39c", "#dca77c", "#c68a5c", "#a86d43", "#8a5434", "#6e3f26"];
const avatarCache = new Map();
let avatarSeq = 0;

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

/** Spec values come from the server's fixed cast lists; still, only known values reach the SVG. */
const col = (c, fallback) => (typeof c === "string" && /^#[0-9a-f]{6}$/i.test(c) ? c : fallback);
const pick = (value, allowed, fallback) => (allowed.includes(value) ? value : fallback);
const tone = (i) => TONE[Number.isInteger(i) && i >= 0 && i < TONE.length ? i : 1];

/**
 * Portrait of a character. `person` is a cell object from the server ({name, avatar}).
 * `avatar` is the football theme's spec (a photo, or a drawn kit when the photo is missing);
 * null means the case file's own character, drawn from its name.
 */
function avatar(person, status) {
  const spec = person && person.avatar && typeof person.avatar === "object" ? person.avatar : null;
  const name = String((person && person.name) || "?");
  const key = `${spec ? JSON.stringify(spec) : name}|${status || ""}`;
  if (!avatarCache.has(key)) {
    let svg;
    if (spec && typeof spec.photo === "string" && /^portraits\/[a-z]+\/[a-z0-9-]+\.jpg$/.test(spec.photo)) svg = photoAvatar(spec, status);
    else if (spec && spec.kind === "football") svg = footballAvatar(spec, status);
    else svg = classicAvatar(name, status);
    avatarCache.set(key, svg);
  }
  return avatarCache.get(key).replaceAll("__CLIP__", `av${++avatarSeq}`);
}

function frame(bg, body, defs = "") {
  return `<svg viewBox="0 0 100 100" class="avatar" aria-hidden="true">
    <circle cx="50" cy="50" r="48" fill="${bg}"/>
    <clipPath id="__CLIP__"><circle cx="50" cy="50" r="48"/></clipPath>${defs}
    <g clip-path="url(#__CLIP__)">${body}</g></svg>`;
}

/* Real photo (web/portraits/, see CREDITS.md) with the same status badges as the drawings. */
function photoAvatar(a, status) {
  let badge = "";
  if (status === "criminal") {
    badge = a.kind === "football"
      ? `<g transform="rotate(14 80 30)"><rect x="72" y="17" width="15" height="20" rx="2.4" fill="#e11d48" stroke="#fff" stroke-width="1.6"/></g>`
      : `<circle cx="79" cy="25" r="9" fill="#e11d48" stroke="#fff" stroke-width="1.6"/><path d="M79 20v6" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><circle cx="79" cy="30" r="1.4" fill="#fff"/>`;
  } else if (status === "innocent") {
    badge = `<circle cx="79" cy="25" r="8" fill="#16a34a" stroke="#fff" stroke-width="1.6"/><path d="M75.5 25l2.6 2.6 5-5.2" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
  }
  const ring = status === "criminal" ? `<circle cx="50" cy="50" r="46.5" fill="none" stroke="#e11d48" stroke-width="3"/>`
    : status === "innocent" ? `<circle cx="50" cy="50" r="46.5" fill="none" stroke="#16a34a" stroke-width="3"/>` : "";
  return `<svg viewBox="0 0 100 100" class="avatar photo" aria-hidden="true">
    <circle cx="50" cy="50" r="48" fill="${col(a.bg, "#e5e7eb")}"/>
    <clipPath id="__CLIP__"><circle cx="50" cy="50" r="48"/></clipPath>
    <image href="${a.photo}" x="2" y="2" width="96" height="96" preserveAspectRatio="xMidYMid slice" clip-path="url(#__CLIP__)"/>
    ${ring}${badge}</svg>`;
}

function classicAvatar(name, status) {
  const h = hash(name);
  const skin = SKIN[h % SKIN.length], hair = HAIR[(h >>> 3) % HAIR.length];
  const bg = BG[(h >>> 6) % BG.length], shirt = SHIRT[(h >>> 10) % SHIRT.length];
  const style = (h >>> 14) % 6, extra = (h >>> 17) % 5;
  let back = "", front = "";
  switch (style) {
    case 0: front = `<path d="M30 44c0-14 9-22 20-22s20 8 20 22c-4-7-10-10-20-10s-16 3-20 10z" fill="${hair}"/>`; break;
    case 1: back = `<path d="M27 46c0-17 10-26 23-26s23 9 23 26v22H27z" fill="${hair}"/>`;
            front = `<path d="M31 42c2-11 9-17 19-17s17 6 19 17c-7-5-12-7-19-7s-12 2-19 7z" fill="${hair}"/>`; break;
    case 2: back = `<circle cx="50" cy="20" r="8" fill="${hair}"/>`;
            front = `<path d="M30 43c0-13 9-20 20-20s20 7 20 20c-5-6-11-8-20-8s-15 2-20 8z" fill="${hair}"/>`; break;
    case 3: front = [[34, 32], [42, 26], [50, 24], [58, 26], [66, 32], [31, 40], [69, 40]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="7.5" fill="${hair}"/>`).join(""); break;
    case 4: front = `<path d="M31 41c1-12 9-18 19-18 6 0 12 2 16 7l-26 9z" fill="${hair}"/>`; break;
    default: front = `<path d="M29 40c3-12 11-17 21-17s18 5 21 17l-6-3-4 4-5-5-6 5-6-5-5 5-4-4z" fill="${hair}"/>`;
  }
  let acc = "";
  if (extra === 1) acc = `<g fill="none" stroke="#1e1b2e" stroke-width="2"><circle cx="42" cy="48" r="5.5"/><circle cx="58" cy="48" r="5.5"/><path d="M47.5 48h5"/></g>`;
  if (extra === 2) acc = `<path d="M28 33c4-10 12-15 22-15s18 5 22 15z" fill="#1f2937"/><rect x="24" y="31" width="52" height="5" rx="2.5" fill="#111827"/>`;
  let mood = `<path d="M44 58c3.5 3 8.5 3 12 0" fill="none" stroke="#5b2c25" stroke-width="2.2" stroke-linecap="round"/>`;
  let mask = "";
  if (status === "criminal") {
    mask = `<path d="M33 44h34c1 0 2 1 2 2v3c0 3-3 5-6 5h-5l-3-3h-6l-3 3h-5c-3 0-6-2-6-5v-3c0-1 1-2 2-2z" fill="#151320"/><circle cx="42.5" cy="48" r="2" fill="#fff"/><circle cx="57.5" cy="48" r="2" fill="#fff"/>`;
    mood = `<path d="M44 60c3.5-2 8.5-2 12 0" fill="none" stroke="#5b2c25" stroke-width="2.2" stroke-linecap="round"/>`;
  } else if (status === "innocent") {
    mood = `<path d="M43 57c4 5 10 5 14 0" fill="none" stroke="#5b2c25" stroke-width="2.4" stroke-linecap="round"/>`;
  }
  return frame(bg, `${back}
      <path d="M20 100c2-17 14-26 30-26s28 9 30 26z" fill="${shirt}"/>
      <rect x="44" y="62" width="12" height="13" rx="4" fill="${skin}"/>
      <ellipse cx="50" cy="48" rx="19" ry="21" fill="${skin}"/>
      <circle cx="40" cy="55" r="3.5" fill="#f08a7a" opacity=".35"/><circle cx="60" cy="55" r="3.5" fill="#f08a7a" opacity=".35"/>
      <circle cx="42.5" cy="48" r="2.3" fill="#2a1d1a"/><circle cx="57.5" cy="48" r="2.3" fill="#2a1d1a"/>
      ${mood}${front}${acc}${mask}`);
}

function luminance(hex) {
  const n = parseInt(hex.slice(1), 16);
  return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
}

/* Football: national-team kit with pattern and shirt number; a red card marks a proven criminal. */
function footballAvatar(a, status) {
  const kit = col(a.kit, "#1e3a8a"), trim = col(a.trim, "#f8fafc"), skin = tone(a.skin), hair = col(a.hairColor, "#2b2220");
  const pattern = pick(a.pattern, ["solid", "stripes", "hoops", "halves", "sash", "checks"], "solid");
  const style = pick(a.hair, ["buzz", "fade", "curly", "afro", "bun", "long", "slick", "mohawk", "bald"], "buzz");
  const facial = pick(a.facial, ["none", "beard", "stubble", "mustache"], "none");
  const extra = pick(a.extra, ["", "armband", "headband", "gloves"], "");
  const number = Number.isInteger(a.number) && a.number >= 0 && a.number < 100 ? a.number : 10;
  const shirt = "M12 100c1-17 14-27 38-27s37 10 38 27z";
  const stripes = {
    solid: "",
    stripes: [24, 37, 50, 63, 76].map((x) => `<rect x="${x - 3.5}" y="70" width="7" height="32" fill="${trim}"/>`).join(""),
    hoops: `<rect x="0" y="81" width="100" height="5" fill="${trim}"/><rect x="0" y="92" width="100" height="5" fill="${trim}"/>`,
    halves: `<rect x="50" y="70" width="50" height="32" fill="${trim}"/>`,
    sash: `<path d="M18 80l9-6 58 30H63z" fill="${trim}"/>`,
    checks: Array.from({ length: 40 }, (_, i) => [(i % 10) * 9 + 8, 70 + Math.floor(i / 10) * 9, i])
      .filter(([, , i]) => (i % 10 + Math.floor(i / 10)) % 2 === 0)
      .map(([x, y]) => `<rect x="${x}" y="${y}" width="9" height="9" fill="${trim}"/>`).join(""),
  }[pattern];
  const back = {
    afro: `<circle cx="50" cy="35" r="23" fill="${hair}"/>`,
    bun: `<circle cx="50" cy="20" r="6.5" fill="${hair}"/>`,
    long: `<path d="M29 42c0-15 9-23 21-23s21 8 21 23v20c-3 3-7 3-9 0V45H38v17c-2 3-6 3-9 0z" fill="${hair}"/>`,
  }[style] || "";
  const front = {
    buzz: `<path d="M32 40c0-12 8-19 18-19s18 7 18 19c-3-5-9-7-18-7s-15 2-18 7z" fill="${hair}" opacity=".85"/>`,
    fade: `<path d="M33 37c1-10 8-16 17-16s16 6 17 16c-5-3-10-4-17-4s-12 1-17 4z" fill="${hair}"/><path d="M32 40c0-2 .3-3 1-4M68 40c0-2-.3-3-1-4" stroke="${hair}" stroke-width="2" opacity=".5"/>`,
    curly: [[36, 31], [43, 26], [50, 24], [57, 26], [64, 31], [33, 38], [67, 38]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="6.5" fill="${hair}"/>`).join(""),
    afro: [[36, 28], [44, 24], [52, 23], [60, 25], [66, 31]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="7" fill="${hair}"/>`).join(""),
    bun: `<path d="M31 41c1-13 9-19 19-19s18 6 19 19c-5-6-11-8-19-8s-14 2-19 8z" fill="${hair}"/>`,
    long: `<path d="M31 42c1-13 9-20 19-20s18 7 19 20c-4-5-8-8-12-9l-7 4-7-4c-4 1-9 4-12 9z" fill="${hair}"/>`,
    slick: `<path d="M31 41c1-13 9-19 19-19 9 0 17 5 19 15-6-4-14-6-22-5-6 1-11 4-16 9z" fill="${hair}"/>`,
    mohawk: `<path d="M45 35c0-9 2-15 5-17 3 2 5 8 5 17z" fill="${hair}"/><path d="M33 40c0-6 3-10 7-12M67 40c0-6-3-10-7-12" stroke="${hair}" stroke-width="3" opacity=".35" fill="none"/>`,
    bald: `<ellipse cx="44" cy="31" rx="7" ry="3.5" fill="#fff" opacity=".28"/>`,
  }[style];
  const beard = {
    none: "",
    beard: `<path d="M32 49c0 14 8 21 18 21s18-7 18-21c-3 6-8 9-18 9s-15-3-18-9z" fill="${hair}"/><path d="M44 61c4 2 8 2 12 0" stroke="${skin}" stroke-width="2" fill="none" stroke-linecap="round"/>`,
    stubble: `<path d="M32 49c0 14 8 21 18 21s18-7 18-21c-3 6-8 9-18 9s-15-3-18-9z" fill="${hair}" opacity=".28"/>`,
    mustache: `<path d="M42 57.5c3-2.5 6-2.5 8-.6 2-1.9 5-1.9 8 .6-2.5 2-5.5 2.2-8 .9-2.5 1.3-5.5 1.1-8-.9z" fill="${hair}"/>`,
  }[facial];
  let mouth = `<path d="M45 61c3 2 7 2 10 0" fill="none" stroke="#5b2c25" stroke-width="2.1" stroke-linecap="round"/>`;
  let badge = "";
  if (status === "criminal") {
    mouth = `<path d="M45 63c3-2 7-2 10 0" fill="none" stroke="#5b2c25" stroke-width="2.1" stroke-linecap="round"/>`;
    badge = `<g transform="rotate(14 80 30)"><rect x="72" y="17" width="15" height="20" rx="2.4" fill="#e11d48" stroke="#fff" stroke-width="1.6"/></g>`;
  } else if (status === "innocent") {
    mouth = `<path d="M44 59.5c3 4.5 9 4.5 12 0z" fill="#7f1d1d"/>`;
    badge = `<circle cx="79" cy="25" r="8" fill="#16a34a" stroke="#fff" stroke-width="1.6"/><path d="M75.5 25l2.6 2.6 5-5.2" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
  }
  const extras = {
    "": "",
    armband: `<g transform="rotate(-28 23 88)"><rect x="15" y="85" width="16" height="6" rx="1.5" fill="#facc15"/><text x="23" y="90.2" text-anchor="middle" font-size="5.5" font-weight="800" font-family="Inter,Arial,sans-serif" fill="#1f2937">C</text></g>`,
    headband: `<rect x="31" y="33" width="38" height="4.5" rx="2" fill="${trim === "#f8fafc" ? "#e11d48" : trim}"/>`,
    gloves: `<ellipse cx="18" cy="90" rx="7" ry="8" fill="#f97316"/><ellipse cx="82" cy="90" rx="7" ry="8" fill="#f97316"/><path d="M14 88h8M78 88h8" stroke="#fff" stroke-width="1.6"/>`,
  }[extra];
  const defs = `<clipPath id="__CLIP__k"><path d="${shirt}"/></clipPath>`;
  // shirt number: dark on light kits, white with a dark outline otherwise (readable on any pattern)
  const lightKit = luminance(kit) > 0.55 && pattern === "solid";
  const numFill = lightKit ? "#111827" : "#fff", numStroke = lightKit ? "#fff" : "#111827";
  return frame(col(a.bg, "#bfdbfe"), `${back}
      <path d="${shirt}" fill="${kit}"/>
      <g clip-path="url(#__CLIP__k)">${stripes}</g>
      <rect x="44" y="60" width="12" height="15" rx="4" fill="${skin}"/>
      <path d="M40 74l10 9 10-9" fill="none" stroke="${trim === kit ? "#fff" : trim}" stroke-width="3" stroke-linejoin="round"/>
      <text x="50" y="94.5" text-anchor="middle" font-size="11" font-weight="800" font-family="Inter,Arial,sans-serif" fill="${numFill}" stroke="${numStroke}" stroke-width="1.6" paint-order="stroke">${number}</text>
      <circle cx="31.5" cy="49" r="4" fill="${skin}"/><circle cx="68.5" cy="49" r="4" fill="${skin}"/>
      <ellipse cx="50" cy="47" rx="18" ry="20.5" fill="${skin}"/>
      ${beard}
      <path d="M39 42.5l6-1M55 41.5l6 1" stroke="${hair === "#e2c27a" || hair === "#d8b06a" || hair === "#c9a46a" ? "#8a6a3a" : hair}" stroke-width="2" stroke-linecap="round"/>
      <circle cx="43" cy="47.5" r="2.3" fill="#231a17"/><circle cx="57" cy="47.5" r="2.3" fill="#231a17"/>
      ${mouth}${front}${extras}${badge}`, defs);
}

/* --------------------------------------------------------------- toasts */
function toast(kind, title, msg = "", ms = 3200) {
  const icons = { ok: "✓", warn: "?", bad: "✕", info: "i" };
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<div class="t-icon">${icons[kind] || "i"}</div><div><div class="t-title">${esc(title)}</div>${msg ? `<div class="t-msg">${msg}</div>` : ""}</div>`;
  const box = $("#toasts");
  box.appendChild(el);
  while (box.children.length > 4) box.firstChild.remove();
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, ms);
}

function banner(kind, icon, html) {
  const b = $("#banner");
  b.className = `banner ${kind}`;
  $("#bannerIcon").textContent = icon;
  $("#bannerBody").innerHTML = html;
  b.hidden = false;
  $("#stage").classList.add("has-banner");
}
function hideBanner() {
  $("#banner").hidden = true;
  $("#stage").classList.remove("has-banner");
}

function setLoading(on, text = "Working…") {
  S.loading = on;
  $("#loading").hidden = !on;
  $("#loadingText").textContent = text;
}

/* ---------------------------------------------------------- puzzle list */
async function loadPuzzleList() {
  try {
    const data = await api("/api/puzzles");
    S.puzzles = data.puzzles;
  } catch (err) {
    toast("bad", "Could not list puzzles", esc(err.message));
    S.puzzles = [];
  }
  if (!S.selectedFile && S.puzzles.length) S.selectedFile = S.puzzles[0].file;
  renderPuzzleList();
}

function renderPuzzleList() {
  const list = $("#puzzleList");
  $("#puzzleCount").textContent = `${S.puzzles.length} cases`;
  list.innerHTML = S.puzzles.map((p) => {
    const tag = p.expected !== "SOLVED" ? ` · <span class="w-crim">${esc(p.expected.toLowerCase())} case</span>` : (p.waves ? ` · ${p.waves} waves` : "");
    return `<button class="puzzle-item${p.file === S.selectedFile ? " selected" : ""}${p.file === S.currentFile ? " current" : ""}" data-file="${esc(p.file)}" role="option" aria-selected="${p.file === S.selectedFile}">
      <span class="pi-size s${esc(p.size)}">${esc(p.size)}×${esc(p.size)}</span>
      <span class="pi-body"><div class="pi-title">${esc(p.title)}</div><div class="pi-sub">${esc(p.file)}${tag}</div></span>
    </button>`;
  }).join("");
  list.querySelector(".current")?.scrollIntoView({ block: "nearest" });
}

/* ------------------------------------------------------------------ board */
function buildBoard(view) {
  const board = $("#board");
  const n = view.puzzle.size;
  board.style.setProperty("--n", n);
  board.className = `board n${n}`;
  board.innerHTML = "";
  S.cards.clear();
  S.known = new Set();
  board.appendChild(Object.assign(document.createElement("div"), { className: "axis corner" }));
  for (let c = 0; c < n; c++) {
    board.appendChild(Object.assign(document.createElement("div"), { className: "axis col", textContent: "ABCDEFGHIJ"[c], id: `axis-c${c}` }));
  }
  for (let r = 0; r < n; r++) {
    board.appendChild(Object.assign(document.createElement("div"), { className: "axis row", textContent: String(r + 1), id: `axis-r${r}` }));
    for (let c = 0; c < n; c++) {
      const info = view.cells[r * n + c];
      const card = document.createElement("div");
      card.className = "card";
      card.dataset.cell = info.cell;
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.innerHTML = `<div class="card-inner">
        <div class="face face-down">
          <span class="coord">${info.cell}</span>
          ${avatar(info)}
          <div class="name">${esc(info.name)}</div>
          <div class="prof">${esc(info.profession)}</div>
        </div>
        <div class="face face-up"></div>
      </div>`;
      board.appendChild(card);
      S.cards.set(info.cell, card);
    }
  }
  S.boardGame = view.game;
}

function renderFaceUp(card, info) {
  const clue = info.clue;
  card.querySelector(".face-up").innerHTML = `
    <span class="coord">${info.cell}</span>
    <span class="status-pill">${esc(term(info.status))}</span>
    <div class="up-head">${avatar(info, info.status)}<div class="who"><div class="name">${esc(info.name)}</div><div class="prof">${esc(info.profession)}</div></div></div>
    <div class="clue-box${clue ? "" : " none"}"><p>${clue ? formatClue(clue.text) : "No statement"}</p></div>`;
}

function updateBoard(view, { animate = true } = {}) {
  const fresh = [];
  for (const info of view.cells) {
    const card = S.cards.get(info.cell);
    if (!card) continue;
    const wasKnown = S.known.has(info.cell);
    card.classList.toggle("known", info.known);
    card.classList.toggle("criminal", info.status === "criminal");
    card.classList.toggle("innocent", info.status === "innocent");
    card.classList.toggle("initial", info.initial);
    card.classList.toggle("has-clue", Boolean(info.clue));
    const label = info.known ? `${info.name}, ${term(info.status)}${info.clue ? ": " + plainClue(info.clue.text) : ""}`
      : `${info.name}, ${info.profession}, unknown. Press Enter to give a verdict.`;
    card.setAttribute("aria-label", label);
    if (info.known && !wasKnown) {
      renderFaceUp(card, info);
      if (animate) fresh.push(card);
    }
    if (!info.known && wasKnown) card.querySelector(".face-up").innerHTML = "";
  }
  S.known = new Set(view.cells.filter((c) => c.known).map((c) => c.cell));
  for (const card of fresh) {
    card.classList.add("just-revealed");
    setTimeout(() => card.classList.remove("just-revealed"), 1500);
  }
  updateDeductionChips();
  updateHighlights();
}

function updateHighlights() {
  const board = $("#board");
  const view = S.view;
  for (const card of S.cards.values()) card.classList.remove("hl-counted", "hl-named", "selected", "hint-target", "support");
  $$(".axis").forEach((a) => a.classList.remove("hl"));
  board.classList.remove("highlighting");
  if (!view) return;
  const clueCell = S.selectedClue;
  const info = clueCell && view.cells.find((c) => c.cell === clueCell);
  if (info && info.clue) {
    board.classList.add("highlighting");
    S.cards.get(clueCell)?.classList.add("selected");
    for (const cell of info.clue.refs.counted) S.cards.get(cell)?.classList.add("hl-counted");
    for (const cell of info.clue.refs.named) S.cards.get(cell)?.classList.add("hl-named");
    highlightAxes(info.clue.data);
  } else {
    S.selectedClue = null;
  }
  if (S.hint) {
    S.cards.get(S.hint.cell)?.classList.add("hint-target");
    for (const cell of S.hint.support) S.cards.get(cell)?.classList.add("support");
  }
  $$(".clue-item").forEach((li) => {
    li.classList.toggle("selected", li.dataset.cell === S.selectedClue);
    li.classList.toggle("support", Boolean(S.hint && S.hint.support.includes(li.dataset.cell)));
  });
}

function highlightAxes(data) {
  const regions = [data.region, data.left, data.right].filter(Boolean);
  for (const r of regions) {
    if (r.kind === "row") $(`#axis-r${r.index - 1}`)?.classList.add("hl");
    if (r.kind === "col") $(`#axis-c${"ABCDEFGHIJ".indexOf(r.index)}`)?.classList.add("hl");
  }
}

function selectClue(cell) {
  S.selectedClue = S.selectedClue === cell ? null : cell;
  updateHighlights();
}

/* ------------------------------------------------------------ side panels */
function renderAll(view, opts) {
  // Responses can arrive out of order (e.g. a verdict and an agent step): never go back in time.
  if (S.view && view.game === S.view.game && view.seq < S.view.seq) return;
  const newGame = view.game !== S.boardGame;
  S.view = view;
  if (newGame) {
    buildBoard(view);
    S.selectedClue = null;
    S.hint = null;
    S.analysis = null;
    clearTimeout(S.celebrateTimer);
    $("#uniqueBox").innerHTML = "";
    hideBanner();
  }
  $("#empty").hidden = true;
  $("#board").hidden = false;
  updateBoard(view, { animate: !newGame && (opts?.animate ?? true) });
  if (S.popCell && view.cells.some((c) => c.cell === S.popCell && c.known)) closePopover(); // solved meanwhile
  renderHeader(view);
  renderClues(view);
  renderTrace(view);
  renderSolverTab(view);
  if ($("#showDeductions").checked || !$('[data-body="solver"]').hidden) refreshAnalysis();
}

function renderHeader(view) {
  $("#caseTitle").textContent = view.puzzle.title;
  $("#legCrim").textContent = term("criminal");
  $("#legInn").textContent = term("innocent");
  const meta = [`<span class="chip chip-accent chip-mono">${view.puzzle.size}×${view.puzzle.size}</span>`,
    `<span class="chip chip-soft chip-mono">${esc(view.puzzle.id)}</span>`];
  if (view.puzzle.case_title && view.puzzle.case_title !== view.puzzle.title) {
    meta.push(`<span class="chip chip-soft" title="Case file">${esc(view.puzzle.case_title)}</span>`);
  }
  if (view.status === "SOLVED") meta.push(`<span class="chip chip-inn">case closed</span>`);
  if (view.status === "LOST") meta.push(`<span class="chip chip-crim">game over</span>`);
  $("#board").classList.toggle("lost", view.status === "LOST");
  if (view.status === "INCONSISTENT") meta.push(`<span class="chip chip-crim">inconsistent clues</span>`);
  if (view.puzzle.expected && view.puzzle.expected !== "SOLVED") meta.push(`<span class="chip chip-warn">failure-case demo</span>`);
  $("#caseMeta").innerHTML = meta.join("");
  $("#mSolved").textContent = view.solved_count;
  $("#mTotal").textContent = view.total;
  $("#mBar").style.width = `${(100 * view.solved_count) / view.total}%`;
  $("#mMistakes").textContent = view.mistakes;
  $("#mSat").textContent = view.sat_calls_total.toLocaleString();
  document.title = `${view.puzzle.title} · Casebook`;
}

function renderClues(view) {
  const items = view.revealed_order.map((cell) => view.cells.find((c) => c.cell === cell)).filter((c) => c && c.clue);
  $("#clueCount").textContent = items.length;
  const seen = new Set($$(".clue-item").map((li) => li.dataset.cell));
  $("#clueList").innerHTML = items.map((c) => `
    <li class="clue-item${seen.has(c.cell) ? " seen" : ""}" data-cell="${c.cell}" tabindex="0">
      ${avatar(c, c.status)}
      <div class="ci-body">
        <div class="ci-top"><span class="ci-dot ${c.status}"></span><span class="ci-name">${esc(c.name)}</span><span class="ci-cell">${c.cell}</span><span class="chip chip-soft chip-mono">${c.clue.type}</span></div>
        <div class="ci-text">${formatClue(c.clue.text)}</div>
      </div>
    </li>`).join("") || `<li class="help">No clues revealed yet.</li>`;
  updateHighlights();
}

function verdictChip(v) {
  if (!v) return "";
  const cls = v === "CRIMINAL" ? "chip-crim" : v === "INNOCENT" ? "chip-inn" : "chip-soft";
  return `<span class="chip ${cls}">${esc(v === "CRIMINAL" || v === "INNOCENT" ? term(v).toLowerCase() : v.toLowerCase())}</span>`;
}

function resultChip(r) {
  const cls = { ACCEPTED: "chip-inn", NOT_PROVABLE: "chip-warn", CONTRADICTED: "chip-crim", STUCK: "chip-warn",
    INCONSISTENT: "chip-crim", SOLVED: "chip-accent", TIMEOUT: "chip-crim" }[r] || "chip-soft";
  return `<span class="chip ${cls} chip-mono">${esc(r)}</span>`;
}

function renderTrace(view) {
  const ol = $("#trace");
  const nearBottom = ol.parentElement.scrollHeight - ol.parentElement.scrollTop - ol.parentElement.clientHeight < 80;
  $("#traceCount").textContent = (view.log_offset || 0) + view.log.length;
  const before = ol.querySelectorAll(".tr").length;
  const offset = view.log_offset || 0;
  ol.innerHTML = view.log.map((e, idx) => {
    const i = idx + offset;
    const seenCls = idx < before ? " seen" : "";
    if (e.kind === "player") {
      return `<li class="tr${seenCls}"><div class="tr-head"><span class="tr-step">#${i + 1}</span><span class="tr-who">You</span>${verdictChip(e.verdict)}<span class="tr-name">${esc(nameOf(e.cell))}</span>${resultChip(e.result)}</div>
        ${e.revealed_text ? `<div class="tr-reveal">${formatClue(e.revealed_text)}</div>` : `<div class="tr-meta">${esc(playerMessage(e))}</div>`}</li>`;
    }
    const terminal = e.result !== "ACCEPTED";
    const unsat = (e.queries || []).filter((q) => q.result === "UNSAT").length;
    const queries = (e.queries || []).map((q) => `<li><span>${esc(q.query)}${q.cell ? ` <span class="ci-cell">${esc(nameOf(q.cell))}</span>` : ""}</span><span class="q-res ${q.result}">${q.result}</span></li>`).join("");
    const active = (e.active_clues || []).map(nameOf).join(", ");
    const meta = e.kb && e.kb.clauses !== undefined
      ? `${e.sat_calls} SAT calls (${unsat} UNSAT) · KB ${e.kb.primary_vars}+${e.kb.aux_vars} vars, ${e.kb.clauses} clauses · ${e.solver.decisions} dec / ${e.solver.propagations} prop / ${e.solver.backtracks} bt`
      : "";
    return `<li class="tr${terminal ? " terminal" : ""}${seenCls}">
      <div class="tr-head"><span class="tr-step">#${i + 1}</span><span class="tr-who">Agent · step ${e.step}</span>${e.cell ? verdictChip(e.verdict) + `<span class="tr-name">${esc(nameOf(e.cell))}</span>` : ""}${resultChip(e.result)}</div>
      ${meta ? `<div class="tr-meta">${meta}</div>` : ""}
      ${active ? `<div class="tr-meta">Active clues: ${esc(active)}</div>` : ""}
      ${e.revealed_text ? `<div class="tr-reveal">${formatClue(e.revealed_text)}</div>` : ""}
      ${queries ? `<details><summary>SAT queries</summary><ul class="q-list">${queries}</ul></details>` : ""}
    </li>`;
  }).join("") || `<li class="help">Moves made by you and by the logic agent appear here.</li>`;
  if (nearBottom) ol.parentElement.scrollTop = ol.parentElement.scrollHeight;
}

/** Rejection text built from the current names and status words. */
function playerMessage(e) {
  const who = nameOf(e.cell);
  if (e.result === "NOT_PROVABLE") return `Not provable yet: ${who} could still be either. No guessing!`;
  if (e.result === "CONTRADICTED") return `Contradicted: the clues prove ${who} is ${term(e.verdict === "CRIMINAL" ? "innocent" : "criminal", "adj")}.`;
  return e.message;
}

function renderSolverTab(view) {
  $("#kbPrimary").textContent = view.kb.primary_vars;
  $("#kbAux").textContent = view.kb.aux_vars;
  $("#kbClauses").textContent = view.kb.clauses;
  $("#cfgStrategy").value = view.config.strategy;
  $("#cfgCard").value = view.config.cardinality;
}

function renderAnalysis() {
  const a = S.analysis;
  const box = $("#analysisBox");
  if (!a) { box.innerHTML = `<p class="help">Run an analysis to see which characters are forced.</p>`; return; }
  if (!a.consistent) { box.innerHTML = `<div class="an-row"><span class="chip chip-crim">KB is UNSAT: inconsistent</span></div>`; return; }
  const vals = Object.values(a.classification);
  const count = (v) => vals.filter((x) => x === v).length;
  const s = a.solver;
  box.innerHTML = `<div class="an-row">
      <span class="chip chip-crim">${count("CRIMINAL")} forced ${esc(term("criminal").toLowerCase())}</span>
      <span class="chip chip-inn">${count("INNOCENT")} forced ${esc(term("innocent").toLowerCase())}</span>
      <span class="chip chip-soft">${count("UNKNOWN")} unknown</span></div>
    <div class="an-stats">
      <span>SAT calls <b>${a.queries.length}</b></span><span>decisions <b>${s.decisions}</b></span>
      <span>propagations <b>${s.propagations}</b></span><span>backtracks <b>${s.backtracks}</b></span>
      <span>conflicts <b>${s.conflicts}</b></span><span>runtime <b>${s.runtime_ms} ms</b></span>
    </div>`;
}

function updateDeductionChips() {
  const show = $("#showDeductions").checked && S.analysis;
  for (const [cell, card] of S.cards) {
    let chip = card.querySelector(".deduce");
    const v = show && !S.known.has(cell) ? S.analysis.classification[cell] : null;
    if (!v) { chip?.remove(); continue; }
    if (!chip) {
      chip = document.createElement("span");
      card.querySelector(".face-down").appendChild(chip);
    }
    chip.className = `deduce ${v}`;
    chip.textContent = v === "UNKNOWN" ? "unknown" : `forced ${term(v).toLowerCase()}`;
  }
}

let analysisSeq = 0;
async function refreshAnalysis() {
  if (!S.view) return;
  const seq = ++analysisSeq;
  const game = S.view.game;
  try {
    const data = await api("/api/analysis", { game });
    if (seq !== analysisSeq || !S.view || S.view.game !== game) return;
    S.analysis = data.analysis;
  } catch (err) {
    if (seq !== analysisSeq || !S.view || S.view.game !== game) return;
    S.analysis = null;
  }
  renderAnalysis();
  updateDeductionChips();
}

/* -------------------------------------------------------------- actions */
async function loadGame(payload, label) {
  stopAuto();
  closePopover();
  clearTimeout(S.celebrateTimer);
  const epoch = ++S.epoch;
  setLoading(true, label || "Opening case file…");
  try {
    const data = await api("/api/load", { ...payload, strategy: $("#cfgStrategy").value, cardinality: $("#cfgCard").value });
    if (epoch !== S.epoch) return;
    S.busy = false; // responses of requests from the previous game are ignored from now on
    S.currentFile = payload.file || null;
    renderPuzzleList();
    renderAll(data.state);
    setAgentState("idle");
    const n = data.state.puzzle.size;
    toast("info", `Case opened: ${data.state.puzzle.title}`, `${n}×${n} board · ${data.state.solved_count} card(s) face-up`);
    if (data.state.puzzle.note) banner("info", "🧪", esc(data.state.puzzle.note));
    if (data.state.theme === "classic") toast("info", "Using the case file's own characters", "This board has more cells than the 30 players in the cast.");
  } catch (err) {
    if (epoch === S.epoch) {
      S.busy = false; // the previous game keeps going; clear any state left by interrupted requests
      toast("bad", "Could not load the puzzle", esc(err.message), 5000);
    }
  } finally {
    if (epoch === S.epoch) setLoading(false);
  }
}

async function submitVerdict(cell, verdict) {
  if (!S.view || S.loading) return;
  if (S.busy) { toast("info", "Please wait", "The previous request is still running."); return; }
  closePopover();
  S.busy = true;
  const epoch = S.epoch;
  try {
    const data = await api("/api/verdict", { game: S.view.game, round: S.view.round, cell, verdict });
    if (epoch !== S.epoch) return;
    const r = data.result;
    S.hint = null;
    hideBannerIfHint();
    renderAll(data.state);
    const card = S.cards.get(cell);
    if (r.status === "CONTRADICTED" && data.state.status === "LOST") {
      card?.classList.remove("shake"); void card?.offsetWidth; card?.classList.add("shake");
      setAgentState("game over");
      setTimeout(() => { if (S.view && S.view.game === data.state.game && S.view.status === "LOST") gameOver(S.view); }, 450);
    } else if (r.status === "ACCEPTED") {
      if (["stuck", "paused"].includes($("#agentState").textContent)) setAgentState("idle");
      toast("ok", `Correct: ${nameOf(cell)} is ${term(verdict, "adj")}.`, r.clue ? `New clue: ${formatClue(r.clue.text)}` : "");
      afterProgress(data.state);
    } else {
      card?.classList.remove("shake"); void card?.offsetWidth; card?.classList.add("shake");
      const kind = r.status === "NOT_PROVABLE" ? "warn" : "bad";
      const title = r.status === "NOT_PROVABLE" ? "Not provable yet" : r.status === "CONTRADICTED" ? "Contradicted" : r.status.replace("_", " ");
      toast(kind, title, esc(playerMessage({ cell, verdict, result: r.status, message: r.message })), 4200);
    }
  } catch (err) {
    if (epoch === S.epoch) toast("bad", "Request failed", esc(err.message));
  } finally {
    if (epoch === S.epoch) S.busy = false;
  }
}

function hideBannerIfHint() {
  if ($("#banner").classList.contains("hint")) hideBanner();
}

/** True (and tells the player) when a contradicted verdict has ended the game. */
function gameIsOver() {
  if (!S.view || S.view.status !== "LOST") return false;
  toast("bad", "Game over", "A contradicted verdict ended this case. Press Restart (R) to play again.");
  return true;
}

async function requestHint() {
  if (!S.view || S.busy || S.loading || gameIsOver()) return;
  S.busy = true;
  const epoch = S.epoch;
  try {
    const data = await api("/api/hint", { game: S.view.game, round: S.view.round });
    if (epoch !== S.epoch) return;
    const h = data.hint;
    renderAll(data.state, { animate: false });
    if (h.status === "HINT") {
      S.hint = { cell: h.cell, support: h.support, verdict: h.verdict, revealed: false };
      const names = h.support.map((c) => `<span class="ref">${esc(nameOf(c))}</span>`).join(", ");
      banner("hint", "💡", `<b>${esc(h.name)}</b> (${h.cell}) can be proved right now. Look at the clue${h.support.length > 1 ? "s" : ""} of ${names}.
        <button class="link-btn" id="revealHint">Show the verdict</button>`);
      $("#revealHint").onclick = () => {
        banner("hint", "💡", `<b>${esc(h.name)}</b> must be <span class="${h.verdict === "CRIMINAL" ? "w-crim" : "w-inn"}">${esc(term(h.verdict, "adj"))}</span>, proved by the clue${h.support.length > 1 ? "s" : ""} of ${names}. ${h.forced_count > 1 ? `(${h.forced_count - 1} other character${h.forced_count > 2 ? "s are" : " is"} also provable.)` : ""}`);
      };
      updateHighlights();
      S.cards.get(h.cell)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } else if (h.status === "STUCK") {
      banner("bad", "🧩", `<b>No provable move.</b> ${esc(h.message)} The puzzle cannot be finished without guessing.`);
    } else if (h.status === "INCONSISTENT") {
      banner("bad", "⚠️", `<b>Inconsistent clues.</b> ${esc(h.message)}`);
    } else {
      banner("info", "✅", esc(h.message));
    }
  } catch (err) {
    if (epoch === S.epoch) toast("bad", "Hint failed", esc(err.message));
  } finally {
    if (epoch === S.epoch) S.busy = false;
  }
}

async function agentStep() {
  if (!S.view) return null;
  const epoch = S.epoch;
  const data = await api("/api/step", { game: S.view.game, round: S.view.round });
  if (epoch !== S.epoch) return null;
  S.hint = null;
  hideBannerIfHint();
  renderAll(data.state);
  const e = data.entry;
  if (e.result === "ACCEPTED") {
    if (!S.auto) toast("ok", `Agent: ${nameOf(e.cell)} is ${term(e.verdict, "adj")}`, `${e.sat_calls} SAT calls${e.revealed_text ? " · new clue revealed" : ""}`, 2200);
    afterProgress(data.state);
  } else if (e.result === "STUCK") {
    setAgentState("stuck");
    banner("bad", "🧩", `<b>Agent stopped: STUCK.</b> ${e.unknown} character(s) remain, but none of them is entailed by the public clues. The agent refuses to guess.`);
  } else if (e.result === "INCONSISTENT") {
    setAgentState("inconsistent");
    banner("bad", "⚠️", `<b>Agent stopped: INCONSISTENT.</b> The revealed clues have no common model (KB is UNSAT).`);
  } else if (e.result === "SOLVED") {
    setAgentState("solved");
  } else if (e.result === "ERROR") {
    setAgentState("error");
    banner("bad", "⚠️", `<b>Agent stopped: corrupt puzzle.</b> A provable verdict contradicts the solution stored in the file.`);
  } else {
    setAgentState(e.result.toLowerCase());
    banner("bad", "⏱️", `<b>Agent stopped: ${esc(e.result)}.</b>`);
  }
  return e;
}

async function stepOnce() {
  if (S.busy || S.auto || S.loading || gameIsOver()) return;
  S.busy = true;
  const epoch = S.epoch;
  try { await agentStep(); } catch (err) { if (epoch === S.epoch) toast("bad", "Agent step failed", esc(err.message)); }
  finally { if (epoch === S.epoch) S.busy = false; }
}

function speedDelay() {
  const v = Number($("#speed").value);
  return Math.round(1500 - v * 14.5);
}

async function toggleAuto() {
  if (S.auto) { stopAuto(); return; }
  if (!S.view || S.busy || S.loading || gameIsOver()) return;
  if (S.view.status === "SOLVED") { toast("info", "Already solved", "Restart to watch the agent solve it."); return; }
  closePopover();
  S.auto = true;
  S.busy = true;
  $("#btnAuto").classList.add("running");
  $("#btnAuto span").textContent = "Stop";
  setAgentState("running");
  const epoch = S.epoch;
  try {
    while (S.auto && epoch === S.epoch) {
      const e = await agentStep();
      if (!e || e.result !== "ACCEPTED") break;
      if (S.view.status === "SOLVED") break;
      // sleep in small slices so that Stop releases the controls immediately
      for (let waited = 0; waited < speedDelay() && S.auto && epoch === S.epoch; waited += 50) await sleep(50);
    }
  } catch (err) {
    if (epoch === S.epoch) { toast("bad", "Auto solve failed", esc(err.message)); setAgentState("idle"); }
  } finally {
    if (epoch === S.epoch) {
      S.busy = false;
      stopAuto();
    }
  }
}

function stopAuto() {
  S.auto = false;
  $("#btnAuto").classList.remove("running");
  $("#btnAuto span").textContent = "Auto solve";
  if ($("#agentState").textContent === "running") setAgentState(S.view && S.view.status === "SOLVED" ? "solved" : "paused");
}

function setAgentState(text) {
  const chip = $("#agentState");
  chip.textContent = text;
  chip.className = "chip " + ({ running: "chip-accent", solved: "chip-inn", stuck: "chip-warn", inconsistent: "chip-crim" }[text] || "chip-soft");
}

async function restart() {
  if (!S.view || S.loading) return;
  stopAuto();
  closePopover();
  clearTimeout(S.celebrateTimer);
  const epoch = ++S.epoch;
  try {
    const data = await api("/api/restart", { game: S.view.game });
    if (epoch !== S.epoch) return;
    S.busy = false;
    S.hint = null;
    S.selectedClue = null;
    hideBanner();
    S.boardGame = null; // rebuild so cards flip back cleanly
    renderAll(data.state);
    setAgentState("idle");
    toast("info", "Case restarted");
  } catch (err) {
    if (epoch === S.epoch) { S.busy = false; toast("bad", "Restart failed", esc(err.message)); }
  }
}

async function changeConfig() {
  if (!S.view) return;
  const game = S.view.game;
  try {
    const data = await api("/api/config", { game, strategy: $("#cfgStrategy").value, cardinality: $("#cfgCard").value });
    if (!S.view || S.view.game !== game) return;
    renderAll(data.state, { animate: false });
    toast("info", "Solver configuration updated", `${esc(data.state.config.strategy)} · ${esc(data.state.config.cardinality)} encoding · ${data.state.kb.clauses} clauses now`);
  } catch (err) {
    toast("bad", "Could not change configuration", esc(err.message));
  }
}

async function checkUnique() {
  if (!S.view) return;
  const box = $("#uniqueBox");
  box.innerHTML = `<div class="res help">Checking…</div>`;
  const game = S.view.game;
  try {
    const data = await api("/api/uniqueness", { game });
    if (!S.view || S.view.game !== game) return;
    const u = data.uniqueness;
    const chip = u.verdict === "UNIQUE" ? "chip-inn" : "chip-crim";
    const text = u.verdict === "UNIQUE" ? "Exactly one assignment satisfies every clue."
      : u.verdict === "MULTIPLE" ? "At least two assignments satisfy every clue." : "No assignment satisfies every clue.";
    box.innerHTML = `<div class="res"><span class="chip ${chip}">${u.verdict}</span> ${text}<div class="help">${u.sat_calls} SAT calls with blocking clauses · ${u.solver.decisions} decisions · ${u.solver.runtime_ms} ms</div></div>`;
  } catch (err) {
    if (S.view && S.view.game === game) box.innerHTML = `<div class="res">${esc(err.message)}</div>`;
  }
}

function afterProgress(view) {
  if (view.status === "SOLVED") {
    setAgentState("solved");
    clearTimeout(S.celebrateTimer);
    S.celebrateTimer = setTimeout(() => { if (S.view && S.view.game === view.game) celebrate(S.view); }, 650);
  }
}

function gameOver(view) {
  const { cell, verdict } = view.lost;
  const proved = verdict === "CRIMINAL" ? "innocent" : "criminal";
  S.modalMode = "lost";
  $("#modalArt").textContent = "🟥";
  $("#modalTitle").textContent = "Game over";
  $("#modalText").textContent = `CONTRADICTED: the clues prove ${nameOf(cell)} is ${term(proved, "adj")}, not ${term(verdict, "adj")}. `
    + "One contradicted verdict ends the case.";
  $("#modalStats").innerHTML = `<div><b>${view.solved_count}/${view.total}</b><span>identified</span></div><div><b>${view.mistakes}</b><span>mistakes</span></div><div><b>${view.sat_calls_total}</b><span>SAT calls</span></div>`;
  $("#modalClose").textContent = "View board";
  $("#modalNext").textContent = "Restart case";
  $("#modal").hidden = false;
  $("#modalNext").focus();
}

function celebrate(view) {
  S.modalMode = "won";
  $("#modalClose").textContent = "Admire the board";
  $("#modalNext").textContent = "Next case";
  const agentSteps = view.log.filter((e) => e.kind === "agent" && e.result === "ACCEPTED").length;
  const playerSteps = view.log.filter((e) => e.kind === "player" && e.result === "ACCEPTED").length;
  $("#modalArt").textContent = view.mistakes === 0 ? "🏆" : "🔎";
  $("#modalTitle").textContent = "Case closed";
  $("#modalText").textContent = view.mistakes === 0
    ? "Every verdict was proved. No guesses, no mistakes."
    : `Solved with ${view.mistakes} rejected verdict${view.mistakes > 1 ? "s" : ""} along the way.`;
  $("#modalStats").innerHTML = `<div><b>${playerSteps}</b><span>your verdicts</span></div><div><b>${agentSteps}</b><span>agent verdicts</span></div><div><b>${view.sat_calls_total}</b><span>SAT calls</span></div>`;
  $("#modal").hidden = false;
  $("#modalNext").focus();
  confetti();
}

function confetti() {
  const box = $("#confetti");
  const colors = ["#4f46e5", "#16946a", "#d9434b", "#f3a93d", "#8b85ff", "#36d394"];
  for (let i = 0; i < 110; i++) {
    const p = document.createElement("i");
    p.style.left = `${Math.random() * 100}%`;
    p.style.background = colors[i % colors.length];
    p.style.setProperty("--dx", `${(Math.random() - 0.5) * 220}px`);
    p.style.setProperty("--rot", `${Math.random() * 900 - 450}deg`);
    p.style.animationDuration = `${2.2 + Math.random() * 1.8}s`;
    p.style.animationDelay = `${Math.random() * 0.5}s`;
    box.appendChild(p);
  }
  setTimeout(() => { box.innerHTML = ""; }, 4800);
}

/* -------------------------------------------------------------- popover */
function openPopover(cell) {
  const card = S.cards.get(cell);
  const info = S.view.cells.find((c) => c.cell === cell);
  if (!card || !info || info.known || gameIsOver()) return;
  S.popCell = cell;
  const pop = $("#popover");
  $("#popAvatar").innerHTML = avatar(info);
  $("#popTitle").textContent = info.name;
  $("#popCrim span").textContent = term("criminal");
  $("#popInn span").textContent = term("innocent");
  $("#popSub").textContent = `${info.profession} · ${cell}`;
  pop.hidden = false;
  const r = card.getBoundingClientRect();
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  let left = r.right + 10;
  if (left + pw > window.innerWidth - 8) left = r.left - pw - 10;
  if (left < 8) left = Math.min(Math.max(8, r.left + r.width / 2 - pw / 2), window.innerWidth - pw - 8);
  let top = r.top + r.height / 2 - ph / 2;
  if (left === r.right + 10 || left === r.left - pw - 10) {
    top = Math.min(Math.max(8, top), window.innerHeight - ph - 8);
  } else {
    top = r.bottom + 8 + ph > window.innerHeight ? r.top - ph - 8 : r.bottom + 8;
  }
  pop.style.left = `${left}px`;
  pop.style.top = `${Math.max(8, top)}px`;
  $("#popCrim").focus({ preventScroll: true });
}

function closePopover() {
  const pop = $("#popover");
  if (pop.hidden) return;
  pop.hidden = true;
  const card = S.popCell && S.cards.get(S.popCell);
  S.popCell = null;
  card?.focus({ preventScroll: true });
}

/* ------------------------------------------------------------------ theme */
function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("casebook-theme"); } catch { /* storage blocked */ }
  if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
  $("#btnTheme").onclick = () => {
    const current = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("casebook-theme", next); } catch { /* ignore */ }
  };
}

/* ----------------------------------------------------------------- wiring */
function wire() {
  $("#puzzleList").addEventListener("click", (ev) => {
    const item = ev.target.closest(".puzzle-item");
    if (!item) return;
    S.selectedFile = item.dataset.file;
    // toggle classes only: re-rendering here would break the dblclick target
    $$(".puzzle-item").forEach((el) => {
      el.classList.toggle("selected", el === item);
      el.setAttribute("aria-selected", String(el === item));
    });
  });
  $("#puzzleList").addEventListener("dblclick", (ev) => {
    const item = ev.target.closest(".puzzle-item");
    if (item) loadGame({ file: item.dataset.file });
  });
  $("#btnLoad").onclick = () => S.selectedFile ? loadGame({ file: S.selectedFile }) : toast("warn", "Pick a case file first");
  $("#btnUpload").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = async (ev) => {
    const file = ev.target.files[0];
    ev.target.value = "";
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      S.currentFile = null;
      await loadGame({ data }, `Opening ${file.name}…`);
    } catch (err) {
      toast("bad", "Not a valid JSON file", esc(err.message));
    }
  };
  $$("#genSize button").forEach((b) => b.onclick = () => {
    S.genSize = Number(b.dataset.size);
    $$("#genSize button").forEach((x) => { x.classList.toggle("active", x === b); x.setAttribute("aria-checked", String(x === b)); });
  });
  $("#btnGenerate").onclick = () => {
    S.currentFile = null;
    loadGame({ generate: { size: S.genSize } }, `Generating a no-guess ${S.genSize}×${S.genSize} case… ${S.genSize === 5 ? "(this can take a few seconds)" : ""}`);
  };
  $("#btnRestart").onclick = restart;
  $("#btnHint").onclick = requestHint;
  $("#btnStep").onclick = stepOnce;
  $("#btnAuto").onclick = toggleAuto;
  $("#bannerClose").onclick = () => { hideBanner(); S.hint = null; updateHighlights(); };
  $("#speed").oninput = () => {
    const text = `${(speedDelay() / 1000).toFixed(2)}s`;
    $("#speedVal").textContent = text;
    $("#speed").setAttribute("aria-valuetext", `${text} between steps`);
  };
  $("#speed").oninput();
  $("#showDeductions").onchange = () => { if ($("#showDeductions").checked) refreshAnalysis(); else updateDeductionChips(); };
  $("#btnAnalyze").onclick = refreshAnalysis;
  $("#cfgStrategy").onchange = changeConfig;
  $("#cfgCard").onchange = changeConfig;
  $("#btnUnique").onclick = checkUnique;

  $("#board").addEventListener("click", (ev) => {
    const card = ev.target.closest(".card");
    if (!card || !S.view) return;
    const cell = card.dataset.cell;
    if (S.known.has(cell)) {
      closePopover();
      const info = S.view.cells.find((c) => c.cell === cell);
      if (info && info.clue) selectClue(cell);
      return;
    }
    if (S.auto) { toast("info", "The agent is solving", "Stop auto solve to play yourself."); return; }
    if (S.popCell === cell) closePopover(); else openPopover(cell);
    ev.stopPropagation();
  });
  $("#board").addEventListener("keydown", (ev) => {
    const card = ev.target.closest(".card");
    if (!card || (ev.key !== "Enter" && ev.key !== " ")) return;
    ev.preventDefault();
    card.click();
  });
  $("#clueList").addEventListener("click", (ev) => {
    const li = ev.target.closest(".clue-item");
    if (li) selectClue(li.dataset.cell);
  });
  $("#clueList").addEventListener("keydown", (ev) => {
    const li = ev.target.closest(".clue-item");
    if (li && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); selectClue(li.dataset.cell); }
  });
  $("#popCrim").onclick = () => S.popCell && submitVerdict(S.popCell, "CRIMINAL");
  $("#popInn").onclick = () => S.popCell && submitVerdict(S.popCell, "INNOCENT");
  document.addEventListener("click", (ev) => {
    if (!$("#popover").hidden && !ev.target.closest("#popover") && !ev.target.closest(".card")) closePopover();
  });
  window.addEventListener("resize", closePopover);
  window.addEventListener("scroll", closePopover, { passive: true, capture: true });

  $$(".tab").forEach((t) => t.onclick = () => {
    $$(".tab").forEach((x) => { x.classList.toggle("active", x === t); x.setAttribute("aria-selected", String(x === t)); });
    $$(".tab-body").forEach((b) => { b.hidden = b.dataset.body !== t.dataset.tab; });
    if (t.dataset.tab === "solver") refreshAnalysis();
  });

  $("#modalClose").onclick = () => { $("#modal").hidden = true; };
  $("#modalNext").onclick = () => {
    $("#modal").hidden = true;
    if (S.modalMode === "lost") { restart(); return; }
    const idx = S.puzzles.findIndex((p) => p.file === S.currentFile);
    const next = S.puzzles[(idx + 1) % S.puzzles.length];
    if (next) { S.selectedFile = next.file; loadGame({ file: next.file }); }
  };

  document.addEventListener("keydown", (ev) => {
    if (ev.target.matches("input, select, textarea")) return;
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    const key = ev.key.toLowerCase();
    if (!$("#popover").hidden) {
      if (key === "c") { ev.preventDefault(); $("#popCrim").click(); return; }
      if (key === "i") { ev.preventDefault(); $("#popInn").click(); return; }
    }
    if (key === "escape") {
      if (!$("#modal").hidden) { $("#modal").hidden = true; return; }
      if (!$("#popover").hidden) { closePopover(); return; }
      S.selectedClue = null; S.hint = null; hideBannerIfHint(); updateHighlights();
      return;
    }
    if (!$("#modal").hidden || S.loading) return;
    if (key === "h") requestHint();
    else if (key === "n") stepOnce();
    else if (key === "a") toggleAuto();
    else if (key === "r") {
      // the keyboard shortcut asks first when there is progress to lose
      const initial = S.view ? S.view.cells.filter((c) => c.initial).length : 0;
      if (!S.view || S.view.status === "SOLVED" || S.view.status === "LOST" || S.view.solved_count <= initial || confirm("Restart this case? Your progress will be lost.")) restart();
    }
  });
}

async function init() {
  initTheme();
  wire();
  $("#board").hidden = true;
  await loadPuzzleList();
  const wanted = new URLSearchParams(location.search).get("case"); // e.g. ?case=05-4x4-a
  const first = S.puzzles.find((p) => p.file === wanted) || S.puzzles[0];
  if (first) { S.selectedFile = first.file; await loadGame({ file: first.file }); }
  // Demo/screenshot helpers: ?steps=N lets the agent make N deductions, ?select=B2 highlights a clue.
  const params = new URLSearchParams(location.search);
  const steps = Math.min(Number.parseInt(params.get("steps") || "0", 10) || 0, 30);
  for (let i = 0; i < steps && S.view && S.view.status === "PLAYING"; i++) {
    try { await agentStep(); } catch { break; }
  }
  const sel = params.get("select");
  if (sel && S.view && S.view.cells.some((c) => c.cell === sel && c.clue)) selectClue(sel);
}

init();
