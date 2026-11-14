// Общий вид «письма»: конверт выбора адресата, стенограмма диалога, лист для ответа.
// Дипломатия и советники — две настройки одного компонента (cfg).
import { h, api, sheet, animate, toast, art, sleep } from "./util.js";
import { App } from "./store.js";

const WAX = `<svg xmlns="http://www.w3.org/2000/svg" width="86" height="86" viewBox="0 0 86 86"><path d="M43 4c10 0 14 8 24 10s12 14 8 24 2 18-6 26-10 14-24 14-22-6-28-16-4-18-4-26S18 12 30 8 38 4 43 4z" fill="#a82525" stroke="#5a0f0f" stroke-width="3"/><circle cx="43" cy="43" r="22" fill="none" stroke="#7a1616" stroke-width="3"/><path d="M33 52l10-24 10 24M36 46h14" fill="none" stroke="#e8b0a0" stroke-width="3.5" stroke-linecap="round"/></svg>`;
const ENVELOPE = `<svg xmlns="http://www.w3.org/2000/svg" width="700" height="400" viewBox="0 0 700 400"><defs><linearGradient id="envG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#cfcab9"/><stop offset="1" stop-color="#a9a391"/></linearGradient></defs><path d="M12 28L660 6 688 372 22 394z" fill="url(#envG)" stroke="#15130f" stroke-width="4" stroke-linejoin="round"/><path class="flap" d="M12 28L350 232 660 6" fill="#bdb7a4" stroke="#15130f" stroke-width="4" stroke-linejoin="round"/><path d="M22 394L300 214M688 372L400 214" stroke="#15130f" stroke-opacity=".5" stroke-width="3" fill="none"/></svg>`;

export function lettersView(cfg) {
  let root = null, picker = null, cur = null, chat = null, list = [];

  const mine = (m) => m.mine;
  function bubbles(msgs) {
    return msgs.length ? msgs.map((m) => h("div", { class: "lt-msg " + (m.mine ? "me" : "them") }, h("b", {}, m.mine ? "Вы" : m.who), h("p", {}, m.text)))
      : [h("p", { class: "lt-empty" }, cfg.emptyText)];
  }

  async function open(key, anim = true) {
    cur = key;
    chat = await cfg.loadChat(key);
    paint();
    App.refresh().catch(() => {});                      // непрочитанное могло сняться
    if (anim) { const f = root.querySelector(".flap"); if (f) await animate(f, [{ transform: "scaleY(1)" }, { transform: "scaleY(.15)" }, { transform: "scaleY(1)" }], { duration: 520 }); }
  }

  function paint() {
    const env = root.querySelector(".env-label"), log = root.querySelector(".lt-log"), sub = root.querySelector(".lt-sub");
    env.replaceChildren(h("small", {}, cfg.envelopeLabel), h("b", {}, chat.title));
    sub.replaceChildren(...[h("span", {}, cfg.logTitle), h("b", {}, chat.title), chat.unread ? h("i", { class: "badge" }, chat.unread) : null].filter(Boolean));
    log.replaceChildren(...bubbles(chat.messages)); log.scrollTop = log.scrollHeight;
    const side = root.querySelector(".lt-side"); side.replaceChildren(...(cfg.side ? cfg.side(chat) : []));
    root.querySelector(".lt-pending").textContent = chat.note || "";
  }

  async function submit() {
    const ta = root.querySelector(".lt-ta"), btn = root.querySelector(".lt-send"), text = ta.value.trim();
    if (!text || !cur) return;
    btn.disabled = ta.disabled = true;
    const waiting = cfg.slow ? h("div", { class: "lt-msg them dim" }, h("p", {}, cfg.slowText)) : null;
    if (waiting) { root.querySelector(".lt-log").append(waiting); root.querySelector(".lt-log").scrollTop = 1e9; }
    try { chat = await cfg.send(cur, text); ta.value = ""; paint(); await App.refresh(); }
    catch (e) { toast(e.message, true); waiting && waiting.remove(); }
    btn.disabled = ta.disabled = false; ta.focus();
  }

  function pickerOpen(show) {
    if (picker) { picker.remove(); picker = null; if (!show) return; }
    picker = h("div", { class: "lt-picker scrollable" }, list.map((r) => h("button", { class: "lt-pick" + (r.key === cur ? " on" : ""), onclick: async () => { pickerOpen(false); await open(r.key); await loadList(); } },
      h("span", {}, (r.great ? "★ " : "") + r.label + (r.sub ? ` (${r.sub})` : "")), r.unread ? h("i", { class: "badge" }, "●") : null, r.last ? h("small", {}, r.last) : null)));
    root.append(picker);
    animate(picker, [{ opacity: 0, transform: "translateY(-14px)" }, { opacity: 1, transform: "none" }], { duration: 220 });
  }
  async function loadList() { list = await cfg.loadList(); }

  function expand() {
    const back = h("div", { class: "telegraph-back", onclick: (e) => { if (e.target === back) back.remove(); } });
    const s = sheet({ x: 360, y: 60, w: 1080, hgt: 960, cls: "white", seed: 55, amp: 5, rot: -.4 });
    const log = h("div", { class: "lt-log big scrollable" }, ...bubbles(chat.messages));
    s.sheet.append(h("div", { class: "lt-full" }, h("h2", { class: "title" }, `${cfg.logTitle} ${chat.title}`), h("div", { class: "lt-full-in" }, log, h("div", { class: "lt-side" }, ...(cfg.side ? cfg.side(chat) : []))),
      h("button", { class: "pill", style: { position: "absolute", right: "30px", bottom: "24px" }, onclick: () => back.remove() }, "свернуть")));
    back.append(s.wrap); root.closest("#stage").append(back);
    log.scrollTop = log.scrollHeight;
    animate(s.wrap, [{ transform: "translateY(60px) scale(.9)", opacity: 0 }, { transform: "rotate(-.4deg)", opacity: 1 }], { duration: 380 });
  }

  return {
    async mount(host) {
      await loadList();
      root = h("div", { class: "view letters" });
      const env = h("button", { class: "envelope", title: cfg.pickTitle, onclick: () => pickerOpen(!picker) });
      env.innerHTML = ENVELOPE;
      env.append(art(WAX, { class: "wax" }), h("div", { class: "env-label hand" }));
      const logSheet = sheet({ x: 392, y: 566, w: 470, hgt: 490, cls: "white", seed: 61, amp: 4, rot: -.8 });
      logSheet.sheet.append(h("div", { class: "lt-logbox" }, h("div", { class: "lt-sub hand" }), h("div", { class: "lt-log noscroll" }), h("button", { class: "pill small ghost", onclick: expand }, "развернуть")));
      const inSheet = sheet({ x: 900, y: 720, w: 640, hgt: 330, cls: "white", seed: 62, amp: 4, rot: .5 });
      const ta = h("textarea", { class: "lt-ta", placeholder: cfg.placeholder, spellcheck: "false" });
      ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(); });
      inSheet.sheet.append(h("div", { class: "lt-write" }, ta, h("div", { class: "lt-wbar" }, h("span", { class: "lt-pending" }), h("button", { class: "pill lt-send", onclick: submit }, cfg.sendLabel))));
      root.append(env, logSheet.wrap, inSheet.wrap, h("div", { class: "lt-side side-note" }));
      host.append(root);
      const first = cfg.initial ? cfg.initial(list) : list[0]?.key;
      if (first) await open(first, false);
      await Promise.all([animate(env, [{ transform: "translateY(-380px) rotate(-8deg)", opacity: 0 }, { transform: "rotate(-3deg)", opacity: 1 }], { duration: 650 }),
        animate(logSheet.wrap, [{ transform: "translateY(520px)" }, { transform: "rotate(-.8deg)" }], { duration: 600 }),
        animate(inSheet.wrap, [{ transform: "translateY(420px)" }, { transform: "rotate(.5deg)" }], { duration: 650 })]);
    },
    async unmount() {
      if (!root) return;
      await animate(root, [{ opacity: 1 }, { opacity: 0, transform: "translateY(40px)" }], { duration: 280 });
      root.remove(); root = null; picker = null;
    },
  };
}
