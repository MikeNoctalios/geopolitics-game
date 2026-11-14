// Саммиты: схематичное здание парламента, державы сидят по кругу, в центре — стенограмма.
import { h, art, api, sheet, animate, toast, sleep } from "./util.js";
import { App } from "./store.js";

const HALL = `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="780" viewBox="0 0 1000 780"><defs><radialGradient id="hallG" cx=".5" cy=".5" r=".6"><stop offset="0" stop-color="#6a4a26"/><stop offset="1" stop-color="#2f1f0e"/></radialGradient></defs>
<ellipse cx="500" cy="390" rx="490" ry="380" fill="url(#hallG)" stroke="#1a1006" stroke-width="6"/><ellipse cx="500" cy="390" rx="400" ry="300" fill="none" stroke="#a07a40" stroke-width="3" stroke-dasharray="3 10"/>
<ellipse cx="500" cy="390" rx="330" ry="240" fill="#c9b78a" stroke="#1a1006" stroke-width="5"/><ellipse cx="500" cy="390" rx="320" ry="230" fill="none" stroke="#7a6438" stroke-width="2"/>
<g fill="#3c2a14" opacity=".6">${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => { const a = i * Math.PI / 6; return `<circle cx="${500 + Math.cos(a) * 455}" cy="${390 + Math.sin(a) * 345}" r="14"/>`; }).join("")}</g></svg>`;
const VOTE = { "За": ["✓", "#2c7a2c"], "Против": ["✗", "#b32424"], "Воздержался": ["○", "#9a7410"] };

export function summitsView() {
  let root = null, S = null, busy = false, shownDialogue = 0;

  const call = async (path, body) => {
    if (busy) return; busy = true;
    try { S = await api(path, body || {}); await App.refresh().catch(() => {}); } catch (e) { toast(e.message, true); throw e; } finally { busy = false; }
  };
  const safe = async (path, body) => { try { await call(path, body); paint(); } catch (_) { /* уже показано */ } };

  /* ---------- созыв ---------- */
  function setup() {
    const sel = new Set(S.nations.filter((n) => n.great).slice(0, 3).map((n) => n.name));
    const title = h("input", { class: "fld big", value: "Мирная конференция" });
    const topic = h("textarea", { class: "fld big", rows: 3 }, "Урегулирование территориальных споров и подписание пакта о ненападении.");
    let secret = false;
    const cards = h("div", { class: "nations" }, S.nations.map((n) => h("button", { class: "placard" + (sel.has(n.name) ? " on" : ""), onclick: (e) => { sel.has(n.name) ? sel.delete(n.name) : sel.add(n.name); e.currentTarget.classList.toggle("on"); } }, (n.great ? "★ " : "") + n.name)));
    const sec = [["Публичный саммит", false], ["Секретные переговоры", true]].map(([t, v]) => h("button", { class: "pill small" + (v === secret ? " on2" : ""), onclick: (e) => { secret = v; sec.forEach((b) => b.classList.remove("on2")); e.currentTarget.classList.add("on2"); } }, t));
    const s = sheet({ x: 440, y: 90, w: 900, hgt: 760, cls: "white", seed: 150, amp: 5, rot: -.4 });
    s.sheet.append(h("div", { class: "sm-setup" }, h("h2", { class: "title" }, "Созыв международного саммита"),
      h("div", { class: "sm-fields" }, h("label", {}, "Название"), title, h("label", {}, "Повестка дня и первоначальные требования"), topic),
      h("label", {}, "Приглашённые державы"), cards, h("div", { class: "row2" }, sec), h("button", { class: "pill go2", onclick: () => safe("/api/summit/create", { title: title.value, topic: topic.value, participants: [...sel], secrecy: secret ? "Секрет" : "Все" }) }, "Объявить созыв")));
    root.append(s.wrap);
    if (S.archive.length) {
      const a = sheet({ x: 1370, y: 640, w: 520, hgt: 390, cls: "news", seed: 151, amp: 4, rot: 1 });
      a.sheet.append(h("div", { class: "sm-arch scrollable" }, h("h3", { class: "title" }, "Архив саммитов"), ...[...S.archive].reverse().map((c) => h("button", { class: "arch", onclick: () => details(c) }, h("b", {}, c.title), h("span", {}, c.status || "Завершён")))));
      root.append(a.wrap);
    }
    animate(s.wrap, [{ transform: "translateY(80px) rotate(-5deg)", opacity: 0 }, { transform: "rotate(-.4deg)", opacity: 1 }], { duration: 500 });
  }
  function details(c) {
    const back = h("div", { class: "telegraph-back", onclick: (e) => { if (e.target === back) back.remove(); } });
    const s = sheet({ x: 520, y: 70, w: 880, hgt: 940, cls: "white", seed: 152, amp: 5, rot: .3 });
    s.sheet.append(h("div", { class: "sm-det scrollable" }, h("h2", { class: "title" }, c.title), h("p", {}, h("b", {}, "Повестка: "), c.topic), h("p", {}, h("b", {}, "Участники: "), c.participants.join(", ")),
      c.positions_summary ? h("p", {}, h("b", {}, "Позиции: "), c.positions_summary) : null, h("p", { class: "verdict" }, c.summary || "Решение не зафиксировано"),
      c.votes ? h("div", {}, Object.entries(c.votes).map(([k, v]) => h("p", {}, `${(VOTE[v.vote] || ["·"])[0]} ${k}: ${v.vote} — ${v.reason || ""}`))) : null,
      c.minister_debrief ? h("p", {}, h("i", {}, c.minister_debrief)) : null, h("button", { class: "pill", onclick: () => back.remove() }, "закрыть")));
    back.append(s.wrap); root.closest("#stage").append(back);
  }

  /* ---------- зал ---------- */
  function hall() {
    const c = S.active, me = S.player, conc = c.stage === "concluded";
    const hallArt = art(HALL, { class: "hall" }); root.append(hallArt);
    const people = [...c.participants.filter((p) => p !== me)], n = people.length, cx = 880, cy = 520;
    const place = (name, a, rx, ry) => {
      const v = c.votes && c.votes[name], card = h("div", { class: "seat" + (name === me ? " me" : ""), "data-n": name, style: { left: cx + Math.cos(a) * rx - 85 + "px", top: cy + Math.sin(a) * ry - 28 + "px" }, title: v ? `${v.vote}: ${v.reason}` : name },
        h("span", {}, name === me ? name + " (Вы)" : name), v ? h("i", { style: { color: VOTE[v.vote][1] } }, VOTE[v.vote][0]) : null);
      root.append(card);
    };
    place(me, Math.PI / 2, 360, 300);
    people.forEach((p, i) => { const ring = n > 9 && i % 2 ? 1 : 0, k = n > 9 ? Math.ceil(n / 2) : n, j = n > 9 ? Math.floor(i / 2) : i;
      place(p, Math.PI * (1.0 + 1.0 * (j + .5) / k) + (ring ? 0 : 0) - (Math.PI * .5) * 0 + Math.PI * 0 , ring ? 270 : 380, ring ? 215 : 320); });
    // стенограмма в центре
    const log = h("div", { class: "lt-log noscroll" }, c.dialogue.map((d) => h("div", { class: "lt-msg " + (d.speaker === me ? "me" : "them") }, h("b", {}, d.speaker + (d.speaker === me ? " (Вы)" : "")), h("p", {}, d.text))));
    const mid = sheet({ x: 650, y: 330, w: 460, hgt: 440, cls: "white", seed: 153, amp: 4, rot: -.3 });
    mid.sheet.append(h("div", { class: "sm-log" }, h("div", { class: "lt-sub hand" }, h("span", {}, "СТЕНОГРАММА"), h("b", {}, c.title)), log,
      conc ? h("div", { class: "sm-result " + (c.passed ? "ok" : "no") }, c.passed ? "ПРИНЯТА" : "ОТКЛОНЕНА") : null));
    root.append(mid.wrap); log.scrollTop = log.scrollHeight;
    const fresh = c.dialogue.slice(shownDialogue); shownDialogue = c.dialogue.length;
    fresh.forEach((d) => { const el = root.querySelector(`.seat[data-n="${CSS.escape(d.speaker)}"]`); el && el.animate([{ transform: "scale(1)" }, { transform: "scale(1.18)", filter: "brightness(1.25)" }, { transform: "scale(1)" }], { duration: 900 }); });
    // повестка
    const top = sheet({ x: 560, y: -14, w: 760, hgt: 120, cls: "news", seed: 154, amp: 4, rot: .2 });
    top.sheet.append(h("div", { class: "sm-top" }, h("b", { class: "title" }, c.title), h("p", {}, c.topic)));
    root.append(top.wrap);
    controls(c);
    // боковые кнопки
    const side = h("div", { class: "sm-side" },
      h("button", { class: "pill", onclick: async () => { try { await call("/api/summit/advice"); advice(S.advice); } catch (_) {} } }, "Совет МИД"),
      conc ? null : h("button", { class: "pill danger2", onclick: () => confirm("Покинуть саммит демонстративно? Остальные продолжат без вас.") && safe("/api/summit/walkout") }, "Покинуть (демарш)"));
    root.append(side);
  }
  function advice(text) {
    document.querySelector(".sm-advice")?.remove();
    const n = h("div", { class: "sticky sm-advice", style: { left: "1290px", top: "300px" } }, h("b", { class: "hand" }, "Конфиденциальный бриф МИД"), h("p", {}, text), h("button", { class: "pill small", onclick: () => n.remove() }, "закрыть"));
    root.closest("#stage").append(n);
  }
  function controls(c) {
    const box = h("div", { class: "sm-ctl" });
    if (c.stage === "discussion") {
      const say = h("input", { class: "fld big", placeholder: "Ваше выступление, требование или компромисс…" });
      say.addEventListener("keydown", (e) => { if (e.key === "Enter") safe("/api/summit/speak", { text: say.value }); });
      box.append(say, h("button", { class: "pill go2", onclick: () => safe("/api/summit/speak", { text: say.value }) }, "Взять слово"), h("button", { class: "pill", onclick: () => safe("/api/summit/speak", { text: "" }) }, "Промолчать"),
        h("button", { class: "pill", onclick: () => safe("/api/summit/propose", { text: say.value || c.topic }) }, "На голосование ⚖"));
    } else if (c.stage === "voting") {
      box.append(h("div", { class: "sm-prop" }, h("b", {}, "Проект резолюции: "), c.final_proposal),
        ...[["За", "green"], ["Против", "red"], ["Воздержался", "yellow"]].map(([v, col]) => h("button", { class: "vote-stamp " + col, onclick: () => safe("/api/summit/vote", { vote: v }) }, v.toUpperCase())));
    } else {
      box.append(h("div", { class: "sm-prop" }, c.summary), h("button", { class: "pill go2", onclick: () => safe("/api/summit/close") }, "Утвердить итоги и закрыть"));
    }
    root.append(box);
  }

  function paint() {
    root.replaceChildren();
    if (!S.active) return setup();
    hall();
  }

  return {
    async mount(host) {
      S = await api("/api/summit"); root = h("div", { class: "view summits" }); host.append(root);
      shownDialogue = S.active ? S.active.dialogue.length : 0;
      paint();
      await animate(root, [{ opacity: 0, transform: "scale(.96)" }, { opacity: 1, transform: "none" }], { duration: 450 });
    },
    async unmount() { if (!root) return; document.querySelector(".sm-advice")?.remove(); await animate(root, [{ opacity: 1 }, { opacity: 0 }], { duration: 250 }); root.remove(); root = null; },
  };
}