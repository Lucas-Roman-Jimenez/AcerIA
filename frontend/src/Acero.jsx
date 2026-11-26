import { fichasDelGrado, gradoVisible } from './grados.js'

export function buscarFicha(grado) {
  const candidatas = fichasDelGrado(grado)
  return candidatas.length === 1 && candidatas[0].descripcion ? candidatas[0] : null
}

// Renders de estudio en public/materiales/<formato>-<acabado>.webp.
const FORMATOS = ['bobina', 'chapa', 'fleje']
const ACABADOS = ['2B', 'BA', '2R', '2D', '4']

export function Dibujo({ formato, acabado }) {
  const f = FORMATOS.includes(formato) ? formato : 'bobina'
  const a = String(acabado ?? '').toUpperCase().replace(/^N[º°O.]*\s*/, '')
  const ac = ACABADOS.includes(a) ? a : '2B'
  return <img src={`/materiales/${f}-${ac}.webp`} alt={`${f} ${ac}`} className={`acero-svg material-${f}`} />
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
export function Acero({ esp, id, sinStock = false }) {
  const grado = esp.grado ?? (esp.opciones?.grado?.length === 1 ? esp.opciones.grado[0] : null)
  if (!grado && !esp.formato) return null
  const acabado = esp.acabado ?? (esp.opciones?.acabado?.length === 1 ? esp.opciones.acabado[0] : null)
  // Del remoto: las fichas del grado (puede haber varias) y el nombre unificado del grado.
  const fichas = fichasDelGrado(grado)
  const ficha = fichas.length === 1 ? fichas[0] : null
  const detalle = [acabado ?? esp.opciones?.acabado?.join('/'), esp.formato].filter(Boolean).join(' · ')
  return (
    <figure className={`acero vitrina ${sinStock ? 'sin-stock' : ''}`}>
      <div className="vitrina-escena">
        {sinStock && <span className="cruz-sin-stock" role="img" aria-label="Sin stock" />}
        <Dibujo formato={esp.formato} acabado={acabado} id={`acero-${id}`} />
      </div>
      <figcaption className="vitrina-pie">
        <div className="vitrina-nombre">
          <span className="vitrina-fina">{ficha?.familia ? `Inoxidable ${ficha.familia}` : 'Acero inoxidable'}</span>
          <span className="vitrina-gruesa">{grado ? gradoVisible(grado) : esp.formato}</span>
        </div>
        {detalle && <div className="vitrina-meta">{detalle}</div>}
        {ficha?.aplicaciones?.length > 0 && <p className="vitrina-desc">{enFrase(ficha.aplicaciones.slice(0, 5))}</p>}
        {fichas.length > 0 && (
          <div className="vitrina-mat" aria-label="Referencias AcerIA">
            {[...new Set(fichas.map(f => f.mat))].map(mat => <span key={mat}>{mat}</span>)}
          </div>
        )}
      </figcaption>
    </figure>
  )
}
