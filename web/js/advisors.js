import { h, api } from "./util.js";
import { lettersView } from "./letters.js";

const ROLES = [{ key: "internal", label: "Министр внутренних дел" }, { key: "foreign", label: "Министр иностранных дел" }, { key: "defense", label: "Министр обороны" }];
const adapt = (key, msgs) => ({ title: ROLES.find((r) => r.key === key).label, unread: 0, note: "",
  messages: msgs.map((m) => ({ mine: m.role === "user", who: ROLES.find((r) => r.key === key).label, text: m.content })) });

export function advisorsView() {
  return lettersView({
    envelopeLabel: "Доклад министру:", logTitle: "ДИАЛОГ С:", placeholder: "Ваш вопрос министру…", sendLabel: "Спросить",
    emptyText: "Министр ждёт ваших вопросов.", pickTitle: "Выбрать министра", slow: true, slowText: "Министр готовит ответ…",
    async loadList() { return ROLES.map((r) => ({ ...r })); },
    async loadChat(k) { return adapt(k, (await api("/api/advisors/chat?role=" + k)).messages); },
    async send(k, text) { return adapt(k, (await api("/api/advisors/send", { role: k, text })).messages); },
  });
}
