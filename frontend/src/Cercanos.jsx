import { useEffect, useState } from 'react'
import { consultarValores } from './api.js'

const num = v => String(v).replace('.', ',')
const MEDIDAS = [
  ['espesor_mm', 'Espesor', v => `El espesor es ${num(v)} mm`],
  ['ancho_mm', 'Ancho', v => `El ancho es ${num(v)} mm`],
]

// Valores reales más próximos a lo pedido, manteniendo el resto de la petición.
function filtrosSin(esp, campo) {
  const f = {}
  for (const k of ['grado', 'acabado', 'formato', 'espesor_mm', 'ancho_mm']) {
    if (k !== campo && esp[k] != null) f[k] = esp[k]
  }
  return f
}

export function Cercanos({ esp, onElegir, deshabilitado }) {
  const [grupos, setGrupos] = useState(null)

  useEffect(() => {
    let vivo = true
    const pedidas = MEDIDAS.filter(([k]) => esp[k] != null)
    Promise.all(pedidas.map(async ([k, etiqueta, frase]) => {
      const { valores } = await consultarValores(k, filtrosSin(esp, k))
      const cercanos = valores
        .filter(v => v.valor !== esp[k])
        .sort((a, b) => Math.abs(a.valor - esp[k]) - Math.abs(b.valor - esp[k]))
        .slice(0, 3)
        .sort((a, b) => a.valor - b.valor)
      return { k, etiqueta, frase, cercanos }
    }))
      .then(gs => vivo && setGrupos(gs.filter(g => g.cercanos.length)))
      .catch(() => vivo && setGrupos([]))
    return () => { vivo = false }
  }, [esp])

  if (!grupos?.length) return null
  return (
    <div className="cercanos">
      <div className="cercanos-titulo">Lo más parecido que sí hay en stock, con el resto de tu petición:</div>
      {grupos.map(g => (
        <div key={g.k} className="cercanos-fila">
          <span className="cercanos-etiqueta">{g.etiqueta}</span>
          {g.cercanos.map(v => (
            <button key={v.valor} type="button" className="valor-stock compacto" disabled={deshabilitado}
              onClick={() => onElegir(g.frase(v.valor))}>
              <span className="valor-stock-nombre">{num(v.valor)} mm</span>
              <span className="valor-stock-cantidad">{v.bultos} {v.bultos === 1 ? 'bulto' : 'bultos'} · {num(v.toneladas)} t</span>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}
