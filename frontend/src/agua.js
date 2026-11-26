// Onda de agua al pulsar un botón (complemento del llenado con olas de styles.css, «Botones de agua»).
// Un único listener para todo el documento: sirve también para los botones que se crean después.
export const BOTONES_AGUA = [
  '.boton-destacado', '.carrito-boton', '.microfono', '.opcion', '.nueva', '.demo-boton', '.salir-flujo',
  '.icono', '.valor-stock', '.demo-siguiente', '.editor form button',
].join(', ')

export function activarOndas() {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
  document.addEventListener('pointerdown', e => {
    const boton = e.target.closest?.(BOTONES_AGUA)
    if (!boton || boton.disabled) return
    const caja = boton.getBoundingClientRect()
    const tam = Math.max(caja.width, caja.height) * 2.2
    const onda = document.createElement('span')
    onda.className = 'onda-agua'
    onda.style.width = onda.style.height = `${tam}px`
    onda.style.left = `${e.clientX - caja.left - tam / 2}px`
    onda.style.top = `${e.clientY - caja.top - tam / 2}px`
    boton.appendChild(onda)
    onda.addEventListener('animationend', () => onda.remove())
  })
}
