// Мелкие помощники: создание узлов, запросы к серверу, «рваные» края бумаги.
const SVG_NS = "http://www.w3.org/2000/svg";

export function h(tag, props, ...kids) {
  const svg = tag.startsWith("svg:");
  const el = svg ? document.createElementNS(SVG_NS, tag.slice(4)) : document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

/** Статичная векторная картинка из нашей же разметки (не из данных игры!). */
export function art(markup, props = {}) {
  const wrap = h("div", props);
  wrap.innerHTML = markup;
  return wrap;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function api(path, body, opts = {}) {
  const init = body === undefined && !opts.post
    ? { method: "GET" }
    : { method: "POST", headers: { "Content-Type": "application/json", "X-Requested-With": "geo-table" }, body: JSON.stringify(body || {}) };
  const res = await fetch(path, init);
  let data = null;
  try { data = await res.json(); } catch (_) { /* не JSON */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Ошибка ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export function rng(seed) {            // детерминированный генератор: одна и та же бумага рвётся одинаково
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export function hash(str) { let x = 7; for (const ch of String(str)) x = (Math.imul(x, 31) + ch.charCodeAt(0)) | 0; return x; }

/** Неровные «вырезанные» края листа. amp — размах в пикселях. */
export function wobble(el, seed = 1, amp = 4, n = 8) {
  const r = rng(seed), pts = [];
  const o = () => (r() * amp).toFixed(1);
  for (let i = 0; i <= n; i++) pts.push(`${(i / n * 100).toFixed(1)}% ${o()}px`);
  for (let i = 1; i <= n; i++) pts.push(`calc(100% - ${o()}px) ${(i / n * 100).toFixed(1)}%`);
  for (let i = n - 1; i >= 0; i--) pts.push(`${(i / n * 100).toFixed(1)}% calc(100% - ${o()}px)`);
  for (let i = n - 1; i > 0; i--) pts.push(`${o()}px ${(i / n * 100).toFixed(1)}%`);
  el.style.clipPath = `polygon(${pts.join(",")})`;
  return el;
}

/** Лист бумаги: обёртка с тенью + внутренний рваный лист. Возвращает {wrap, sheet}. */
export function sheet({ x, y, w, hgt, cls = "", seed = 1, amp = 4, rot = 0, z, children = [] }) {
  const inner = h("div", { class: `sheet ${cls}` }, ...children);
  wobble(inner, seed, amp);
  const auto = hgt == null;      // hgt не задан — высота по содержимому (газета)
  const wrap = h("div", { class: "sheet-wrap", style: { left: x + "px", top: y + "px", width: w + "px", height: auto ? "auto" : hgt + "px", position: auto ? "relative" : "absolute", transform: rot ? `rotate(${rot}deg)` : "", zIndex: z ?? "" } }, inner);
  if (auto) { wrap.style.left = wrap.style.top = ""; inner.style.height = "auto"; }
  return { wrap, sheet: inner };
}

export function animate(el, frames, opts) { return el.animate(frames, { fill: "both", easing: "cubic-bezier(.2,.8,.2,1)", ...opts }).finished.catch(() => {}); }

/** Загрузочная карточка «Накрываем на стол...». Возвращает async-функцию закрытия. */
export function loading(stage, title = "Накрываем на стол...", sub = "") {
  const card = h("div", { class: "load-card" },
    h("h2", { class: "title" }, title),
    h("div", { class: "dots" }, h("i"), h("i"), h("i")),
    sub ? h("p", {}, sub) : null);
  const back = h("div", { class: "load-back" }, card);
  stage.append(back);
  animate(back, [{ opacity: 0 }, { opacity: 1 }], { duration: 180 });
  animate(card, [{ opacity: 0, transform: "scale(.95) translateY(8px)" }, { opacity: 1, transform: "none" }], { duration: 240 });
  let closed = false;
  return async () => {
    if (closed) return;
    closed = true;
    await animate(back, [{ opacity: 1 }, { opacity: 0 }], { duration: 180 });
    back.remove();
  };
}

export function toast(msg, bad = false, ms = 3800) {
  let box = document.getElementById("toasts");
  if (!box) { box = h("div", { id: "toasts" }); document.getElementById("stage").append(box); }
  const t = h("div", { class: "toast" + (bad ? " bad" : "") }, msg);
  box.append(t);
  t.animate([{ opacity: 0, transform: "translateY(-14px) rotate(-.6deg)" }, { opacity: 1, transform: "none" }], { duration: 220, fill: "both" });
  setTimeout(() => t.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 400, fill: "both" }).finished.then(() => t.remove()), ms);
}

export const esc = (s) => String(s ?? "");
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));