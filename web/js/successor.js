// Держава игрока распалась или ликвидирована: выбираем государство-преемника (как в прежнем интерфейсе).
import { h, api, sheet, animate, toast } from "./util.js";
import { App } from "./store.js";

export function mountSuccessor(stage, onDone) {
  const back = h("div", { class: "telegraph-back" });
  const list = h("div", { class: "succ-list scrollable" }, (App.candidates || []).map((name) =>
    h("button", { class: "country", onclick: async () => {
      try { await api("/api/successor", { name }); await animate(s.wrap, [{ opacity: 1 }, { opacity: 0, transform: "scale(.9)" }], { duration: 300 }); back.remove(); onDone(); }
      catch (e) { toast(e.message, true); }
    } }, name)));
  const s = sheet({ x: 560, y: 150, w: 800, hgt: 780, cls: "white", seed: 99, amp: 5, rot: -.8 });
  s.sheet.append(h("div", { class: "succ" },
    h("h2", { class: "title" }, "Ваша держава прекратила существование"),
    h("p", {}, "Она распалась, была расформирована или поглощена. Выберите государство-преемника, чтобы продолжить правление:"), list));
  back.append(s.wrap); stage.append(back);
  animate(s.wrap, [{ transform: "translateY(80px) rotate(-6deg)", opacity: 0 }, { transform: "rotate(-.8deg)", opacity: 1 }], { duration: 500 });
}
