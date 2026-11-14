// Лист-заглушка для вкладок, которые ещё в разработке.
import { h, sheet, animate } from "./util.js";

export function placeholderView(title, hint) {
  let node = null;
  return {
    async mount(host) {
      const s = sheet({ x: 560, y: 360, w: 700, hgt: 280, cls: "white", seed: 91, amp: 4, rot: -1.5 });
      s.sheet.append(h("div", { class: "ph" }, h("h3", { class: "title" }, title), h("p", {}, hint)));
      node = s.wrap; host.append(node);
      await animate(node, [{ transform: "translateY(60px) rotate(-6deg)", opacity: 0 }, { transform: "rotate(-1.5deg)", opacity: 1 }], { duration: 450 });
    },
    async unmount() { if (node) { await animate(node, [{ opacity: 1 }, { opacity: 0, transform: "translateY(40px)" }], { duration: 250 }); node.remove(); } },
  };
}
