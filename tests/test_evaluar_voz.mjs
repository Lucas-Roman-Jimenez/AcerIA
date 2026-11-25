import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { evaluarVoz } from "./evaluar_voz.mjs";

const casos = JSON.parse(readFileSync(new URL("./casos_voz.json", import.meta.url), "utf8"));
const simuladas = Object.fromEntries(casos.map(({ id, dictar }) => [id, dictar]));

test("el 90 % exige nueve dictados completos y cuenta los intentos vacíos", () => {
  const informe = evaluarVoz({ ...simuladas, "VOZ-02": "" });
  assert.equal(informe.porcentaje, 90);
  assert.equal(informe.cumple_umbral, true);
  assert.deepEqual(informe.fallos, [{ id: "VOZ-02", transcripcion: "", faltan: ["316L"] }]);
  const incompletos = evaluarVoz({ ...simuladas, "VOZ-02": "", "VOZ-09": "2B y 316LX" });
  assert.equal(incompletos.porcentaje, 80);
  assert.equal(incompletos.cumple_umbral, false);
  assert.deepEqual(incompletos.fallos[1].faltan, ["316L"]);
});

test("una captura parcial no produce un porcentaje", () => {
  const informe = evaluarVoz({ "VOZ-01": "dos be" });
  assert.equal(informe.aciertos, 1);
  assert.equal(informe.porcentaje, null);
  assert.equal(informe.cumple_umbral, false);
  assert.equal(informe.pendientes.length, 9);
});
