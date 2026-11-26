import { useState } from 'react'
import { ReporteDiarioInventario } from './ReporteDiarioInventario.jsx'
import { ReporteSemanal } from './ReporteSemanal.jsx'

export function Reportes({ onVolver }) {
  const [verCompras, setVerCompras] = useState(false)

  return (
    <main className="reportes">
      <nav className="reporte-botones reportes-nav" aria-label="Reportes">
        <button type="button" className="nueva" aria-pressed={!verCompras} onClick={() => setVerCompras(false)}>
          Reporte diario de inventario
        </button>
        <button type="button" className="nueva" aria-pressed={verCompras} onClick={() => setVerCompras(true)}>
          Reporte semanal de compras
        </button>
        <button type="button" className="nueva" onClick={onVolver}>Volver al chat</button>
      </nav>
      {verCompras ? <ReporteSemanal /> : <ReporteDiarioInventario />}
    </main>
  )
}
