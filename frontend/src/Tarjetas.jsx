import { useEffect, useState } from 'react'
import { fichasDelGrado, gradoVisible, tienePdf } from './grados.js'
import { urlFicha } from './api.js'

const ETIQUETAS = { exacto: 'Cumple', transformable: 'Transformable', alternativa: 'Alternativa' }

const num = v => String(v).replace('.', ',')

// El motor de reglas devuelve cada acción como objeto {regla, descripcion, parametros, merma_kg, orden}.
// Se aceptan también textos (respuestas de prueba) y se muestran en el orden de aplicación (RF-13).
const textoAccion = a => (typeof a === 'string' ? a : a?.descripcion ?? a?.regla ?? '')
const acciones = item => [...(item.acciones ?? [])]
  .sort((x, y) => (x?.orden ?? 0) - (y?.orden ?? 0))
  .map(textoAccion)

function medidas(b) {
  return [b.espesor_mm, b.ancho_mm, b.largo_mm].filter(v => v != null).map(num).join(' × ') + ' mm'
}

// En un transformable, los datos del bulto vienen en `origen` (o en el propio objeto si el backend los aplana).
const datosBulto = (tipo, item) => (tipo === 'transformable' ? item.origen ?? item : item)
const gradoBulto = bulto => gradoVisible(bulto.grado ?? bulto.aisi, bulto.euronorma)
const valorBulto = (bulto, campo) => campo === 'grado' ? gradoBulto(bulto) : bulto[campo]

// Transformable: qué bulto hay hoy, qué se obtiene y qué hay que hacer. Lo usan la tarjeta y el carrito.
// Todo sale del motor de reglas (resultado, acciones, merma); si no viene `resultado`, devuelve null.
export function transformacion(item) {
  const r = item.resultado
  if (!r) return null
  const antes = item.origen ?? item.bulto ?? item
  const peso = r.peso_util_kg ?? r.peso_kg
  const piezas = r.piezas > 1 ? ` (${r.piezas} piezas)` : ''
  return {
    antes: `${antes.formato} ${medidas(antes)}${antes.peso_kg != null ? `, ${num(antes.peso_kg)} kg` : ''}`,
    despues: `${r.formato} ${medidas(r)}${piezas}${peso != null ? `, ${num(peso)} kg útiles` : ''}`,
    acciones: acciones(item).join(' y '),
    merma: item.merma_kg != null
      ? `merma ${item.merma_estimada ? 'estimada ' : ''}${num(item.merma_kg)} kg${item.merma_pct != null ? ` (${num(item.merma_pct)} %)` : ''}`
      : null,
  }
}

const ORIGEN = {
  exacto: 'Inventario',
  transformable: 'Inventario + reglas de transformación',
  alternativa: 'Inventario (no cumple todo)',
}

export function Tarjeta({ tipo, item, onClick, comparando, onComparar }) {
  const b = datosBulto(tipo, item)
  const t = tipo === 'transformable' ? transformacion(item) : null
  if (t) return <TarjetaTransformable item={item} b={b} t={t} onClick={onClick} comparando={comparando} onComparar={onComparar} />
  return (
    <div className={`tarjeta ${tipo} ${comparando ? 'comparando' : ''}`}>
      <button type="button" className="tarjeta-cuerpo" onClick={onClick}>
        <div className="tarjeta-cabeza">
          <span className="tarjeta-id">{item.id}</span>
          <span className="tarjeta-tipo">{ETIQUETAS[tipo]}</span>
        </div>
        {gradoBulto(b) && <div className="tarjeta-spec">{gradoBulto(b)} {b.acabado} · {b.formato}</div>}
        {b.espesor_mm != null && <div className="tarjeta-medidas">{medidas(b)}</div>}
        <div className="tarjeta-extra">
          {b.peso_kg != null && <span>{num(b.peso_kg)} kg</span>}
          {b.ubicacion && <span>{b.ubicacion}</span>}
        </div>
        {tipo === 'transformable' && (
          <div className="tarjeta-acciones">
            {acciones(item).join(' · ')}
            {item.merma_kg != null && <> · merma {num(item.merma_kg)} kg</>}
            {item.merma_pct != null && <> ({num(item.merma_pct)} %)</>}
            {item.num_operaciones > 1 && <> · {item.num_operaciones} operaciones</>}
          </div>
        )}
        <div className="tarjeta-origen">Fuente: {ORIGEN[tipo]} · ver de dónde sale</div>
      </button>
      {onComparar && (
        <label className="tarjeta-comparar">
          <input type="checkbox" checked={comparando} onChange={onComparar} /> Comparar
        </label>
      )}
    </div>
  )
}

const FILAS = [
  ['grado', 'Grado'], ['acabado', 'Acabado'], ['formato', 'Formato'],
  ['espesor_mm', 'Espesor (mm)'], ['ancho_mm', 'Ancho (mm)'], ['largo_mm', 'Largo (mm)'],
  ['peso_kg', 'Peso (kg)'], ['piezas', 'Piezas'], ['ubicacion', 'Ubicación'], ['estado', 'Estado'],
]

function useEscape(onCerrar) {
  useEffect(() => {
    const f = e => e.key === 'Escape' && onCerrar()
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [onCerrar])
}

const igual = (pedido, real) => typeof pedido === 'number'
  ? Math.abs(pedido - real) < 1e-9
  : String(real ?? '').toUpperCase().split('/').map(s => s.trim()).includes(String(pedido).toUpperCase())

// Qué pedía el comercial y qué tiene el bulto, campo a campo (RNF-09).
function Coincidencias({ esp, bulto }) {
  if (!esp) return null
  const filas = FILAS.slice(0, 6)
    .map(([k, etiqueta]) => {
      const pedido = esp[k] ?? null
      const opciones = esp.opciones?.[k]
      if (pedido == null && !opciones) return null
      const ok = pedido != null ? igual(pedido, bulto[k]) : opciones.some(o => igual(o, bulto[k]))
      return { k, etiqueta, pedido: pedido ?? opciones.join(' o '), real: valorBulto(bulto, k) ?? '—', ok }
    })
    .filter(Boolean)
  if (!filas.length) return null
  return (
    <>
      <h3>Por qué se propone</h3>
      <table className="coincidencias">
        <thead><tr><th /><th>Pediste</th><th>El bulto</th><th /></tr></thead>
        <tbody>
          {filas.map(f => (
            <tr key={f.k} className={f.ok ? 'ok' : 'no'}>
              <th>{f.etiqueta}</th><td>{f.pedido}</td><td>{f.real}</td><td>{f.ok ? '✓' : '✗'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

// Un transformable no cumple tal cual: se dice arriba, se enseña en grande lo que se obtiene y
// debajo de qué bulto sale y qué hay que hacer.
function TarjetaTransformable({ item, b, t, onClick, comparando, onComparar }) {
  const r = item.resultado
  return (
    <div className={`tarjeta transformable ${comparando ? 'comparando' : ''}`}>
      <button type="button" className="tarjeta-cuerpo" onClick={onClick}>
        <div className="tarjeta-cabeza">
          <span className="tarjeta-id">{item.id}</span>
          <span className="tarjeta-tipo">{ETIQUETAS.transformable}</span>
        </div>
        <div className="tarjeta-requiere">Requiere transformación</div>
        <div className="tarjeta-paso tarjeta-obtienes"><span>Obtienes</span>{b.grado} {r.acabado ?? b.acabado} · {t.despues}</div>
        <div className="tarjeta-paso"><span>Sale de</span>{t.antes}{b.ubicacion ? ` · ${b.ubicacion}` : ''}</div>
        <div className="tarjeta-paso"><span>Hay que</span>{t.acciones}{t.merma ? ` · ${t.merma}` : ''}
          {item.num_operaciones > 1 && ` · ${item.num_operaciones} operaciones`}</div>
        <div className="tarjeta-origen">Fuente: {ORIGEN.transformable} · ver de dónde sale</div>
      </button>
      {onComparar && (
        <label className="tarjeta-comparar">
          <input type="checkbox" checked={comparando} onChange={onComparar} /> Comparar
        </label>
      )}
    </div>
  )
}

function Fuentes({ tipo, item, bulto }) {
  const fichas = fichasDelGrado(bulto.grado ?? bulto.aisi, bulto.euronorma)
  return (
    <div className="fuentes">
      <h3>De dónde sale cada dato</h3>
      <ul>
        <li><b>Bulto {item.id}</b>: registro real del inventario de AcerIA (base de datos del backend). Medidas, peso y estado tal cual están guardados.</li>
        {tipo === 'transformable' && (
          <li><b>Acciones{item.merma_kg != null ? ' y merma' : ''}</b>: las calcula el motor de reglas a partir del fichero de reglas de transformación de AcerIA, no el asistente.
            {item.merma_estimada && ' La merma es una estimación.'}</li>
        )}
        {fichas.length > 0 && (
          <li><b>Referencias AcerIA del grado {gradoBulto(bulto)}</b> · {fichas.map((f, i) => (
            <span key={f.mat}>{i > 0 && ', '}{urlFicha(f.mat) && tienePdf(f.mat)
              ? <a href={urlFicha(f.mat)} target="_blank" rel="noopener noreferrer">{f.mat}</a>
              : f.mat} (EN {f.en})</span>
          ))}</li>
        )}
        <li><b>Texto de la respuesta</b>: lo redacta el asistente solo con estos datos; si añadiera algo que no está aquí, se sustituye por una plantilla.</li>
      </ul>
    </div>
  )
}

// Ficha técnica en PDF del grado del bulto, a la derecha del detalle: estrecha y plegable.
// Un bulto con doble certificado (304L/304) puede tener varias fichas: se eligen con pestañas.
function PanelFicha({ fichas }) {
  const [abierto, setAbierto] = useState(true)
  const [activa, setActiva] = useState(0)
  if (!fichas.length) return null
  const ficha = fichas[Math.min(activa, fichas.length - 1)]
  const url = urlFicha(ficha.mat)
  const parar = e => e.stopPropagation()             // un clic en el panel no cierra el detalle
  if (!abierto) {
    return (
      <button type="button" className="ficha-plegada" onClick={e => { parar(e); setAbierto(true) }}
        title="Ver la ficha técnica">‹ Ficha {ficha.mat}</button>
    )
  }
  return (
    <aside className="ficha-panel" onClick={parar} aria-label={`Ficha técnica ${ficha.mat}`}>
      <div className="ficha-cabeza">
        <div className="ficha-pestanas" role="tablist">
          {fichas.map((f, i) => (
            <button key={f.mat} type="button" role="tab" aria-selected={f.mat === ficha.mat}
              onClick={() => setActiva(i)} title={`EN ${f.en}`}>{f.mat}</button>
          ))}
        </div>
        {url && <a href={url} target="_blank" rel="noopener noreferrer" title="Abrir en otra pestaña">↗</a>}
        <button type="button" className="cerrar" onClick={() => setAbierto(false)} aria-label="Plegar la ficha">›</button>
      </div>
      {url
        ? <iframe key={ficha.mat} title={`Ficha técnica ${ficha.mat}`} src={`${url}#view=FitH&navpanes=0`} />
        : <p className="tenue">Las fichas técnicas necesitan conexión con el backend.</p>}
    </aside>
  )
}

export function Detalle({ item: { tipo, item }, esp, onCerrar }) {
  useEscape(onCerrar)
  const antes = datosBulto(tipo, item)
  const despues = tipo === 'transformable' ? item.resultado : null
  const fichas = fichasDelGrado(antes.grado ?? antes.aisi, antes.euronorma).filter(f => tienePdf(f.mat))
  return (
    <div className="modal-fondo con-ficha" onClick={onCerrar}>
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
                <td>{valorBulto(antes, k) ?? '—'}</td>
                {despues && <td>{valorBulto(despues, k) ?? '—'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        {tipo === 'transformable' && (
          <div className="modal-acciones">
            <h3>Acciones</h3>
            <ol>{acciones(item).map((a, i) => <li key={i}>{a}</li>)}</ol>
            {item.merma_kg != null && (
              <p>Merma estimada: <b>{num(item.merma_kg)} kg</b>{item.merma_pct != null && <> ({num(item.merma_pct)} %)</>}</p>
            )}
          </div>
        )}
        <Coincidencias esp={esp} bulto={despues ? { ...antes, ...despues } : antes} />
        <Fuentes tipo={tipo} item={item} bulto={antes} />
      </div>
      <PanelFicha fichas={fichas} />
    </div>
  )
}

const FILAS_COMPARAR = [
  ['Tipo', (t) => ETIQUETAS[t.tipo]],
  ...FILAS.slice(0, 8).map(([k, etiqueta]) => [etiqueta, (t) => {
    const b = datosBulto(t.tipo, t.item)
    const antes = valorBulto(b, k)
    const d = t.tipo === 'transformable' && t.item.resultado ? valorBulto(t.item.resultado, k) : undefined
    return d != null && d !== antes ? `${antes ?? '—'} → ${d}` : antes
  }]),
  ['Ubicación', (t) => datosBulto(t.tipo, t.item).ubicacion],
  ['Acciones', (t) => acciones(t.item).join(' · ') || 'Ninguna'],
  ['Operaciones', (t) => t.item.num_operaciones ?? (t.tipo === 'exacto' ? 0 : t.item.acciones?.length)],
  ['Merma', (t) => (t.item.merma_kg != null ? `${num(t.item.merma_kg)} kg${t.item.merma_pct != null ? ` (${num(t.item.merma_pct)} %)` : ''}` : t.tipo === 'exacto' ? '0 kg' : null)],
]

export function Comparador({ seleccion, onQuitar, onCerrar }) {
  useEscape(onCerrar)
  return (
    <div className="modal-fondo" onClick={onCerrar}>
      <div className="modal modal-ancho" onClick={e => e.stopPropagation()} role="dialog" aria-label="Comparar propuestas">
        <div className="modal-cabeza">
          <h2>Comparar propuestas</h2>
          <button className="cerrar" onClick={onCerrar} aria-label="Cerrar">×</button>
        </div>
        <table className="tabla-comparar">
          <thead>
            <tr><th />{seleccion.map(t => (
              <th key={t.item.id} className={t.tipo}>
                {t.item.id} <button className="quitar" onClick={() => onQuitar(t)} aria-label={`Quitar ${t.item.id}`}>×</button>
              </th>
            ))}</tr>
          </thead>
          <tbody>
            {FILAS_COMPARAR.map(([etiqueta, valor]) => {
              const vs = seleccion.map(valor)
              if (vs.every(v => v == null)) return null
              const distintos = new Set(vs.map(String)).size > 1
              return (
                <tr key={etiqueta} className={distintos ? 'cambia' : ''}>
                  <th>{etiqueta}</th>
                  {vs.map((v, i) => <td key={i}>{v ?? '—'}</td>)}
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="tenue">Las filas resaltadas son las que distinguen las propuestas.</p>
      </div>
    </div>
  )
}
