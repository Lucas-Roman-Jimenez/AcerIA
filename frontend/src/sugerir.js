// Erratas de usuarios no técnicos: «bbbobina» → «bobina», «brilante» → «brillante».
// Solo propone palabras del vocabulario de la aplicación; el valor válido lo sigue decidiendo el backend.
import glosario from '../../datos/glosario.json'
import fichas from './fichas_aceria.json'

const BASE = [
  // formatos y sinónimos (previa.js)
  'chapa', 'lamina', 'plancha', 'placa', 'hoja', 'bobina', 'rollo', 'fleje', 'tira', 'banda',
  // acabados coloquiales
  'brillante', 'mate', 'pulido', 'satinado', 'caliente', 'frio', 'laminado', 'decapado', 'recocido',
  // medidas y cantidades
  'espesor', 'grosor', 'galga', 'ancho', 'anchura', 'largo', 'longitud', 'medida', 'medidas',
  'milimetros', 'metros', 'kilos', 'toneladas', 'bultos',
  // material
  'acero', 'inoxidable', 'inox', 'austenitico', 'ferritico', 'martensitico', 'duplex', 'acabado', 'formato', 'grado',
  // preguntas por lo que hay («¿qué espesores tenéis de bobina?»)
  'tipo', 'tipos', 'metal', 'metales', 'aceros', 'material', 'materiales', 'grados', 'calidad', 'calidades', 'aleacion', 'aleaciones',
  'espesores', 'grosores', 'galgas', 'calibre', 'calibres', 'anchos', 'anchuras', 'tamano', 'tamanos', 'dimensiones', 'acabados',
  'formatos', 'chapas', 'bobinas', 'flejes', 'laminas', 'planchas', 'rollos', 'disponible', 'disponibles', 'tienes', 'teneis',
  'tenemos', 'tienen', 'existen', 'quedan', 'cuales', 'cuantos', 'cuantas', 'ensename', 'muestrame', 'dime', 'lista', 'listado',
  'stock', 'catalogo', 'opciones',
  // preguntas por el uso («¿cuál es mejor para hornos?»)
  'mejor', 'recomiendas', 'recomienda', 'recomiendame', 'recomendarme', 'recomendar', 'aconsejame', 'sugiereme', 'sugieres',
  'austenitico', 'austeniticos', 'ferriticos', 'martensiticos', 'inoxidables', 'familia', 'recomendarias', 'aconsejas', 'adecuado', 'indicado', 'conviene', 'sirve', 'aguanta',
  'resiste', 'resistente', 'oxide', 'oxida', 'corrosion', 'soldar', 'soldadura', 'doblar', 'calor', 'temperatura', 'temperaturas',
  'cocina', 'cuchillos', 'cubiertos', 'ambiente', 'marino', 'quimica', 'alimentaria', 'escape', 'tubos', 'tuberias', 'tanques',
  'decoracion', 'electrodomesticos', 'industria', 'industrial', 'exterior', 'interior',
  // quitar datos o borrar la consulta
  'quita', 'quitar', 'quitame', 'borra', 'borrar', 'borrame', 'elimina', 'eliminar', 'eliminame', 'descarta', 'olvida',
  'olvidalo', 'consulta', 'busqueda', 'peticion', 'conversacion', 'empezar', 'empieza', 'reinicia', 'reiniciar', 'cancela',
  'cancelar', 'nuevo', 'nueva', 'cero', 'principio', 'inicio', 'todo',
]
const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
const VOCABULARIO = new Set([
  ...BASE,
  ...glosario.terminos.flatMap(t => normaliza(t.termino).split(/[^a-z]+/)).filter(w => w.length >= 4),
  ...fichas.flatMap(f => f.aplicaciones.flatMap(a => normaliza(a).split(/[^a-z]+/))).filter(w => w.length >= 5),
])
// Palabras corrientes que se parecen a un término y no son erratas.
const CORRIENTES = new Set(['hola', 'para', 'como', 'esta', 'este', 'quiero', 'necesito', 'tengo', 'tiene', 'cliente',
  'hoy', 'gracias', 'algo', 'ahora', 'otra', 'otro', 'otras', 'otros', 'mismo', 'misma', 'cual', 'donde', 'cuanto',
  'mano', 'mesa', 'casa', 'cosa', 'nada', 'todo', 'toda', 'bien', 'malo', 'mala', 'alto', 'alta', 'baja', 'bajo',
  'grande', 'buena', 'bueno', 'vale', 'venta', 'precio', 'plazo', 'largos', 'tengo', 'tener', 'saber', 'todos', 'todas', 'sobre', 'entre',
  'media', 'medio', 'dame', 'deme', 'mira', 'pero', 'nueve', 'larga', 'corta', 'corto', 'ancha', 'coste', 'color', 'colores',
  'pedido', 'pedidos', 'clientes', 'viernes', 'esperar', 'espera', 'playa', 'valga', 'grandes', 'cuanta'])

function distancia(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i])
  for (let j = 1; j <= b.length; j++) d[0][j] = j
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1)
    }
  }
  return d[a.length][b.length]
}

const sinRepetidas = w => w.replace(/(.)\1+/g, '$1')

// Singular o plural de una palabra conocida («kilo», «hornos», «hojas»): no es una errata.
const conocida = w => (/ss$/.test(w) ? [w] : [w, w.replace(/es$/, ''), w.replace(/s$/, ''), `${w}s`, `${w}es`])
  .some(x => VOCABULARIO.has(x) || CORRIENTES.has(x))
// Dos letras intercambiadas («mjeor», «brora»).
const intercambio = (a, b) => a.length === b.length
  && [...a].filter((c, i) => c !== b[i]).length === 2 && [...a].sort().join('') === [...b].sort().join('')

function parecida(palabra) {
  const w = normaliza(palabra)
  if (w.length < 4 || /\d/.test(w) || conocida(w)) return null
  // «bbbobina», «chappa»: letras repetidas de más.
  const colapsada = sinRepetidas(w)
  const porRepetidas = [...VOCABULARIO].find(v => sinRepetidas(v) === colapsada)
  if (porRepetidas) return porRepetidas
  // Palabras cortas: cambiar una letra suele dar otra palabra real («dame»/«dime», «pero»/«cero», «color»/«calor»),
  // así que solo se corrige si falta una letra («chpa») o hay dos intercambiadas («mjeor»).
  const maximo = w.length >= 9 ? 2 : 1
  let mejor = null
  for (const v of VOCABULARIO) {
    if (Math.abs(v.length - w.length) > maximo) continue
    const d = distancia(w, v)
    if (d > maximo) continue
    if (w.length <= 5 && !(v.length === w.length + 1 || intercambio(w, v))) continue
    if (!mejor || d < mejor.d) mejor = { v, d }
  }
  return mejor?.v ?? null
}

// Devuelve { corregido, cambios: [[escrita, propuesta]] } o null si no hay erratas.
export function sugerirCorreccion(texto) {
  const cambios = []
  const corregido = texto.replace(/[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+/g, palabra => {
    const p = parecida(palabra)
    if (!p) return palabra
    cambios.push([palabra, p])
    return p
  })
  return cambios.length ? { corregido, cambios } : null
}
