import { ReporteDiarioInventario } from './ReporteDiarioInventario.jsx'
import { ReporteSemanal } from './ReporteSemanal.jsx'

export function Reportes({ vista, onCambiarVista, onVolver }) {
  const verCompras = vista === 'compras'
  return (
    <main className="reportes">
      <nav className="reporte-botones reportes-nav" aria-label="Reportes">
        <button type="button" className="nueva" aria-pressed={!verCompras} onClick={() => onCambiarVista('inventario')}>
          Reporte diario de inventario
        </button>
        <button type="button" className="nueva" aria-pressed={verCompras} onClick={() => onCambiarVista('compras')}>
          Reporte semanal de compras
        </button>
        <button type="button" className="nueva" onClick={onVolver}>Volver al chat</button>
      </nav>
      {verCompras ? <ReporteSemanal /> : <ReporteDiarioInventario />}
    </main>
  )
}
