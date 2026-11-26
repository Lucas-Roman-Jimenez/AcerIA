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
  return <img src={`/materiales/${f}-${ac}.webp`} alt={`${f} ${ac}`} className="acero-svg" />
}

export function Acero({ esp, id }) {
  const grado = esp.grado ?? (esp.opciones?.grado?.length === 1 ? esp.opciones.grado[0] : null)
  if (!grado && !esp.formato) return null
  const acabado = esp.acabado ?? (esp.opciones?.acabado?.length === 1 ? esp.opciones.acabado[0] : null)
  const fichas = fichasDelGrado(grado)
  const ficha = fichas.length === 1 ? fichas[0] : null
  return (
    <div className="acero">
      <Dibujo formato={esp.formato} acabado={acabado} id={`acero-${id}`} />
      <div className="acero-info">
        <div className="acero-nombre">
          {[gradoVisible(grado), acabado ?? esp.opciones?.acabado?.join('/'), esp.formato].filter(Boolean).join(' · ')}
        </div>
        {ficha?.familia && (
          <>
            <div className="acero-familia">Inoxidable {ficha.familia}</div>
            <ul>{ficha.aplicaciones.slice(0, 4).map(a => <li key={a}>{a.replace(/\.$/, '')}</li>)}</ul>
          </>
        )}
        {fichas.length > 0 && <small className="fuente">Referencias AcerIA · {fichas.map(f => `${f.mat} (EN ${f.en})`).join(', ')}</small>}
      </div>
    </div>
  )
}
