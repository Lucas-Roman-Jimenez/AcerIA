import { interpretarTexto } from './previa.js'

const num = v => String(v).replace('.', ',')
const lista = vs => (vs?.length > 3 ? `${vs.slice(0, 3).join(', ')}…` : vs?.join(' o '))

// Lo que se va reconociendo mientras se escribe, sobre lo que el backend ya entendió en la conversación.
export function Casillas({ texto, base }) {
  const previa = texto.trim() ? interpretarTexto(texto) : null
  const valor = k => previa?.[k] ?? base?.[k] ?? null
  const opciones = k => previa?.opciones?.[k] ?? base?.opciones?.[k]

  const cualquiera = k => (base?.indiferentes?.includes(k) ? 'Cualquiera' : null)

  const ancho = valor('ancho_mm'), largo = valor('largo_mm')
  const casillas = [
    ['Grado', valor('grado') ?? lista(opciones('grado')) ?? cualquiera('grado')],
    ['Espesor', valor('espesor_mm') != null ? `${num(valor('espesor_mm'))} mm` : cualquiera('espesor_mm')],
    ['Acabado', valor('acabado') ?? lista(opciones('acabado')) ?? cualquiera('acabado')],
    ['Formato', valor('formato') ?? cualquiera('formato')],
    ['Medidas', ancho || largo ? `${ancho ?? '—'} × ${largo ?? '—'} mm` : cualquiera('ancho_mm')],
  ]

  return (
    <div className="casillas" aria-live="polite">
      {casillas.map(([etiqueta, v]) => (
        <div key={etiqueta} className={`casilla ${v ? 'llena' : ''}`}>
          <span className="casilla-etiqueta">{etiqueta}</span>
          <span className="casilla-valor">{v ?? '—'}</span>
        </div>
      ))}
    </div>
  )
}
