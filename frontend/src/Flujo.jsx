import { useState } from 'react'
import { consultarValores, buscarStock } from './api.js'
import { Tarjeta } from './Tarjetas.jsx'

// Campos que el comercial puede dar, en el orden en que se dan por buenos.
export const CAMPOS = [
  ['grado', 'Grado'],
  ['formato', 'Formato'],
  ['acabado', 'Acabado'],
  ['espesor_mm', 'Espesor', 'mm'],
  ['ancho_mm', 'Ancho', 'mm'],
]
const MAX_RESULTADOS = 10
const num = v => String(v).replace('.', ',')
const etiqueta = k => CAMPOS.find(c => c[0] === k)?.[1] ?? k
const unidad = k => CAMPOS.find(c => c[0] === k)?.[2]
const conUnidad = (k, v) => `${num(v)}${unidad(k) ? ' ' + unidad(k) : ''}`
// El inventario trae grados dobles («304L/304») que el intérprete no reconoce: se envía una de sus partes
// (la preferida si está, si no la primera). El buscador acepta cualquier bulto que tenga esa designación.
export function gradoParaBackend(valor, preferido) {
  const partes = String(valor).split('/').map(p => p.trim()).filter(Boolean)
  if (partes.length < 2) return valor
  return partes.find(p => p.toUpperCase() === String(preferido ?? '').toUpperCase()) ?? partes[0]
}
export const fraseCambio = (k, v) => `El ${etiqueta(k).toLowerCase()} es ${k === 'grado' ? gradoParaBackend(v) : conUnidad(k, v)}`

const hayStock = async filtros => (await consultarValores('grado', filtros)).total_bultos > 0

// Qué datos de la petición son correctos (hay stock con ellos) y cuáles fallan.
// Todo sale del stock real: /stock/valores y /buscar. El frontend no decide qué existe.
export async function analizar(r) {
  const esp = r.especificacion
  const dados = CAMPOS.map(c => c[0]).filter(k => esp[k] != null)
  const correctos = {}
  const fallan = []
  for (const k of dados) {
    if (await hayStock({ ...correctos, [k]: esp[k] })) correctos[k] = esp[k]
    else fallan.push(k)
  }
  const avisos = esp.avisos ?? []
  const conOpciones = Object.keys(esp.opciones ?? {}).length > 0
  const nada = Object.keys(correctos).length === 0 && !conOpciones

  // Todo lo que ha escrito es incorrecto: se vuelve a empezar.
  if (nada && (fallan.length || avisos.length)) return { estado: 'todo_mal', fallan, avisos, esp }
  // No ha dado ningún dato de material (saludo, pregunta general…): se deja la conversación como está.
  if (nada) return null

  const opcionesFallo = await Promise.all(fallan.map(async k => ({
    campo: k, pedido: esp[k], valores: (await consultarValores(k, correctos)).valores,
  })))

  let lista
  if (!fallan.length && (r.exactos?.length || r.transformables?.length)) {
    lista = [
      ...(r.exactos ?? []).map(item => ({ tipo: 'exacto', item })),
      ...(r.exactos?.length ? [] : (r.transformables ?? []).map(item => ({ tipo: 'transformable', item }))),
    ]
  } else {
    const b = await buscarStock({ ...correctos, opciones: esp.opciones ?? {} })
    lista = (b.exactos ?? []).map(item => ({ tipo: fallan.length ? 'alternativa' : 'exacto', item }))
  }

  const faltan = CAMPOS.map(c => c[0]).filter(k => esp[k] == null && !esp.indiferentes?.includes(k))
  const completo = faltan.length === 0
  let estado
  if (fallan.length || avisos.length) estado = 'fallos'
  else if (lista.length > MAX_RESULTADOS && !completo) estado = 'criba'
  else if (!lista.length) estado = 'sin_stock'
  else estado = completo ? 'encontrado' : 'parcial'

  // Para cribar: valores en stock de los campos que aún no ha dicho, con lo que ya es correcto.
  const cribar = estado === 'criba' || (estado === 'fallos' && lista.length > MAX_RESULTADOS)
    ? await Promise.all(faltan.filter(k => !esp.opciones?.[k]).slice(0, 3).map(async k => ({
      campo: k, valores: (await consultarValores(k, correctos)).valores,
    })))
    : []

  return { estado, correctos, fallan: opcionesFallo, avisos, lista, total: lista.length, cribar, esp }
}

export function textoAnalisis(a) {
  const n = a.total
  switch (a.estado) {
    case 'encontrado': return n === 1 ? 'Tengo justo lo que pides. Añádelo al carrito o cancela para empezar de nuevo.'
      : `Tengo ${n} bultos que cumplen todo lo que pides. Elige cuál añadir al carrito o cancela para empezar de nuevo.`
    case 'parcial': return `Con lo que me has dicho hay ${n} material${n === 1 ? '' : 'es'} en stock. Elige uno o dame más datos para afinar.`
    case 'criba': return `Con lo que me has dicho hay ${n} materiales en stock: son demasiados. Dime más datos para cribar.`
    case 'sin_stock': return 'No hay stock con esa combinación. Prueba a cambiar algún dato.'
    case 'fallos': return n
      ? `Lo que pides no está en stock tal cual. Te enseño ${Math.min(n, MAX_RESULTADOS)} opciones que cumplen el resto de requisitos; abajo puedes cambiar lo que falla.`
      : 'Lo que pides no está en stock tal cual. Abajo puedes cambiar lo que falla por algo que sí hay.'
    default: return ''
  }
}

function ValoresStock({ campo, valores, onElegir, deshabilitado }) {
  if (!valores.length) return <span className="tenue">No hay stock con el resto de datos.</span>
  return (
    <div className="editor-lista">
      {valores.map(v => (
        <button key={v.valor} type="button" className="chip-stock" disabled={deshabilitado}
          onClick={() => onElegir(fraseCambio(campo, v.valor))}
          title={`${v.bultos} bultos · ${num(v.toneladas)} t`}>
          {conUnidad(campo, v.valor)} <small>{v.bultos}</small>
        </button>
      ))}
    </div>
  )
}

export function Flujo({ analisis: a, activo, onEnviar, onCancelar, carrito, onCarrito, onAbrir, deshabilitado }) {
  const [abierto, setAbierto] = useState(null)
  const enCarrito = id => carrito.some(c => c.item.id === id)
  const visibles = a.estado === 'criba' ? [] : a.lista.slice(0, MAX_RESULTADOS)
  const filas = a.estado === 'fallos' ? a.fallan : a.cribar.map(c => ({ ...c, pedido: null }))

  return (
    <div className="flujo">
      {Object.keys(a.correctos).length > 0 && (
        <div className="flujo-datos">
          {Object.entries(a.correctos).map(([k, v]) => (
            <span key={k} className="flujo-dato ok">{etiqueta(k)}: {conUnidad(k, v)} ✓</span>
          ))}
          {a.fallan.map(f => (
            <span key={f.campo} className="flujo-dato mal">{etiqueta(f.campo)}: {conUnidad(f.campo, f.pedido)} ✗ sin stock</span>
          ))}
        </div>
      )}
      {a.avisos.length > 0 && <ul className="avisos">{a.avisos.map((t, i) => <li key={i}>{t}</li>)}</ul>}

      {visibles.length > 0 && (
        <div className="tarjetas">
          {visibles.map(({ tipo, item }) => (
            <div key={`${tipo}-${item.id}`} className="flujo-tarjeta">
              <Tarjeta tipo={tipo} item={item} onClick={() => onAbrir({ tipo, item })} />
              <button type="button" className={`carrito-boton ${enCarrito(item.id) ? 'dentro' : ''}`}
                onClick={() => onCarrito(tipo, item)}>
                {enCarrito(item.id) ? '✓ En el carrito' : '+ Añadir al carrito'}
              </button>
            </div>
          ))}
        </div>
      )}

      {activo && filas.length > 0 && (
        <div className="cercanos">
          <div className="cercanos-titulo">
            {a.estado === 'fallos' ? 'Pulsa lo que falla y elige un valor que sí hay en stock:' : 'Elige un dato más para cribar:'}
          </div>
          <div className="cercanos-fila">
            {filas.map(f => (
              <button key={f.campo} type="button" className={`opcion ${abierto === f.campo ? 'activa' : ''}`}
                disabled={deshabilitado} onClick={() => setAbierto(abierto === f.campo ? null : f.campo)}>
                {etiqueta(f.campo)}{f.pedido != null ? ` (${conUnidad(f.campo, f.pedido)})` : ''} ⌄
              </button>
            ))}
          </div>
          {abierto && (
            <ValoresStock campo={abierto} valores={filas.find(f => f.campo === abierto)?.valores ?? []}
              onElegir={onEnviar} deshabilitado={deshabilitado} />
          )}
        </div>
      )}

      {activo && (
        <div className="flujo-acciones">
          <span className="tenue">También puedes escribir más datos o la petición entera abajo.</span>
        </div>
      )}
    </div>
  )
}

export function Carrito({ carrito, onQuitar, onVaciar, onCerrar, onVender }) {
  const [vendiendo, setVendiendo] = useState(false)
  const [mensaje, setMensaje] = useState(null)   // {tipo: 'ok' | 'error', texto}

  async function confirmarVenta() {
    setVendiendo(true)
    setMensaje(null)
    try {
      const r = await onVender(carrito.map(c => c.item.id))
      setMensaje({ tipo: 'ok', texto: `Vendidos ${r.vendidos.length} bultos. Ya no salen en el stock y aparecen en el reporte semanal.` })
    } catch (e) {
      setMensaje({ tipo: 'error', texto: e.message })
    } finally {
      setVendiendo(false)
    }
  }

  return (
    <div className="modal-fondo" onClick={onCerrar}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-cabeza">
          <h2>Carrito</h2>
          <button className="demo-salir" onClick={onCerrar}>Cerrar</button>
        </div>
        {mensaje && <p className={mensaje.tipo === 'error' ? 'carrito-error' : 'carrito-ok'}>{mensaje.texto}</p>}
        {carrito.length === 0 ? (!mensaje && <p className="tenue">Aún no has añadido nada.</p>) : (
          <>
            <ul className="carrito-lista">
              {carrito.map(({ tipo, item }) => {
                const b = item.origen ?? item
                return (
                  <li key={item.id}>
                    <span><b>{item.id}</b> · {b.grado} {b.acabado} · {b.formato} · {[b.espesor_mm, b.ancho_mm, b.largo_mm].filter(v => v != null).map(num).join(' × ')} mm
                      {tipo === 'transformable' && ' (transformable)'}</span>
                    <button className="demo-salir" onClick={() => onQuitar(item.id)}>Quitar</button>
                  </li>
                )
              })}
            </ul>
            <div className="carrito-pie">
              <button className="demo-salir" onClick={onVaciar} disabled={vendiendo}>Vaciar carrito</button>
              {onVender && (
                <button className="carrito-boton" onClick={confirmarVenta} disabled={vendiendo}>
                  {vendiendo ? 'Vendiendo…' : `Confirmar venta (${carrito.length})`}
                </button>
              )}
            </div>
            <p className="tenue">Simulación para la demo: no se envía nada a los sistemas de AcerIA.</p>
          </>
        )}
      </div>
    </div>
  )
}
