// «Армия и ВПК»: сводный лист с печатями (печать берётся в руку и ставится на технику, пока не положишь обратно),
// полигон и отдельный жёлтый разведывательный лист, который пододвигается снизу.
import { h, art, api, sheet, animate, toast, sleep, loading } from "./util.js";
import { App } from "./store.js";
import { line } from "./scribble.js";

const TABS = [["infantry", "Пехота"], ["ground", "Техника"], ["air", "Авиация"], ["navy", "Флот"], ["stock", "Склад"], ["range", "Полигон"]];
const INTEL_TABS = TABS.slice(0, 4);
const ICONS = {
  red: '<svg viewBox="0 0 48 48" fill="none" stroke="#b32424" stroke-width="4" stroke-linecap="round"><circle cx="24" cy="12" r="6"/><path d="M24 18v14M14 24h20M24 32l-8 10M24 32l8 10"/><path d="M6 6l36 36M42 6L6 42" stroke-width="3.5"/></svg>',
  yellow: '<svg viewBox="0 0 48 48" fill="none" stroke="#c98a10" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 20L24 8l18 12v20H6z"/><path d="M14 40V26h20v14M14 31h20M14 36h20"/></svg>',
  blue: '<svg viewBox="0 0 48 48" fill="none" stroke="#2b6cb0" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><circle cx="24" cy="24" r="7"/><path d="M24 4v7M24 37v7M4 24h7M37 24h7M10 10l5 5M33 33l5 5M10 38l5-5M33 15l5-5"/></svg>',
};
const MEANING = {   // что делает печать на каждом листе
  cat: { red: "Снять с производства", yellow: "На консервацию", blue: "Модернизация (КБ)" },
  stock: { red: "В утиль", yellow: "Вернуть в строй", blue: "Глубокая модернизация" },
  range: { red: "Закрыть проект", yellow: "Принять на вооружение", blue: "На доработку (+6 мес.)" },
};
const IMPRINT = { red: "СНЯТ", yellow: "КОНС.", blue: "МОД." };
const hashStr = (s) => { let x = 7; for (const ch of String(s)) x = (Math.imul(x, 31) + ch.charCodeAt(0)) | 0; return Math.abs(x); };
function imprint(kind, name, k) {          // у каждого оттиска свой наклон, сторона недопечатки и вариант размазывания
  const n = hashStr(name + kind + k);
  return h("span", { class: `imprint ${kind} n${(n % 3) + 1}`, style: { "--tilt": ((n % 9) - 4) + "deg", "--fade": [120, 160, 200, 240][n % 4] + "deg" } }, IMPRINT[kind]);
}
const fmt = (n) => (n >= 10000 ? Math.round(n / 1000) + "k" : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "));
const LUPA = '<svg viewBox="0 0 48 48" fill="none" stroke="#3b382f" stroke-width="4.5" stroke-linecap="round"><circle cx="20" cy="20" r="12"/><path d="M29 29l13 13"/></svg>';

export function armyView() {
  let root = null, data = null, tab = "infantry", expanded = false, held = null, intelOpen = false, sureScrap = false, busy = false;
  let main, intel, tools = {}, cursor = null, ic = { country: null, tab: "infantry", data: null }, onMove = null, onKey = null;
  const mode = () => (tab === "stock" ? "stock" : tab === "range" ? "range" : "cat");

  /* ---------- главный лист ---------- */
  function rows() {
    if (tab === "range") {
      return data.projects.map((p) => ({ p, el: h("div", { class: "ar-row" },
        h("div", { class: "ar-main" }, h("b", {}, p.name), h("span", { class: "cnt" }, p.progress + "%"), h("span", {}, p.ready ? "готов к принятию" : p.status || "")),
        h("div", { class: "bar" }, h("i", { style: { width: p.progress + "%" } })),
        h("p", {}, `${p.type || ""} · срок: ${p.target_date || "?"} · база: ${p.base || "—"}`), p.report ? h("p", { class: "ev" }, p.report) : null) }));
    }
    const list = data.items.filter((i) => (tab === "stock" ? i.in_service === false : i.cat === tab && i.in_service !== false)).sort((a, b) => b.count - a.count);
    return list.map((it) => {
      const name = h("b", { class: "nm" }, it.name);
      const pen = h("button", { class: "pen", title: "Переименовать", onclick: () => rename(it, name) }, "✎");
      const chip = tab === "stock" ? null : h("button", { class: "chip2" + (it.production ? " on" : ""), title: "Выпуск", onclick: () => run(it.production ? "stop" : "start", it) }, it.production ? "выпуск идёт" : "выпуск остановлен");
      const marks = [!it.production && tab !== "stock" ? "red" : null, it.in_rd ? "blue" : null, tab === "stock" ? "yellow" : null].filter(Boolean);
      return { it, el: h("div", { class: "ar-row" }, pen, h("div", { class: "ar-main" }, name, h("span", {}, it.type ? `(${it.type})` : ""), h("span", { class: "cnt" }, fmt(it.count)), chip),
        h("p", {}, it.specs || ""), it.evaluation ? h("p", { class: "ev" }, it.evaluation) : null,
        h("div", { class: "marks" }, marks.map((m, k) => imprint(m, it.name, k)))) };
    });
  }

  function paintMain() {
    const all = rows(), shown = expanded ? all : all.slice(0, 4);
    const total = tab === "infantry" ? `ОБЩАЯ ЧИСЛЕННОСТЬ: ${data.manpower}` : tab === "range" ? `ПРОЕКТОВ В РАБОТЕ: ${data.projects.length}` : tab === "stock" ? `НА СКЛАДЕ: ${all.length} образцов` : `В СТРОЮ: ${fmt(all.reduce((s, r) => s + r.it.count, 0))} ед.`;
    const body = main.querySelector(".ar-body");
    body.replaceChildren(...(shown.length ? shown.map((r) => { r.el.onclick = (e) => stampOn(r, e); return r.el; }) : [h("p", { class: "ar-empty" }, tab === "navy" && data.landlocked ? "У державы нет выхода к морю." : "Здесь пока пусто.")]));
    main.querySelector(".ar-total").textContent = total;
    main.querySelector(".ar-more").textContent = all.length > 4 ? (expanded ? "▲ свернуть список" : `▼ развернуть: ещё ${all.length - 4}`) : "";
    main.querySelectorAll(".ar-tab").forEach((b) => b.classList.toggle("on", b.dataset.t === tab));
    for (const [k, t] of Object.entries(tools)) t.title = MEANING[mode()][k];
    main.parentElement.classList.toggle("tall", expanded);
  }

  async function run(kind, it) {
    if (busy) return; busy = true;
    try { const r = await api("/api/army/act", { kind, cat: it.cat, idx: it.idx, name: it.name }); data = r.army; toast(r.message); paintMain(); }
    catch (e) { toast(e.message, true); } finally { busy = false; }
  }
  function rename(it, nameEl) {
    const inp = h("input", { class: "ren", value: it.name });
    nameEl.replaceWith(inp); inp.focus(); inp.select();
    const done = async (ok) => {
      if (!ok || !inp.value.trim() || inp.value === it.name) return paintMain();
      try { data = (await api("/api/army/act", { kind: "rename", cat: it.cat, idx: it.idx, name: it.name, value: inp.value })).army; } catch (e) { toast(e.message, true); }
      paintMain();
    };
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") done(true); if (e.key === "Escape") done(false); });
    inp.addEventListener("blur", () => done(true));
  }

  /* ---------- печать в руке ---------- */
  function hold(kind) {
    release();
    if (!kind) return;
    held = kind; sureScrap = false;
    cursor = h("div", { class: "stamp-cursor " + kind }); cursor.innerHTML = tools[kind].innerHTML;
    root.closest("#stage").append(cursor);
    root.classList.add("holding");
    Object.entries(tools).forEach(([k, t]) => t.classList.toggle("held", k === kind));
    toast(`В руке печать: ${MEANING[mode()][kind]}. Щёлкайте по строкам; Esc или правая кнопка — положить.`, false, 3200);
  }
  function release() {
    held = null; if (cursor) { cursor.remove(); cursor = null; }
    root && root.classList.remove("holding"); Object.values(tools).forEach((t) => t.classList.remove("held"));
  }
  async function stampOn(r, ev) {
    if (!held || busy || ev.target.closest("button,input")) return;
    const kind = held, m = mode();
    try {
      if (m === "range") {
        const p = r.p;
        if (kind === "yellow") {
          const name = prompt("Армейское обозначение для серийного образца:", p.name);
          if (name === null) return;
          await thump(r.el, kind); const res = await api("/api/army/project", { kind: "adopt", idx: p.idx, value: name }); data = res.army; toast(res.message);
        } else { await thump(r.el, kind); const res = await api("/api/army/project", { kind: kind === "red" ? "cancel" : "refine", idx: p.idx }); data = res.army; toast(res.message); }
      } else {
        const it = r.it, action = m === "stock" ? { red: "scrap", yellow: "unmoth", blue: "modernize" }[kind] : { red: "stop", yellow: "moth", blue: "modernize" }[kind];
        if (action === "stop" && !it.production) return toast("Производство уже остановлено", true);
        if (action === "scrap" && !sureScrap) { if (!confirm("Утилизировать образец навсегда? Это действие необратимо.")) return; sureScrap = true; }
        busy = true; await thump(r.el, kind);
        const res = await api("/api/army/act", { kind: action, cat: it.cat, idx: it.idx, name: it.name }); data = res.army; toast(res.message);
      }
    } catch (e) { toast(e.message, true); } finally { busy = false; }
    paintMain();
  }
  async function thump(el, kind) {
    const mark = h("div", { class: "thump " + kind }); mark.innerHTML = ICONS[kind]; el.append(mark);
    await animate(mark, [{ transform: "scale(2.6) rotate(-14deg)", opacity: 0 }, { transform: "scale(1) rotate(-8deg)", opacity: .95, offset: .55 }, { transform: "scale(1.06) rotate(-8deg)", opacity: .9 }], { duration: 330 });
    await sleep(120);
  }

  /* ---------- разведка ---------- */
  async function loadIntel(country) {
    try { ic.data = await api("/api/army/intel" + (country ? "?country=" + encodeURIComponent(country) : "")); ic.country = ic.data.country; paintIntel(); }
    catch (e) { toast(e.message, true); }
  }
  function paintIntel() {
    const d = ic.data; if (!d) return;
    intel.querySelector(".ic-head").replaceChildren(h("span", {}, "ЛИСТ РАЗВЕДЫВАТЕЛЬНЫЙ ПО ВПК"), h("button", { class: "ic-country hand", onclick: pickCountry }, d.country + " ▾"));
    intel.querySelector(".ic-tabs").replaceChildren(...INTEL_TABS.map(([id, label]) => h("button", { class: "ar-tab" + (id === ic.tab ? " on" : ""), onclick: () => { ic.tab = id; paintIntel(); } }, label)));
    const items = d.categories[ic.tab] || [];
    intel.querySelector(".ic-body").replaceChildren(h("p", { class: "ar-total" }, ic.tab === "infantry" ? `ЧИСЛЕННОСТЬ (оценка): ${d.manpower}` : `ИЗВЕСТНО ЕДИНИЦ: ${items.length}`),
      ...(items.length ? items.map((i) => h("div", { class: "ar-row ic" }, h("div", { class: "ar-main" }, h("b", {}, i.name), h("span", {}, i.type ? `(${i.type})` : ""), h("span", { class: "cnt" }, "~" + (typeof i.count === "number" ? fmt(i.count) : i.count))))) : [h("p", { class: "ar-empty" }, ic.tab === "navy" && d.landlocked ? "Выхода к морю нет." : "Разведка ничего не знает.")]));
  }
  function pickCountry() {
    const old = intel.querySelector(".lt-picker"); if (old) return old.remove();
    const box = h("div", { class: "lt-picker scrollable", style: { left: "60px", top: "100px", width: "420px" } }, ic.data.targets.map((c) => h("button", { class: "lt-pick" + (c === ic.country ? " on" : ""), onclick: () => { box.remove(); loadIntel(c); } }, c)));
    intel.append(box);
  }
  async function audit(country, btn) {
    btn.disabled = true; toast("Инспекция ВПК проводит аудит…");
    try { const r = await api("/api/army/audit", { country }); data = r.army; toast(r.message); paintMain(); if (country !== data.country) loadIntel(country); }
    catch (e) { toast(e.message, true); } btn.disabled = false;
  }
  async function showIntel(on) {
    if (on === intelOpen) return; intelOpen = on; release();
    if (on && !ic.data) await loadIntel();
    const AWAY = "translate(0,940px)";
    main.parentElement.style.zIndex = on ? 11 : 13; intel.parentElement.style.zIndex = on ? 13 : 11;
    root.classList.toggle("intel-on", on);
    await Promise.all([animate(main.parentElement, [{ transform: on ? "none" : AWAY }, { transform: on ? AWAY : "none" }], { duration: 650 }),
      animate(intel.parentElement, [{ transform: on ? AWAY : "none" }, { transform: "none" }], { duration: 650 })]);
  }

  return {
    async mount(host) {
      const stage = host.closest("#stage");
      let closeLoad = null;
      const timer = stage ? setTimeout(() => { closeLoad = loading(stage, "Накрываем на стол...", "ИИ составляет реестр вооружений вашей державы. Это может занять до минуты."); }, 250) : null;
      try { data = await api("/api/army"); }
      finally { if (timer) clearTimeout(timer); if (closeLoad) await closeLoad(); }
      root = h("div", { class: "view army" });
      const ms = sheet({ x: 480, y: 70, w: 760, hgt: 940, cls: "news", seed: 140, amp: 5, rot: .3 });
      const is = sheet({ x: 500, y: 70, w: 760, hgt: 940, cls: "intel", seed: 141, amp: 5, rot: -.7 });
      main = ms.sheet; intel = is.sheet; ms.wrap.classList.add("main-w"); is.wrap.classList.add("intel-w");
      const lupa = h("button", { class: "lupa", title: "Аудит реестра ВПК", onclick: (e) => audit(null, e.currentTarget) }); lupa.innerHTML = LUPA;
      main.append(h("div", { class: "ar" }, h("div", { class: "ar-tabs" }, TABS.map(([id, label]) => h("button", { class: "ar-tab", "data-t": id, onclick: () => { tab = id; expanded = false; release(); paintMain(); } }, label))),
        h("div", { class: "ar-title" }, h("span", { class: "ar-total" }), lupa), h("div", { class: "ar-body" }), h("button", { class: "ar-more hand", onclick: () => { expanded = !expanded; paintMain(); } }),
        h("button", { class: "peek-label label", onclick: () => showIntel(false) }, "↑ вернуть сводный лист ВПК")));
      const ilupa = h("button", { class: "lupa", title: "Аудит данных разведки", onclick: (e) => audit(ic.country, e.currentTarget) }); ilupa.innerHTML = LUPA;
      intel.append(h("div", { class: "ar" }, h("div", { class: "ic-head label" }), ilupa, h("div", { class: "ic-tabs ar-tabs" }), h("div", { class: "ic-body ar-body" }),
        h("button", { class: "peek-label label", onclick: () => showIntel(true) }, "↑ пододвинуть лист разведки")));
      // печати справа от листа
      const rack = h("div", { class: "stamp-rack" }, ["red", "yellow", "blue"].map((k) => {
        const t = h("button", { class: "stamp-tool " + k, onclick: () => (held === k ? release() : hold(k)) }, h("i", {}, ""), h("div", { class: "ink" }));
        t.querySelector(".ink").innerHTML = ICONS[k]; t.title = ""; tools[k] = t; return t;
      }));
      root.append(is.wrap, ms.wrap, rack);
      host.append(root);
      paintMain();
      ms.wrap.style.zIndex = 13; is.wrap.style.zIndex = 11; is.wrap.style.transform = "translate(0,940px)"; is.wrap.style.setProperty("--x", "1");
      onMove = (e) => { if (!cursor) return; const r = stage.getBoundingClientRect(), k = r.width / 1920; cursor.style.left = (e.clientX - r.left) / k + "px"; cursor.style.top = (e.clientY - r.top) / k + "px"; };
      onKey = (e) => { if (e.key === "Escape") release(); };
      addEventListener("pointermove", onMove); addEventListener("keydown", onKey);
      root.addEventListener("contextmenu", (e) => { if (held) { e.preventDefault(); release(); } });
      await Promise.all([animate(ms.wrap, [{ transform: "translateY(900px) rotate(4deg)" }, { transform: "none" }], { duration: 650 }),
        animate(rack, [{ transform: "translateX(300px)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 650 }),
        animate(is.wrap, [{ transform: "translate(0,1100px)" }, { transform: "translate(0,940px)" }], { duration: 650 })]);
    },
    async unmount() {
      if (!root) return;
      release(); removeEventListener("pointermove", onMove); removeEventListener("keydown", onKey);
      await animate(root, [{ opacity: 1 }, { opacity: 0, transform: "translateY(60px)" }], { duration: 300 });
      root.remove(); root = null;
    },
  };
}