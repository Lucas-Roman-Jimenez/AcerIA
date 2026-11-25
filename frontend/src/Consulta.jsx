import { buscarFicha } from './Acero.jsx'

const NOMBRES = {
  espesor_mm: 'grosores', ancho_mm: 'anchos', acabado: 'acabados', formato: 'formatos', grado: 'tipos de acero',
}
const num = v => String(v).replace('.', ',')

export function formatearValor(campo, v) {
  if (campo === 'espesor_mm' || campo === 'ancho_mm') return `${num(v)} mm`
  return String(v)
}

function describirFiltros(filtros) {
  const partes = [filtros.formato, filtros.grado, filtros.acabado,
    filtros.espesor_mm != null && `${num(filtros.espesor_mm)} mm`,
    filtros.ancho_mm != null && `${num(filtros.ancho_mm)} mm de ancho`].filter(Boolean)
  return partes.length ? ` de ${partes.join(' · ')}` : ''
}

// Texto para el chat y la voz: solo con los datos devueltos por el inventario.
export function textoConsulta({ campo, filtros, valores }, avisos = []) {
  const aviso = avisos.length ? `${avisos.join(' ')} ` : ''
  const desc = describirFiltros(filtros)
  if (!valores.length) {
    return `${aviso}Ahora mismo no hay stock disponible${desc}.${desc ? ' Prueba quitando algún dato.' : ''}`
  }
  const primeros = valores.slice(0, 6).map(v => formatearValor(campo, v.valor)).join(', ')
  const resto = valores.length > 6 ? ` y ${valores.length - 6} más` : ''
  return `${aviso}En stock${desc} hay ${valores.length} ${NOMBRES[campo]}: ${primeros}${resto}. Pulsa uno para añadirlo a tu petición.`
}

// Lo que se añade a la caja de texto al pulsar un valor: lo ya filtrado más el valor elegido.
export function fragmentoPeticion(campo, filtros, valor) {
  const d = { ...filtros, [campo]: valor }
  const producto = [d.formato, d.grado, d.acabado, d.espesor_mm != null && `de ${num(d.espesor_mm)} mm`].filter(Boolean).join(' ')
  return [producto, d.ancho_mm != null && `${num(d.ancho_mm)} de ancho`].filter(Boolean).join(', ')
}

export function Consulta({ consulta, onElegir, deshabilitado }) {
  const { campo, filtros, valores } = consulta
  if (!valores.length) return null
  return (
    <div className="consulta">
      {valores.map(v => {
        const ficha = campo === 'grado' ? buscarFicha(v.valor) : null
        return (
          <button key={v.valor} type="button" className="valor-stock" disabled={deshabilitado}
            onClick={() => onElegir(fragmentoPeticion(campo, filtros, v.valor))}
            title={ficha ? `${ficha.descripcion} (ficha ${ficha.mat})` : undefined}>
            <span className="valor-stock-nombre">{formatearValor(campo, v.valor)}</span>
            {ficha && <span className="valor-stock-ayuda">Inoxidable {ficha.familia}</span>}
            <span className="valor-stock-cantidad">
              {v.bultos} {v.bultos === 1 ? 'bulto' : 'bultos'} · {num(v.toneladas)} t
            </span>
          </button>
        )
      })}
    </div>
  )
}
