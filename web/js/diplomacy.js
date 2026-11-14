import { h, api } from "./util.js";
import { App } from "./store.js";
import { lettersView } from "./letters.js";

const adapt = (c) => ({
  title: c.country, unread: 0, note: c.pending ? `✉ ${c.pending} уйдёт с завершением хода` : "",
  messages: c.messages.map((m) => ({ mine: m.from === App.hud.country, who: m.from, text: m.text })), dossier: c.dossier,
});

export function diplomacyView() {
  return lettersView({
    envelopeLabel: "Официальное письмо:", logTitle: "СТЕНОГРАММА ДИАЛОГА С:", placeholder: "Текст депеши…", sendLabel: "Отправить депешу",
    emptyText: "История переписки пуста. Отправьте первую депешу.", pickTitle: "Выбрать адресата",
    async loadList() { return (await api("/api/diplo/contacts")).contacts.map((c) => ({ key: c.name, label: c.name, sub: c.overlord, great: c.great, unread: c.unread, last: c.last })); },
    initial: (list) => (list.find((r) => r.unread) || list[0])?.key,
    async loadChat(k) { return adapt(await api("/api/diplo/chat?country=" + encodeURIComponent(k))); },
    async send(k, text) { return adapt(await api("/api/diplo/send", { country: k, text })); },
    side(chat) {
      const d = chat.dossier;
      return [h("h4", { class: "hand" }, "Досье"), ...[["Регион", d.region], ["Режим", d.regime], ["Фракция", d.faction], ["К нам", d.stance], ["Армия", d.manpower], ["Амбиции", d.ambitions], ["Страхи", d.fears]]
        .map(([k, v]) => h("p", {}, h("b", {}, k + ": "), v))];
    },
  });
}
