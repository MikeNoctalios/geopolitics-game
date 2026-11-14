// «Нарисованные от руки» штрихи: обводки, подчёркивания, линии шкал. Только наша собственная разметка.
import { rng } from "./util.js";

const NS = 'xmlns="http://www.w3.org/2000/svg"';

/** Овальная обводка карандашом вокруг w×h. */
export function circle(w, hgt, seed = 1, color = "#15130f", sw = 3) {
  const r = rng(seed), cx = w / 2, cy = hgt / 2, rx = w / 2 - 4, ry = hgt / 2 - 4, pts = [];
  const n = 22, start = r() * 6.28;
  for (let i = 0; i <= n + 3; i++) {
    const a = start + (i / n) * 6.28 + 0.12, k = 1 + (r() - .5) * .07 + i * .0016;
    pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
  }
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  return `<svg ${NS} width="${w}" height="${hgt}" viewBox="0 0 ${w} ${hgt}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" style="position:absolute;left:0;top:0;pointer-events:none"><path d="${d}"/></svg>`;
}

/** Слегка кривая линия длиной w. */
export function line(w, seed = 1, color = "#15130f", sw = 3.5) {
  const r = rng(seed), n = 8;
  let d = `M2 ${6 + r() * 2}`;
  for (let i = 1; i <= n; i++) d += ` L${(w * i / n).toFixed(1)} ${(6 + (r() - .5) * 3).toFixed(1)}`;
  return `<svg ${NS} width="${w}" height="12" viewBox="0 0 ${w} 12" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" style="display:block;overflow:visible"><path d="${d}"/></svg>`;
}

export const arrowLeft = (color = "#15130f") =>
  `<svg ${NS} width="64" height="34" viewBox="0 0 64 34" fill="none" stroke="${color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M60 24 C40 26 24 22 8 8 M8 8 L8 22 M8 8 L21 11"/></svg>`;

export const pearLogo = (size = 54) =>
  `<svg ${NS} width="${size}" height="${size}" viewBox="0 0 64 64"><path d="M32 18c-9 0-15 8-15 18 0 11 7 20 15 20s15-9 15-20c0-10-6-18-15-18z" fill="#cfd3d8"/><path d="M32 18c-3 0-3-5-1-9 5 0 8 3 7 8" fill="#7ec27a"/><path d="M33 17c1-5 4-8 9-9" stroke="#8a8f96" stroke-width="2.4" fill="none" stroke-linecap="round"/></svg>`;
