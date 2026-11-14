// Газета «Сводка»: слева мир, справа мы; обратная сторона — второстепенное и пресса; прошлые выпуски — свёртки внизу.
import { h, art, api, sheet, animate, sleep, toast, wobble } from "./util.js";
import { App } from "./store.js";
import { line } from "./scribble.js";

const ROLL = `<svg xmlns="http://www.w3.org/2000/svg" width="86" height="64" viewBox="0 0 86 64"><rect x="8" y="14" width="66" height="36" rx="6" fill="#d9d5ca" stroke="#15130f" stroke-width="3"/><ellipse cx="74" cy="32" rx="8" ry="18" fill="#c9c4b6" stroke="#15130f" stroke-width="3"/><ellipse cx="74" cy="32" rx="3" ry="8" fill="none" stroke="#15130f" stroke-width="2"/><rect x="34" y="12" width="9" height="40" fill="#b33" opacity=".8"/><path d="M14 24h14M14 32h12M14 40h14" stroke="#6b665a" stroke-width="2.4" stroke-linecap="round"/></svg>`;

const ARROW = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 70 130" width="70" height="130"><path d="M16 14 L54 65 L16 116" fill="none" stroke="#15130f" stroke-opacity=".55" stroke-width="17" stroke-linecap="round" stroke-linejoin="round"/><path d="M16 14 L54 65 L16 116" fill="none" stroke="#f4ecd0" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const item = (n, e, cls = "") => h("div", { class: "n-item " + cls },
  h("span", { class: "n-num hand" }, n), h("div", {}, h("b", {}, e.title || "Событие"), e.desc && h("p", {}, e.desc)));

export function newsView() {
  let root = null, scroller = null, pad = null, paperEl = null, flipBtn = null, lane = null, backBtn = null, fsz = null;
  let data = null, side = "front", busy = false, index = [];

  function front() {
    const our = [];
    const orders = (data.orders || "").trim();
    if (orders && !["Старт сценария", "Нет прямых приказов"].includes(orders)) our.push({ title: "Высочайший указ", desc: orders.length > 260 ? orders.slice(0, 260) + "…" : orders });
    our.push(...data.ours);
    const col = (title, list, empty) => h("div", { class: "n-col" }, h("h3", {}, title), h("div", { class: "n-rule" }),
      list.length ? list.map((e, i) => item(i + 1, e)) : h("p", { class: "n-empty" }, empty));
    return [
      h("div", { class: "n-mast" }, h("div", { class: "n-title" }, "СВОДКА"), h("div", { class: "n-sub" }, `${data.date} · выпуск ${data.turn}${data.is_current ? "" : " · из архива"}`)),
      h("div", { class: "n-cols" }, col("Новости", data.world, "В мире тихо."), col(App.hud.country, our, "Правительство хранит молчание.")),
    ];
  }
  function backSide() {
    const press = data.press;
    return [
      h("div", { class: "n-mast small" }, h("div", { class: "n-title" }, "ОБРАТНАЯ СТОРОНА"), h("div", { class: "n-sub" }, "второстепенные новости и вырезки из прессы")),
      h("div", { class: "n-cols one" },
        h("div", { class: "n-col" }, h("h3", {}, "Культура, открытия, слухи"), h("div", { class: "n-rule" }),
          data.flavor.length ? data.flavor.map((e, i) => item(i + 1, e)) : h("p", { class: "n-empty" }, "Ничего примечательного.")),
        h("div", { class: "n-col" }, h("h3", {}, "Мировая пресса о нас"), h("div", { class: "n-rule" }),
          press ? h("blockquote", { class: "n-quote" }, `«${press.quote}»`, h("cite", {}, "— " + press.source)) : h("p", { class: "n-empty" }, "О нас пока не пишут."))),
    ];
  }

  function buildPaper() {
    const s = sheet({ w: 900, cls: "news", seed: 40 + (data.turn || 0), amp: 6, rot: (data.turn % 2 ? -0.5 : 0.4) });
    s.sheet.append(h("div", { class: "paper-in" }, side === "front" ? front() : backSide()));
    return s.wrap;
  }

  async function show(turn, how = "unfold") {
    data = await api("/api/news" + (turn ? "?turn=" + turn : ""));
    side = "front";
    const fresh = buildPaper();
    if (paperEl) paperEl.remove();
    paperEl = fresh; pad.append(paperEl); scroller.scrollTop = 0;
    flipBtn.classList.remove("hidden", "back"); fsz.classList.remove("hidden");
    paintLane();
    const frames = how === "unfold"
      ? [{ transform: "translateY(520px) scale(.35,.05) rotate(5deg)", opacity: .5 }, { transform: "translateY(-10px) scale(1,1.015)", opacity: 1, offset: .7 }, { transform: "none" }]
      : [{ transform: "translateX(260px) rotate(6deg)", opacity: 0 }, { transform: "none", opacity: 1 }];
    await animate(paperEl, frames, { duration: how === "unfold" ? 800 : 520 });
  }

  async function flip() {
    if (busy) return; busy = true;
    await animate(paperEl, [{ transform: "perspective(1800px) rotateY(0)" }, { transform: "perspective(1800px) rotateY(88deg)" }], { duration: 230, easing: "ease-in" });
    side = side === "front" ? "back" : "front";
    const inner = paperEl.querySelector(".paper-in");
    inner.replaceChildren(...(side === "front" ? front() : backSide()));
    flipBtn.classList.toggle("back", side === "back");
    flipBtn.title = side === "front" ? "Перевернуть газету" : "Вернуть лицевую сторону";
    await animate(paperEl, [{ transform: "perspective(1800px) rotateY(-88deg)" }, { transform: "perspective(1800px) rotateY(0)" }], { duration: 260, easing: "ease-out" });
    busy = false;
  }

  function paintLane() {
    const older = index.filter((t) => t.turn !== data.turn).sort((a, b) => b.turn - a.turn);
    lane.classList.toggle("hidden", !older.length);
    backBtn.textContent = data.is_current ? "предыдущий ход ↓" : "к свежему выпуску ↑";
    lane.querySelector(".rolls").replaceChildren(...older.map((t) => {
      const b = h("button", { class: "roll", title: t.date, onclick: () => open(t.turn) }, art(ROLL), h("span", {}, "ход " + t.turn));
      return b;
    }));
  }
  async function open(turn) {
    if (busy) return; busy = true;
    try {
      if (paperEl) await animate(paperEl, [{ transform: "none", opacity: 1 }, { transform: "translateY(380px) scale(.4,.1)", opacity: 0 }], { duration: 380, easing: "ease-in" });
      await show(turn, "slide");
    } finally { busy = false; }
  }
  const prev = () => {
    if (!data.is_current) return open(null);
    const older = index.filter((t) => t.turn < data.turn).sort((a, b) => b.turn - a.turn);
    if (older.length) open(older[0].turn); else toast("Прошлых выпусков пока нет");
  };

  return {
    async mount(host) {
      index = (await api("/api/news/index")).turns;
      pad = h("div", { class: "news-pad" });
      scroller = h("div", { class: "news-scroll noscroll" }, pad);
      flipBtn = h("button", { class: "flip-arrow", title: "Перевернуть газету", "aria-label": "Перевернуть газету", onclick: flip });
      flipBtn.innerHTML = ARROW;
      const pct = h("span", {}, "");
      const bump = async (d) => {
        const cur = App.ui.prefs.scale.news_body, v = Math.round(Math.max(0.7, Math.min(1.8, cur + d)) * 100) / 100;
        pct.textContent = Math.round(v * 100) + "%";
        await App.setPrefs({ scale: { news_body: v, news_head: Math.round((1 + (v - 1) / 2) * 100) / 100 } });
      };
      pct.textContent = Math.round(App.ui.prefs.scale.news_body * 100) + "%";
      fsz = h("div", { class: "fsz", title: "Размер шрифта газеты" }, h("button", { onclick: () => bump(-0.1), "aria-label": "Мельче" }, "A−"), pct, h("button", { onclick: () => bump(0.1), "aria-label": "Крупнее" }, "A+"));
      backBtn = h("button", { class: "pill soft prev", onclick: prev }, "предыдущий ход ↓");
      lane = h("div", { class: "lane" }, backBtn, h("div", { class: "rolls noscroll" }));
      root = h("div", { class: "view news-root" }, scroller, flipBtn, fsz, lane);
      host.append(root);
      await show(null, "unfold");
    },
    async unmount() {
      if (!root) return;
      flipBtn.classList.add("hidden"); fsz.classList.add("hidden");
      await animate(paperEl, [{ transform: "none", opacity: 1 }, { transform: "translateY(520px) scale(.3,.05) rotate(-4deg)", opacity: 0 }], { duration: 480, easing: "cubic-bezier(.6,0,.9,.5)" });
      root.remove(); root = null; paperEl = null;
    },
  };
}
