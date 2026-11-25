// Lectura orientativa del texto contra el catálogo. La interpretación válida es siempre la del backend.
import fichas from './fichas_aceria.json'

const GLOSARIO = { brillante: ['BA', '2R'], mate: ['2B'], 'en caliente': ['1D'] }
const FORMATOS = {
  chapa: 'chapa|lamina|plancha|placa|hoja',
  bobina: 'bobina|rollo',
  fleje: 'fleje|tira|banda',
}
const FAMILIAS = { austenitico: 'austenítico', duplex: 'dúplex', ferritico: 'ferrítico', martensitico: 'martensítico' }

const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/mat\s*/g, 'mat ')
const nombreGrado = f => f.aisi?.replace(' DDQ', '') ?? f.mat
const escapa = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const unicos = xs => [...new Set(xs)]
const numero = s => parseFloat(s.replace(',', '.'))

// Cada designación del catálogo (AISI, EN, MAT) apunta a su grado; las más largas primero.
const DESIGNACIONES = fichas.flatMap(f => [f.aisi, f.aisi?.replace(' DDQ', ''), f.en, f.mat]
  .filter(Boolean).map(d => [normaliza(d), nombreGrado(f)]))
  .sort((a, b) => b[0].length - a[0].length)

export function interpretarTexto(texto) {
  let t = normaliza(texto)
  const esp = {
    grado: null, acabado: null, formato: null, espesor_mm: null, ancho_mm: null,
    largo_mm: null, cantidad: null, uso: null, fuente_uso: null, opciones: {}, faltan: [], avisos: [],
  }
  const grado = DESIGNACIONES.find(([d]) => new RegExp(`(?<![\\w.])${escapa(d)}(?![\\w.])`).test(t))
  if (grado) esp.grado = grado[1]
  const familia = Object.keys(FAMILIAS).find(f => t.includes(f.slice(0, -1)))
  if (!esp.grado && familia) {
    esp.opciones.grado = unicos(fichas.filter(f => f.familia === FAMILIAS[familia]).map(nombreGrado))
  }
  const conUso = fichas.flatMap(f => f.aplicaciones.map(a => [normaliza(a.replace(/\.$/, '')), a.replace(/\.$/, ''), f]))
    .filter(([a]) => t.includes(a))
  if (conUso.length) {
    esp.uso = conUso[0][1]
    const fuentes = conUso.filter(([a]) => a === conUso[0][0]).map(([, , f]) => f)
    esp.fuente_uso = `Fichas ${unicos(fuentes.map(f => f.mat)).join(', ')}`
    if (!esp.grado && !esp.opciones.grado) esp.opciones.grado = unicos(fuentes.map(nombreGrado))
  }
  const acabado = t.match(/\b(ba|2r|2b|2d|1d)\b/)
  if (acabado) esp.acabado = acabado[1].toUpperCase()
  else for (const [k, v] of Object.entries(GLOSARIO)) if (t.includes(k)) esp.opciones.acabado = v
  const formato = Object.entries(FORMATOS).find(([, palabras]) => new RegExp(`\\b(${palabras})(s|es)?\\b`).test(t))
  if (formato) esp.formato = formato[0]

  // Medidas antes que espesor, para que «300 mm de ancho» no se lea como espesor.
  const medidas = t.match(/(\d{3,4})\s*[x×]\s*(\d{3,4})/)
  if (medidas) { esp.ancho_mm = +medidas[1]; esp.largo_mm = +medidas[2]; t = t.replace(medidas[0], ' ') }
  const ancho = t.match(/(\d{2,4})\s*(?:mm\s*)?de\s*ancho/) ?? t.match(/ancho\s*(?:de\s*)?(\d{2,4})(?:\s*mm)?/)
  if (ancho) { esp.ancho_mm = +ancho[1]; t = t.replace(ancho[0], ' ') }
  const largo = t.match(/(\d{3,5})\s*(?:mm\s*)?de\s*largo/) ?? t.match(/largo\s*(?:de\s*)?(\d{3,5})(?:\s*mm)?/)
  if (largo) { esp.largo_mm = +largo[1]; t = t.replace(largo[0], ' ') }
  const espesor = t.match(/(\d+(?:[.,]\d+)?)\s*mm/)
  if (espesor) esp.espesor_mm = numero(espesor[1])
  const kg = t.match(/(\d+(?:[.,]\d+)?)\s*(kg|t)\b/)
  if (kg) esp.cantidad = { valor: numero(kg[1]), unidad: kg[2] }

  if (!esp.grado && !esp.opciones.grado) esp.faltan.push('grado')
  if (!esp.espesor_mm) esp.faltan.push('espesor_mm')
  return esp
}
