// Шрифты: встроенные, загруженные игроком и (по желанию) Google Fonts. Категории → CSS-переменные.
// Декоративные шрифты без кириллицы безопасны: цепочка font-family сама отдаёт русские буквы следующему шрифту.
import { App } from "./store.js";

const SERIF = 'Georgia, "Times New Roman", "DejaVu Serif", serif';
const HAND = '"Segoe Print", "Bradley Hand", "Marker Felt", "Comic Sans MS", "Chalkboard SE", cursive';
const MONO = '"Courier New", "DejaVu Sans Mono", monospace';
const SANS = '"Segoe UI", "Trebuchet MS", "Nunito", system-ui, sans-serif';

export const DEFAULT_STACK = { news_head: SERIF, news_body: SERIF, title: SERIF, hand: HAND, label: HAND, stamp: SANS, tech: SANS, type: MONO, ui: SANS };
// Только шрифты с кириллицей (проверено по ParaType и авторам); подключаются по желанию, нужен интернет.
const ONLINE = { news_head: '"Old Standard TT"', news_body: '"PT Serif"', title: '"Old Standard TT"', hand: '"Marck Script"', label: '"Marck Script"', stamp: '"PT Sans"', tech: '"PT Sans"', type: '"PT Mono"', ui: '"PT Sans"' };
const ONLINE_URL = "https://fonts.googleapis.com/css2?family=Old+Standard+TT:wght@400;700&family=Marck+Script&family=PT+Serif:wght@400;700&family=PT+Sans:wght@400;700&family=PT+Mono&display=swap";
const DIGITS = "U+0030-0039, U+0023, U+2116";                // №, #, цифры

const srcOf = (id) => {
  const [kind, ...rest] = String(id).split(":"), file = rest.join(":");
  return kind === "bundled" ? `/web/fonts/${encodeURIComponent(file)}` : kind === "user" ? `/fonts/${encodeURIComponent(file)}` : null;
};
const famOf = (id) => `"gf-${String(id).replace(/[^\w]/g, "_")}"`;

export function applyFonts() {
  const { prefs, fonts } = App.ui;
  const used = new Set(Object.values(prefs.fonts).filter((v) => v !== "default"));
  let css = "";
  for (const id of used) {
    if (!srcOf(id)) continue;
    const digitsOnly = ["numerals", "seals"].some((c) => prefs.fonts[c] === id) && !Object.entries(prefs.fonts).some(([c, v]) => v === id && !["numerals", "seals"].includes(c));
    const entry = id.startsWith("bundled:") ? fonts.bundled.find((f) => "bundled:" + f.file === id) : null;
    // несколько начертаний (прямое/курсив, обычное/жирное); size-adjust выравнивает кегль разных шрифтов
    const faces = entry ? entry.faces : [{ file: id.slice(5 + (id.startsWith("bundled:") ? 3 : 0)), weight: "100 900", style: "normal" }];
    for (const fc of faces) {
      const url = id.startsWith("bundled:") ? `/web/fonts/${encodeURIComponent(fc.file)}` : srcOf(id);
      css += `@font-face{font-family:${famOf(id)};src:url("${url}");font-weight:${fc.weight};font-style:${fc.style};font-display:swap;${entry && entry.adjust !== 100 ? `size-adjust:${entry.adjust}%;` : ""}${digitsOnly ? `unicode-range:${DIGITS};` : ""}}\n`;
    }
  }
  const num = prefs.fonts.numerals !== "default" ? famOf(prefs.fonts.numerals) : null;
  const seal = prefs.fonts.seals !== "default" ? famOf(prefs.fonts.seals) : null;
  const online = prefs.online_fonts;
  const stack = (cat) => {
    const own = prefs.fonts[cat] !== "default" ? famOf(prefs.fonts[cat]) : null;
    const parts = [own, ["news_head", "hand", "ui", "title"].includes(cat) ? num && `${num}` : null, online ? ONLINE[cat] : null, DEFAULT_STACK[cat]];
    return parts.filter(Boolean).join(", ");
  };
  const vars = {
    "--f-news-head": stack("news_head"), "--f-news-body": stack("news_body"), "--f-hand": stack("hand"),
    "--f-title": stack("title"), "--f-label": stack("label"), "--f-stamp": stack("stamp"), "--f-tech": stack("tech"),
    "--f-type": stack("type"), "--f-ui": stack("ui"),
    "--f-num": [num, num ? null : '"Georgia"', SERIF].filter(Boolean).join(", "),
    "--f-seal": [seal, num, HAND].filter(Boolean).join(", "),
  };
  for (const c of Object.keys(prefs.scale)) vars[`--s-${c}`] = String(prefs.scale[c]);
  css += `:root{${Object.entries(vars).map(([k, v]) => `${k}:${v}`).join(";")}}`;
  let el = document.getElementById("geo-fonts");
  if (!el) { el = document.createElement("style"); el.id = "geo-fonts"; document.head.append(el); }
  el.textContent = css;

  const link = document.getElementById("geo-online-fonts");
  if (online && !link) { const l = document.createElement("link"); l.id = "geo-online-fonts"; l.rel = "stylesheet"; l.href = ONLINE_URL; document.head.append(l); }
  if (!online && link) link.remove();
}

/** Есть ли в загруженном шрифте русские буквы: сравниваем ширину строки с запасным шрифтом. */
export async function hasCyrillic(file, kind = "user") {
  const id = `${kind}:${file}`, fam = famOf(id).replace(/"/g, "");
  try {
    const face = new FontFace(fam + "-probe", `url("${srcOf(id)}")`);
    await face.load(); document.fonts.add(face);
    const ctx = document.createElement("canvas").getContext("2d"), t = "ЖЩЮЯфщдл";
    const w = (f) => { ctx.font = `48px ${f}`; return ctx.measureText(t).width; };
    const own = `"${fam}-probe"`;
    return w(`${own}, serif`) !== w("serif") || w(`${own}, monospace`) !== w("monospace");
  } catch (_) { return null; }
}
