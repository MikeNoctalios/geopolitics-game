// Книга выбора партии: ячейка → сценарий и держава → сложность и хаос. Страницы переворачиваются в 3D.
import { h, art, api, sleep, animate, wobble, toast, loading } from "./util.js";
import { App } from "./store.js";
import { circle, line, arrowLeft } from "./scribble.js";

const DIFFS = ["Шутка", "Лёгкий", "Нормальный", "Хардкор"];
const CHAOS_HINT = ["строгий протокол", "строгий протокол", "строгий протокол", "лёгкое напряжение", "лёгкое напряжение", "наглость и дерзость", "наглость и дерзость", "паника и угрозы", "паника и угрозы", "безумие", "полный беспредел"];

const p = (txt, cls = "") => h("p", { class: "book-p " + cls }, txt);

function highlight(el, seed) {            // карандашная обводка выбранного пункта
  let tries = 0;
  const draw = () => {
    if (!el.isConnected) { if (tries++ < 120) requestAnimationFrame(draw); return; }
    const w = el.offsetWidth + 30, hh = el.offsetHeight + 22;     // размеры без учёта 3D-поворота
    if (!w || !hh) return;
    el.querySelector(".hl")?.remove();
    const holder = h("div", { class: "hl", style: { left: "-15px", top: "-11px", width: w + "px", height: hh + "px" } });
    holder.innerHTML = circle(w, hh, seed);
    el.append(holder);
  };
  requestAnimationFrame(draw);
}

export function mountBook(stage, onStarted) {
  const S = { step: 1, slot: null, scenario: null, country: null, diff: 2, solar: 2, menu: null, countries: {}, confirmDel: null };
  const left = h("div", { class: "page left" }), right = h("div", { class: "page right" });
  wobble(left, 11, 7); wobble(right, 12, 7);
  const spine = h("div", { class: "spine" });
  const scene = h("div", { class: "book-3d" }, left, right, spine);
  const book = h("div", { class: "book" }, scene);
  stage.append(book);

  async function load() {
    S.menu = await api("/api/menu");
    S.scenario = S.scenario || (S.menu.scenarios[0] && S.menu.scenarios[0].file);
  }
  async function countriesOf(file) {
    if (!S.countries[file]) S.countries[file] = (await api("/api/scenario?file=" + encodeURIComponent(file))).countries;
    return S.countries[file];
  }
  const scen = () => S.menu.scenarios.find((s) => s.file === S.scenario);

  /* ---------- шаг 1: ячейки ---------- */
  function step1() {
    const L = h("div", { class: "in" },
      h("h2", { class: "book-title" }, "Выбор ячейки сохранения"),
      p("Каждая ячейка хранит одну партию целиком: ход, дату, карту мира, переписку и армию."),
      p("Продолжите старую кампанию или начните новую в пустой ячейке. Сохранение можно скачать файлом и позже загрузить обратно."),
      p("Ключ API и модель настраиваются на телефоне в левом нижнем углу стола."),
      !App.config.has_key && h("p", { class: "book-p warn" }, "⚠ Ключ API не указан: без него мир не сможет обработать ни одного хода."));
    const R = h("div", { class: "in slots" }, S.menu.slots.map((s) => slotCard(s)));
    return { L, R };
  }
  function slotCard(s) {
    if (!s.exists) {
      const file = h("input", { type: "file", accept: "application/json", style: { display: "none" }, onchange: async (e) => {
        const f = e.target.files[0]; if (!f) return;
        try { await api("/api/menu/import", { slot: s.id, data: JSON.parse(await f.text()) }); await load(); render(0); }
        catch (err) { toast(err.message || "Файл не прочитан", true); }
      } });
      return h("div", { class: "slot empty" },
        h("div", { class: "slot-n hand" }, "Ячейка " + s.id), h("div", { class: "slot-sub" }, "пусто"),
        h("div", { class: "slot-btns" },
          h("button", { class: "pill", onclick: () => { S.slot = s.id; go(2); } }, "Новая игра"),
          h("button", { class: "pill small", onclick: () => file.click() }, "Загрузить файл"), file));
    }
    const del = S.confirmDel === s.id;
    return h("div", { class: "slot" },
      h("div", { class: "slot-n hand" }, "Ячейка " + s.id),
      h("div", { class: "slot-country" }, s.country),
      h("div", { class: "slot-sub" }, `Ход ${s.turn} · ${s.date}`),
      h("div", { class: "slot-sub" }, `${s.difficulty} · хаос ${s.solar}`),
      h("div", { class: "slot-btns" },
        h("button", { class: "pill", onclick: async (e) => {
          const btn = e.currentTarget; btn.disabled = true;
          let closeLoad = null;
          const timer = setTimeout(() => { closeLoad = loading(stage, "Накрываем на стол...", "Загружаем сохранённую партию…"); }, 160);
          try { await api("/api/menu/load", { slot: s.id }); clearTimeout(timer); if (closeLoad) await closeLoad(); onStarted(); }
          catch (err) { clearTimeout(timer); if (closeLoad) await closeLoad(); toast(err.message, true); btn.disabled = false; }
        } }, "Продолжить"),
        h("a", { class: "pill small", href: "/api/menu/download?slot=" + s.id, download: "" }, "Скачать"),
        h("button", { class: "pill small" + (del ? " danger" : ""), onclick: async () => {
          if (!del) { S.confirmDel = s.id; render(0); return; }
          S.confirmDel = null; await api("/api/menu/delete", { slot: s.id }); await load(); render(0);
        } }, del ? "Точно удалить?" : "Удалить")));
  }

  /* ---------- шаг 2: сценарий и держава ---------- */
  async function step2() {
    const cs = await countriesOf(S.scenario);
    if (!cs.find((c) => c.name === S.country)) S.country = cs[0]?.name;
    const list = h("div", { class: "scen-list" }, S.menu.scenarios.map((s) => {
      const on = s.file === S.scenario;
      const row = h("button", { class: "scen" + (on ? " on" : ""), onclick: () => { S.scenario = s.file; S.country = null; render(0); } },
        h("b", {}, s.name), h("span", {}, `старт ${s.start_date} · стран: ${s.count}` + (s.is_alt_history ? " · альт-история" : "")));
      if (on) highlight(row, 31);
      return row;
    }));
    const L = h("div", { class: "in" }, h("h2", { class: "book-title" }, "Сценарий"), list,
      scen() && p(scen().description || "Описание отсутствует.", "small"),
      p("Даже с подробным лором ИИ-гейммастер может ошибаться в географии и истории. Править мир вручную можно через чат с Гейммастером на телефоне.", "small dim"));
    const cur = cs.find((c) => c.name === S.country);
    const rows = h("div", { class: "country-list scrollable" }, cs.map((c) => {
      const on = c.name === S.country;
      const b = h("button", { class: "country" + (on ? " on" : ""), onclick: () => { S.country = c.name; render(0); } }, (c.is_great_power ? "★ " : "") + c.name, h("small", {}, c.region));
      return b;
    }));
    const R = h("div", { class: "in" }, h("h2", { class: "book-title" }, "Выбор державы"), rows,
      cur && h("div", { class: "country-card" },
        h("div", { class: "cc-head hand" }, cur.name),
        h("div", { class: "cc-row" }, `${cur.regime} · фракция: ${cur.faction}`),
        h("div", { class: "cc-row dim" }, cur.profile),
        h("div", { class: "cc-row" }, `Амбиции: ${cur.ambitions}`),
        h("div", { class: "cc-row" }, `Страхи: ${cur.fears}`),
        h("div", { class: "cc-stats" }, stat("Стаб.", cur.stability), stat("Боеготовн.", cur.military_readiness), stat("Подд. войны", cur.war_support), h("span", { class: "cc-army" }, "армия " + cur.manpower))),
      h("button", { class: "pill next", disabled: !cur, onclick: () => go(3) }, "Далее →"),
      h("button", { class: "back", onclick: () => go(1, true), title: "Назад" }, art(arrowLeft()), h("span", { class: "hand" }, "назад")));
    return { L, R };
  }
  const stat = (name, v) => h("span", { class: "cc-stat" }, h("b", {}, v), name);

  /* ---------- шаг 3: сложность, хаос, итог ---------- */
  function slider(kind) {
    const n = kind === "diff" ? 4 : 11, W = 520, pad = 14, key = kind === "diff" ? "diff" : "solar";
    const x = (i) => pad + (W - 2 * pad) * (n === 1 ? 0 : i / (n - 1));
    const svg = h("div", { class: "slider", style: { width: W + "px" } });
    const draw = () => {
      const cur = S[key];
      const dots = [...Array(n)].map((_, i) => `<circle cx="${x(i)}" cy="44" r="${i === cur ? 11 : 7}" fill="${i === cur ? "#15130f" : "#fdf0c4"}" stroke="#15130f" stroke-width="3.5"/>`).join("");
      const label = kind === "diff" ? DIFFS[cur].toLowerCase() : String(cur);
      svg.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="96" viewBox="0 0 ${W} 96">
        <path d="M${pad} 46 L${W - pad} 44" stroke="#15130f" stroke-width="3.5" stroke-linecap="round"/>${dots}
        <text x="${x(cur)}" y="22" text-anchor="middle" font-size="26" font-weight="700" font-family="var(--font-hand)" fill="#15130f">${label}</text></svg>`;
    };
    const pick = (ev) => {
      const r = svg.getBoundingClientRect(), k = r.width / W;
      const px = (ev.clientX - r.left) / k;
      S[key] = Math.max(0, Math.min(n - 1, Math.round(((px - pad) / (W - 2 * pad)) * (n - 1))));
      draw(); renderSummary();
    };
    svg.addEventListener("pointerdown", (e) => { svg.setPointerCapture(e.pointerId); pick(e); svg.onpointermove = pick; });
    svg.addEventListener("pointerup", () => { svg.onpointermove = null; });
    draw();
    return h("div", { class: "slider-box" }, svg, h("div", { class: "slider-cap hand" }, kind === "diff" ? "ШКАЛА СЛОЖНОСТИ" : "ШКАЛА ХАОСА"));
  }
  let summaryEl = null;
  function renderSummary() {
    if (!summaryEl) return;
    summaryEl.replaceChildren(
      h("div", { class: "sum-date" }, scen()?.start_date || ""),
      h("div", { class: "sum-country" }, S.country || "—"),
      h("div", { class: "sum-line" }, "Сложность: " + DIFFS[S.diff].toLowerCase()),
      h("div", { class: "sum-line" }, `Хаос: ${S.solar} — ${CHAOS_HINT[S.solar]}`));
  }
  function step3() {
    const L = h("div", { class: "in" },
      h("h2", { class: "book-title" }, "Выбор уровня сложности и хаоса"),
      p("Сложность влияет на простоту продвижения решений игрока. Чем она ниже, тем легче мир принимает любые его решения. Чем выше — тем больше ему придётся продумывать каждый свой шаг. Не влияет на реальную сложность ведения войн и установки дипломатических отношений — лишь требует большей проработки."),
      p("Шкала хаоса определяет долю случайности в поведении ботов и мировых событий. Низкие значения гарантируют строгое следование мировой истории, средние — умеренный элемент случайности и неожиданных поворотов, высокий — полный беспредел без чёткой логики."),
      slider("diff"), slider("solar"));
    summaryEl = h("div", { class: "summary" });
    const start = h("button", { class: "pill start", onclick: async () => {
      start.disabled = true;
      const closeLoad = loading(stage, "Накрываем на стол...", "Для новой партии ИИ составляет реестр вооружений вашей державы. Это может занять до минуты.");
      try {
        await api("/api/menu/start", { slot: S.slot, file: S.scenario, country: S.country, difficulty: DIFFS[S.diff], solar: S.solar });
        await closeLoad();
        onStarted();
      } catch (e) {
        await closeLoad();
        toast(e.message, true);
        start.disabled = false;
      }
    } }, "Начать!");
    const R = h("div", { class: "in" }, summaryEl, start,
      h("button", { class: "back", onclick: () => go(2, true), title: "Назад" }, art(arrowLeft()), h("span", { class: "hand" }, "назад")));
    renderSummary();
    return { L, R };
  }

  /* ---------- переключение шагов с переворотом страницы ---------- */
  async function build() { return S.step === 1 ? step1() : S.step === 2 ? await step2() : step3(); }

  let rid = 0, stale = false;
  async function render(dir) {                 // dir: 0 — просто перерисовать, 1 — вперёд, -1 — назад
    if (!dir && busy) { stale = true; return; }   // идёт переворот: перерисуем сразу после него
    const my = ++rid;
    const next = await build();
    if (my !== rid) return;                    // пока строили, запросили другую страницу — этот результат устарел
    if (!dir) { left.replaceChildren(next.L); right.replaceChildren(next.R); return; }
    const old = { L: left.firstChild, R: right.firstChild };
    // скрываем уходящий текст перед анимацией переворота, а сам лист крутим пустым — так исключается отзеркаливание
    const hiding = dir > 0 ? old.R : old.L;
    if (hiding) await animate(hiding, [{ opacity: 1 }, { opacity: 0 }], { duration: 100 });
    const leaf = h("div", { class: "leaf" + (dir > 0 ? "" : " rev") });
    const front = h("div", { class: "face front" }), back = h("div", { class: "face back" });
    wobble(front, 13, 6); wobble(back, 14, 6);
    leaf.append(front, back);
    scene.append(leaf);
    if (dir > 0) right.replaceChildren(next.R); else left.replaceChildren(next.L);
    await animate(leaf, [{ transform: "rotateY(0deg)" }, { transform: `rotateY(${dir > 0 ? -180 : 180}deg)` }], { duration: 680, easing: "cubic-bezier(.45,.05,.3,1)" });
    const reveal = dir > 0 ? next.L : next.R;
    reveal.style.opacity = "0";
    if (dir > 0) left.replaceChildren(next.L); else right.replaceChildren(next.R);
    leaf.remove();
    await animate(reveal, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
    reveal.style.opacity = "";
  }
  let busy = false;
  async function go(step, back = false) {
    while (busy) await sleep(40);              // клик во время переворота не теряем, а ждём его конца
    busy = true;
    try { S.step = step; App.emit("book-step", step); await render(back ? -1 : 1); } finally { busy = false; }
    if (stale) { stale = false; render(0); }
  }

  return {
    async start() {
      await load();
      const first = await build();
      left.replaceChildren(first.L); right.replaceChildren(first.R);
      App.emit("book-step", 1);
      await animate(book, [{ transform: "translateY(120px) rotate(-2deg) scale(.96)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 650 });
    },
    async destroy() {
      App.emit("book-step", 0);
      await animate(book, [{ transform: "none", opacity: 1 }, { transform: "translateX(-1100px) rotate(-6deg)", opacity: 0 }], { duration: 700, easing: "cubic-bezier(.5,0,.8,.4)" });
      book.remove();
    },
  };
}