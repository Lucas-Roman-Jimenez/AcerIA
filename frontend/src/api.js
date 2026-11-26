import { chatFalso, resumenFalso, valoresFalsos, buscarFalso } from './mock.js'

// Sin VITE_API_URL se usa la API falsa (src/mock.js).
const API = import.meta.env.VITE_API_URL

export async function enviarMensaje(conversacionId, texto) {
  if (!API) return chatFalso(conversacionId, texto)
  const r = await fetch(`${API}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversacion_id: conversacionId, texto }),
  })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

export async function consultarValores(campo, filtros) {
  if (!API) return valoresFalsos(campo, filtros)
  const q = new URLSearchParams({ campo, ...filtros })
  const r = await fetch(`${API}/stock/valores?${q}`)
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

export async function resumenStock() {
  if (!API) return resumenFalso()
  const r = await fetch(`${API}/stock/resumen`)
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

// Bultos que cumplen una especificación parcial (solo los campos que no son null).
export async function buscarStock(esp) {
  if (!API) return buscarFalso(esp)
  const r = await fetch(`${API}/buscar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(esp),
  })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}`)
  return r.json()
}

// ---------- Carrito con reservas (tarea 4): dos comerciales no pueden coger el mismo bulto ----------
// Cada pestaña tiene un ID de carrito aleatorio (128 bits) que va en la cabecera X-Carrito; no hay login.
// Se guarda en sessionStorage para que, al recargar, se puedan soltar las
// reservas de esta pestaña: el carrito vive en la memoria de React y se pierde al recargar.
function idCarrito() {
  const nuevo = () => `k-${Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')}`
  try {
    const guardado = sessionStorage.getItem('aceria-carrito')
    if (guardado) return guardado
    const id = nuevo()
    sessionStorage.setItem('aceria-carrito', id)
    return id
  } catch {
    return nuevo()                 // sin sessionStorage (modo privado estricto): ID solo para esta carga
  }
}

const ID_CARRITO = idCarrito()
const conCarrito = (extra = {}) => ({ 'X-Carrito': ID_CARRITO, ...extra })

// Al cargar la página el carrito está vacío: se sueltan las reservas que esta pestaña dejó al recargar.
// Las reservas nuevas esperan a que termine, para que este borrado no se lleve una recién hecha.
const inicioCarrito = API
  ? fetch(`${API}/reservas`, { method: 'DELETE', headers: conCarrito() }).catch(() => {})
  : Promise.resolve()

// Al añadir al carrito (o antes de vender, para renovar la caducidad). Todos o ninguno.
export async function reservarBultos(ids) {
  if (!API) return { reservas: ids.map(bulto_id => ({ bulto_id })) }   // API falsa: no hay reservas
  await inicioCarrito
  const r = await fetch(`${API}/reservas`, {
    method: 'POST',
    headers: conCarrito({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ bultos: ids }),
  })
  const datos = await r.json().catch(() => ({}))
  if (r.status === 409) {
    const ocupados = datos.detail?.no_disponibles ?? ids
    throw new Error(`${ocupados.length === 1 ? `El bulto ${ocupados[0]}` : `Los bultos ${ocupados.join(', ')}`} `
      + 'lo tiene reservado otro comercial o ya no está disponible.')
  }
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return datos
}

// Al quitar un bulto del carrito vuelve a estar disponible para los demás. Si falla, la reserva caduca sola.
export async function liberarBulto(id) {
  if (!API) return
  await inicioCarrito
  await fetch(`${API}/reservas/${encodeURIComponent(id)}`, { method: 'DELETE', headers: conCarrito() }).catch(() => {})
}

export async function vaciarReservas() {
  if (!API) return
  await inicioCarrito
  await fetch(`${API}/reservas`, { method: 'DELETE', headers: conCarrito() }).catch(() => {})
}

// Venta simulada del carrito: los bultos pasan a «vendido» y aparecen en el reporte semanal.
// Solo se vende lo reservado por este carrito; antes se renuevan las reservas por si han caducado.
export async function venderCarrito(ids) {
  if (!API) throw new Error('La venta necesita conexión con el backend.')
  await reservarBultos(ids)
  const r = await fetch(`${API}/compras`, {
    method: 'POST',
    headers: conCarrito({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ bultos: ids }),
  })
  const datos = await r.json().catch(() => ({}))
  if (r.status === 409) {
    throw new Error(`Ya no están disponibles: ${datos.detail?.no_disponibles?.join(', ')}. No se ha vendido nada.`)
  }
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return datos
}

async function cargarReporte(ruta, signal) {
  if (!API) throw new Error('El reporte necesita conexión con el backend.')
  let r
  try {
    r = await fetch(`${API}/reportes/${ruta}`, { signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('No se puede conectar con el servidor. Comprueba que el backend está en marcha.')
  }
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return r.json()
}

export const cargarReporteSemanal = signal => cargarReporte('compras/semanal', signal)
export const cargarReporteDiarioInventario = signal => cargarReporte('inventario/diario', signal)
export const cargarReposicion = signal => cargarReporte('reposicion', signal)

// Tendencias de compras por semana y formato (Lucas): unidad 'kg', 'bultos' o 'piezas'.
export async function cargarTendencias(semanas, unidad, signal) {
  if (!API) throw new Error('Las tendencias necesitan conexión con el backend.')
  const consulta = new URLSearchParams({ semanas: String(semanas), unidad })
  const r = await fetch(`${API}/reportes/compras/tendencias?${consulta}`, { signal })
  if (!r.ok) throw new Error(`El servidor respondió ${r.status}.`)
  return r.json()
}
