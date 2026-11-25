import assert from "node:assert/strict";
import test from "node:test";

import { microfonoDisponible, transcribirVoz } from "../voz/microfono.mjs";
import { escuchar } from "../frontend/src/voz.js";

class ReconocimientoFalso {
  static instancia;

  start() {
    ReconocimientoFalso.instancia = this;
  }

  stop() {
    this.onend();
  }

  abort() {
    this.onerror({ error: "aborted" });
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

test("el punto de entrada del chat entrega el dictado completo con la nomenclatura normalizada", async (t) => {
  globalThis.SpeechRecognition = ReconocimientoFalso;
  t.after(() => { delete globalThis.SpeechRecognition; });
  const dictado = escuchar();
  const microfono = ReconocimientoFalso.instancia;
  microfono.onresult({
    results: [{ isFinal: true, 0: {
      transcript: "Buenas, necesito trescientos dieciséis ele, DOS  BE. Busco también dos beige.",
    } }],
  });
  microfono.onend();
  assert.equal(await dictado.texto, "Buenas, necesito 316L, 2B. Busco también dos beige.");
});

test("cancelar descarta el texto pendiente y permite empezar otro dictado", async (t) => {
  globalThis.SpeechRecognition = ReconocimientoFalso;
  t.after(() => { delete globalThis.SpeechRecognition; });
  const anterior = escuchar();
  ReconocimientoFalso.instancia.onresult({
    results: [{ isFinal: true, 0: { transcript: "Texto de la consulta anterior" } }],
  });
  anterior.cancelar();
  assert.equal(await anterior.texto, "");

  const nuevo = escuchar();
  ReconocimientoFalso.instancia.onresult({
    results: [{ isFinal: true, 0: { transcript: "Necesito dos be." } }],
  });
  nuevo.detener();
  assert.equal(await nuevo.texto, "Necesito 2B.");
});
