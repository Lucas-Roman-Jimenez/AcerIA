const ETIQUETAS = { exacto: 'Cumple', transformable: 'Transformable', alternativa: 'Alternativa' }

const num = v => String(v).replace('.', ',')

function medidas(b) {
  return [b.espesor_mm, b.ancho_mm, b.largo_mm].filter(v => v != null).map(num).join(' × ') + ' mm'
}

// En un transformable, los datos del bulto vienen en `origen` (o en el propio objeto si el backend los aplana).
const datosBulto = (tipo, item) => (tipo === 'transformable' ? item.origen ?? item : item)

export function Tarjeta({ tipo, item, onClick }) {
  const b = datosBulto(tipo, item)
  return (
    <button className={`tarjeta ${tipo}`} onClick={onClick}>
      <div className="tarjeta-cabeza">
        <span className="tarjeta-id">{item.id}</span>
        <span className="tarjeta-tipo">{ETIQUETAS[tipo]}</span>
      </div>
      {b.grado && <div className="tarjeta-spec">{b.grado} {b.acabado} · {b.formato}</div>}
      {b.espesor_mm != null && <div className="tarjeta-medidas">{medidas(b)}</div>}
      <div className="tarjeta-extra">
        {b.peso_kg != null && <span>{num(b.peso_kg)} kg</span>}
        {b.ubicacion && <span>{b.ubicacion}</span>}
      </div>
      {tipo === 'transformable' && (
        <div className="tarjeta-acciones">
          {item.acciones.join(' · ')}
          {item.merma_kg != null && <> · merma {num(item.merma_kg)} kg</>}
          {item.merma_pct != null && <> ({num(item.merma_pct)} %)</>}
          {item.num_operaciones > 1 && <> · {item.num_operaciones} operaciones</>}
        </div>
      )}
    </button>
  )
}

const FILAS = [
  ['grado', 'Grado'], ['acabado', 'Acabado'], ['formato', 'Formato'],
  ['espesor_mm', 'Espesor (mm)'], ['ancho_mm', 'Ancho (mm)'], ['largo_mm', 'Largo (mm)'],
  ['peso_kg', 'Peso (kg)'], ['piezas', 'Piezas'], ['ubicacion', 'Ubicación'], ['estado', 'Estado'],
]

export function Detalle({ item: { tipo, item }, onCerrar }) {
  const antes = datosBulto(tipo, item)
  const despues = tipo === 'transformable' ? item.resultado : null
  return (
    <div className="modal-fondo" onClick={onCerrar}>
      <div className={`modal ${tipo}`} onClick={e => e.stopPropagation()} role="dialog" aria-label={`Detalle del bulto ${item.id}`}>
        <div className="modal-cabeza">
          <h2>{item.id} <span className="tarjeta-tipo">{ETIQUETAS[tipo]}</span></h2>
          <button className="cerrar" onClick={onCerrar} aria-label="Cerrar">×</button>
        </div>
        {tipo === 'alternativa' && <p className="tenue">No cumple todos los requisitos: se muestra como alternativa cercana.</p>}
        <table>
          <thead><tr><th /><th>{despues ? 'Antes' : 'Valor'}</th>{despues && <th>Después</th>}</tr></thead>
          <tbody>
            {FILAS.filter(([k]) => antes[k] != null || despues?.[k] != null).map(([k, etiqueta]) => (
              <tr key={k} className={despues && antes[k] !== despues[k] ? 'cambia' : ''}>
                <th>{etiqueta}</th>
                <td>{antes[k] ?? '—'}</td>
                {despues && <td>{despues[k] ?? '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        {tipo === 'transformable' && (
          <div className="modal-acciones">
            <h3>Acciones</h3>
            <ol>{item.acciones.map((a, i) => <li key={i}>{a}</li>)}</ol>
            {item.merma_kg != null && (
              <p>Merma estimada: <b>{num(item.merma_kg)} kg</b>{item.merma_pct != null && <> ({num(item.merma_pct)} %)</>}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
