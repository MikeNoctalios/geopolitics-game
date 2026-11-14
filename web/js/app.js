import { h, api, sleep, toast } from "./util.js";
import { App } from "./store.js";
import { mountBook } from "./book.js";
import { mountGame } from "./game.js";
import { mountPhone } from "./phone.js";
import { mountSuccessor } from "./successor.js";

const stage = document.getElementById("stage");

function fit() {
  const k = Math.min(innerWidth / 1920, innerHeight / 1080);
  stage.style.transform = `scale(${k})`;
  stage.style.left = (innerWidth - 1920 * k) / 2 + "px";
  stage.style.top = (innerHeight - 1080 * k) / 2 + "px";
  stage.style.setProperty("--k", k);
}
addEventListener("resize", fit); fit();

let book = null, game = null;
const phone = mountPhone(stage, {
  onWorldChanged: () => App.emit("world-changed"),
  onExit: async () => { if (game) { const g = game; game = null; await g.destroy(); } await route(); },
});
async function showMenu() {
  book = mountBook(stage, async () => { await book.destroy(); book = null; await route(); });
  await book.start();
}

async function route() {
  await App.refresh();
  if (App.phase === "menu") return showMenu();
  if (App.phase === "game") { game = mountGame(stage); return game.start(); }
  if (App.phase === "successor") mountSuccessor(stage, route);
}

window.GEO = { App };        // отладочный доступ (для тестов)
App.loadUi().then(route).catch((e) => toast("Сервер недоступен: " + e.message, true));
