import { useState } from 'react'

const CAMPOS = [
  ['grado', 'Grado'],
  ['acabado', 'Acabado'],
  ['formato', 'Formato'],
  ['espesor_mm', 'Espesor', 'mm'],
  ['ancho_mm', 'Ancho', 'mm'],
  ['largo_mm', 'Largo', 'mm'],
]

const fmt = v => String(v).replace('.', ',')

// RF-19: la corrección se envía como mensaje, así la valida el backend y no el frontend.
export function Panel({ esp, onCorregir, deshabilitado }) {
  const [editando, setEditando] = useState(null)
  const [valor, setValor] = useState('')

  if (!esp) return <aside className="panel"><h2>Lo que he entendido</h2><p className="tenue">Aún nada.</p></aside>

  function confirmar(etiqueta, unidad) {
    if (valor.trim()) onCorregir(`El ${etiqueta.toLowerCase()} es ${valor.trim()}${unidad ? ' ' + unidad : ''}`)
    setEditando(null)
  }

  return (
    <aside className="panel">
      <h2>Lo que he entendido</h2>
      <dl>
        {CAMPOS.map(([k, etiqueta, unidad]) => {
          const falta = esp.faltan?.includes(k)
          const opciones = esp.opciones?.[k]
          return (
            <div key={k} className={`campo ${falta ? 'falta' : ''}`}>
              <dt>{etiqueta}</dt>
              <dd>
                {editando === k ? (
                  <form onSubmit={e => { e.preventDefault(); confirmar(etiqueta, unidad) }}>
                    <input autoFocus value={valor} onChange={e => setValor(e.target.value)}
                      onBlur={() => setEditando(null)} />
                  </form>
                ) : (
                  <button className="valor" disabled={deshabilitado} title="Corregir"
                    onClick={() => { setEditando(k); setValor(esp[k] ?? '') }}>
                    {esp[k] != null ? `${fmt(esp[k])}${unidad ? ' ' + unidad : ''}`
                      : opciones ? opciones.join(' o ')
                      : esp.indiferentes?.includes(k) ? 'Cualquiera'
                      : falta ? 'Falta' : '—'}
                  </button>
                )}
              </dd>
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
