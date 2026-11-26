// Reposición (GET /reportes/reposicion): qué referencias reponer según la cobertura de stock.
// El backend clasifica y ordena; aquí solo se pinta y se aplica el filtro con `cumple_filtro`.
import { useEffect, useState } from 'react'
import { cargarReposicion } from './api.js'

const toneladas = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 3 })
const dias = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 })
const medida = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 })
const fecha = new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeZone: 'UTC' })
const fechaHora = new Intl.DateTimeFormat('es-ES', { dateStyle: 'long', timeStyle: 'short', timeZone: 'Europe/Madrid' })

function secciones(u) {
  return [
    { id: 'reponer', titulo: 'Recomendar reposición',
      condicion: `Ventas en ${u.semanas_minimas_recurrente} semanas o más y cobertura inferior a ${u.cobertura_reponer_dias} días` },
    { id: 'vigilar', titulo: 'Vigilar',
      condicion: `Ventas en ${u.semanas_minimas_recurrente} semanas o más y cobertura de ${u.cobertura_reponer_dias} a ${u.cobertura_vigilar_max_dias} días` },
    { id: 'puntual', titulo: 'Revisar salida puntual',
      condicion: `Ventas en una sola semana y menos de ${toneladas.format(u.puntual_stock_max_t)} t disponibles` },
  ]
}

function referencia(f) {
  const medidas = [f.espesor_mm, f.ancho_mm, f.largo_mm].filter(v => v != null).map(v => medida.format(v)).join(' × ')
  return { material: [f.formato, f.grado, f.acabado].filter(Boolean).join(' '), medidas: medidas && `${medidas} mm` }
}

function Seccion({ seccion, filas }) {
  return (
    <section className={`repo-seccion ${seccion.id}`} aria-labelledby={`repo-${seccion.id}`}>
      <header className="repo-seccion-cabecera">
        <h2 id={`repo-${seccion.id}`}>{seccion.titulo} <span className="repo-contador">({filas.length})</span></h2>
        <p>{seccion.condicion}</p>
      </header>
      {filas.length === 0 ? <p className="repo-vacia">Ninguna referencia en esta sección.</p> : (
        <div className="reporte-tabla-scroll">
          <table className="repo-tabla">
            <thead>
              <tr>
                <th scope="col">Referencia</th><th scope="col">Vendido</th><th scope="col">Disponible</th>
                <th scope="col">Semanas con ventas</th><th scope="col">Cobertura</th>
              </tr>
            </thead>
            <tbody>
              {filas.map(f => {
                const { material, medidas } = referencia(f)
                return (
                  <tr key={[f.formato, f.grado, f.acabado, f.espesor_mm, f.ancho_mm, f.largo_mm].join('|')}>
                    <td data-campo="Referencia"><span className="repo-material">{material}</span> {medidas}</td>
                    <td data-campo="Vendido">{toneladas.format(f.vendido_t)} t</td>
                    <td data-campo="Disponible">{toneladas.format(f.disponible_t)} t</td>
                    <td data-campo="Semanas con ventas">{f.semanas_con_ventas}</td>
                    <td data-campo="Cobertura">{dias.format(f.cobertura_dias)} días</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export function Reposicion() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [filtrar, setFiltrar] = useState(false)

  useEffect(() => {
    const control = new AbortController()
    cargarReposicion(control.signal)
      .then(d => { if (!control.signal.aborted) setDatos(d) })
      .catch(e => { if (!control.signal.aborted) setError(e.message) })
    return () => control.abort()
  }, [])

  const filas = id => (datos?.secciones[id] ?? []).filter(f => !filtrar || f.cumple_filtro)
  const lista = datos ? secciones(datos.umbrales) : []
  const sinCoincidencias = datos && lista.every(s => filas(s.id).length === 0)

  return (
    <section aria-labelledby="reposicion-titulo">
      <header className="reporte-cabecera">
        <div>
          <h1 id="reposicion-titulo">Reposición</h1>
          {datos && (
            <p className="reporte-fecha">
              Ventas del <time dateTime={datos.periodo.inicio}>{fecha.format(new Date(datos.periodo.inicio))}</time>
              {' al '}<time dateTime={datos.periodo.fin}>{fecha.format(new Date(datos.periodo.fin))}</time>
              {' · '}stock a <time dateTime={datos.stock_a}>{fechaHora.format(new Date(datos.stock_a))}</time>
            </p>
          )}
        </div>
        {datos && (
          <label className="repo-filtro">
            <input type="checkbox" checked={filtrar} onChange={e => setFiltrar(e.target.checked)} />
            Más de {toneladas.format(datos.filtro.vendido_min_t)} t vendidas y menos
            de {toneladas.format(datos.filtro.stock_max_t)} t disponibles
          </label>
        )}
      </header>

      {error && <p role="alert">{error}</p>}
      {!datos && !error && <p role="status">Cargando reposición…</p>}
      {sinCoincidencias && <p role="status">No hay materiales que coincidan con los filtros.</p>}
      {datos && !sinCoincidencias && lista.map(s => <Seccion key={s.id} seccion={s} filas={filas(s.id)} />)}
    </section>
  )
}
