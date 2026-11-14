// Общее состояние интерфейса. Все модули читают и меняют только его.
import { api } from "./util.js";

export const CLOTHS = {
  green:  { name: "Зелёное сукно", base: "#2a6326", d: "#1b4a1a" },
  dark:   { name: "Тёмно-зелёное", base: "#173f1d", d: "#0d2a13" },
  olive:  { name: "Хаки", base: "#5a5b32", d: "#3f4022" },
  grey:   { name: "Фельдграу", base: "#50575c", d: "#383d41" },
  blue:   { name: "Синее", base: "#264370", d: "#192e4f" },
  desert: { name: "Пустынное", base: "#9c8350", d: "#7a6538" },
  black:  { name: "Чёрное", base: "#22242a", d: "#121317" },
  pink:   { name: "Розовое (в шутку)", base: "#b95a8c", d: "#923f6b" },
  horizon: { name: "Серо-голубое («горизонт»)", base: "#4d6b86", d: "#364d63" },
  brown:  { name: "Шинельное коричневое", base: "#573f29", d: "#3c2b1b" },
  burgundy: { name: "Бордо", base: "#5a2132", d: "#3f1623" },
};
const shade = (hex, k) => "#" + [1, 3, 5].map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * k).toString(16).padStart(2, "0")).join("");
export const TYPEWRITERS = {
  black: { name: "Чёрный лак", body: "#2b2d33", dark: "#17181c", hi: "#5a5e68" },
  green: { name: "Зелёная эмаль", body: "#2f5d43", dark: "#1b3a29", hi: "#6a9a7d" },
  blue:  { name: "Синяя эмаль", body: "#2f4c7a", dark: "#1c3052", hi: "#7596c6" },
  red:   { name: "Красная эмаль", body: "#7a2a2a", dark: "#4a1515", hi: "#c07a7a" },
  cream: { name: "Слоновая кость", body: "#cdbf93", dark: "#a49668", hi: "#f2e8c8" },
  steel: { name: "Серая сталь", body: "#6b727b", dark: "#454b52", hi: "#b4bbc4" },
};

export const App = {
  phase: "menu", hud: null, config: null, busy: false,
  tab: "news", bus: new EventTarget(), ui: null,
  tabs: [],   // вкладки задаёт game.js (TABS); меню умеет расти: setTabs() перестраивает его
  emit(name, detail) { this.bus.dispatchEvent(new CustomEvent(name, { detail })); },
  on(name, fn) { this.bus.addEventListener(name, (e) => fn(e.detail)); },

  applyCloth(id, custom) {
    let c = CLOTHS[id];
    if (id === "custom" && /^#[0-9a-f]{6}$/i.test(custom || "")) c = { base: custom, d: shade(custom, 0.7) };
    c = c || CLOTHS.green;
    const r = document.documentElement.style;
    r.setProperty("--cloth", c.base); r.setProperty("--cloth-d", c.d);
    this.clothId = id === "custom" && c.base === custom ? "custom" : CLOTHS[id] ? id : "green";
  },

  async refresh() {
    const s = await api("/api/state");
    this.phase = s.phase; this.busy = s.busy; this.config = s.config;
    if (s.hud) this.hud = s.hud;
    this.candidates = s.candidates || [];
    this.emit("state", s);
    return s;
  },

  async loadUi() {                         // оформление: цвета, шрифты, размеры
    this.ui = await api("/api/ui");
    this.applyCloth(this.ui.prefs.cloth, this.ui.prefs.cloth_custom);
    (await import("./fonts.js")).applyFonts();
    this.emit("prefs", this.ui.prefs);
  },
  async setPrefs(patch) {
    const r = await api("/api/ui", patch);
    this.ui.prefs = r.prefs;
    this.applyCloth(r.prefs.cloth, r.prefs.cloth_custom);
    (await import("./fonts.js")).applyFonts();
    this.emit("prefs", r.prefs);
  },
  setTabs(list) { this.tabs = list; this.emit("tabs", list); },
};

export const TABS = [
  { id: "news", label: "Газета" }, { id: "decrees", label: "Указы" }, { id: "diplomacy", label: "Дипломатия" },
  { id: "summits", label: "Саммиты" }, { id: "army", label: "Армия" }, { id: "advisors", label: "Советники" },
];
