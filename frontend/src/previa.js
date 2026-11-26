// Lectura orientativa del texto contra el catálogo. La interpretación válida es siempre la del backend.
import fichas from './fichas_aceria.json'
import glosario from '../../datos/glosario.json'

const GLOSARIO = { mate: ['2B'], 'en caliente': ['1D'] }
const ALIAS_ACABADO = Object.fromEntries(glosario.terminos
  .filter(t => t.campo === 'acabado' && t.valores.length === 1)
  .map(t => [t.termino.toLowerCase(), t.valores[0]]))
const FORMATOS = {
  chapa: 'chapa|lamina|plancha|placa|hoja',
  bobina: 'bobina|rollo',
  fleje: 'fleje|tira|banda',
}
const FAMILIAS = { austenitico: 'austenítico', duplex: 'dúplex', ferritico: 'ferrítico', martensitico: 'martensítico' }

const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/mat\s*/g, 'mat ')
const nombreGrado = f => f.aisi?.replace(' DDQ', '') ?? f.mat
const escapa = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const unicos = xs => [...new Set(xs)]
const numero = s => parseFloat(s.replace(',', '.'))

// Cada designación del catálogo (AISI, EN, MAT) apunta a su grado; las más largas primero.
const DESIGNACIONES = fichas.flatMap(f => [f.aisi, f.aisi?.replace(' DDQ', ''), f.en, f.mat]
  .filter(Boolean).map(d => [normaliza(d), nombreGrado(f)]))
  .sort((a, b) => b[0].length - a[0].length)

const CONSULTAS = [
  ['espesor_mm', /\b(grosor|espesor|galga|calibre)(es|s)?\b|\bgruesos?\b/],
  ['ancho_mm', /\b(ancho|anchura|medida|tamano|dimension)(es|s)?\b/],
  ['acabado', /\b(acabado|terminacion|superficie|brillo)(es|s)?\b/],
  ['formato', /\b(formato|presentacion|forma)(es|s)?\b/],
  ['grado', /\b(tipo|grado|acero|calidad|metal|aleacion|material|inoxidable|referencia)(es|s)?\b/],
]
const PREGUNTA = /\b(que|cuales?|cuantos|cuantas|dime|dame|ensename|ensenadme|muestrame|mostrar|lista|listado|ver|saber|opciones|catalogo|informacion|info|disponibles?)\b/
const HAY = /\b(hay|habra|tienes|tiene|teneis|tenemos|tienen|existen|existe|disponibles?|quedan|queda|ofreceis|ofreces|vendeis|vendes|manejais|trabajais|stock|almacen|sirves)\b/
const PLURAL = /\b(grosores|espesores|galgas|calibres|anchos|anchuras|medidas|tamanos|dimensiones|acabados|terminaciones|superficies|formatos|presentaciones|tipos|grados|aceros|calidades|metales|aleaciones|materiales|referencias)\b/

// «¿Qué grosores hay de 304?», «tipos de metales», «espesores de bobina?», «dime los acabados que tenéis»…
// Solo si es una pregunta por lo que hay, no un pedido.
export function detectarConsulta(texto) {
  const t = normaliza(texto)
  const interrogativa = texto.includes('?') || texto.includes('¿') || PREGUNTA.test(t)
  const pregunta = (interrogativa && HAY.test(t))
    || (PLURAL.test(t) && (interrogativa || t.split(/\s+/).length <= 6))
  if (!pregunta) return null
  const campo = CONSULTAS.find(([, re]) => re.test(t))
  return campo ? { campo: campo[0] } : null
}

const VACIAS = new Set(['para', 'que', 'una', 'uno', 'unos', 'unas', 'con', 'del', 'los', 'las', 'por', 'como', 'esta', 'este',
  'estar', 'cerca', 'muy', 'mas', 'acero', 'inox', 'inoxidable', 'chapa', 'bobina', 'fleje', 'cliente', 'quiere', 'necesita',
  'necesito', 'recomiendas', 'recomienda', 'recomendarias', 'aconsejas', 'mejor', 'sirve', 'usar', 'uso', 'cual', 'cuales',
  'tipo', 'grado', 'material', 'hacer', 'valdria', 'vale', 'puedo', 'pongo', 'seria', 'donde', 'tiene', 'tener', 'algo'])
const raiz = w => w.slice(0, 5)
const palabrasSignificativas = s => normaliza(s).split(/[^a-z0-9]+/).filter(w => w.length >= 4 && !VACIAS.has(w))
const SALINO = /\b(mar|marino|marina|costa|costero|salino|salina|salada|salado|sal|salitre|playa|cloruro|cloruros)s?\b/

// Lo que dicen las fichas de cada grado: sus aplicaciones y cada frase de su descripción (propiedades).
const frasesDe = d => d.split(/(?<=\.)\s+/).map(x => x.trim().replace(/\.$/, '')).filter(x => x.length > 10)
const APLICACIONES = fichas.flatMap(f => [
  ...f.aplicaciones.map(a => ({ ficha: f, tipo: 'aplicacion', texto: a.replace(/\.$/, '') })),
  ...frasesDe(f.descripcion).map(d => ({ ficha: f, tipo: 'propiedad', texto: d })),
]).map(a => ({ ...a, raices: new Set(palabrasSignificativas(a.texto).map(raiz)) }))
const FRECUENCIA = {}
for (const a of APLICACIONES) for (const r of a.raices) FRECUENCIA[r] = (FRECUENCIA[r] ?? 0) + 1

// Palabras coloquiales → cómo lo dicen las fichas. Solo amplía la búsqueda: lo que se responde sale de las fichas.
const SINONIMOS = [
  [/\b(calor|caliente|calientes|temperatura|temperaturas|fuego|quemar|quema|llama)\b/, 'altas temperaturas hornos oxidacion'],
  [/\b(hornos?|horno)\b/, 'hornos'],
  [/\b(oxid\w*|herrumbre|corro\w*|picad\w*)\b/, 'corrosion'],
  [/\b(sold\w*)\b/, 'soldabilidad soldadura soldadas'],
  [/\b(doblar|dobla\w*|curvar|moldear|conformar|estampar|embuti\w*|deformar|dar forma)\b/, 'conformabilidad embuticion conformado formabilidad'],
  [/\b(cort\w*|cuchill\w*|navaja\w*|filo|tijeras?)\b/, 'herramientas corte cuchilleria'],
  [/\b(duro|dura|dureza|rayar|desgaste)\b/, 'dureza'],
  [/\b(fuerte|fuertes|robusto|estructura\w*|carga|cargas|aguant\w*|soport\w*)\b/, 'resistencia mecanica estructurales'],
  [/\b(cocina\w*|ollas?|sartene?s?|cazuelas?)\b/, 'menaje cocina'],
  [/\b(comida|alimento\w*|alimenticia|bebidas?)\b/, 'alimentaria agroalimentaria'],
  [/\b(quimic\w*|acido\w*)\b/, 'quimica'],
  [/\b(coches?|automovil\w*|vehiculos?|tubos de escape|escapes?)\b/, 'automovilisticos automocion escape'],
  [/\b(tuberias?|tubos?)\b/, 'tubos tuberias'],
  [/\b(decor\w*|bonito|estetic\w*|brillo)\b/, 'decorativos decoracion'],
  [/\b(frio extremo|criogeni\w*|congela\w*)\b/, 'criogenicas'],
  [/\b(electrodomesticos?|lavadoras?|neveras?)\b/, 'electrodomesticos lavadoras'],
  [/\b(depositos?|tanques?|cisternas?)\b/, 'tanques almacenamiento cisternas'],
  [/\b(cubiertos|tenedor\w*|cucharas?)\b/, 'cuberteria'],
]
const ampliar = t => [t, ...SINONIMOS.filter(([re]) => re.test(t)).map(([, extra]) => extra)].join(' ')

// «¿Qué acero para una cocina industrial?», «¿cuál me viene mejor para soldar?», «qué aguanta más el calor»…
// Pregunta por uso o por una característica, sin grado concreto.
const CONSEJO = /\b(recomienda\w*|aconseja\w*|sugier\w*|mejor|adecuado|indicado|apropiado|conviene|convendria|sirve|servir|serviria|valdria|vale|uso|utilizo|usaria|pongo|elijo|escojo)\b/
export function detectarUso(texto) {
  const t = normaliza(texto)
  const pregunta = texto.includes('?') || texto.includes('¿')
    || /\b(que|cual|cuales|dime|necesito|busco|quiero saber)\b/.test(t) || CONSEJO.test(t)
  const deUso = /\b(para|uso|aplicacion|va a (estar|ir|usarse)|en un|en una|en el|en la|expuest\w*|contra|frente)\b/.test(t)
    || /\b(resist\w*|aguant\w*|soport\w*|sold\w*|oxid\w*|corro\w*|dobl\w*|dur\w*|fuerte|duradero|barat\w*|car\w*|ligero|pesado|magnetic\w*|iman|conduc\w*)\b/.test(t)
  if (!pregunta || !deUso || interpretarTexto(texto).grado) return null
  // «¿Qué espesores hay para bobina?» es una pregunta por lo que hay, no por el uso.
  if (detectarConsulta(texto) && !CONSEJO.test(t)) return null
  return { texto }
}

// Propiedades de las que las fichas no dicen nada: se responde que lo consulte con un comercial.
const SIN_DATO_EN_FICHAS = /\b(precio|precios|barat\w*|car[oa]s?|cuesta|coste|economic\w*|conduc\w*|electricidad|magnetic\w*|iman\w*|pes[oa]s?|pesad\w*|ligero\w*|liviano\w*|pintar|pintura|color\w*|plazo\w*|entrega|garantia)\b/

// Grados que el catálogo indica para un uso, con la aplicación o el dato de la ficha que lo respalda.
export function recomendarPorUso(texto) {
  if (SIN_DATO_EN_FICHAS.test(normaliza(texto))) return { criterio: 'sin_dato', grados: [] }
  if (SALINO.test(normaliza(texto))) {
    const conLimite = fichas.filter(f => f.cloruros_max_ppm && f.aisi)
    const max = Math.max(...conLimite.map(f => f.cloruros_max_ppm))
    const mejores = conLimite.filter(f => f.cloruros_max_ppm === max)
    return {
      criterio: 'cloruros',
      grados: unicos(mejores.map(nombreGrado)).map(g => {
        const f = mejores.find(x => nombreGrado(x) === g)
        return { grado: g, ficha: f, motivo: `admite hasta ${f.cloruros_max_ppm} ppm de cloruros según su ficha` }
      }),
      comparacion: unicos(conLimite.filter(f => f.cloruros_max_ppm < max).map(f => `${nombreGrado(f)} (${f.cloruros_max_ppm} ppm)`)),
    }
  }
  const raices = unicos(palabrasSignificativas(ampliar(normaliza(texto))).map(raiz))
  const puntuadas = APLICACIONES.map(a => ({
    ...a, puntos: raices.filter(r => a.raices.has(r)).reduce((s, r) => s + 1 / FRECUENCIA[r], 0),
  })).filter(a => a.puntos > 0)
  if (!puntuadas.length) return { criterio: 'aplicacion', grados: [] }
  const max = Math.max(...puntuadas.map(a => a.puntos))
  const elegidas = puntuadas.filter(a => a.puntos >= max * 0.6).sort((a, b) => b.puntos - a.puntos).slice(0, 12)
  const porGrado = new Map()
  for (const a of elegidas) {
    const g = nombreGrado(a.ficha)
    if (!porGrado.has(g)) {
      porGrado.set(g, { grado: g, ficha: a.ficha,
        motivo: a.tipo === 'aplicacion' ? `aplicación «${a.texto}» en su ficha` : `su ficha dice: «${a.texto}»` })
    }
  }
  return { criterio: 'aplicacion', grados: [...porGrado.values()] }
}

export function interpretarTexto(texto) {
  let t = normaliza(texto)
  const esp = {
    grado: null, acabado: null, formato: null, espesor_mm: null, ancho_mm: null,
    largo_mm: null, cantidad: null, uso: null, fuente_uso: null, opciones: {}, faltan: [], avisos: [],
  }
  const grado = DESIGNACIONES.find(([d]) => new RegExp(`(?<![\\w.])${escapa(d)}(?![\\w.])`).test(t))
  if (grado) esp.grado = grado[1]
  const familia = Object.keys(FAMILIAS).find(f => t.includes(f.slice(0, -1)))
  if (!esp.grado && familia) {
    esp.opciones.grado = unicos(fichas.filter(f => f.familia === FAMILIAS[familia]).map(nombreGrado))
  }
  const conUso = fichas.flatMap(f => f.aplicaciones.map(a => [normaliza(a.replace(/\.$/, '')), a.replace(/\.$/, ''), f]))
    .filter(([a]) => t.includes(a))
  if (conUso.length) {
    esp.uso = conUso[0][1]
    const fuentes = conUso.filter(([a]) => a === conUso[0][0]).map(([, , f]) => f)
    esp.fuente_uso = `Fichas ${unicos(fuentes.map(f => f.mat)).join(', ')}`
    if (!esp.grado && !esp.opciones.grado) esp.opciones.grado = unicos(fuentes.map(nombreGrado))
  }
  const acabado = t.match(/\b(ba|2r|2b|2d|1d)\b/)
  if (acabado) esp.acabado = ALIAS_ACABADO[acabado[1]] ?? acabado[1].toUpperCase()
  else if (ALIAS_ACABADO.brillante && /\bbrillantes?\b/.test(t) && !/\b(no|sin)\s+(acabado\s+)?brillantes?\b/.test(t)) {
    esp.acabado = ALIAS_ACABADO.brillante
  }
  else for (const [k, v] of Object.entries(GLOSARIO)) if (t.includes(k)) esp.opciones.acabado = v
  const formato = Object.entries(FORMATOS).find(([, palabras]) => new RegExp(`\\b(${palabras})(s|es)?\\b`).test(t))
  if (formato) esp.formato = formato[0]

  // Medidas antes que espesor, para que «300 mm de ancho» no se lea como espesor.
  const medidas = t.match(/(\d{3,4})\s*[x×]\s*(\d{3,4})/)
  if (medidas) { esp.ancho_mm = +medidas[1]; esp.largo_mm = +medidas[2]; t = t.replace(medidas[0], ' ') }
  const ancho = t.match(/(\d{2,4}(?:[.,]\d+)?)\s*(?:mm\s*)?de\s*ancho/) ?? t.match(/ancho\s*(?:de\s*)?(\d{2,4}(?:[.,]\d+)?)(?:\s*mm)?/)
  if (ancho) { esp.ancho_mm = numero(ancho[1]); t = t.replace(ancho[0], ' ') }
  const largo = t.match(/(\d{3,5}(?:[.,]\d+)?)\s*(?:mm\s*)?de\s*largo/) ?? t.match(/largo\s*(?:de\s*)?(\d{3,5}(?:[.,]\d+)?)(?:\s*mm)?/)
  if (largo) { esp.largo_mm = numero(largo[1]); t = t.replace(largo[0], ' ') }
  const espesor = t.match(/(\d+(?:[.,]\d+)?)\s*mm/)
  if (espesor) { esp.espesor_mm = numero(espesor[1]); t = t.replace(espesor[0], ' ') }
  const kg = t.match(/(\d+(?:[.,]\d+)?)\s*(kg|t)\b/)
  if (kg) { esp.cantidad = { valor: numero(kg[1]), unidad: kg[2] }; t = t.replace(kg[0], ' ') }

  // Un código con pinta de grado que no está en el catálogo se avisa, no se ignora en silencio (RF-06).
  const desconocido = !esp.grado && t.match(/(?<![\d.,])(\d{3}[a-z]{0,2})(?![\d.,])/)
  if (desconocido) esp.avisos.push(`No encuentro el grado «${desconocido[1].toUpperCase()}» en el catálogo.`)

  if (!esp.grado && !esp.opciones.grado) esp.faltan.push('grado')
  if (!esp.espesor_mm) esp.faltan.push('espesor_mm')
  return esp
}
