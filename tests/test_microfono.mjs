import assert from "node:assert/strict";
import test from "node:test";

import { microfonoDisponible, transcribirVoz } from "../voz/microfono.mjs";

class ReconocimientoFalso {
  static instancia;

  start() {
    ReconocimientoFalso.instancia = this;
  }

  stop() {
    this.onend();
  }
}

test("devuelve el mensaje completo en español sin interpretar la petición", async (t) => {
  globalThis.SpeechRecognition = ReconocimientoFalso;
  t.after(() => { delete globalThis.SpeechRecognition; });
  const dictado = transcribirVoz();
  const microfono = ReconocimientoFalso.instancia;
  assert.equal(microfono.lang, "es-ES");
  microfono.onresult({
    results: [
      { isFinal: true, 0: { transcript: "Busco una chapa, acabado dos be." } },
      { isFinal: false, 0: { transcript: "parcial" } },
    ],
  });
  dictado.detener();
  assert.equal(await dictado.texto, "Busco una chapa, acabado dos be.");
});

test("permite detectar navegadores sin reconocimiento y comunica errores", async (t) => {
  assert.equal(microfonoDisponible(), false);
  assert.throws(transcribirVoz, /no admite/);

  globalThis.webkitSpeechRecognition = ReconocimientoFalso;
  t.after(() => { delete globalThis.webkitSpeechRecognition; });
  const dictado = transcribirVoz();
  const microfono = ReconocimientoFalso.instancia;
  microfono.onerror({ error: "not-allowed" });
  microfono.onend();
  await assert.rejects(dictado.texto, /not-allowed/);
});
