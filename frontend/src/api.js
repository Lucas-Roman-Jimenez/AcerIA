import { chatFalso, resumenFalso, valoresFalsos, buscarFalso } from './mock.js'

// Sin VITE_API_URL se usa la API falsa (src/mock.js).
const API = import.meta.env.VITE_API_URL

export async function enviarMensaje(conversacionId, texto) {
  if (!API) return chatFalso(conversacionId, texto)
  const r = await fetch(`${API}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversacion_id: conversacionId, texto }),
  })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

export async function consultarValores(campo, filtros) {
  if (!API) return valoresFalsos(campo, filtros)
  const q = new URLSearchParams({ campo, ...filtros })
  const r = await fetch(`${API}/stock/valores?${q}`)
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

export async function resumenStock() {
  if (!API) return resumenFalso()
  const r = await fetch(`${API}/stock/resumen`)
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

// Bultos que cumplen una especificación parcial (solo los campos que no son null).
export async function buscarStock(esp) {
  if (!API) return buscarFalso(esp)
  const r = await fetch(`${API}/buscar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(esp),
  })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

// Venta simulada del carrito: los bultos pasan a «vendido» y aparecen en el reporte semanal.
export async function venderCarrito(ids) {
  if (!API) throw new Error('La venta necesita conexión con el backend.')
  const r = await fetch(`${API}/compras`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bultos: ids }),
  })
  const datos = await r.json().catch(() => ({}))
  if (r.status === 409) {
    throw new Error(`Ya no están disponibles: ${datos.detail?.no_disponibles?.join(', ')}. No se ha vendido nada.`)
  }
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return datos
}

export async function cargarReporteSemanal(signal) {
  if (!API) throw new Error('El reporte necesita conexión con el backend.')
  const r = await fetch(`${API}/reportes/compras/semanal`, { signal })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return r.json()
}

// Tendencias de compras por semana y formato (Lucas): unidad 'kg', 'bultos' o 'piezas'.
export async function cargarTendencias(semanas, unidad, signal) {
  if (!API) throw new Error('Las tendencias necesitan conexión con el backend.')
  const consulta = new URLSearchParams({ semanas: String(semanas), unidad })
  const r = await fetch(`${API}/reportes/compras/tendencias?${consulta}`, { signal })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return r.json()
}
