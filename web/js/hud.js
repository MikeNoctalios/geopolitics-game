// Верхний левый лист: дата, держава, сложность, хаос, ход + три печати показателей. Всегда на экране.
import { h, sheet, animate } from "./util.js";
import { circle } from "./scribble.js";
import { App } from "./store.js";

const SEALS = [["stability", "Стабильность"], ["military_readiness", "Боеготовность"], ["war_support", "Поддержка войны"]];
const tone = (v) => (v >= 60 ? "good" : v >= 35 ? "mid" : "bad");

export function mountHud(stage) {
  const { wrap, sheet: sh } = sheet({ x: -34, y: -38, w: 396, hgt: 800, cls: "cream", seed: 5, amp: 7, rot: -0.5 });
  wrap.classList.add("hud"); wrap.style.zIndex = 50;
  const body = h("div", { class: "hud-in" });
  sh.append(body); stage.append(wrap);
  const shown = {};

  function tween(el, from, to) {
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 700);
      el.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function update() {
    const d = App.hud;
    if (!d) return;
    const len = d.country.length, size = len > 20 ? 30 : len > 13 ? 38 : 50;
    body.replaceChildren(
      h("div", { class: "hud-country hand", style: { fontSize: size + "px" } }, d.country),
      h("div", { class: "hud-line hand" }, "Сложность: " + d.difficulty.toLowerCase()),
      h("div", { class: "hud-line hand" }, "Хаос: " + d.solar),
      h("div", { class: "hud-line hand" }, "Ход - " + d.turn),
      h("div", { class: "seals" }, SEALS.map(([key, label], i) => {
        const v = d.stats[key], num = h("b", { class: "seal-n " + tone(v) }, shown[key] ?? v);
        const el = h("div", { class: "seal", title: `${label}: ${v}` },
          num, h("span", {}, label));
        el.insertAdjacentHTML("afterbegin", circle(142, 142, 70 + i) + circle(138, 140, 90 + i * 3, "#15130f", 2));
        if (shown[key] != null && shown[key] !== v) tween(num, shown[key], v);
        shown[key] = v;
        return el;
      })));
  }
  App.on("state", update); update();
  return {
    el: wrap,
    enter: () => animate(wrap, [{ transform: "translateX(-420px) rotate(-6deg)" }, { transform: "rotate(-.5deg)" }], { duration: 800 }),
    leave: () => animate(wrap, [{ transform: "rotate(-.5deg)" }, { transform: "translateX(-420px) rotate(-6deg)" }], { duration: 600 }),
  };
}
