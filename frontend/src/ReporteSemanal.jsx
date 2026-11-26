import { useEffect, useState } from 'react'
import { cargarReporteSemanal } from './api.js'
import { Tendencias } from './Tendencias.jsx'
import { descargarJson } from './descargarJson.js'

const numero = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 6 })
const fecha = new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeZone: 'UTC' })
const medidas = n => `${numero.format(n)} mm`
const CARACTERISTICAS = [
  ['id', 'ID del bulto'], ['grado', 'Grado'], ['acabado', 'Acabado'],
  ['espesor_mm', 'Espesor', medidas], ['ancho_mm', 'Ancho', medidas],
  ['largo_mm', 'Largo', medidas], ['peso_kg', 'Peso del bulto', n => `${numero.format(n)} kg`],
]

export function ReporteSemanal({ onVolver }) {
  const [reporte, setReporte] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const control = new AbortController()
    cargarReporteSemanal(control.signal)
      .then(datos => { if (!control.signal.aborted) setReporte(datos) })
      .catch(e => { if (!control.signal.aborted) setError(e.message) })
    return () => control.abort()
  }, [])

  return (
    <main className="reporte-semanal">
      <header className="reporte-cabecera">
        <div>
          <h1>{reporte?.titulo ?? 'Reporte semanal de compras'}</h1>
          {reporte && (
            <p className="reporte-fecha">
              Del <time dateTime={reporte.semana.inicio}>{fecha.format(new Date(reporte.semana.inicio))}</time>
              {' al '}<time dateTime={reporte.semana.fin}>{fecha.format(new Date(reporte.semana.fin))}</time>
            </p>
          )}
        </div>
        <div className="reporte-botones">
          <button type="button" className="nueva" onClick={onVolver}>Volver a reportes</button>
          <button type="button" className="nueva" disabled={!reporte}
            onClick={() => descargarJson(reporte, `reporte-semanal-compras-${reporte.semana.inicio}.json`)}>
            Descargar JSON
          </button>
        </div>
      </header>
      {error && <p role="alert">{error}</p>}
      {!reporte && !error && <p role="status">Cargando compras…</p>}
      {reporte?.compras.length === 0 && <p role="status">No hay compras registradas esta semana.</p>}
      {Boolean(reporte?.compras.length) && (
        <ul className="reporte-compras" aria-label="Compras de la semana">
          {reporte.compras.map(compra => (
            <li key={compra.caracteristicas.id} className="reporte-compra">
              <div>
                <h2>{compra.nombre_material}</h2>
                <dl className="reporte-caracteristicas">
                  {CARACTERISTICAS.filter(([campo]) => campo !== 'largo_mm' || compra.caracteristicas[campo] != null)
                    .map(([campo, nombre, formato]) => {
                      const valor = compra.caracteristicas[campo]
                      return (
                        <div key={campo}>
                          <dt>{nombre}</dt>
                          <dd>{valor == null ? 'Sin dato' : formato ? formato(valor) : valor}</dd>
                        </div>
                      )
                    })}
                </dl>
              </div>
              <div className="reporte-cantidad">
                <span>Cantidad sustraída</span>
                {compra.cantidades_sustraidas.map(({ valor, unidad }) => (
                  <strong key={unidad}>{numero.format(valor)} {unidad}</strong>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
      <Tendencias />
    </main>
  )
}
