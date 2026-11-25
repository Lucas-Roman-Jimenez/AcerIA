import fichas from './fichas_aceria.json'

export const INICIALES = [
  { tipo: 'Chapa', texto: 'Chapa brillante de 2 mm, 1000 × 2000' },
  { tipo: 'Bobina', texto: 'Bobina para sistemas de escape de 1,5 mm' },
  { tipo: 'Fleje', texto: 'Fleje de 316L de 2 mm' },
  { tipo: 'Dúplex', texto: 'Dúplex en caliente de 6 mm' },
]

const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
const palabras = s => normaliza(s).split(/[^a-z0-9.]+/).filter(Boolean)

const FORMATOS = ['chapa', 'bobina', 'fleje'].map(f => ({
  tipo: 'Formato', texto: f, detalle: 'Formato', peso: 1,
}))

const GRADOS = [...new Map(fichas.filter(f => f.aisi).map(f => [f.aisi, f])).values()].map(f => ({
  tipo: f.familia, texto: f.aisi.replace(' DDQ', ''), detalle: `${f.mat} · EN ${f.en}`, extra: `${f.mat} ${f.en}`, peso: 0,
}))

const FAMILIAS = [...new Set(fichas.map(f => f.familia))].map(familia => ({
  tipo: 'Familia', texto: familia, peso: 0.5,
  detalle: [...new Set(fichas.filter(f => f.familia === familia && f.aisi).map(f => f.aisi.replace(' DDQ', '')))].join(', '),
}))

// Primero lo que hay en stock; después formatos, familias y grados del catálogo.
function candidatos(stock) {
  const enStock = stock.map(s => {
    const [producto, formato] = s.etiqueta.split(' · ')
    return {
      tipo: `${formato} · en stock`, texto: `${formato} ${producto}`,
      detalle: `${s.bultos} bultos · ${s.toneladas.toFixed(1).replace('.', ',')} t`, peso: 2 + s.bultos / 100,
    }
  })
  return [...enStock, ...FORMATOS, ...FAMILIAS, ...GRADOS]
}

export function sugerir(escrito, stock) {
  const tokens = palabras(escrito)
  if (!tokens.length) return INICIALES
  const ultimo = tokens.at(-1)
  return candidatos(stock)
    .map(c => {
      const ws = palabras(`${c.texto} ${c.extra ?? ''}`)
      const coincide = t => ws.some(w => w.startsWith(t))
      const aciertos = tokens.filter(coincide).length
      return { ...c, puntos: aciertos ? aciertos + (coincide(ultimo) ? 2 : 0) + c.peso : 0 }
    })
    .filter(c => c.puntos > 0)
    .sort((a, b) => b.puntos - a.puntos)
    .slice(0, 4)
}

// Completa la palabra a medio escribir sin borrar el resto de la frase.
export function completar(escrito, sugerencia) {
  if (!palabras(escrito).length) return sugerencia.texto
  // Sustituye las últimas palabras escritas que ya forman parte de la sugerencia.
  const ws = palabras(sugerencia.texto)
  const trozos = escrito.trimEnd().split(/(\s+)/)
  let corte = trozos.length
  while (corte > 0 && ws.some(w => w.startsWith(normaliza(trozos[corte - 1])))) corte -= 2
  const base = trozos.slice(0, Math.max(corte, 0)).join('')
  return `${base}${base && !/\s$/.test(base) ? ' ' : ''}${sugerencia.texto} `
}
