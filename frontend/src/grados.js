import { nomenclatura_grados } from '../../datos/catalogo.json'
import fichas from './fichas_aceria.json'

const normalizar = valor => String(valor ?? '').toUpperCase().replace(/\s+/g, '')
const componentes = valor => String(valor ?? '').split('/').map(s => s.trim()).filter(Boolean)
const porCodigo = new Map()
const porEN = new Map()
const enPorUNS = new Map()
const fichasPorMAT = new Map(fichas.map(f => [normalizar(f.mat), f]))
const referencias = nomenclatura_grados.referencias_en

for (const [en, referencia] of Object.entries(referencias)) {
  for (const ficha of referencia.fichas ?? []) {
    for (const uns of ficha.uns) {
      if (!enPorUNS.has(uns)) enPorUNS.set(uns, new Set())
      enPorUNS.get(uns).add(en)
    }
  }
  for (const fuente of referencia.otras_fuentes ?? []) {
    if (fuente.mat) fichasPorMAT.set(normalizar(fuente.mat), { mat: fuente.mat, en })
  }
}

for (const [codigo, grado] of Object.entries(nomenclatura_grados.grados)) {
  const entrada = { codigo, ...grado }
  for (const alias of [codigo, ...(grado.alias ?? [])]) porCodigo.set(normalizar(alias), entrada)
  for (const en of grado.en) porEN.set(normalizar(en), entrada)
}

function gradoDocumentado(valor) {
  const clave = normalizar(valor)
  const ficha = fichasPorMAT.get(clave)
  const directo = porCodigo.get(clave) ?? porEN.get(clave) ?? porEN.get(normalizar(ficha?.en))
  if (directo) return directo
  const porUNS = new Set([...(enPorUNS.get(clave) ?? [])].map(en => porEN.get(normalizar(en))))
  return porUNS.size === 1 ? [...porUNS][0] : undefined
}

// Las 41 fichas del catálogo tienen PDF (GET /fichas/{mat}); alguna referencia de otras fuentes no.
const MAT_CON_PDF = new Set(fichas.map(f => f.mat))
export const tienePdf = mat => MAT_CON_PDF.has(mat)

export function gradoVisible(valor, euronorma) {
  return componentes(valor || euronorma).map(codigo => {
    if (normalizar(codigo) === '304DDQ') return '304 DDQ'
    const en = componentes(euronorma).find(en => referencias[en]?.designaciones_inventario
      ?.some(alias => normalizar(alias) === normalizar(codigo)))
    const grado = gradoDocumentado(codigo) ?? porEN.get(normalizar(en))
    if (!grado) return codigo
    return grado.sistema === 'EN' ? `EN ${grado.codigo}` : grado.codigo
  }).join('/')
}

// Referencias de un material: la internacional (designación EN del inventario, p. ej. 1.4301/1.4307) y las
// de AcerIA (códigos MAT de sus fichas, de menor a mayor). Sin EN en el bulto, las EN de sus fichas.
export function referenciasDelGrado(valor, euronorma) {
  const fichasGrado = fichasDelGrado(valor, euronorma)
  const en = componentes(euronorma).length ? componentes(euronorma) : [...new Set(fichasGrado.map(f => f.en))]
  const numero = mat => Number(String(mat).replace(/\D/g, '')) || 0
  const mat = [...new Set(fichasGrado.map(f => f.mat))].sort((a, b) => numero(a) - numero(b))
  return { en, mat }
}

// «EN 1.4301/1.4307» y «MAT 120/140» (con `max`, «MAT 120/140/150 +2»). null si no hay.
export const textoEN = ({ en }) => (en.length ? `EN ${en.join('/')}` : null)
export function textoMAT({ mat }, max = Infinity) {
  if (!mat.length) return null
  const numeros = mat.map(a => String(a).replace(/^MAT\s*/i, ''))
  const resto = numeros.length - max
  return `MAT ${numeros.slice(0, max).join('/')}${resto > 0 ? ` +${resto}` : ''}`
}

export function fichasDelGrado(valor, euronorma) {
  const gradosEN = new Set(componentes(euronorma).map(normalizar))
  const resultados = new Map()
  for (const codigo of componentes(valor || euronorma)) {
    const clave = normalizar(codigo)
    const ficha = fichasPorMAT.get(clave)
    const grado = gradoDocumentado(codigo)
    const opcionEN = ficha?.en ?? Object.keys(referencias).find(en => normalizar(en) === clave)
    const candidatas = opcionEN ? [opcionEN] : (enPorUNS.get(clave) ?? grado?.en ?? gradosEN)
    for (const en of candidatas) {
      if (gradosEN.size && !gradosEN.has(normalizar(en))) continue
      const referencia = referencias[en]
      if (!referencia) continue
      for (const registro of [...(referencia.fichas ?? []), ...(referencia.otras_fuentes ?? [])]) {
        if (ficha && ficha.mat !== registro.mat) continue
        if (clave === '304DDQ' && registro.grado_comercial !== '304DDQ') continue
        if (clave === '304' && registro.grado_comercial === '304DDQ') continue
        if (!registro.mat) continue
        resultados.set(registro.mat, { ...fichasPorMAT.get(normalizar(registro.mat)), mat: registro.mat, en })
      }
    }
  }
  return [...resultados.values()]
}
