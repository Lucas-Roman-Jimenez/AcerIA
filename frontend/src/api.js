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

export async function cargarReporteSemanal(signal) {
  if (!API) throw new Error('El reporte necesita conexión con el backend.')
  const r = await fetch(`${API}/reportes/compras/semanal`, { signal })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return r.json()
}
