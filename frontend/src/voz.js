// Punto de entrada de la voz de Lucas: debe llamar a onTexto(transcripcion).
// La transcripción se coloca en la caja de texto para revisarla antes de enviar (RF-03).
export function escuchar(onTexto, onError) {
  if (window.vozLucas?.escuchar) return window.vozLucas.escuchar(onTexto, onError)
  onError('La entrada por voz todavía no está conectada. Puedes escribir la petición.')
}

export function leerEnAlto(texto) {
  if (!('speechSynthesis' in window) || !texto) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'es-ES'
  window.speechSynthesis.speak(u)
}
