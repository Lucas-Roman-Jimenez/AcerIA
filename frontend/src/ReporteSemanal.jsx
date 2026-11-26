import { useEffect, useState } from 'react'
import { cargarReporteSemanal } from './api.js'

const numero = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 6 })
const fecha = new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeZone: 'UTC' })
const medidas = n => `${numero.format(n)} mm`
const CARACTERISTICAS = [
  ['id', 'Bulto'], ['formato', 'Formato'], ['aisi', 'AISI'], ['euronorma', 'EN'],
  ['acabado', 'Acabado superior'], ['acabado_inf', 'Acabado inferior'],
  ['codigo_acabado_inf', 'Código de acabado inferior'],
  ['espesor_mm', 'Espesor nominal', medidas], ['espesor_min_mm', 'Espesor mínimo', medidas],
  ['espesor_max_mm', 'Espesor máximo', medidas], ['ancho_mm', 'Ancho', medidas],
  ['largo_mm', 'Largo', medidas], ['peso_kg', 'Peso del bulto', n => `${numero.format(n)} kg`],
  ['papel', 'Papel', n => n ? 'Sí' : 'No'], ['cantidad', 'Cantidad en origen', n => numero.format(n)],
  ['estado', 'Estado en origen'],
]

function descargarJson(reporte) {
  const contenido = JSON.stringify(reporte, null, 2)
  const url = URL.createObjectURL(new Blob([contenido], { type: 'application/json' }))
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = `reporte-semanal-compras-${reporte.semana.inicio}.json`
  enlace.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

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
          <button type="button" className="nueva" onClick={onVolver}>Volver al chat</button>
          <button type="button" className="nueva" disabled={!reporte} onClick={() => descargarJson(reporte)}>
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
            <li key={compra.id} className="reporte-compra">
              <div>
                <h2>{compra.nombre_material}</h2>
                <dl className="reporte-caracteristicas">
                  {CARACTERISTICAS.filter(([campo]) => compra.caracteristicas[campo] != null).map(([campo, nombre, formato]) => (
                    <div key={campo}>
                      <dt>{nombre}</dt>
                      <dd>{formato ? formato(compra.caracteristicas[campo]) : compra.caracteristicas[campo]}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="reporte-cantidad">
                <span>Cantidad sustraída</span>
                <strong>{numero.format(compra.cantidad_sustraida.valor)} {compra.cantidad_sustraida.unidad}</strong>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
