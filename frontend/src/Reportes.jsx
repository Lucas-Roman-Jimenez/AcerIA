import { ReporteDiarioInventario } from './ReporteDiarioInventario.jsx'
import { ReporteSemanal } from './ReporteSemanal.jsx'
import { Reposicion } from './Reposicion.jsx'

const VISTAS = [
  ['inventario', 'Reporte diario de inventario', ReporteDiarioInventario],
  ['compras', 'Reporte semanal de compras', ReporteSemanal],
  ['reposicion', 'Reposición', Reposicion],
]

export function Reportes({ vista, onCambiarVista, onVolver }) {
  const [actual, , Vista] = VISTAS.find(([id]) => id === vista) ?? VISTAS[0]
  return (
    <main className="reportes">
      <nav className="reporte-botones reportes-nav" aria-label="Reportes">
        {VISTAS.map(([id, nombre]) => (
          <button key={id} type="button" className="nueva" aria-pressed={id === actual}
            onClick={() => onCambiarVista(id)}>
            {nombre}
          </button>
        ))}
        <button type="button" className="nueva" onClick={onVolver}>Volver al chat</button>
      </nav>
      <Vista />
    </main>
  )
}
