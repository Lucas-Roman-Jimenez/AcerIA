// Órdenes escritas para quitar datos seleccionados («quita el espesor», «bórrame el 2B», «elimina la bobina»)
// o para borrar la consulta entera («borra la consulta», «empezar de nuevo», «olvídalo»).
// Solo se quita un dato si de verdad está seleccionado.

const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const NOMBRES = {
  grado: 'grado', espesor_mm: 'espesor', acabado: 'acabado', formato: 'formato', ancho_mm: 'ancho', largo_mm: 'largo',
}
const SINONIMOS = {
  grado: /\b(grados?|tipos?|aceros?|materiale?s?|metale?s?|calidad(es)?|aleacion(es)?)\b/,
  espesor_mm: /\b(espesor(es)?|grosor(es)?|galgas?|calibres?|gruesos?)\b/,
  acabado: /\b(acabados?|terminacion(es)?|superficies?|brillos?)\b/,
  formato: /\b(formatos?|presentacion(es)?)\b/,
  ancho_mm: /\b(anchos?|anchuras?)\b/,
  largo_mm: /\b(largos?|longitud(es)?)\b/,
}

const QUITAR = /\b(quita\w*|quite\w*|quitar\w*|borra\w*|borre\w*|elimina\w*|elimine\w*|suprim\w*|descarta\w*|desmarca\w*|deselecciona\w*|saca\w*|olvida\w*|retira\w*|limpia\w*|anula\w*|fuera)\b/
const ENTERA = /\b(consultas?|chat|conversacion(es)?|busquedas?|peticion(es)?|pedidos?|todo|todos los datos|todas? las? caracteristicas?|filtros|seleccion)\b/
const EMPEZAR = /\b(empez\w*|empiez\w*|comenz\w*|comienz\w*|reinici\w*|resetea\w*|reset|volver al (inicio|principio)|vuelve al (inicio|principio)|ir al inicio|de nuevo|de cero|desde cero|otra vez desde)\b/
const OLVIDALO = /^\s*(olvidalo|olvida(lo)? todo|dejalo|cancela(r)?( todo)?|reset|reinicia(r)?|nueva consulta|empezar de nuevo|empecemos de nuevo|volver a empezar)\s*[.!]*\s*$/

// ¿Pide borrar la consulta entera y volver a la página principal?
export function pideBorrarConsulta(texto) {
  const t = normaliza(texto)
  if (OLVIDALO.test(t)) return true
  if (QUITAR.test(t) && ENTERA.test(t) && !Object.values(SINONIMOS).some(re => re.test(t.replace(ENTERA, '')))) return true
  return /\b(cancela\w*|nueva|otra)\b/.test(t) && /\b(consulta|busqueda|peticion|chat)\b/.test(t)
    || (/\b(quiero|vamos a|podemos|puedo)\b/.test(t) && EMPEZAR.test(t))
    || EMPEZAR.test(t) && t.split(/\s+/).length <= 4
}

// ¿Nombra el valor seleccionado? «quita el 2B», «borra los 2 mm», «elimina la bobina», «sin el 304».
function nombraValor(t, k, v) {
  if (typeof v === 'number') {
    // «2», «2 mm», «2mm», «2,0 mm»; pero no el «2» de «2B».
    const n = [...new Set([String(v), v.toFixed(1), String(v).replace(/\.0$/, '')])].map(x => x.replace('.', '[.,]'))
    return new RegExp(`(?<![\\w.,])(${n.join('|')})(\\s*mm\\b|(?![\\w.,]))`).test(t)
  }
  return String(v).split('/').map(p => normaliza(p.trim())).filter(Boolean)
    .some(p => new RegExp(`(?<![\\w])${p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}s?(?![\\w])`).test(t))
}

// Devuelve { quitar: [campos seleccionados que se quitan], noSeleccionados: [campos pedidos que no están elegidos] } o null.
export function pideQuitar(texto, esp) {
  const t = normaliza(texto)
  if (!QUITAR.test(t)) return null
  const quitar = []
  const noSeleccionados = []
  for (const k of Object.keys(NOMBRES)) {
    const seleccionado = esp?.[k] != null
    if (seleccionado && (SINONIMOS[k].test(t) || nombraValor(t, k, esp[k]))) quitar.push(k)
    else if (!seleccionado && SINONIMOS[k].test(t)) noSeleccionados.push(k)
  }
  return quitar.length || noSeleccionados.length ? { quitar, noSeleccionados } : null
}

const enumerar = xs => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} y ${xs.at(-1)}` : xs[0])

// Lo que se ve en el chat («Quita el espesor») y lo que entiende el backend («…, me da igual» → indiferentes).
export function frasesQuitar(campos) {
  const visible = `Quita ${enumerar(campos.map(k => `el ${NOMBRES[k]}`))}`
  return { visible, backend: `${visible}, me da igual` }
}

export function textoNoSeleccionado(campos) {
  const lista = enumerar(campos.map(k => NOMBRES[k]))
  return `No tienes ${campos.length > 1 ? 'seleccionados' : 'seleccionado ningún'} ${lista}, así que no hay nada que quitar.`
}
