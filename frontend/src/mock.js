// API falsa con el formato de docs/contrato.md §6. Solo para desarrollar sin backend.
import datos from '../../datos_ejemplo/inventario.json'

const BULTOS = datos.bultos.filter(b => b.estado !== 'reservado')
const GLOSARIO = { brillante: ['BA', '2R'], mate: ['2B'], 'en caliente': ['1D'] }
const historiales = {}

function interpretar(textos) {
  const t = textos.join(' ').toLowerCase()
  const esp = {
    grado: null, acabado: null, formato: null, espesor_mm: null, ancho_mm: null,
    largo_mm: null, cantidad: null, uso: null, fuente_uso: null, opciones: {}, faltan: [], avisos: [],
  }
  const grado = t.match(/\b(316l|304l?|316|321|430|2205)\b/)
  if (grado) esp.grado = grado[1].toUpperCase()
  const acabado = t.match(/\b(ba|2r|2b|2d|1d)\b/)
  if (acabado) esp.acabado = acabado[1].toUpperCase()
  else for (const [k, v] of Object.entries(GLOSARIO)) if (t.includes(k)) esp.opciones.acabado = v
  const formato = t.match(/\b(chapa|bobina|fleje)\b/)
  if (formato) esp.formato = formato[1]
  else if (t.includes('rollo')) esp.formato = 'bobina'
  const espesor = t.match(/(\d+(?:[.,]\d+)?)\s*mm/)
  if (espesor) esp.espesor_mm = parseFloat(espesor[1].replace(',', '.'))
  const medidas = t.match(/(\d{3,4})\s*[x×]\s*(\d{3,4})/)
  if (medidas) { esp.ancho_mm = +medidas[1]; esp.largo_mm = +medidas[2] }
  const ancho = t.match(/ancho\s*(?:de\s*)?(\d{3,4})/)
  if (ancho) esp.ancho_mm = +ancho[1]
  const kg = t.match(/(\d+)\s*kg/)
  if (kg) esp.cantidad = { valor: +kg[1], unidad: 'kg' }
  if (t.includes('marino')) { esp.uso = 'ambiente marino'; esp.fuente_uso = 'Catálogo de ejemplo' }
  if (!esp.grado) esp.faltan.push('grado')
  if (!esp.espesor_mm) esp.faltan.push('espesor_mm')
  return esp
}

function cumple(b, esp) {
  for (const k of ['grado', 'acabado', 'formato', 'espesor_mm', 'ancho_mm']) {
    if (esp[k] != null && b[k] !== esp[k]) return false
  }
  if (esp.opciones.acabado && !esp.opciones.acabado.includes(b.acabado)) return false
  return true
}

function buscar(esp) {
  const exactos = BULTOS.filter(b => cumple(b, esp))
  const transformables = BULTOS
    .filter(b => !exactos.includes(b) && b.grado === esp.grado && esp.ancho_mm && b.ancho_mm > esp.ancho_mm
      && (esp.espesor_mm == null || b.espesor_mm === esp.espesor_mm))
    .map(b => ({
      id: b.id,
      acciones: [`Cortar ancho ${b.ancho_mm} → ${esp.ancho_mm} mm`],
      merma_kg: Math.round(b.peso_kg * (b.ancho_mm - esp.ancho_mm) / b.ancho_mm),
      origen: b,
      resultado: { ...b, ancho_mm: esp.ancho_mm, peso_kg: Math.round(b.peso_kg * esp.ancho_mm / b.ancho_mm) },
    }))
  const alternativas = exactos.length || transformables.length ? []
    : BULTOS.filter(b => b.grado === esp.grado).slice(0, 2)
  return { exactos, transformables, alternativas }
}

const NOMBRES = { grado: 'el grado', espesor_mm: 'el espesor' }

export async function chatFalso(conversacionId, texto) {
  await new Promise(r => setTimeout(r, 700))
  if (texto.toLowerCase().includes('error')) throw new Error('Fallo simulado del LLM')
  const h = (historiales[conversacionId] ??= [])
  h.push(texto)
  const especificacion = interpretar(h)
  const base = { conversacion_id: conversacionId, especificacion, exactos: [], transformables: [], alternativas: [], error: null, texto: null, pregunta: null }
  if (especificacion.faltan.length) {
    return { ...base, tipo: 'pregunta', pregunta: `¿Me dices ${especificacion.faltan.map(f => NOMBRES[f]).join(' y ')}?` }
  }
  const res = buscar(especificacion)
  const n = res.exactos.length, m = res.transformables.length
  let txt
  if (n) txt = `Hay ${n} bulto${n > 1 ? 's' : ''} que cumple${n > 1 ? 'n' : ''} la petición: ${res.exactos.map(b => b.id).join(', ')}.`
  else if (m) txt = `No hay coincidencia exacta, pero ${m} bulto${m > 1 ? 's' : ''} se puede${m > 1 ? 'n' : ''} transformar: ${res.transformables.map(b => b.id).join(', ')}.`
  else txt = 'No hay stock ni transformación posible para esa petición.'
  return { ...base, tipo: 'respuesta', texto: txt, ...res }
}

export async function resumenFalso() {
  const g = {}
  for (const b of BULTOS) {
    const k = `${b.grado} ${b.acabado} · ${b.formato}`
    g[k] ??= { etiqueta: k, bultos: 0, toneladas: 0 }
    g[k].bultos++
    g[k].toneladas += b.peso_kg / 1000
  }
  return Object.values(g)
}
