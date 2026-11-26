import { useEffect, useState } from 'react'

// Texto que se escribe letra a letra, como en un teclado: ritmo irregular, pausa tras los espacios
// y la puntuación, y un cursor que parpadea al terminar. Con «reducir movimiento» se muestra entero.
//  - rapido: para las respuestas del chat; los textos largos avanzan de varias letras en varias
//    para que ninguna respuesta tarde más de unos 3 segundos.
//  - velocidad: multiplica el ritmo normal (2 = el doble de rápido), con el mismo tecleo irregular.
//  - cursorFinal: si el cursor se queda parpadeando al terminar (en el chat desaparece).
const reducido = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function retardo(letra, rapido, velocidad) {
  const f = (rapido ? 0.15 : 1) / velocidad
  if (/[.,;:!?¿¡]/.test(letra)) return (260 + Math.random() * 120) * (rapido ? 0.3 : 1) / velocidad
  if (letra === ' ') return (120 + Math.random() * 80) * f
  return (55 + Math.random() * 75) * f
}

export function Escritura({ texto, inicio = 350, as: Etiqueta = 'span', className = '', rapido = false, velocidad = 1, cursorFinal = true, onFin }) {
  const [n, setN] = useState(() => (reducido() ? texto.length : 0))

  useEffect(() => {
    if (reducido()) { setN(texto.length); onFin?.(); return }
    setN(0)
    const paso = rapido ? Math.max(1, Math.ceil(texto.length / 120)) : 1
    let i = 0
    let t = setTimeout(function siguiente() {
      i = Math.min(texto.length, i + paso)
      setN(i)
      if (i < texto.length) t = setTimeout(siguiente, retardo(texto[i - 1], rapido, velocidad))
      else onFin?.()
    }, inicio)
    return () => clearTimeout(t)
  }, [texto, inicio, rapido, velocidad])

  const terminado = n >= texto.length
  return (
    <Etiqueta className={`escritura ${className}`} aria-label={texto}>
      {/* El texto completo, invisible, reserva el sitio: no se mueve nada mientras se escribe */}
      <span className="escritura-hueco" aria-hidden>{texto}</span>
      <span className="escritura-texto" aria-hidden>
        {texto.slice(0, n)}
        {(!terminado || cursorFinal) && <span className={`escritura-cursor ${terminado ? 'parpadea' : ''}`} />}
      </span>
    </Etiqueta>
  )
}
