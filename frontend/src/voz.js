import { transcribirVoz } from '../../voz/microfono.mjs'
import { normalizarTranscripcion } from '../../voz/normalizacion.mjs'

// La transcripción se coloca en la caja de texto para revisarla antes de enviar (RF-03).
export function escuchar() {
  const dictado = transcribirVoz()
  return { ...dictado, texto: dictado.texto.then(normalizarTranscripcion) }
}

export function leerEnAlto(texto) {
  if (!('speechSynthesis' in window) || !texto) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'es-ES'
  window.speechSynthesis.speak(u)
}
