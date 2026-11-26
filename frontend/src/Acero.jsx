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

// «Sistemas de escape, Tubos» → «Sistemas de escape y tubos.»: las aplicaciones de la ficha como un párrafo.
function enFrase(aplicaciones) {
  const xs = aplicaciones.map(a => a.replace(/\.$/, '').trim()).filter(Boolean)
    .map((a, i) => (i && !/^[A-Z0-9]{2,}/.test(a) ? a[0].toLowerCase() + a.slice(1) : a))
  if (!xs.length) return ''
  return `${xs.length > 1 ? `${xs.slice(0, -1).join(', ')} y ${xs.at(-1)}` : xs[0]}.`
}

// Vitrina del material: el render en grande sobre un fondo topográfico, el nombre centrado
// (familia en fino, grado en grueso) y para qué se usa, todo sacado de la ficha técnica de AcerIA.
export function Acero({ esp, id }) {
  const grado = esp.grado ?? (esp.opciones?.grado?.length === 1 ? esp.opciones.grado[0] : null)
  if (!grado && !esp.formato) return null
  const acabado = esp.acabado ?? (esp.opciones?.acabado?.length === 1 ? esp.opciones.acabado[0] : null)
  const ficha = buscarFicha(grado)
  const detalle = [acabado ?? esp.opciones?.acabado?.join('/'), esp.formato].filter(Boolean).join(' · ')
  return (
    <figure className="acero vitrina">
      <div className="vitrina-escena">
        <Dibujo formato={esp.formato} acabado={acabado} id={`acero-${id}`} />
      </div>
      <figcaption className="vitrina-pie">
        <div className="vitrina-nombre">
          <span className="vitrina-fina">{ficha ? `Inoxidable ${ficha.familia}` : 'Acero inoxidable'}</span>
          <span className="vitrina-gruesa">{grado ?? esp.formato}</span>
        </div>
        {(detalle || ficha) && (
          <div className="vitrina-meta">{[detalle, ficha && `EN ${ficha.en}`, ficha?.mat].filter(Boolean).join(' · ')}</div>
        )}
        {ficha && <p className="vitrina-desc">{enFrase(ficha.aplicaciones.slice(0, 5))}</p>}
        {ficha && <small className="fuente">Fuente: ficha técnica {ficha.mat} de AcerIA</small>}
      </figcaption>
    </figure>
  )
}
