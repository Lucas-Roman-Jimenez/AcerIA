import { useEffect, useRef, useState } from 'react'
import { interpretarTexto } from './previa.js'
import { consultarValores } from './api.js'
import { fraseCambio } from './Flujo.jsx'

const num = v => String(v).replace('.', ',')
const lista = vs => (vs?.length > 3 ? `${vs.slice(0, 3).join(', ')}…` : vs?.join(' o '))

const CAMPOS = [
  ['grado', 'Grado'],
  ['espesor_mm', 'Espesor', 'mm'],
  ['acabado', 'Acabado'],
  ['formato', 'Formato'],
  ['ancho_mm', 'Ancho', 'mm'],
]
// El stock trae grados dobles («304L/304»): cuenta como elegido si coincide con cualquiera de ellos.
const igual = (a, b) => a === b || String(a).toUpperCase().split('/').map(x => x.trim()).includes(String(b).toUpperCase())
const conUnidad = (unidad, v) => `${num(v)}${unidad ? ' ' + unidad : ''}`

// Filtros de un campo: lo ya elegido en los demás. Así, al elegir 2 mm, el resto solo ofrece lo que hay en 2 mm.
function filtrosSin(esp, campo) {
  const f = {}
  for (const [k] of CAMPOS) if (k !== campo && esp?.[k] != null) f[k] = esp[k]
  return f
}

// Cifra que cuenta desde 0 (o desde la anterior) hasta su valor, con frenada al final.
const sinMovimiento = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
function Contador({ n }) {
  const [v, setV] = useState(0)
  const desde = useRef(0)
  useEffect(() => {
    if (sinMovimiento()) { setV(n); desde.current = n; return }
    const inicio = performance.now(), a = desde.current, dur = 750
    let id = requestAnimationFrame(function paso(t) {
      const x = Math.min(1, (t - inicio) / dur)
      setV(Math.round(a + (n - a) * (1 - Math.pow(2, -10 * x))))
      if (x < 1) id = requestAnimationFrame(paso)
      else { setV(n); desde.current = n }
    })
    return () => cancelAnimationFrame(id)
  }, [n])
  return <>{v.toLocaleString('es-ES')}</>
}

// Foco de luz que sigue al ratón dentro de la casilla
function foco(e) {
  const c = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--mx', `${e.clientX - c.left}px`)
  e.currentTarget.style.setProperty('--my', `${e.clientY - c.top}px`)
}

// Regla de rayitas sobre las casillas: el indicador azul sigue al cursor (con suavidad) solo mientras está
// dentro de la zona, y las rayitas cercanas crecen a su paso. Se pinta con requestAnimationFrame, sin re-render.
const RAYAS = 96
function useRegla(zona) {
  const rayas = useRef([])
  const indicador = useRef(null)
  useEffect(() => {
    const el = zona.current
    if (!el) return
    const quieto = sinMovimiento()
    let objetivo = null, x = null, id = 0
    const pintar = () => {
      id = 0
      if (objetivo == null) return
      x = x == null || quieto ? objetivo : x + (objetivo - x) * 0.2
      indicador.current.style.transform = `translateX(${x}px)`
      const ancho = el.clientWidth
      rayas.current.forEach((r, i) => {
        if (!r) return
        const d = (((i + 0.5) / RAYAS) * ancho - x) / 30
        const g = Math.exp(-d * d)
        r.style.transform = `scaleY(${1 + 1.7 * g})`
        r.style.opacity = String(0.35 + 0.65 * g)
      })
      if (Math.abs(objetivo - x) > 0.3) id = requestAnimationFrame(pintar)
    }
    const mover = e => {
      const c = el.getBoundingClientRect()
      objetivo = Math.max(0, Math.min(c.width, e.clientX - c.left))
      el.classList.add('regla-activa')
      if (!id) id = requestAnimationFrame(pintar)
    }
    const fuera = () => {
      objetivo = null; x = null
      el.classList.remove('regla-activa')
      rayas.current.forEach(r => { if (r) { r.style.transform = ''; r.style.opacity = '' } })
    }
    el.addEventListener('pointermove', mover)
    el.addEventListener('pointerleave', fuera)
    return () => { cancelAnimationFrame(id); el.removeEventListener('pointermove', mover); el.removeEventListener('pointerleave', fuera) }
  }, [zona])
  return { rayas, indicador }
}

// Datos del metal: lo que se va reconociendo al escribir y lo ya entendido en la conversación.
// Cada casilla se pulsa para ver los valores en stock con el resto de lo elegido.
export function Casillas({ texto, base, onElegir, onQuitar, deshabilitado }) {
  const [abierto, setAbierto] = useState(null)
  const [valores, setValores] = useState({})
  const raiz = useRef(null)
  const regla = useRegla(raiz)
  const previa = texto.trim() ? interpretarTexto(texto) : null
  const valor = k => previa?.[k] ?? base?.[k] ?? null
  const opciones = k => previa?.opciones?.[k] ?? base?.opciones?.[k]
  const clave = JSON.stringify(CAMPOS.map(([k]) => base?.[k] ?? null))

  // Valores en stock de cada campo con lo ya elegido; se recalculan al cambiar cualquier dato.
  useEffect(() => {
    let vivo = true
    setValores({})
    Promise.all(CAMPOS.map(async ([k]) => [k, (await consultarValores(k, filtrosSin(base, k))).valores]))
      .then(pares => vivo && setValores(Object.fromEntries(pares)))
      .catch(() => vivo && setValores({}))
    return () => { vivo = false }
  }, [clave])

  useEffect(() => {
    if (!abierto) return
    const cerrar = e => { if (!raiz.current?.contains(e.target)) setAbierto(null) }
    const escape = e => e.key === 'Escape' && setAbierto(null)
    document.addEventListener('mousedown', cerrar)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('mousedown', cerrar); document.removeEventListener('keydown', escape) }
  }, [abierto])

  const esElegido = (k, v) => base?.[k] != null && igual(v, base[k])

  function elegir(k, v) {
    setAbierto(null)
    onElegir(fraseCambio(k, v))
  }

  // Deseleccionar: el dato deja de filtrar (queda en «indiferentes» del backend).
  function quitar(k) {
    setAbierto(null)
    onQuitar(k)
  }

  const largo = valor('largo_mm')
  return (
    <div className="casillas" aria-live="polite" ref={raiz}>
      <div className="regla" aria-hidden>
        {Array.from({ length: RAYAS }, (_, i) => <span key={i} ref={el => { regla.rayas.current[i] = el }} />)}
        <span className="regla-indicador" ref={regla.indicador} />
      </div>
      {CAMPOS.map(([k, etiqueta, unidad], i) => {
        // Un dato quitado («me da igual») queda vacío, como al principio: se puede volver a elegir cualquier valor.
        const v = valor(k) != null ? conUnidad(unidad, valor(k)) : lista(opciones(k)) ?? null
        const enStock = valores[k]
        return (
          <div key={k} className="casilla-bloque" style={{ '--i': i }}>
            <button type="button" className={`casilla ${v ? 'llena' : ''} ${abierto === k ? 'abierta' : ''}`}
              disabled={deshabilitado} aria-expanded={abierto === k}
              title={`Ver los ${etiqueta.toLowerCase()}s que hay en stock`}
              onPointerMove={foco} onClick={() => setAbierto(abierto === k ? null : k)}>
              <span className="casilla-etiqueta">{etiqueta} ⌄</span>
              <span className="casilla-valor">
                {v ?? (enStock ? <><b className="casilla-num"><Contador n={enStock.length} /></b> en stock</> : '—')}
              </span>
            </button>
            {base?.[k] != null && (
              <button type="button" className="casilla-quitar" disabled={deshabilitado}
                title={`Quitar ${etiqueta.toLowerCase()}`} aria-label={`Quitar ${etiqueta.toLowerCase()}`}
                onClick={() => quitar(k)}>✕</button>
            )}
            {abierto === k && (
              <div className="casilla-opciones" role="listbox" aria-label={`${etiqueta} en stock`}>
                <div className="casilla-opciones-titulo">
                  {etiqueta} en stock{Object.keys(filtrosSin(base, k)).length ? ' con lo que ya has elegido' : ''}
                </div>
                {!enStock ? <span className="tenue">Buscando…</span>
                  : !enStock.length ? <span className="tenue">No hay stock con el resto de datos.</span>
                  : (
                    <div className="editor-lista">
                      {enStock.map(o => (
                        <button key={o.valor} type="button" role="option" aria-selected={esElegido(k, o.valor)}
                          className={`chip-stock ${esElegido(k, o.valor) ? 'elegido' : ''}`} disabled={deshabilitado}
                          onClick={() => (esElegido(k, o.valor) ? quitar(k) : elegir(k, o.valor))}
                          title={esElegido(k, o.valor) ? 'Pulsa para quitarlo' : `${o.bultos} bultos · ${num(o.toneladas)} t`}>
                          {conUnidad(unidad, o.valor)} <small>{esElegido(k, o.valor) ? '✕' : o.bultos}</small>
                        </button>
                      ))}
                    </div>
                  )}
              </div>
            )}
          </div>
        )
      })}
      {largo != null && (
        <div className="casilla-bloque">
          <div className="casilla llena">
            <span className="casilla-etiqueta">Largo</span>
            <span className="casilla-valor">{num(largo)} mm</span>
          </div>
        </div>
      )}
    </div>
  )
}
