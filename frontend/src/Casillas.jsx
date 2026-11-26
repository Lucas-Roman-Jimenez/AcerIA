import { useEffect, useRef, useState } from 'react'
import { interpretarTexto } from './previa.js'
import { consultarValores } from './api.js'
import { fraseCambio } from './Flujo.jsx'

const num = v => String(v).replace('.', ',')
const lista = vs => (vs?.length > 3 ? `${vs.slice(0, 3).join(', ')}…` : vs?.join(' o '))

const CAMPOS = [
  ['grado', 'Grado'],
  ['espesor_mm', 'Espesor', 'mm'],
  ['acabado', 'Acabado'],
  ['formato', 'Formato'],
  ['ancho_mm', 'Ancho', 'mm'],
]
// El stock trae grados dobles («304L/304»): cuenta como elegido si coincide con cualquiera de ellos.
const igual = (a, b) => a === b || String(a).toUpperCase().split('/').map(x => x.trim()).includes(String(b).toUpperCase())
const conUnidad = (unidad, v) => `${num(v)}${unidad ? ' ' + unidad : ''}`

// Filtros de un campo: lo ya elegido en los demás. Así, al elegir 2 mm, el resto solo ofrece lo que hay en 2 mm.
function filtrosSin(esp, campo) {
  const f = {}
  for (const [k] of CAMPOS) if (k !== campo && esp?.[k] != null) f[k] = esp[k]
  return f
}

// Datos del metal: lo que se va reconociendo al escribir y lo ya entendido en la conversación.
// Cada casilla se pulsa para ver los valores en stock con el resto de lo elegido.
export function Casillas({ texto, base, onElegir, onQuitar, deshabilitado }) {
  const [abierto, setAbierto] = useState(null)
  const [valores, setValores] = useState({})
  const raiz = useRef(null)
  const previa = texto.trim() ? interpretarTexto(texto) : null
  const valor = k => previa?.[k] ?? base?.[k] ?? null
  const opciones = k => previa?.opciones?.[k] ?? base?.opciones?.[k]
  const clave = JSON.stringify(CAMPOS.map(([k]) => base?.[k] ?? null))

  // Valores en stock de cada campo con lo ya elegido; se recalculan al cambiar cualquier dato.
  useEffect(() => {
    let vivo = true
    setValores({})
    Promise.all(CAMPOS.map(async ([k]) => [k, (await consultarValores(k, filtrosSin(base, k))).valores]))
      .then(pares => vivo && setValores(Object.fromEntries(pares)))
      .catch(() => vivo && setValores({}))
    return () => { vivo = false }
  }, [clave])

  useEffect(() => {
    if (!abierto) return
    const cerrar = e => { if (!raiz.current?.contains(e.target)) setAbierto(null) }
    const escape = e => e.key === 'Escape' && setAbierto(null)
    document.addEventListener('mousedown', cerrar)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('mousedown', cerrar); document.removeEventListener('keydown', escape) }
  }, [abierto])

  const esElegido = (k, v) => base?.[k] != null && igual(v, base[k])

  function elegir(k, v) {
    setAbierto(null)
    onElegir(fraseCambio(k, v))
  }

  // Deseleccionar: el dato deja de filtrar (queda en «indiferentes» del backend).
  function quitar(k) {
    setAbierto(null)
    onQuitar(k)
  }

  const largo = valor('largo_mm')
  return (
    <div className="casillas" aria-live="polite" ref={raiz}>
      {CAMPOS.map(([k, etiqueta, unidad]) => {
        // Un dato quitado («me da igual») queda vacío, como al principio: se puede volver a elegir cualquier valor.
        const v = valor(k) != null ? conUnidad(unidad, valor(k)) : lista(opciones(k)) ?? null
        const enStock = valores[k]
        return (
          <div key={k} className="casilla-bloque">
            <button type="button" className={`casilla ${v ? 'llena' : ''} ${abierto === k ? 'abierta' : ''}`}
              disabled={deshabilitado} aria-expanded={abierto === k}
              title={`Ver los ${etiqueta.toLowerCase()}s que hay en stock`}
              onClick={() => setAbierto(abierto === k ? null : k)}>
              <span className="casilla-etiqueta">{etiqueta} ⌄</span>
              <span className="casilla-valor">{v ?? (enStock ? `${enStock.length} en stock` : '—')}</span>
            </button>
            {base?.[k] != null && (
              <button type="button" className="casilla-quitar" disabled={deshabilitado}
                title={`Quitar ${etiqueta.toLowerCase()}`} aria-label={`Quitar ${etiqueta.toLowerCase()}`}
                onClick={() => quitar(k)}>✕</button>
            )}
            {abierto === k && (
              <div className="casilla-opciones" role="listbox" aria-label={`${etiqueta} en stock`}>
                <div className="casilla-opciones-titulo">
                  {etiqueta} en stock{Object.keys(filtrosSin(base, k)).length ? ' con lo que ya has elegido' : ''}
                </div>
                {!enStock ? <span className="tenue">Buscando…</span>
                  : !enStock.length ? <span className="tenue">No hay stock con el resto de datos.</span>
                  : (
                    <div className="editor-lista">
                      {enStock.map(o => (
                        <button key={o.valor} type="button" role="option" aria-selected={esElegido(k, o.valor)}
                          className={`chip-stock ${esElegido(k, o.valor) ? 'elegido' : ''}`} disabled={deshabilitado}
                          onClick={() => (esElegido(k, o.valor) ? quitar(k) : elegir(k, o.valor))}
                          title={esElegido(k, o.valor) ? 'Pulsa para quitarlo' : `${o.bultos} bultos · ${num(o.toneladas)} t`}>
                          {conUnidad(unidad, o.valor)} <small>{esElegido(k, o.valor) ? '✕' : o.bultos}</small>
                        </button>
                      ))}
                    </div>
                  )}
              </div>
            )}
          </div>
        )
      })}
      {largo != null && (
        <div className="casilla-bloque">
          <div className="casilla llena">
            <span className="casilla-etiqueta">Largo</span>
            <span className="casilla-valor">{num(largo)} mm</span>
          </div>
        </div>
      )}
    </div>
  )
}
