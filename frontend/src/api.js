import { chatFalso, resumenFalso } from './mock.js'

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

export async function resumenStock() {
  if (!API) return resumenFalso()
  const r = await fetch(`${API}/stock/resumen`)
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}
