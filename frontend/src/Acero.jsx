import fichas from './fichas_aceria.json'

// Apariencia por acabado: los brillantes con reflejos marcados, los mates planos.
const ACABADOS = {
  BA: ['#ffffff', '#7d8296', '#f7f8fc', '#4d5163', '#e9ebf3'],
  '2R': ['#ffffff', '#7d8296', '#f7f8fc', '#4d5163', '#e9ebf3'],
  '2B': ['#c9ccd6', '#aeb2bf', '#c3c6d0', '#a3a7b5', '#bcc0cb'],
  '2D': ['#a4a7b2', '#8f939f', '#9ea1ad', '#878b97', '#9a9ea9'],
  '1D': ['#7c7f88', '#686b74', '#777a83', '#62656e', '#73767f'],
}
const DEFECTO = ['#e4e6ee', '#9195a8', '#d9dce6', '#6c7084', '#c4c7d3']

// El inventario real trae grados dobles como «304L/304»: vale la ficha de cualquiera de ellos.
export function buscarFicha(grado) {
  if (!grado) return null
  if (grado.includes('/')) return grado.split('/').map(buscarFicha).find(Boolean) ?? null
  const g = grado.toUpperCase()
  return fichas.find(f => f.aisi?.toUpperCase() === g)
    ?? fichas.find(f => f.en === grado || f.mat.replace(' ', '') === g.replace(' ', ''))
    ?? null
}

function Degradado({ id, colores, vertical }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2={vertical ? 0 : 1} y2={vertical ? 1 : 0}>
      {colores.map((c, i) => <stop key={i} offset={i / (colores.length - 1)} stopColor={c} />)}
    </linearGradient>
  )
}

export function Dibujo({ formato, acabado, id }) {
  const colores = ACABADOS[acabado] ?? DEFECTO
  if (formato === 'chapa') {
    return (
      <svg viewBox="0 0 200 130" className="acero-svg">
        <defs><Degradado id={id} colores={colores} /></defs>
        <polygon points="20,80 120,20 185,50 85,110" fill={`url(#${id})`} />
        <polygon points="20,80 85,110 85,118 20,88" fill="#5d6175" />
        <polygon points="85,110 185,50 185,58 85,118" fill="#8a8ea0" />
      </svg>
    )
  }
  const ancho = formato === 'fleje' ? 28 : 80
  return (
    <svg viewBox="0 0 200 130" className="acero-svg">
      <defs><Degradado id={id} colores={colores} vertical /></defs>
      <rect x={100 - ancho / 2} y="15" width={ancho} height="100" fill={`url(#${id})`} />
      <ellipse cx={100 - ancho / 2} cy="65" rx="14" ry="50" fill={`url(#${id})`} />
      <ellipse cx={100 + ancho / 2} cy="65" rx="14" ry="50" fill={colores[2]} stroke="#6c7084" />
      <ellipse cx={100 + ancho / 2} cy="65" rx="5" ry="16" fill="#2a2c3c" />
    </svg>
  )
}

export function Acero({ esp, id }) {
  const grado = esp.grado ?? (esp.opciones?.grado?.length === 1 ? esp.opciones.grado[0] : null)
  if (!grado && !esp.formato) return null
  const acabado = esp.acabado ?? (esp.opciones?.acabado?.length === 1 ? esp.opciones.acabado[0] : null)
  const ficha = buscarFicha(grado)
  return (
    <div className="acero">
      <Dibujo formato={esp.formato} acabado={acabado} id={`acero-${id}`} />
      <div className="acero-info">
        <div className="acero-nombre">
          {[grado, acabado ?? esp.opciones?.acabado?.join('/'), esp.formato].filter(Boolean).join(' · ')}
        </div>
        {ficha && (
          <>
            <div className="acero-familia">Inoxidable {ficha.familia} · EN {ficha.en} · {ficha.mat}</div>
            <ul>{ficha.aplicaciones.slice(0, 4).map(a => <li key={a}>{a.replace(/\.$/, '')}</li>)}</ul>
            <small className="fuente">Fuente: ficha técnica {ficha.mat} de AcerIA</small>
          </>
        )}
      </div>
    </div>
  )
}
