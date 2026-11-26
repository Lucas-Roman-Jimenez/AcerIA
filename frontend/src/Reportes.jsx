import { useState } from 'react'
import { ReporteDiarioInventario } from './ReporteDiarioInventario.jsx'
import { ReporteSemanal } from './ReporteSemanal.jsx'

export function Reportes({ onVolver }) {
  const [vista, setVista] = useState(null)
  const volverAlMenu = () => setVista(null)

  if (vista === 'inventario') return <ReporteDiarioInventario onVolver={volverAlMenu} />
  if (vista === 'compras') return <ReporteSemanal onVolver={volverAlMenu} />

  return (
    <main className="reporte-semanal">
      <header className="reporte-cabecera">
        <h1>Reportes</h1>
        <div className="reporte-botones">
          <button type="button" className="nueva" onClick={onVolver}>Volver al chat</button>
        </div>
      </header>
      <nav className="reporte-botones" aria-label="Reportes disponibles">
        <button type="button" className="nueva" onClick={() => setVista('inventario')}>
          Reporte diario de inventario
        </button>
        <button type="button" className="nueva" onClick={() => setVista('compras')}>
          Reporte semanal de compras
        </button>
      </nav>
    </main>
  )
}
