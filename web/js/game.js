// Игровой стол: собирает шапку, меню, календарь, блокнот, подсказки и текущую вкладку.
import { h, sleep, toast, animate } from "./util.js";
import { App, TABS } from "./store.js";
import { mountHud } from "./hud.js";
import { mountNav } from "./nav.js";
import { mountTurn } from "./turn.js";
import { newsView } from "./news.js";
import { placeholderView } from "./placeholder.js";
import { decreesView } from "./decrees.js";
import { diplomacyView } from "./diplomacy.js";
import { advisorsView } from "./advisors.js";
import { armyView } from "./army.js";
import { summitsView } from "./summits.js";
import { mountNotebook } from "./notebook.js";

const VIEWS = {
  news: () => newsView(),
  decrees: () => decreesView(),
  diplomacy: () => diplomacyView(),
  summits: () => summitsView(),
  army: () => armyView(),
  advisors: () => advisorsView(),
};

/* ---------- интерактивные подсказки по всем вкладкам ---------- */
function isVisible(el) {
  if (!el || !el.isConnected) return false;
  const cs = getComputedStyle(el);
  if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) return false;
  const r = el.getBoundingClientRect();
  return r.width > 4 && r.height > 4;
}

function boxOf(stage, el, pad = 6, clipSel = null) {
  const sr = stage.getBoundingClientRect(), k = sr.width / 1920;
  if (!k) return null;
  const r = el.getBoundingClientRect();
  let x1 = (r.left - sr.left) / k, y1 = (r.top - sr.top) / k;
  let x2 = x1 + r.width / k, y2 = y1 + r.height / k;
  const clipEl = clipSel ? document.querySelector(clipSel) : null;
  if (clipEl && isVisible(clipEl)) {
    const cr = clipEl.getBoundingClientRect();
    const cx1 = (cr.left - sr.left) / k, cy1 = (cr.top - sr.top) / k;
    x1 = Math.max(x1, cx1); y1 = Math.max(y1, cy1);
    x2 = Math.min(x2, cx1 + cr.width / k); y2 = Math.min(y2, cy1 + cr.height / k);
  }
  x1 = Math.max(4, x1 - pad); y1 = Math.max(4, y1 - pad);
  x2 = Math.min(1916, x2 + pad); y2 = Math.min(1076, y2 + pad);
  if (x2 - x1 < 12 || y2 - y1 < 12) return null;
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

function overlapArea(a, b) {
  const ox = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
  const oy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  return ox * oy;
}

function distBox(a, b) {
  const dx = Math.max(0, a.x - (b.x + b.w), b.x - (a.x + a.w));
  const dy = Math.max(0, a.y - (b.y + b.h), b.y - (a.y + a.h));
  return Math.hypot(dx, dy);
}

function placeCard(cw, ch, T, side, obstacles, placed) {
  const minX = 18, maxX = 1902 - cw, minY = 70, maxY = 1062 - ch;
  const clampX = (v) => Math.max(minX, Math.min(maxX, v));
  const clampY = (v) => Math.max(minY, Math.min(maxY, v));
  const cands = [];
  const ys = [T.y, T.y + (T.h - ch) / 2, T.y + T.h - ch, T.y - 24, T.y + 24];
  const xs = [T.x, T.x + (T.w - cw) / 2, T.x + T.w - cw, T.x - 36, T.x + 36];
  for (const g of [16, 26, 40]) {
    for (const y of ys) cands.push([T.x + T.w + g, y], [T.x - cw - g, y]);
    for (const x of xs) cands.push([x, T.y - ch - g], [x, T.y + T.h + g]);
  }
  for (let gx = minX; gx <= maxX; gx += 34) {
    for (let gy = minY; gy <= maxY; gy += 30) cands.push([gx, gy]);
    cands.push([gx, maxY]);
  }
  let best = { x: minX, y: minY, score: Infinity };
  for (const [rx, ry] of cands) {
    const x = clampX(rx), y = clampY(ry);
    const c = { x, y, w: cw, h: ch };
    let cardHit = 0;
    for (const p of placed) cardHit += overlapArea(c, p);
    let obsHit = 0;
    for (const o of obstacles) obsHit += overlapArea(c, o);
    const d = distBox(c, T);
    const onSide =
      (side === "left" && x + cw <= T.x + 2) ||
      (side === "right" && x >= T.x + T.w - 2) ||
      (side === "top" && y + ch <= T.y + 2) ||
      (side === "bottom" && y >= T.y + T.h - 2);
    const score = cardHit * 1e6 + obsHit * 1e3 + d - (onSide ? 28 : 0);
    if (score < best.score) best = { x, y, score };
    if (score <= 16 && cardHit === 0 && obsHit === 0) break;
  }
  placed.push({ x: best.x - 10, y: best.y - 10, w: cw + 20, h: ch + 20 });
  return best;
}

function tabSpecs(tab) {
  if (tab === "news") {
    return [
      { sel: ".news-scroll .sheet-wrap", clip: ".news-scroll", side: "left", text: "Газета «Сводка»: слева — мировые события, справа — дела вашей державы и ваши указы. Прокручивайте колесом мыши." },
      { sel: ".flip-arrow", pad: 8, side: "right", text: "Стрелка: перевернуть газету на обратную сторону (второстепенные новости, слухи и вырезки из мировой прессы)." },
      { sel: ".fsz", side: "left", text: "Размер шрифта газеты: уменьшить (A−) или увеличить (A+) текст выпуска." },
      { sel: ".lane:not(.hidden)", side: "top", text: "Архив выпусков: нажмите «предыдущий ход» или выберите нужный свёрток газеты за прошлые ходы." },
    ];
  }
  if (tab === "decrees") {
    return [
      { sel: ".paper-window .typed-sheet", clip: ".paper-window", side: "right", text: "Бумага из машинки: пишите указы свободным текстом. Они сохраняются сами и уйдут при завершении хода." },
      { sel: ".agenda", side: "left", text: "Повестка дня. Нажмите на лист, чтобы развернуть весь список задач и происшествий." },
      { sel: ".typewriter", side: "top", text: "Машинка — просто украшение. Её цвет меняется на телефоне, в «Оформлении»." },
    ];
  }
  if (tab === "diplomacy") {
    return [
      { sel: ".envelope", side: "right", text: "Конверт с печатью: нажмите, чтобы выбрать державу-адресата. Значок у имени — непрочитанная депеша." },
      { sel: () => document.querySelector(".lt-logbox")?.closest(".sheet-wrap"), side: "top", text: "Стенограмма диалога: история переписки с выбранной державой. Кнопка «развернуть» откроет беседу на большой лист." },
      { sel: () => document.querySelector(".lt-write")?.closest(".sheet-wrap"), side: "top", text: "Лист для ответа: напишите депешу и нажмите «Отправить депешу» (или Ctrl+Enter). Письма уходят с завершением хода." },
      { sel: ".side-note", side: "bottom", text: "Досье державы: регион, строй, фракция, отношение к вам, её амбиции и страхи." },
    ];
  }
  if (tab === "summits") {
    if (document.querySelector(".view.summits .hall")) {
      return [
        { sel: () => document.querySelector(".sm-top")?.closest(".sheet-wrap"), side: "left", text: "Повестка саммита: название конференции и обсуждаемый вопрос." },
        { sel: () => document.querySelector(".sm-log")?.closest(".sheet-wrap"), side: "left", text: "Стенограмма круглого стола: здесь появляются речи делегатов и итоговый вердикт." },
        { sel: ".seat.me", pad: 8, side: "left", text: "Места делегаций за столом. При выступлении табличка подсвечивается, а после голосования видны отметки: ✓, ✗ или ○." },
        { sel: ".sm-ctl", pad: 8, side: "top", text: "Управление саммитом: выступите с речью, промолчите, вынесите проект на голосование или поставьте штамп-голос." },
        { sel: ".sm-side", pad: 8, side: "right", text: "«Совет МИД» — конфиденциальный бриф министра; «Покинуть (демарш)» — демонстративно сорвать переговоры и уйти." },
      ];
    }
    return [
      { sel: ".sm-fields", side: "left", text: "Название и повестка дня: сформулируйте тему конференции и ваши первоначальные требования." },
      { sel: ".sm-setup .nations", side: "right", text: "Приглашённые державы: выберите участников круглого стола (★ — великие державы)." },
      { sel: ".sm-setup .row2", side: "top", text: "Степень секретности: публичный саммит или секретные переговоры только для участников." },
      { sel: ".sm-setup .go2", side: "top", text: "Объявить созыв: открыть конференцию и перейти в зал заседаний." },
      { sel: () => document.querySelector(".sm-arch")?.closest(".sheet-wrap"), side: "top", text: "Архив саммитов: нажмите на завершённую встречу, чтобы открыть стенограмму и итоги." },
    ];
  }
  if (tab === "army") {
    if (document.querySelector(".view.army.intel-on")) {
      return [
        { sel: ".ic-country", side: "right", text: "Держава: нажмите на название, чтобы выбрать другую страну для изучения данных разведки." },
        { sel: ".ic-tabs", side: "bottom", text: "Категории разведки: стрелковое вооружение, техника, авиация и флот выбранной державы." },
        { sel: ".sheet.intel .lupa", side: "right", text: "Лупа: ИИ-аудит и упорядочивание разведданных по выбранной державе." },
        { sel: ".sheet.news .peek-label", side: "top", text: "Уголок листа: вернуть ваш сводный лист ВПК и печати." },
      ];
    }
    return [
      { sel: ".main-w .ar-tabs", side: "bottom", text: "Вкладки: пехота, техника, авиация, флот, склад (законсервированное) и полигон (разработки конструкторского бюро)." },
      { sel: ".stamp-rack", pad: 8, side: "left", text: "Три печати. Нажмите на печать, чтобы взять её в руку, и щёлкайте по строкам. Красная — снять с производства (на складе — в утиль), жёлтая — на консервацию (со склада — в строй), синяя — модернизация. Esc или правая кнопка — положить печать." },
      { sel: ".main-w .chip2", side: "right", text: "Статус выпуска. Нажмите, чтобы остановить или возобновить производство." },
      { sel: ".main-w .pen", side: "left", text: "Карандаш: переименовать образец." },
      { sel: ".main-w .lupa", side: "right", text: "Лупа: ИИ-аудит реестра (убирает дубли, исправляет категории и эпоху)." },
      { sel: ".main-w .ar-more", side: "bottom", text: "Развернуть: показать весь список, а не четыре самых многочисленных образца." },
      { sel: ".sheet.intel .peek-label", side: "top", text: "Уголок листа: пододвинуть лист разведки с данными о других державах." },
    ];
  }
  if (tab === "advisors") {
    return [
      { sel: ".envelope", side: "right", text: "Конверт с печатью: нажмите, чтобы выбрать министра (внутренних дел, иностранных дел или обороны)." },
      { sel: () => document.querySelector(".lt-logbox")?.closest(".sheet-wrap"), side: "top", text: "Стенограмма беседы с министром. Нажмите «развернуть», чтобы читать переписку на большом листе." },
      { sel: () => document.querySelector(".lt-write")?.closest(".sheet-wrap"), side: "top", text: "Лист для вопроса: задайте вопрос министру и нажмите «Спросить» (или Ctrl+Enter). Министр отвечает сразу с помощью ИИ, ход не тратится." },
    ];
  }
  return [];
}

const COMMON_HINTS = [
  { sel: ".nav", side: "left", text: "Меню вкладок. Значок у «Дипломатии» — непрочитанные письма." },
  { sel: ".cal", side: "top", text: "Календарь: «Завершить ход». Мир обработает указы, депеши и приказы." },
  { sel: ".nb-closed", side: "left", text: () => ["Блокнот на ", h("b", {}, "99"), " страниц. Записи хранятся вместе с партией."] },
  { sel: ".nb-wrap", side: "left", text: () => ["Открытый блокнот на ", h("b", {}, "99"), " страниц: пишите заметки, подписывайте и листайте страницы."] },
  { sel: ".phone-closed", side: "top", text: "Телефон: Гейммастер, настройки, оформление, экспорт, ходы назад и вперёд, выход." },
  { sel: ".seals", side: "right", text: "Печати показателей: стабильность, боеготовность и поддержка войны." },
];

function mountHints(stage) {
  let overlay = null;
  const btn = h("button", { class: "hint-btn label", title: "Подсказки по экрану", "aria-label": "Подсказки", onclick: () => (overlay ? close() : open()) }, "?");
  stage.append(btn);

  function buildOverlay() {
    const specs = [...tabSpecs(App.tab), ...COMMON_HINTS], spots = [];
    for (const s of specs) {
      const el = typeof s.sel === "function" ? s.sel() : document.querySelector(s.sel);
      if (!isVisible(el)) continue;
      const box = boxOf(stage, el, s.pad ?? 6, s.clip);
      if (box) spots.push({ ...s, box });
    }
    const holes = spots.map((s) => `<rect x="${s.box.x.toFixed(1)}" y="${s.box.y.toFixed(1)}" width="${s.box.w.toFixed(1)}" height="${s.box.h.toFixed(1)}" rx="12" fill="#000"/>`).join("");
    const dim = h("div", { class: "hints-dim-wrap" });
    dim.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="hints-dim" width="1920" height="1080" viewBox="0 0 1920 1080"><defs><mask id="geo-hints-mask"><rect width="1920" height="1080" fill="#fff"/>${holes}</mask></defs><rect width="1920" height="1080" fill="rgba(0,0,0,.55)" mask="url(#geo-hints-mask)"/></svg>`;
    const banner = h("div", { class: "hints-banner" }, "Подсказки · нажмите в любом месте, чтобы закрыть");
    const back = h("div", { class: "hints-back", onclick: () => close() }, dim, banner);
    const obstacles = [
      { x: 520, y: 0, w: 880, h: 68 },      // верхний баннер
      { x: 1810, y: 68, w: 76, h: 76 },     // кнопка «?»
    ];
    const cards = spots.map((s, idx) => {
      const n = idx + 1;
      const num = h("span", { class: "hint-num" }, n);
      if (s.box.x < 18) num.style.left = "2px";
      if (s.box.y < 18) num.style.top = "2px";
      back.append(h("div", { class: "hint-spot", style: { left: s.box.x + "px", top: s.box.y + "px", width: s.box.w + "px", height: s.box.h + "px" } }, num));
      obstacles.push({ x: s.box.x - 10, y: s.box.y - 10, w: s.box.w + 20, h: s.box.h + 20 });
      obstacles.push({ x: Math.max(0, s.box.x - 16), y: Math.max(0, s.box.y - 16), w: 34, h: 34 });
      const content = typeof s.text === "function" ? s.text() : s.text;
      const card = h("div", { class: "hint-card", style: { visibility: "hidden", transform: `rotate(${((idx % 5) - 2) * 0.65}deg)` } },
        h("span", { class: "hint-badge" }, n), h("p", {}, content));
      back.append(card);
      return { card, box: s.box, side: s.side };
    });
    stage.append(back);
    const placed = [];
    for (const c of cards) {
      const pos = placeCard(c.card.offsetWidth, c.card.offsetHeight, c.box, c.side, obstacles, placed);
      c.card.style.left = pos.x + "px";
      c.card.style.top = pos.y + "px";
      c.card.style.visibility = "";
    }
    return back;
  }

  const onResize = () => {
    if (!overlay) return;
    overlay.remove();
    overlay = buildOverlay();
  };
  const onKey = (e) => {
    if (e.key === "Escape" && overlay) {
      e.stopImmediatePropagation();
      e.preventDefault();
      close();
    }
  };
  function open() {
    if (overlay) return;
    btn.classList.add("on");
    overlay = buildOverlay();
    addEventListener("resize", onResize);
    addEventListener("keydown", onKey, true);
    animate(overlay, [{ opacity: 0 }, { opacity: 1 }], { duration: 180 });
  }
  function close() {
    if (!overlay) return;
    const el = overlay; overlay = null;
    btn.classList.remove("on");
    removeEventListener("resize", onResize);
    removeEventListener("keydown", onKey, true);
    animate(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 150 }).then(() => el.remove());
  }

  return {
    el: btn,
    close,
    enter: () => animate(btn, [{ transform: "translateY(-160px) scale(.6)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 600 }),
    leave: () => { close(); return animate(btn, [{ opacity: 1 }, { transform: "translateY(-160px) scale(.6)", opacity: 0 }], { duration: 400 }); },
  };
}

export function mountGame(stage) {
  App.setTabs(TABS);                       // меню строится из списка; новые вкладки = новая запись в TABS и в VIEWS
  const host = h("div", { class: "desk-host" });
  stage.append(host);
  const hud = mountHud(stage);
  const nav = mountNav(stage, switchTab);
  const turn = mountTurn(stage);
  const notebook = mountNotebook(stage);
  const hints = mountHints(stage);
  let view = null, switching = false, pending = null;

  async function switchTab(id, force = false) {
    if (switching) { pending = { id, force }; return; }     // клик во время анимации не теряем: побеждает последний
    if (id === App.tab && view && !force) return;
    switching = true;
    hints.close();
    try {
      if (view) await view.unmount();
      App.tab = id; App.emit("tab", id);
      const tab = App.tabs.find((t) => t.id === id);
      view = (VIEWS[id] || (() => placeholderView(tab ? tab.label : id, "Этот раздел появится позже.")))();
      await view.mount(host);
    } catch (e) { toast(e.message, true); } finally {
      switching = false;
      if (pending) { const p = pending; pending = null; switchTab(p.id, p.force); }
    }
  }
  App.on("turn-done", () => switchTab("news", true));
  App.on("world-changed", () => view && switchTab(App.tab, true));

  return {
    async start() {
      hud.enter(); nav.enter(); turn.enter(); notebook.enter(); hints.enter();
      await sleep(350);
      await switchTab(App.tab || "news", true);
    },
    async destroy() {
      hints.close();
      if (view) await view.unmount();
      await Promise.all([hud.leave(), nav.leave(), turn.leave(), notebook.leave(), hints.leave()]);
      [hud.el, nav.el, turn.el, notebook.el, hints.el, host].forEach((e) => e?.remove?.());
    },
  };
}