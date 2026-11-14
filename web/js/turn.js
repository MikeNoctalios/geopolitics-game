// Отрывной календарь «Завершить ход» + телеграф с ходом обработки.
import { h, api, sheet, animate, sleep, toast } from "./util.js";
import { App } from "./store.js";

function parseDate(s) {
  const m = String(s).match(/^\s*(\d{1,2})\s+([^\d\s]+)\s+(\d{3,4})/);
  return m ? { day: m[1], month: m[2], year: m[3] } : { day: "", month: String(s), year: "" };
}

export function mountTurn(stage) {
  const { wrap, sheet: sh } = sheet({ x: 46, y: 774, w: 262, hgt: 196, cls: "white", seed: 60, amp: 3, rot: -2 });
  wrap.style.zIndex = 50; wrap.classList.add("cal");
  const face = h("div", { class: "cal-face" });
  const btn = h("button", { class: "cal-btn", onclick: () => press() }, "ЗАВЕРШИТЬ ХОД");
  sh.append(h("div", { class: "cal-rings" }, h("i"), h("i"), h("i")), face, btn);
  stage.append(wrap);
  let note = null, running = false;

  function paint() {
    const d = parseDate(App.hud?.date || "");
    face.replaceChildren(h("div", { class: "cal-month hand" }, `${d.month} ${d.year}`.trim()), h("div", { class: "cal-day" }, d.day || "·"), h("div", { class: "cal-turn hand" }, "ход " + (App.hud?.turn ?? "")));
  }
  App.on("state", paint); paint();

  function closeNote() { if (note) { note.remove(); note = null; } }

  async function press() {
    if (running || App.busy) return;
    closeNote();
    let warnings = [];
    try { warnings = (await api("/api/turn/precheck")).warnings; } catch (e) { return toast(e.message, true); }
    if (!warnings.length) return go();
    note = h("div", { class: "sticky" },
      h("b", { class: "hand" }, "Обратите внимание:"), h("ul", {}, warnings.map((w) => h("li", {}, w))),
      h("div", { class: "sticky-btns" },
        h("button", { class: "pill small", onclick: closeNote }, "Вернуться"),
        h("button", { class: "pill small go", onclick: () => { closeNote(); go(); } }, "Всё равно завершить")));
    stage.append(note);
    animate(note, [{ transform: "translateY(24px) rotate(6deg)", opacity: 0 }, { transform: "rotate(-2deg)", opacity: 1 }], { duration: 300 });
  }

  async function go() {
    running = true;
    animate(face, [{ transform: "none", opacity: 1 }, { transform: "translate(-120px,-60px) rotate(-28deg)", opacity: 0 }], { duration: 520, easing: "ease-in" });
    const over = h("div", { class: "telegraph-back" });
    const lines = h("div", { class: "tg-lines" });
    const title = h("h2", { class: "title" }, "Мир обрабатывает ход…");
    const spinner = h("div", { class: "dots" }, h("i"), h("i"), h("i"));
    const foot = h("div", { class: "tg-foot" });
    const s = sheet({ x: 580, y: 230, w: 760, hgt: 560, cls: "white", seed: 77, amp: 5, rot: -1 });
    s.sheet.append(h("div", { class: "tg" }, title, spinner, lines, foot));
    over.append(s.wrap); stage.append(over);
    animate(s.wrap, [{ transform: "translateY(80px) rotate(-8deg)", opacity: 0 }, { transform: "rotate(-1deg)", opacity: 1 }], { duration: 480 });
    let shown = 0, result = null;
    try {
      await api("/api/turn/start", {});
      App.busy = true;
      while (!result) {
        await sleep(350);
        const st = await api("/api/turn/status");
        st.lines.slice(shown).forEach((l) => lines.append(h("div", { class: "tg-line " + l.kind }, l.text)));
        shown = st.lines.length;
        if (!st.running && st.result) result = st.result;
      }
    } catch (e) { result = { ok: false, error: e.message }; }
    App.busy = false; spinner.remove();
    if (result.ok) {
      title.textContent = "Ход завершён";
      (result.lines || []).forEach((t) => lines.append(h("div", { class: "tg-line warn" }, t)));
      foot.append(h("div", { class: "stamp" }, "ПРИНЯТО"));
      await sleep(result.lines && result.lines.length ? 2600 : 1400);
    } else {
      title.textContent = "Ход не обработан";
      lines.append(h("div", { class: "tg-line fail" }, result.error));
      const ok = h("button", { class: "pill", onclick: () => { ok.disabled = true; } }, "Понятно");
      foot.append(ok);
      await new Promise((r) => ok.addEventListener("click", r, { once: true }));
    }
    await animate(s.wrap, [{ opacity: 1 }, { opacity: 0, transform: "translateY(60px) rotate(5deg)" }], { duration: 420 });
    over.remove(); running = false;
    await App.refresh();
    animate(face, [{ transform: "translateY(-40px)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 400 });
    if (result.ok) App.emit("turn-done");
  }

  return {
    el: wrap,
    enter: () => animate(wrap, [{ transform: "translateX(-420px) rotate(-10deg)" }, { transform: "rotate(-2deg)" }], { duration: 800 }),
    leave: () => animate(wrap, [{ transform: "rotate(-2deg)" }, { transform: "translateX(-420px) rotate(-10deg)" }], { duration: 600 }),
  };
}
