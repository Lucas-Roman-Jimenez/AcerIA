import { transcribirVoz } from '../../voz/microfono.mjs'
import { normalizarTranscripcion } from '../../voz/normalizacion.mjs'

let dictando = false

// La transcripción se coloca en la caja de texto para revisarla antes de enviar (RF-03).
export async function escuchar(onTexto, onError) {
  if (globalThis.vozLucas?.escuchar) return globalThis.vozLucas.escuchar(onTexto, onError)
  if (dictando) return
  dictando = true
  try {
    const transcripcion = await transcribirVoz().texto
    if (transcripcion) onTexto(normalizarTranscripcion(transcripcion))
  } catch (error) {
    onError(`${error.message} Puedes escribir la petición.`)
  } finally {
    dictando = false
  }
}

export function leerEnAlto(texto) {
  if (!('speechSynthesis' in window) || !texto) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'es-ES'
  window.speechSynthesis.speak(u)
}
