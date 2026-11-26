import fichas from './fichas_aceria.json'

// El inventario real trae grados dobles como «304L/304»: vale la ficha de cualquiera de ellos.
export function buscarFicha(grado) {
  if (!grado) return null
  if (grado.includes('/')) return grado.split('/').map(buscarFicha).find(Boolean) ?? null
  const g = grado.toUpperCase()
  return fichas.find(f => f.aisi?.toUpperCase() === g)
    ?? fichas.find(f => f.en === grado || f.uns?.toUpperCase().includes(g) || f.mat.replace(' ', '') === g.replace(' ', ''))
    ?? null
}

// Renders de estudio en public/materiales/<formato>-<acabado>.webp.
const FORMATOS = ['bobina', 'chapa', 'fleje']
const ACABADOS = ['2B', 'BA', '2R', '2D', '4']

export function Dibujo({ formato, acabado }) {
  const f = FORMATOS.includes(formato) ? formato : 'bobina'
  const a = String(acabado ?? '').toUpperCase().replace(/^N[º°O.]*\s*/, '')
  const ac = ACABADOS.includes(a) ? a : '2B'
  return <img src={`/materiales/${f}-${ac}.webp`} alt={`${f} ${ac}`} className="acero-svg" />
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
