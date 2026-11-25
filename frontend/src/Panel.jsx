import { useState } from 'react'
import { consultarValores } from './api.js'

const CAMPOS = [
  ['grado', 'Grado'],
  ['acabado', 'Acabado'],
  ['formato', 'Formato'],
  ['espesor_mm', 'Espesor', 'mm'],
  ['ancho_mm', 'Ancho', 'mm'],
  ['largo_mm', 'Largo', 'mm'],
]
const CONSULTABLES = ['grado', 'acabado', 'formato', 'espesor_mm', 'ancho_mm']

const fmt = v => String(v).replace('.', ',')

function filtrosSin(esp, campo) {
  const f = {}
  for (const k of CONSULTABLES) if (k !== campo && esp[k] != null) f[k] = esp[k]
  return f
}

// RF-19: la corrección se envía como mensaje, así la valida el backend y no el frontend.
export function Panel({ esp, onCorregir, deshabilitado }) {
  const [editando, setEditando] = useState(null)
  const [valor, setValor] = useState('')
  const [enStock, setEnStock] = useState(null)

  if (!esp) return <aside className="panel"><h2>Lo que he entendido</h2><p className="tenue">Aún nada.</p></aside>

  function abrir(k) {
    setEditando(k)
    setValor(esp[k] != null ? fmt(esp[k]) : '')
    setEnStock(null)
    if (!CONSULTABLES.includes(k)) return
    consultarValores(k, filtrosSin(esp, k))
      .then(r => setEnStock(r.valores))
      .catch(() => setEnStock([]))
  }

  function corregir(etiqueta, unidad, v) {
    const limpio = String(v).trim()
    if (limpio) onCorregir(`El ${etiqueta.toLowerCase()} es ${limpio}${unidad ? ' ' + unidad : ''}`)
    setEditando(null)
  }

  return (
    <aside className="panel">
      <h2>Lo que he entendido</h2>
      <p className="panel-ayuda">Pulsa un dato para cambiarlo.</p>
      <dl>
        {CAMPOS.map(([k, etiqueta, unidad]) => {
          const falta = esp.faltan?.includes(k)
          const opciones = esp.opciones?.[k]
          return (
            <div key={k} className={`campo-bloque ${editando === k ? 'abierto' : ''}`}>
              <div className={`campo ${falta ? 'falta' : ''}`}>
                <dt>{etiqueta}</dt>
                <dd>
                  <button className="valor" disabled={deshabilitado} title="Corregir"
                    onClick={() => (editando === k ? setEditando(null) : abrir(k))}>
                    {esp[k] != null ? `${fmt(esp[k])}${unidad ? ' ' + unidad : ''}`
                      : opciones ? opciones.join(' o ')
                      : esp.indiferentes?.includes(k) ? 'Cualquiera'
                      : falta ? 'Falta' : '—'}
                  </button>
                </dd>
              </div>
              {editando === k && (
                <div className="editor" onKeyDown={e => e.key === 'Escape' && setEditando(null)}>
                  <form onSubmit={e => { e.preventDefault(); corregir(etiqueta, unidad, valor) }}>
                    <input autoFocus value={valor} onChange={e => setValor(e.target.value)}
                      placeholder={unidad ? `En ${unidad}` : 'Escribe el valor'} aria-label={`Nuevo ${etiqueta.toLowerCase()}`} />
                    <button type="submit" disabled={!valor.trim()}>Cambiar</button>
                  </form>
                  {CONSULTABLES.includes(k) && (
                    <div className="editor-stock">
                      {enStock === null ? <span className="tenue">Buscando lo que hay en stock…</span>
                        : enStock.length === 0 ? <span className="tenue">No hay stock con el resto de datos.</span>
                        : (
                          <>
                            <span className="tenue">En stock con el resto de datos:</span>
                            <div className="editor-lista">
                              {enStock.map(v => (
                                <button key={v.valor} type="button" className="chip-stock" disabled={deshabilitado}
                                  onClick={() => corregir(etiqueta, unidad, fmt(v.valor))}
                                  title={`${v.bultos} bultos · ${fmt(v.toneladas)} t`}>
                                  {fmt(v.valor)}{unidad ? ` ${unidad}` : ''} <small>{v.bultos}</small>
                                </button>
                              ))}
                            </div>
                          </>
                        )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
        <div className="campo">
          <dt>Cantidad</dt>
          <dd>{esp.cantidad ? `${fmt(esp.cantidad.valor)} ${esp.cantidad.unidad}` : '—'}</dd>
        </div>
        {esp.uso && (
          <div className="campo">
            <dt>Uso</dt>
            <dd>{esp.uso}{esp.fuente_uso && <small className="fuente">Fuente: {esp.fuente_uso}</small>}</dd>
          </div>
        )}
      </dl>
      {esp.avisos?.length > 0 && (
        <ul className="avisos">{esp.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
      )}
    </aside>
  )
}
