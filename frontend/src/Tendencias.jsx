// Tendencias de compras (GET /reportes/compras/tendencias, de Lucas): barras por semana y formato
// y los materiales más vendidos frente al stock actual. Sin librerías: barras con CSS.
import { useEffect, useState } from 'react'
import { cargarTendencias } from './api.js'

const numero = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 })
const diaMes = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const UNIDADES = { kg: 'kg', bultos: 'bultos', piezas: 'piezas' }
const SEMANAS = [4, 8, 12, 26]
const FLECHA = { sube: '↑', baja: '↓', estable: '=' }
const ESTADO = { en_curso: 'en curso', inicio_historial: 'primera semana', sin_historial: 'sin datos' }

function Variacion({ barra }) {
  if (!FLECHA[barra.tendencia]) return null
  const pct = barra.variacion_pct == null ? '' : ` ${numero.format(Math.abs(barra.variacion_pct))} %`
  return <span className={`tend-var ${barra.tendencia}`}>{FLECHA[barra.tendencia]}{pct}</span>
}

// Escala del eje: 4 tramos de tamaño redondo (1, 2, 2,5 o 5 × 10^n) que cubren el máximo.
const TRAMOS = 4
function escala(maximo) {
  const bruto = Math.max(maximo, 1) / TRAMOS
  const potencia = 10 ** Math.floor(Math.log10(bruto))
  const paso = [1, 2, 2.5, 5, 10].map(f => f * potencia).find(p => p >= bruto)
  return Array.from({ length: TRAMOS + 1 }, (_, i) => i * paso)
}

function medidas(m) {
  return [m.espesor_mm, m.ancho_mm, m.largo_mm].filter(v => v != null).map(v => numero.format(v)).join(' × ')
}

export function Tendencias() {
  const [semanas, setSemanas] = useState(8)
  const [unidad, setUnidad] = useState('kg')
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const control = new AbortController()
    setError('')
    cargarTendencias(semanas, unidad, control.signal)
      .then(d => { if (!control.signal.aborted) setDatos(d) })
      .catch(e => { if (!control.signal.aborted) setError(e.message) })
    return () => control.abort()
  }, [semanas, unidad])

  const marcas = escala(Math.max(0, ...(datos?.semanas ?? []).flatMap(s => s.barras.map(b => b.cantidad ?? 0))))
  const maximo = marcas[TRAMOS]
  const hayCompras = Boolean(datos?.materiales.length)

  return (
    <section className="tendencias" aria-labelledby="tendencias-titulo">
      <header className="tend-cabecera">
        <h2 id="tendencias-titulo">Tendencias de compras</h2>
        <div className="tend-controles">
          <label>Unidad{' '}
            <select value={unidad} onChange={e => setUnidad(e.target.value)}>
              {Object.entries(UNIDADES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </label>
          <label>Periodo{' '}
            <select value={semanas} onChange={e => setSemanas(Number(e.target.value))}>
              {SEMANAS.map(n => <option key={n} value={n}>{n} semanas</option>)}
            </select>
          </label>
        </div>
      </header>

      {error && <p role="alert">{error}</p>}
      {!datos && !error && <p role="status">Cargando tendencias…</p>}
      {datos && !hayCompras && <p role="status">Todavía no hay compras en este periodo.</p>}

      {datos && hayCompras && (
        <>
          <ul className="tend-leyenda" aria-label="Leyenda">
            {datos.semanas[0].barras.map(b => <li key={b.formato} className={b.formato}>{b.formato}</li>)}
          </ul>
          <div className="tend-zona">
          <div className="tend-eje" aria-hidden="true">
            <span className="tend-eje-unidad">{UNIDADES[unidad]}</span>
            {marcas.map(v => (
              <span key={v} className="tend-marca" style={{ bottom: `${(v / maximo) * 100}%` }}>{numero.format(v)}</span>
            ))}
          </div>
          <ol className="tend-grafico" aria-label={`Compras por semana en ${UNIDADES[unidad]}`}>
            {datos.semanas.map(s => (
              <li key={s.inicio} className={`tend-semana ${s.estado}`}>
                <div className="tend-barras">
                  {s.barras.map(b => (
                    <div key={b.formato} className="tend-columna">
                      <Variacion barra={b} />
                      <div
                        className={`tend-barra ${b.formato}`}
                        style={{ height: `${((b.cantidad ?? 0) / maximo) * 100}%` }}
                        title={`${b.formato}: ${b.cantidad == null ? 'sin datos' : `${numero.format(b.cantidad)} ${UNIDADES[unidad]}`}`}
                      />
                    </div>
                  ))}
                </div>
                <span className="tend-fecha">{diaMes.format(new Date(s.inicio))}</span>
                {ESTADO[s.estado] && <span className="tend-estado">{ESTADO[s.estado]}</span>}
              </li>
            ))}
          </ol>
          </div>

          <h3>Lo más vendido</h3>
          <table className="tend-tabla">
            <thead>
              <tr><th>Material</th><th>Medidas (mm)</th><th>Comprado</th><th>Stock actual</th></tr>
            </thead>
            <tbody>
              {datos.materiales.slice(0, 10).map((m, i) => (
                <tr key={i}>
                  <td>{[m.formato, m.grado, m.acabado].filter(Boolean).join(' ')}</td>
                  <td>{medidas(m)}</td>
                  <td>{numero.format(m.comprado)} {UNIDADES[unidad]}</td>
                  <td>{m.stock_actual == null ? '—' : `${numero.format(m.stock_actual)} ${UNIDADES[unidad]}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
