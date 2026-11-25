import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { normalizarTranscripcion } from "../voz/normalizacion.mjs";

const casos = JSON.parse(readFileSync(new URL("./casos_voz.json", import.meta.url), "utf8"));
const umbral = 90;

export function evaluarVoz(transcripciones) {
  if (!transcripciones || typeof transcripciones !== "object" || Array.isArray(transcripciones)) {
    throw new TypeError("Las transcripciones deben ser un objeto JSON con un texto por ID.");
  }
  const ids = new Set(casos.map(({ id }) => id));
  for (const [id, texto] of Object.entries(transcripciones)) {
    if (!ids.has(id) || typeof texto !== "string") {
      throw new TypeError(`ID o transcripción inválidos: ${id}`);
    }
  }

  let aciertos = 0;
  const fallos = [];
  const pendientes = [];
  for (const { id, codigos } of casos) {
    if (!Object.hasOwn(transcripciones, id)) {
      pendientes.push(id);
      continue;
    }
    const texto = normalizarTranscripcion(transcripciones[id]);
    const palabras = new Set(texto.toUpperCase().match(/[\p{L}\p{N}_]+/gu) ?? []);
    const faltan = codigos.filter((codigo) => !palabras.has(codigo));
    if (faltan.length) {
      fallos.push({ id, transcripcion: transcripciones[id], faltan });
    } else {
      aciertos++;
    }
  }

  const porcentaje = pendientes.length ? null : (100 * aciertos) / casos.length;
  return {
    total: casos.length,
    aciertos,
    porcentaje,
    umbral_pct: umbral,
    cumple_umbral: porcentaje !== null && porcentaje >= umbral,
    pendientes,
    fallos,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const archivo = process.argv[2];
    if (!archivo) throw new Error("Uso: node tests/evaluar_voz.mjs transcripciones.json");
    const informe = evaluarVoz(JSON.parse(readFileSync(archivo, "utf8")));
    console.log(JSON.stringify(informe, null, 2));
    process.exitCode = informe.cumple_umbral ? 0 : 1;
  } catch (error) {
    console.error(error.message);
    process.exitCode = 2;
  }
}
