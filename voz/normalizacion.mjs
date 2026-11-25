import equivalencias from "./equivalencias.json" with { type: "json" };

const expresiones = Object.keys(equivalencias).map((expresion) =>
  expresion.split(" ").map((palabra) => palabra.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+"),
);
const patron = new RegExp(
  `(?<![\\p{L}\\p{N}_])(?:${expresiones.join("|")})(?![\\p{L}\\p{N}_])`,
  "giu",
);

export function normalizarTranscripcion(texto) {
  return texto.replace(patron, (fragmento) =>
    equivalencias[fragmento.toLowerCase().replace(/\s+/g, " ")] ?? fragmento,
  );
}
