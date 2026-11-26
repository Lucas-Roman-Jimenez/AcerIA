// API falsa con el formato de docs/contrato.md §6. Solo para desarrollar sin backend.
import datos from '../../datos_ejemplo/inventario.json'
import { interpretarTexto } from './previa.js'

const BULTOS = datos.bultos.filter(b => b.estado !== 'reservado')
const historiales = {}
const interpretar = textos => interpretarTexto(textos.join(' '))

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
      merma_pct: Math.round(1000 * (b.ancho_mm - esp.ancho_mm) / b.ancho_mm) / 10,
      num_operaciones: 1,
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
  const base = { conversacion_id: conversacionId, especificacion, exactos: [], transformables: [], alternativas: [], error: null, texto: null, pregunta: null, opciones: [],
    criterio_orden: 'exactos > % de merma > nº de operaciones' }
  if (especificacion.faltan.length) {
    return { ...base, tipo: 'pregunta', pregunta: `¿Me dices ${especificacion.faltan.map(f => NOMBRES[f]).join(' y ')}?` }
  }
  const res = buscar(especificacion)
  // Segundo momento de pregunta (RF-07): el stock real se distingue por el acabado.
  const acabados = [...new Set(res.exactos.map(b => b.acabado))]
  if (!especificacion.acabado && acabados.length > 1) {
    const pregunta = `Tengo ${especificacion.grado ?? 'ese material'} en ${acabados.join(' y en ')}. ¿Cuál necesitas?`
    return { ...base, tipo: 'pregunta', pregunta, texto: pregunta, opciones: acabados }
  }
  const n = res.exactos.length, m = res.transformables.length
  let txt
  if (n) txt = `Hay ${n} bulto${n > 1 ? 's' : ''} que cumple${n > 1 ? 'n' : ''} la petición: ${res.exactos.map(b => b.id).join(', ')}.`
  else if (m) txt = `No hay coincidencia exacta, pero ${m} bulto${m > 1 ? 's' : ''} se puede${m > 1 ? 'n' : ''} transformar: ${res.transformables.map(b => b.id).join(', ')}.`
  else txt = 'No hay stock ni transformación posible para esa petición.'
  return { ...base, tipo: 'respuesta', texto: txt, ...res }
}

export async function valoresFalsos(campo, filtros) {
  await new Promise(r => setTimeout(r, 300))
  const esp = { opciones: {}, ...filtros }
  const g = {}
  for (const b of BULTOS.filter(b => cumple(b, esp))) {
    const v = b[campo]
    if (v == null) continue
    g[v] ??= { valor: v, bultos: 0, toneladas: 0 }
    g[v].bultos++
    g[v].toneladas = Math.round((g[v].toneladas + b.peso_kg / 1000) * 10) / 10
  }
  const valores = Object.values(g).sort((a, b) => (typeof a.valor === 'number' ? a.valor - b.valor : b.toneladas - a.toneladas))
  return { campo, filtros, valores, total_bultos: valores.reduce((s, v) => s + v.bultos, 0) }
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

export async function buscarFalso(esp) {
  await new Promise(r => setTimeout(r, 200))
  return buscar({ opciones: {}, ...esp })
}
