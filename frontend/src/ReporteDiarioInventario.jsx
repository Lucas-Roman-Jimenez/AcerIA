import { useEffect, useState } from 'react'
import { cargarReporteDiarioInventario } from './api.js'

const numero = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 })
const columnas = [
  ['total_bultos', 'Total de bultos'], ['disponibles', 'Disponibles'],
  ['reservados', 'Reservados'], ['bloqueados', 'Bloqueados'], ['peso_kg', 'Peso total (kg)'],
]

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

  const fecha = reporte && new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'long', timeStyle: 'short', timeZone: reporte.zona_horaria,
  }).format(new Date(reporte.consultado_en))

  return (
    <main className="reporte-semanal">
      <header className="reporte-cabecera">
        <div>
          <h1>{reporte?.titulo ?? 'Reporte diario de inventario'}</h1>
          {reporte && <p className="reporte-fecha">Consultado el <time dateTime={reporte.consultado_en}>{fecha}</time></p>}
        </div>
        <div className="reporte-botones">
          <button type="button" className="nueva" onClick={onVolver}>Volver a reportes</button>
        </div>
      </header>
      {error && <p role="alert">{error}</p>}
      {!reporte && !error && <p role="status">Cargando inventario…</p>}
      {reporte?.formatos.length === 0 && <p role="status">No hay bultos en inventario.</p>}
      {Boolean(reporte?.formatos.length) && (
        <div className="reporte-tabla-scroll">
          <table className="reporte-tabla" aria-label="Inventario actual por formato">
            <thead>
              <tr><th scope="col">Formato</th>{columnas.map(([id, nombre]) => <th key={id} scope="col">{nombre}</th>)}</tr>
            </thead>
            <tbody>
              {reporte.formatos.map(fila => (
                <tr key={fila.formato}>
                  <th scope="row">{fila.formato}</th>
                  {columnas.map(([id]) => <td key={id}>{numero.format(fila[id])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}
