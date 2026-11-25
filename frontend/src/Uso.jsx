const num = v => String(v).replace('.', ',')

// Stock de un grado recomendado: vale el AISI, la Euronorma o el UNS de su ficha, también en dobles como «304L/304».
function stockDe(rec, valores) {
  const nombres = [rec.grado, rec.ficha.en, rec.ficha.uns].filter(Boolean).map(s => s.toUpperCase())
  const encontrados = valores.filter(v => String(v.valor).toUpperCase().split('/').some(p => nombres.includes(p.trim())))
  return encontrados.length
    ? { bultos: encontrados.reduce((s, v) => s + v.bultos, 0), toneladas: encontrados.reduce((s, v) => s + v.toneladas, 0) }
    : null
}

export function construirUso(texto, recomendacion, valoresStock) {
  const grados = recomendacion.grados.map(r => ({ ...r, stock: stockDe(r, valoresStock) }))
  const lista = grados.map(g => g.grado).join(', ')
  const conStock = grados.filter(g => g.stock).map(g => g.grado)
  const sinStock = grados.filter(g => !g.stock).map(g => g.grado)
  let textoBot
  if (!grados.length) {
    textoBot = 'El catálogo de AcerIA no indica ningún grado para ese uso. Prueba a describirlo con otras palabras '
      + '(por ejemplo «menaje», «hornos», «tanques» o «sistemas de escape») o pregunta qué tipos de acero hay.'
  } else if (recomendacion.criterio === 'cloruros') {
    textoBot = `Para ambientes con cloruros, las fichas de AcerIA dan el límite más alto a ${lista} `
      + `(hasta ${grados[0].ficha.cloruros_max_ppm} ppm), frente a ${recomendacion.comparacion.join(', ')}.`
  } else {
    textoBot = `Según el catálogo de AcerIA, para ese uso se indican: ${lista}.`
  }
  if (grados.length) {
    textoBot += conStock.length ? ` En stock hay ${conStock.join(', ')}.` : ' Ahora mismo no hay stock de ninguno.'
    if (conStock.length && sinStock.length) textoBot += ` De ${sinStock.join(', ')} no hay ahora.`
    if (conStock.length) textoBot += ' Pulsa uno para añadirlo a tu petición.'
  }
  return { textoBot, uso: { grados } }
}

export function Uso({ uso, onElegir, deshabilitado }) {
  if (!uso.grados.length) return null
  return (
    <div className="consulta">
      {uso.grados.map(g => (
        <button key={g.grado} type="button" className={`valor-stock ${g.stock ? '' : 'sin-stock'}`}
          disabled={deshabilitado} onClick={() => onElegir(g.grado)} title={g.ficha.descripcion}>
          <span className="valor-stock-nombre">{g.grado}</span>
          <span className="valor-stock-ayuda">Inoxidable {g.ficha.familia} · {g.ficha.mat}</span>
          <span className="valor-stock-motivo">{g.motivo}</span>
          <span className="valor-stock-cantidad">
            {g.stock ? `${g.stock.bultos} ${g.stock.bultos === 1 ? 'bulto' : 'bultos'} · ${num(Math.round(g.stock.toneladas * 10) / 10)} t` : 'Sin stock ahora'}
          </span>
        </button>
      ))}
    </div>
  )
}
