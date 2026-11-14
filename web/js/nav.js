// Меню вкладок: лист со списком в правом верхнем углу. Список берётся из App.tabs и умеет расти:
// при многих вкладках строки уплотняются, а при совсем многих лист прокручивается.
import { h, sheet, animate } from "./util.js";
import { line } from "./scribble.js";
import { App } from "./store.js";

export function mountNav(stage, onSelect) {
  const { wrap, sheet: sh } = sheet({ x: 1548, y: 150, w: 330, hgt: 450, cls: "", seed: 21, amp: 5, rot: 0.8 });
  wrap.style.zIndex = 50; wrap.classList.add("nav");
  const list = h("div", { class: "nav-in" });
  sh.append(list); stage.append(wrap);
  let items = {};

  function build() {
    const tabs = App.tabs, n = tabs.length;
    const ih = n <= 7 ? 62 : Math.max(38, Math.floor(540 / n));
    wrap.style.setProperty("--nav-ih", ih + "px");
    wrap.style.setProperty("--nav-fs", (n <= 7 ? 36 : Math.max(22, Math.round(ih * 0.58))) + "px");
    wrap.style.height = Math.min(660, 82 + n * ih) + "px";
    items = {};
    list.replaceChildren(...tabs.map((t, i) => {
      const badge = h("span", { class: "badge hidden" });
      const ul = h("div", { class: "ul" }); ul.innerHTML = line(180, 40 + i);
      const b = h("button", { class: "nav-item", onclick: () => onSelect(t.id) }, t.label, badge, ul);
      items[t.id] = { b, badge };
      return b;
    }));
    paint();
  }
  function paint() {
    for (const [id, it] of Object.entries(items)) it.b.classList.toggle("on", id === App.tab);
    const n = (App.hud?.unread || []).length;
    if (items.diplomacy) { items.diplomacy.badge.textContent = n; items.diplomacy.badge.classList.toggle("hidden", !n); }
  }
  App.on("state", paint); App.on("tab", paint); App.on("tabs", build); build();
  return {
    el: wrap, select: paint,
    enter: () => animate(wrap, [{ transform: "translateY(-420px) rotate(8deg)" }, { transform: "rotate(.8deg)" }], { duration: 750 }),
    leave: () => animate(wrap, [{ transform: "rotate(.8deg)" }, { transform: "translateY(-420px) rotate(8deg)" }], { duration: 600 }),
  };
}
