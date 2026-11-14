// Вкладка «Указы»: сверху лист повестки дня, снизу печатная машинка (чистая декорация), текст свободно редактируется.
import { h, art, api, sheet, animate, sleep, toast, rng } from "./util.js";
import { App, TYPEWRITERS } from "./store.js";

function typewriterSvg(c) {
  const rows = [13, 12, 11];
  let keys = "", idx = 0;
  rows.forEach((n, r) => {
    const y = 156 + r * 46, x0 = 460 - ((n - 1) * 52) / 2;
    for (let i = 0; i < n; i++) {
      const x = x0 + i * 52;
      keys += `<g class="key" data-k="${idx++}"><ellipse cx="${x + 1}" cy="${y + 7}" rx="20" ry="17" fill="#000" opacity=".45"/>
        <circle class="cap" cx="${x}" cy="${y}" r="19" fill="url(#keyG)" stroke="#3d4147" stroke-width="2.5"/><circle cx="${x}" cy="${y}" r="12.5" fill="none" stroke="rgba(0,0,0,.28)" stroke-width="2"/>
        <path d="M${x - 11} ${y - 6}a13 13 0 0 1 11-8" fill="none" stroke="rgba(255,255,255,.7)" stroke-width="2.2" stroke-linecap="round"/></g>`;
    }
  });
  keys += `<g class="key" data-k="space"><rect x="300" y="276" width="320" height="26" rx="13" fill="#000" opacity=".4" transform="translate(1,5)"/><rect class="cap" x="300" y="276" width="320" height="26" rx="13" fill="url(#keyG)" stroke="#3d4147" stroke-width="2.5"/></g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="920" height="324" viewBox="0 0 920 324">
  <defs>
    <linearGradient id="bodyG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c.hi}"/><stop offset=".12" stop-color="${c.body}"/><stop offset="1" stop-color="${c.dark}"/></linearGradient>
    <linearGradient id="chrome" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f3f4f6"/><stop offset=".45" stop-color="#a9afb7"/><stop offset=".55" stop-color="#7b818a"/><stop offset="1" stop-color="#d4d8de"/></linearGradient>
    <linearGradient id="rubber" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a4a4e"/><stop offset=".3" stop-color="#1b1b1e"/><stop offset=".75" stop-color="#101012"/><stop offset="1" stop-color="#36363a"/></linearGradient>
    <radialGradient id="keyG" cx=".36" cy=".3" r=".85"><stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#d9dce0"/><stop offset="1" stop-color="#8b9199"/></radialGradient>
    <filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="4"/><feColorMatrix values="0 0 0 0 .5  0 0 0 0 .5  0 0 0 0 .5  0 0 0 .9 0"/><feComposite in2="SourceAlpha" operator="in"/></filter>
  </defs>
  <path d="M10 324V168Q10 98 84 92H836Q910 98 910 168V324Z" fill="url(#bodyG)" stroke="#0b0b0d" stroke-width="3.5"/>
  <path d="M10 324V168Q10 98 84 92H836Q910 98 910 168V324Z" fill="#888" filter="url(#grain)" opacity=".42" style="mix-blend-mode:overlay"/>
  <path d="M44 124Q44 108 96 106H824Q876 108 876 124" fill="none" stroke="url(#chrome)" stroke-width="6" stroke-linecap="round"/>
  <rect x="62" y="132" width="796" height="176" rx="26" fill="rgba(0,0,0,.28)" stroke="rgba(255,255,255,.08)" stroke-width="2"/>
  <rect x="402" y="112" width="116" height="16" rx="3" fill="#a8863a" stroke="#4d3a10" stroke-width="2"/>
  <circle cx="40" cy="304" r="6" fill="url(#chrome)" stroke="#222" stroke-width="1.5"/><circle cx="880" cy="304" r="6" fill="url(#chrome)" stroke="#222" stroke-width="1.5"/>
  <rect x="48" y="8" width="824" height="86" rx="22" fill="url(#rubber)" stroke="#070708" stroke-width="3.5"/>
  <rect x="64" y="20" width="792" height="9" rx="4.5" fill="rgba(255,255,255,.16)"/>
  <rect x="64" y="70" width="792" height="8" rx="4" fill="url(#chrome)" opacity=".85"/>
  <circle cx="34" cy="52" r="24" fill="url(#chrome)" stroke="#0b0b0d" stroke-width="3.5"/><circle cx="34" cy="52" r="9" fill="#555a61"/>
  <circle cx="886" cy="52" r="24" fill="url(#chrome)" stroke="#0b0b0d" stroke-width="3.5"/><circle cx="886" cy="52" r="9" fill="#555a61"/>
  <path d="M872 70L902 36" stroke="#0b0b0d" stroke-width="12" stroke-linecap="round"/><path d="M872 70L902 36" stroke="url(#chrome)" stroke-width="6" stroke-linecap="round"/>
  <circle cx="904" cy="32" r="11" fill="url(#chrome)" stroke="#0b0b0d" stroke-width="3"/>
  <rect x="120" y="86" width="680" height="9" rx="4.5" fill="url(#chrome)" stroke="#2a2d31" stroke-width="1.5"/>
  ${keys}
</svg>`;
}

function typewriter() {
  const el = h("div", { class: "typewriter" });
  let all = [];
  const paint = () => {
    el.innerHTML = typewriterSvg(TYPEWRITERS[App.ui.prefs.typewriter] || TYPEWRITERS.black);
    all = [...el.querySelectorAll(".key")];
  };
  paint();
  const press = () => {
    for (let n = 0; n < (Math.random() < .3 ? 2 : 1); n++) {
      const k = all[Math.floor(Math.random() * all.length)];
      if (!k) continue;
      k.classList.add("down"); setTimeout(() => k.classList.remove("down"), 110);
    }
  };
  return { el, press, paint };
}

export function decreesView() {
  let root = null, timer = null, agendaWrap = null, expanded = false, agenda = null, onPrefs = null;
  const typed = typewriter();

  function row(kind, e) {
    return h("div", { class: "ag-row " + kind },
      h("div", { class: "ag-main" }, h("b", {}, e.name || e.title), e.target_date ? h("span", {}, "дедлайн: " + e.target_date) : null, e.status ? h("span", {}, "статус: " + e.status) : null, e.impact ? h("span", {}, "эффект: " + e.impact) : null),
      e.desc ? h("p", {}, e.desc) : null,
      e.index != null ? h("button", { class: "ag-x", title: "Снять с повестки", onclick: async (ev) => { ev.stopPropagation(); agenda = await api("/api/event/dismiss", { index: e.index }); paintAgenda(); } }, "✕") : null);
  }
  function paintAgenda() {
    const list = [
      ...agenda.issues.map((i) => row("issue", i)),
      ...agenda.events.map((e) => row(e.type === "negative" ? "bad" : "good", e)),
    ];
    const body = agendaWrap.querySelector(".ag-body");
    const shown = expanded ? list : list.slice(-2);
    body.replaceChildren(...(shown.length ? shown : [h("p", { class: "ag-empty" }, "Повестка дня чиста.")]));
    agendaWrap.querySelector(".ag-more").textContent = expanded ? "▲ свернуть" : list.length > 2 ? `▼ ещё ${list.length - 2} — нажмите, чтобы развернуть` : "";
  }

  async function mount(host) {
    agenda = await api("/api/agenda");
    const orders = await api("/api/orders");
    // повестка дня
    const ag = sheet({ x: 476, y: -30, w: 940, hgt: 448, cls: "white", seed: 120, amp: 5, rot: 0.2 });
    agendaWrap = ag.wrap; agendaWrap.style.zIndex = 30; agendaWrap.classList.add("agenda");
    ag.sheet.append(h("div", { class: "ag", onclick: () => toggle() }, h("h3", { class: "title" }, "Повестка дня"), h("div", { class: "ag-body noscroll" }), h("div", { class: "ag-more hand" })));
    // бумага из машинки
    const header = h("div", { class: "typed-head" }, "УКАЗ — " + orders.date.toUpperCase());
    const ta = h("textarea", { class: "typed-ta", rows: 3, spellcheck: "false", placeholder: "Что повелеваете, государь?", value: orders.text });
    ta.value = orders.text;
    const scroll = h("div", { class: "typed-scroll noscroll" }, header, ta);
    const paper = sheet({ x: 0, y: 0, w: 760, hgt: null, cls: "white", seed: 130, amp: 3, rot: 0.3 });
    paper.sheet.append(scroll); paper.sheet.classList.add("typed-sheet");
    const win = h("div", { class: "paper-window" }, paper.wrap);
    typed.el.style.zIndex = 20;
    onPrefs = () => typed.paint(); App.on("prefs", () => onPrefs && onPrefs());
    const fit = () => { ta.style.height = "auto"; ta.style.height = Math.max(110, ta.scrollHeight) + "px"; scroll.scrollTop = scroll.scrollHeight; };
    ta.addEventListener("input", () => {
      typed.press(); fit();
      clearTimeout(timer);
      timer = setTimeout(() => api("/api/orders", { text: ta.value }).catch((e) => toast(e.message, true)), 450);
    });
    ta.addEventListener("keydown", () => typed.press());
    root = h("div", { class: "view decrees" }, win, typed.el, agendaWrap);
    host.append(root);
    paintAgenda(); fit();
    await Promise.all([
      animate(agendaWrap, [{ transform: "translateY(-460px) rotate(-4deg)" }, { transform: "rotate(.2deg)" }], { duration: 650 }),
      animate(typed.el, [{ transform: "translateY(340px)" }, { transform: "none" }], { duration: 650 }),
      animate(win, [{ transform: "translateY(260px)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 750, delay: 120 }),
    ]);
    ta.focus({ preventScroll: true });
  }
  async function toggle() {
    expanded = !expanded; paintAgenda();
    const to = expanded ? 800 : 448;
    agendaWrap.style.transition = "height .45s cubic-bezier(.2,.9,.2,1)";
    agendaWrap.style.height = to + "px";
    agendaWrap.classList.toggle("open", expanded);
  }
  async function unmount() {
    if (!root) return;
    onPrefs = null; clearTimeout(timer);
    const ta = root.querySelector("textarea");
    if (ta) await api("/api/orders", { text: ta.value }).catch(() => {});
    await Promise.all([
      animate(agendaWrap, [{ transform: "none" }, { transform: "translateY(-520px) rotate(4deg)" }], { duration: 480, easing: "ease-in" }),
      animate(typed.el, [{ transform: "none" }, { transform: "translateY(380px)" }], { duration: 480, easing: "ease-in" }),
      animate(root.querySelector(".paper-window"), [{ opacity: 1 }, { opacity: 0, transform: "translateY(260px)" }], { duration: 380 }),
    ]);
    root.remove(); root = null;
  }
  return { mount, unmount };
}
