// API falsa con el formato de docs/contrato.md §6. Solo para desarrollar sin backend.
import datos from '../../datos_ejemplo/inventario.json'
import fichas from './fichas_aceria.json'

const BULTOS = datos.bultos.filter(b => b.estado !== 'reservado')
const GLOSARIO = { brillante: ['BA', '2R'], mate: ['2B'], 'en caliente': ['1D'] }
const historiales = {}

const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/mat\s*/g, 'mat ')
const nombreGrado = f => f.aisi?.replace(' DDQ', '') ?? f.mat
const escapa = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Cada designación del catálogo (AISI, EN, MAT) apunta a su grado; las más largas primero.
const DESIGNACIONES = fichas.flatMap(f => [f.aisi, f.aisi?.replace(' DDQ', ''), f.en, f.mat]
  .filter(Boolean).map(d => [normaliza(d), nombreGrado(f)]))
  .sort((a, b) => b[0].length - a[0].length)
const FAMILIAS = { austenitico: 'austenítico', duplex: 'dúplex', ferritico: 'ferrítico', martensitico: 'martensítico' }
const unicos = xs => [...new Set(xs)]

function interpretar(textos) {
  const t = normaliza(textos.join(' '))
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
  if (!esp.grado && !esp.opciones.grado) esp.faltan.push('grado')
  if (!esp.espesor_mm) esp.faltan.push('espesor_mm')
  return esp
}

function cumple(b, esp) {
  for (const k of ['grado', 'acabado', 'formato', 'espesor_mm', 'ancho_mm']) {
    if (esp[k] != null && b[k] !== esp[k]) return false
  }
  for (const [k, vs] of Object.entries(esp.opciones)) if (!vs.includes(b[k])) return false
  return true
}

const gradoValido = (b, esp) => esp.grado ? b.grado === esp.grado : esp.opciones.grado?.includes(b.grado)

function buscar(esp) {
  const exactos = BULTOS.filter(b => cumple(b, esp))
  const transformables = BULTOS
    .filter(b => !exactos.includes(b) && gradoValido(b, esp) && esp.ancho_mm && b.ancho_mm > esp.ancho_mm
      && (esp.espesor_mm == null || b.espesor_mm === esp.espesor_mm))
    .map(b => ({
      id: b.id,
      acciones: [`Cortar ancho ${b.ancho_mm} → ${esp.ancho_mm} mm`],
      merma_kg: Math.round(b.peso_kg * (b.ancho_mm - esp.ancho_mm) / b.ancho_mm),
      origen: b,
      resultado: { ...b, ancho_mm: esp.ancho_mm, peso_kg: Math.round(b.peso_kg * esp.ancho_mm / b.ancho_mm) },
    }))
  const alternativas = exactos.length || transformables.length ? []
    : BULTOS.filter(b => gradoValido(b, esp)).slice(0, 2)
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
