// Блокнот в правом нижнем углу: 99 подписанных страниц, листается стрелками, сверху — быстрый переход.
import { h, art, api, animate, toast, sleep } from "./util.js";
import { App } from "./store.js";

const COUNT = 99;

export function mountNotebook(stage) {
  let pages = {}, page = App.notePage || 1, open = false, saveTimer = null, ui = null;

  const closed = h("button", { class: "nb-closed", title: "Открыть блокнот", onclick: () => toggle(true) },
    h("div", { class: "nb-stitch" }), h("span", {}, "БЛОКНОТ"));
  closed.style.zIndex = 80;
  stage.append(closed);

  let dirty = null;                      // несохранённые правки {page, text?, title?}
  async function flush() {               // отправить сразу (при листании и закрытии): раньше правки уходили в никуда
    clearTimeout(saveTimer);
    const d = dirty; dirty = null;
    if (d) await api("/api/notes", d).catch((e) => toast(e.message, true));
  }
  function save(key) {
    if (dirty && dirty.page !== page) flush();
    dirty = { ...(dirty || {}), page, ...key };
    clearTimeout(saveTimer);
    saveTimer = setTimeout(flush, 450);
  }
  const rec = () => (pages[page] = pages[page] || { text: "", title: "" });

  function build() {
    const title = h("input", { class: "nb-title hand", placeholder: "подпись страницы", maxlength: 60, value: rec().title });
    const text = h("textarea", { class: "nb-text", placeholder: "Заметки…", spellcheck: "false" });
    text.value = rec().text;
    title.addEventListener("input", () => { rec().title = title.value; save({ title: title.value }); paintChips(); });
    text.addEventListener("input", () => { rec().text = text.value; save({ text: text.value }); paintChips(); });
    const num = h("div", { class: "nb-num hand" }, `${page} / ${COUNT}`);
    const sheetEl = h("div", { class: "nb-page" }, h("div", { class: "nb-head" }, h("span", { class: "hand" }, "Стр. " + page), title), text, h("div", { class: "nb-foot" },
      h("button", { class: "nb-arrow", title: "Назад", onclick: () => turn(-1) }, "◀"), num, h("button", { class: "nb-arrow", title: "Вперёд", onclick: () => turn(1) }, "▶")));
    return { sheetEl, text };
  }
  function paintChips() {
    if (!ui) return;
    const filled = Object.keys(pages).filter((k) => pages[k].text || pages[k].title).map(Number).sort((a, b) => a - b);
    ui.chips.replaceChildren(...filled.slice(0, 40).map((n) => h("button", { class: "chip" + (n === page ? " on" : ""), title: pages[n].title || "без подписи", onclick: () => goto(n) }, n)));
    if (!filled.length) ui.chips.append(h("span", { class: "chip-empty" }, "страницы пока пусты"));
  }
  async function turn(d, instant) { await goto(Math.max(1, Math.min(COUNT, page + d)), d); }
  async function goto(n, dir = 1) {
    if (!ui || n === page) return;
    await flush();
    const old = ui.cur;
    await animate(old.sheetEl, [{ transform: "perspective(1400px) rotateY(0)" }, { transform: `perspective(1400px) rotateY(${dir > 0 ? -80 : 80}deg)`, opacity: .2 }], { duration: 170, easing: "ease-in" });
    page = n; App.notePage = n;
    ui.cur = build(); old.sheetEl.replaceWith(ui.cur.sheetEl);
    ui.jump.value = "";
    paintChips();
    await animate(ui.cur.sheetEl, [{ transform: `perspective(1400px) rotateY(${dir > 0 ? 80 : -80}deg)`, opacity: .2 }, { transform: "perspective(1400px) rotateY(0)", opacity: 1 }], { duration: 200, easing: "ease-out" });
    ui.cur.text.focus({ preventScroll: true });
  }

  async function toggle(want) {
    if (want === open) return;
    if (want) {
      try { pages = (await api("/api/notes")).pages; } catch (e) { return toast(e.message, true); }
      page = Math.min(COUNT, App.notePage || 1);
      const cur = build();
      const jump = h("input", { class: "nb-jump", type: "number", min: 1, max: COUNT, placeholder: "№" });
      const chips = h("div", { class: "chips noscroll" });
      const go = () => { const n = parseInt(jump.value, 10); if (n >= 1 && n <= COUNT) goto(n, n > page ? 1 : -1); else toast("Страницы от 1 до " + COUNT, true); };
      jump.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
      const bar = h("div", { class: "nb-bar" }, h("span", { class: "hand" }, "К странице:"), jump, h("button", { class: "chip go", onclick: go }, "⏎"), chips);
      const cover = h("div", { class: "nb-open" }, h("button", { class: "nb-close", title: "Закрыть", onclick: () => toggle(false) }, "✕"), cur.sheetEl);
      const wrap = h("div", { class: "nb-wrap" }, bar, cover);
      wrap.style.zIndex = 85;
      ui = { wrap, cur, chips, jump }; stage.append(wrap); paintChips();
      closed.classList.add("away"); open = true;
      await animate(wrap, [{ transform: "translate(520px,320px) scale(.4) rotate(8deg)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 420 });
      cur.text.focus({ preventScroll: true });
    } else {
      await flush();
      await animate(ui.wrap, [{ transform: "none", opacity: 1 }, { transform: "translate(520px,320px) scale(.4) rotate(8deg)", opacity: 0 }], { duration: 320, easing: "ease-in" });
      ui.wrap.remove(); ui = null; open = false; closed.classList.remove("away");
    }
  }
  addEventListener("keydown", (e) => { if (e.key === "Escape" && open) toggle(false); });

  return {
    el: closed,
    enter: () => animate(closed, [{ transform: "translate(300px,300px) rotate(10deg)" }, { transform: "none" }], { duration: 800 }),
    leave: async () => { if (open) await toggle(false); await animate(closed, [{ transform: "none" }, { transform: "translate(300px,300px) rotate(10deg)" }], { duration: 600 }); },
  };
}
