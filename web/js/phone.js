// Телефон «Pear» (слева снизу): чат с Гейммастером, настройки, экспорт, откат хода, выход. Доступен и в меню.
import { h, art, api, animate, toast, sleep } from "./util.js";
import { App, CLOTHS, TYPEWRITERS } from "./store.js";
import { hasCyrillic } from "./fonts.js";
import { pearLogo } from "./scribble.js";

const ICON = {
  gm: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><path d="M8 10h32v22H22l-9 8v-8H8z"/><path d="M16 18h16M16 25h10"/></svg>',
  settings: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="24" cy="24" r="7"/><path d="M24 5v6M24 37v6M5 24h6M37 24h6M10.5 10.5l4.2 4.2M33.3 33.3l4.2 4.2M10.5 37.5l4.2-4.2M33.3 14.7l4.2-4.2"/></svg>',
  export: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><path d="M24 6v24M14 21l10 10 10-10M8 34v8h32v-8"/></svg>',
  turns: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><path d="M18 12L8 22l10 10M8 22h22a10 10 0 0 1 0 20h-6"/></svg>',
  look: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><path d="M24 5C12 5 5 14 5 24s7 19 15 19c4 0 5-3 4-6s1-5 5-5h5c6 0 9-3 9-8C43 12 35 5 24 5z"/><circle cx="15" cy="22" r="2.4"/><circle cx="22" cy="14" r="2.4"/><circle cx="32" cy="15" r="2.4"/></svg>',
  exit: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6H8v36h10M30 14l10 10-10 10M40 24H18"/></svg>',
};
const APPS = [
  { id: "gm", name: "Гейммастер", color: "#6a5acd", game: true }, { id: "settings", name: "Настройки", color: "#6b7280" }, { id: "look", name: "Оформление", color: "#d69e2e" },
  { id: "export", name: "Экспорт", color: "#2c7a7b", game: true }, { id: "turns", name: "Ходы", color: "#b7791f", game: true },
  { id: "exit", name: "Выход", color: "#c53030", game: true },
];

export function mountPhone(stage, { onWorldChanged, onExit }) {
  let open = false, screen = "home", root = null, content = null;
  const body = h("div", { class: "ph-back" }, h("div", { class: "ph-cam" }), art(pearLogo(30), { class: "ph-logo" }));
  const closed = h("button", { class: "phone-closed", title: "Телефон", onclick: () => toggle(true) }, body);
  closed.style.zIndex = 90; stage.append(closed);

  App.on("book-step", (n) => closed.classList.toggle("hide", n === 3));   // на выборе сложности управлять нечем
  const inGame = () => App.phase === "game";

  /* ---- экраны ---- */
  const screens = {
    home() {
      const list = APPS.filter((a) => !a.game || inGame());
      return [h("div", { class: "ph-grid" }, list.map((a) => h("button", { class: "app", onclick: () => nav(a.id) }, art(ICON[a.id], { class: "app-ic", style: { background: a.color } }), h("span", {}, a.name))))];
    },
    async gm() {
      const log = h("div", { class: "gm-log noscroll" });
      const input = h("input", { class: "gm-in", placeholder: "Указание Гейммастеру…" });
      const send = h("button", { class: "gm-send", onclick: () => submit() }, "➤");
      const paint = (msgs) => { log.replaceChildren(...msgs.map((m) => h("div", { class: "gm-msg " + m.role }, m.content))); log.scrollTop = log.scrollHeight; };
      const submit = async () => {
        const text = input.value.trim(); if (!text) return;
        input.value = ""; input.disabled = send.disabled = true;
        log.append(h("div", { class: "gm-msg user" }, text), h("div", { class: "gm-msg assistant dim" }, "Гейммастер думает…")); log.scrollTop = log.scrollHeight;
        try { const r = await api("/api/gm", { text }); paint(r.messages); App.hud = r.hud; await App.refresh(); onWorldChanged(); }
        catch (e) { toast(e.message, true); }
        input.disabled = send.disabled = false; input.focus();
      };
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
      paint((await api("/api/gm")).messages);
      return [log, h("div", { class: "gm-bar" }, input, send)];
    },
    async settings() {
      const cfg = await api("/api/config");
      const key = h("input", { class: "fld", type: "password", placeholder: cfg.has_key ? `ключ сохранён (…${cfg.key_tail})` : "API-ключ", autocomplete: "off" });
      const url = h("input", { class: "fld", placeholder: "Base URL (пусто = OpenAI)", value: cfg.base_url });
      const model = h("input", { class: "fld", placeholder: "Модель", value: cfg.model_name });
      const note = h("div", { class: "ph-note" });
      const save = async () => { try { await api("/api/config", { api_key: key.value, base_url: url.value, model_name: model.value }); key.value = ""; await App.refresh(); toast("Настройки сохранены"); } catch (e) { toast(e.message, true); } };
      const test = async () => { note.textContent = "Пробный запрос…"; await save(); const r = await api("/api/config/test", {}); note.textContent = (r.ok ? "✅ " : "❌ ") + r.message; };
      const out = [h("div", { class: "ph-sec" }, "Подключение к ИИ"), key, url, model,
        h("div", { class: "row" }, h("button", { class: "ph-btn", onclick: save }, "Сохранить"), h("button", { class: "ph-btn alt", onclick: test }, "Проверить связь")), note];
      if (inGame()) {
        const hud = App.hud;
        const auto = h("span", { class: "val" }, hud.autosave_interval);
        const step = async (d) => { const v = Math.max(1, Math.min(50, Number(auto.textContent) + d)); auto.textContent = v; App.hud = await api("/api/settings", { autosave: v }); };
        const alarm = h("input", { type: "checkbox", checked: hud.alarm ? "" : null, onchange: async (e) => { App.hud = await api("/api/settings", { alarm: e.target.checked }); } });
        alarm.checked = !!hud.alarm;
        out.push(h("div", { class: "ph-sec" }, "Игра"),
          h("div", { class: "row between" }, h("span", {}, "Автосохранение каждые N ходов"), h("span", { class: "stepper" }, h("button", { onclick: () => step(-1) }, "−"), auto, h("button", { onclick: () => step(1) }, "+"))),
          h("label", { class: "row between" }, h("span", {}, "Будильник (мир целиком, 4 региона)"), alarm),
          h("div", { class: "ph-note" }, `Токены: последний ход — ${hud.tokens.turn.toLocaleString("ru")}, всего — ${hud.tokens.total.toLocaleString("ru")}`));
      }
      return out;
    },
    async look() {
      await App.loadUi();
      const P = App.ui.prefs, info = App.ui.fonts;
      const swatches = (set, key) => {
        const box = h("div", { class: "swatches" }, Object.entries(set).map(([id, c]) => h("button", { class: "sw" + (key === "typewriter" ? " tw" : "") + (id === P[key] ? " on" : ""), title: c.name, style: { background: c.base || c.body }, onclick: async () => {
          await App.setPrefs({ [key]: id }); [...box.children].forEach((b, i) => b.classList.toggle("on", Object.keys(set)[i] === id));
        } })));
        if (key === "cloth") {                                   // двенадцатая ячейка: свой цвет, с живым предпросмотром
          const inp = h("input", { type: "color", class: "cw-input", value: P.cloth_custom || "#3a6b5a" });
          const lab = h("label", { class: "sw custom" + (P.cloth === "custom" ? " on" : ""), title: "Свой цвет" }, inp);
          if (P.cloth_custom) lab.style.background = P.cloth_custom;
          inp.addEventListener("input", () => { App.applyCloth("custom", inp.value); lab.style.background = inp.value; });
          inp.addEventListener("change", async () => {
            await App.setPrefs({ cloth: "custom", cloth_custom: inp.value });
            [...box.children].forEach((b) => b.classList.remove("on")); lab.classList.add("on");
          });
          box.append(lab);
        }
        return box;
      };
      const cyr = {};                                           // file -> true/false/null, определяется в браузере
      const label = (f, kind) => f.name + (kind === "bundled" ? " — без кириллицы" : cyr[f.file] === false ? " — без кириллицы" : cyr[f.file] === true ? " — кириллица есть" : "");
      const cats = Object.entries(App.ui.categories).map(([cat, title]) => {
        const sel = h("select", {}, h("option", { value: "default" }, "Стандартный"),
          ...info.bundled.map((f) => h("option", { value: "bundled:" + f.file }, label(f, "bundled"))),
          ...info.user.map((f) => h("option", { value: "user:" + f.file }, label(f, "user"))));
        sel.value = P.fonts[cat];
        const warn = h("div", { class: "warn" });
        const range = h("input", { type: "range", min: 0.6, max: 2, step: 0.05, value: P.scale[cat] });
        const val = h("span", {}, Math.round(P.scale[cat] * 100) + "%");
        const check = () => {
          const id = sel.value, f = id.startsWith("bundled:") ? info.bundled.find((x) => "bundled:" + x.file === id) : info.user.find((x) => "user:" + x.file === id);
          const lacks = f && (f.cyrillic === false || cyr[f.file] === false) && !["numerals", "seals"].includes(cat);
          warn.textContent = lacks ? "В этом шрифте нет русских букв: он применится только к цифрам и латинице, русский текст покажется стандартным шрифтом." : "";
        };
        sel.onchange = async () => { await App.setPrefs({ fonts: { [cat]: sel.value } }); check(); };
        range.oninput = () => { val.textContent = Math.round(range.value * 100) + "%"; };
        range.onchange = () => App.setPrefs({ scale: { [cat]: Number(range.value) } });
        check();
        return h("div", { class: "cat" }, h("label", {}, title), sel, h("div", { class: "row between" }, range, val), warn);
      });
      const file = h("input", { type: "file", accept: ".ttf,.otf,.woff,.woff2", style: { display: "none" }, onchange: async (e) => {
        const f = e.target.files[0]; if (!f) return;
        try {
          const r = await fetch("/api/fonts/upload", { method: "POST", headers: { "X-Requested-With": "geo-table", "X-File-Name": encodeURIComponent(f.name) }, body: f });
          const j = await r.json(); if (!r.ok) throw new Error(j.error);
          toast("Шрифт «" + j.file + "» загружен"); nav("look");
        } catch (err) { toast(err.message, true); }
      } });
      const mine = h("div", {}, info.user.length ? info.user.map((f) => {
        const b = h("span", { class: "badge-c" }, "проверяю…");
        hasCyrillic(f.file).then((ok) => { cyr[f.file] = ok; b.textContent = ok === null ? "не удалось проверить" : ok ? "кириллица есть" : "без кириллицы"; b.className = "badge-c " + (ok ? "yes" : "no"); });
        return h("div", { class: "fontrow" }, h("span", {}, f.name), b, h("button", { class: "ph-btn danger", style: { flex: "none", padding: "4px 10px" }, onclick: async () => { await api("/api/fonts/delete", { file: f.file }); await App.loadUi(); nav("look"); } }, "✕"));
      }) : h("div", { class: "ph-note" }, "Своих шрифтов пока нет."));
      const online = h("input", { type: "checkbox", onchange: (e) => App.setPrefs({ online_fonts: e.target.checked }) });
      online.checked = !!P.online_fonts;
      return [h("div", { class: "ph-sec" }, "Цвет скатерти"), swatches(CLOTHS, "cloth"),
        h("div", { class: "ph-sec" }, "Цвет печатной машинки"), swatches(TYPEWRITERS, "typewriter"),
        h("div", { class: "ph-sec" }, "Шрифты по категориям"), ...cats,
        h("div", { class: "ph-sec" }, "Свои шрифты"), mine,
        h("button", { class: "ph-btn alt", onclick: () => file.click() }, "Загрузить шрифт (.ttf, .otf, .woff)"), file,
        h("div", { class: "ph-note" }, "Если в шрифте нет кириллицы, он применяется к цифрам и латинице, а русские буквы берутся из стандартного шрифта."),
        h("div", { class: "ph-sec" }, "Онлайн-шрифты"),
        h("label", { class: "row between" }, h("span", {}, "Подключить Google Fonts с кириллицей (нужен интернет)"), online),
        h("div", { class: "ph-note" }, "Old Standard TT, PT Serif, PT Sans, PT Mono, Marck Script. Без интернета ничего не ломается: подставятся стандартные шрифты.")];
    },
    export() {
      return [h("div", { class: "ph-sec" }, "Выгрузка партии"),
        h("a", { class: "ph-btn", href: "/api/export/log", download: "" }, "Полный лог партии (.txt)"),
        h("a", { class: "ph-btn", href: "/api/export/newspaper", download: "" }, "Хроника эпохи (.html)"),
        h("button", { class: "ph-btn alt", onclick: async () => { await api("/api/save", {}); toast("Партия сохранена"); } }, "Сохранить сейчас")];
    },
    turns() {
      const d = App.hud, st = { sure: null };
      const mk = (label, kind, fn, can) => {
        const b = h("button", { class: "ph-btn", disabled: !can ? "" : null }, label);
        b.disabled = !can;
        b.onclick = async () => {
          if (st.sure !== kind) { st.sure = kind; b.textContent = "Точно? " + label; b.classList.add("danger"); return; }
          try { await api(fn, {}); await App.refresh(); onWorldChanged(); nav("turns"); toast("Готово"); } catch (e) { toast(e.message, true); }
        };
        return b;
      };
      return [h("div", { class: "ph-sec" }, "Перемотка"), h("div", { class: "ph-note" }, `Сейчас ход ${d.turn}. Доступно шагов назад: ${d.can_rollback}, вперёд: ${d.can_redo}. «Вперёд» работает, пока не сыгран новый ход.`),
        mk("↩ Ход назад", "back", "/api/rollback", d.can_rollback > 0), mk("↪ Ход вперёд", "fwd", "/api/redo", d.can_redo > 0)];
    },
    exit() {
      const b = h("button", { class: "ph-btn danger", onclick: async () => { await api("/api/exit", {}); await toggle(false); onExit(); } }, "Сохранить и выйти в меню");
      return [h("div", { class: "ph-sec" }, "Выход"), h("div", { class: "ph-note" }, "Партия будет сохранена в её ячейку."), b];
    },
  };

  async function nav(id) {
    screen = id;
    const nodes = await screens[id]();
    const title = id === "home" ? "Pear" : (APPS.find((a) => a.id === id)?.name || "");
    const bodyEl = h("div", { class: "ph-body scrollable" + (id === "gm" ? " gm" : "") }, nodes);
    content.replaceChildren(h("div", { class: "ph-bar" }, id === "home" ? h("span") : h("button", { class: "ph-home", onclick: () => nav("home") }, "‹"), h("b", {}, title), h("span")), bodyEl);
  }

  async function toggle(want) {
    if (want === open) return;
    if (want) {
      content = h("div", { class: "ph-screen" });
      const phone = h("div", { class: "phone" }, h("div", { class: "ph-notch" }), content, h("button", { class: "ph-homebar", title: "На главный экран", onclick: () => nav("home") }));
      root = h("div", { class: "phone-wrap" }, h("div", { class: "phone-away", onclick: () => toggle(false) }), phone);
      root.style.zIndex = 95; stage.append(root);
      closed.classList.add("away"); open = true;
      await nav(inGame() ? "home" : "settings");
      await animate(phone, [{ transform: "translateY(520px) rotate(-14deg)" }, { transform: "rotate(-1.5deg)" }], { duration: 480 });
    } else {
      const phone = root.querySelector(".phone");
      await animate(phone, [{ transform: "rotate(-1.5deg)" }, { transform: "translateY(560px) rotate(-14deg)" }], { duration: 360, easing: "ease-in" });
      root.remove(); root = null; open = false; closed.classList.remove("away");
    }
  }
  addEventListener("keydown", (e) => { if (e.key === "Escape" && open && !document.querySelector(".nb-wrap")) toggle(false); });
  return { el: closed, close: () => toggle(false) };
}
