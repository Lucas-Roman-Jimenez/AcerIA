import { useEffect, useState } from 'react'
import { cargarReporteDiarioInventario } from './api.js'
import { descargarJson } from './descargarJson.js'

const fecha = new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeZone: 'UTC' })
const fechaLegible = iso => fecha.format(new Date(iso))

export function ReporteDiarioInventario({ onVolver }) {
  const [reporte, setReporte] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const control = new AbortController()
    cargarReporteDiarioInventario(control.signal)
      .then(datos => { if (!control.signal.aborted) setReporte(datos) })
      .catch(e => { if (!control.signal.aborted) setError(e.message) })
    return () => control.abort()
  }, [])

  return (
    <main className="reporte-semanal">
      <header className="reporte-cabecera">
        <div>
          <h1>{reporte?.titulo ?? 'Reporte diario'}</h1>
          {reporte && <p className="reporte-fecha"><time dateTime={reporte.fecha}>{fechaLegible(reporte.fecha)}</time></p>}
        </div>
        <div className="reporte-botones">
          <button type="button" className="nueva" onClick={onVolver}>Volver a reportes</button>
          <button type="button" className="nueva" disabled={!reporte}
            onClick={() => descargarJson(reporte, `reporte-diario-inventario-${reporte.fecha}.json`)}>
            Descargar reporte
          </button>
        </div>
      </header>
      {error && <p role="alert">{error}</p>}
      {!reporte && !error && <p role="status">Cargando reporte…</p>}
      {reporte?.materiales_sin_stock.length === 0 && <p role="status">No hay materiales del catálogo sin stock.</p>}
      {Boolean(reporte?.materiales_sin_stock.length) && (
        <div className="reporte-tabla-scroll">
          <table className="reporte-tabla" aria-label="Materiales del catálogo sin stock">
            <thead>
              <tr><th scope="col">Fecha sin stock</th><th scope="col">Nombre</th><th scope="col">ID</th></tr>
            </thead>
            <tbody>
              {reporte.materiales_sin_stock.map(fila => (
                <tr key={fila.id}>
                  <td>{fila.fecha_sin_stock
                    ? <time dateTime={fila.fecha_sin_stock}>{fechaLegible(fila.fecha_sin_stock)}</time>
                    : 'Sin fecha registrada'}</td>
                  <td>{fila.nombre}</td>
                  <td>{fila.id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}
