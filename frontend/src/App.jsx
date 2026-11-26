import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, resumenStock, consultarValores } from './api.js'
import { escuchar, leerEnAlto } from './voz.js'
import { Panel } from './Panel.jsx'
import { Tarjeta, Detalle, Comparador } from './Tarjetas.jsx'
import { Acero, Dibujo } from './Acero.jsx'
import { Casillas } from './Casillas.jsx'
import { interpretarTexto, detectarConsulta, detectarUso, recomendarPorUso } from './previa.js'
import { Consulta, textoConsulta } from './Consulta.jsx'
import { Uso, construirUso } from './Uso.jsx'
import { Cercanos } from './Cercanos.jsx'

// Guion de docs/guion_demo.md (rama de Nacho) más las consultas para quien no conoce la nomenclatura.
const DEMO = [
  { texto: 'chapa brillante 304', nota: '«Brillante» es coloquial: puede ser BA o 2R. No lo supone, lo guarda como dos opciones y solo pregunta lo que falta.' },
  { texto: 'de 2 mm', nota: 'Ha buscado en el inventario real: hay stock en los dos acabados, así que ahora sí pregunta, y solo por el acabado.' },
  { texto: 'BA', nota: 'Todo lo que dice sale del inventario. Abre una tarjeta: «Por qué se propone» y «De dónde sale cada dato».' },
  { texto: '¿qué acero recomiendas para ambiente marino?', nueva: true, nota: 'Recomienda solo lo que respaldan las fichas de AcerIA (límite de cloruros) y comprueba qué hay en stock.' },
  { texto: '¿qué grosores hay de 316L?', nota: 'Para quien no conoce la nomenclatura: pregunta qué hay y elige con un clic, sin saber los códigos.' },
]
const espera = ms => new Promise(r => setTimeout(r, ms))

// Filtros de «¿qué hay?»: lo que dice esta pregunta y, si no, lo ya entendido en la conversación.
function filtrosConsulta(campo, texto, esp) {
  const previa = interpretarTexto(texto)
  const filtros = {}
  for (const k of ['grado', 'acabado', 'formato', 'espesor_mm', 'ancho_mm']) {
    const v = previa[k] ?? esp?.[k]
    if (k !== campo && v != null) filtros[k] = v
  }
  return filtros
}

const nuevoId = () => `c-${Date.now().toString(36)}`
const plural = (n, palabra) => `${n} ${palabra}${n === 1 ? '' : 's'}`

function cuando(fecha) {
  const hora = fecha.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
  return fecha.toDateString() === new Date().toDateString()
    ? `Hoy, ${hora}`
    : `${fecha.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}, ${hora}`
}

export default function App() {
  const [conversaciones, setConversaciones] = useState([])
  const [actual, setActual] = useState(() => ({ id: nuevoId(), mensajes: [], ultima: null }))
  const [texto, setTexto] = useState('')
  const [pensando, setPensando] = useState(false)
  const [vozActiva, setVozActiva] = useState(false)
  const [estadoDictado, setEstadoDictado] = useState(null)
  const [mensajeDictado, setMensajeDictado] = useState('')
  const [detalle, setDetalle] = useState(null)
  const [stock, setStock] = useState([])
  const [comparar, setComparar] = useState([])
  const [verComparacion, setVerComparacion] = useState(false)
  const [demo, setDemo] = useState(null)
  const actualRef = useRef(actual)
  actualRef.current = actual
  const finRef = useRef(null)
  const entradaRef = useRef(null)
  const dictadoRef = useRef(null)

  useEffect(() => { resumenStock().then(setStock).catch(() => setStock([])) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [actual.mensajes, pensando])
  useEffect(() => () => descartarDictado(dictadoRef), [])
  const [lento, setLento] = useState(false)
  useEffect(() => {
    setLento(false)
    if (!pensando) return
    const t = setTimeout(() => setLento(true), 2500)
    return () => clearTimeout(t)
  }, [pensando])

  function cancelarDictado() {
    descartarDictado(dictadoRef)
    setEstadoDictado(null)
    setMensajeDictado('')
  }

  async function alternarDictado() {
    if (estadoDictado === 'procesando') return
    if (dictadoRef.current) {
      setEstadoDictado('procesando')
      dictadoRef.current.detener()
      return
    }

    setMensajeDictado('')
    window.speechSynthesis?.cancel()
    let dictado
    try {
      dictado = escuchar()
      dictadoRef.current = dictado
      setEstadoDictado('escuchando')
      const transcripcion = await dictado.texto
      if (dictadoRef.current !== dictado) return
      if (transcripcion) {
        setTexto(anterior => [anterior.trimEnd(), transcripcion].filter(Boolean).join(' '))
        entradaRef.current?.focus()
      } else {
        setMensajeDictado('No se reconoció voz. Prueba otra vez o escribe la petición.')
      }
    } catch (error) {
      if (dictadoRef.current === dictado || !dictado) {
        setMensajeDictado(`${error.message} Puedes escribir la petición.`)
      }
    } finally {
      if (dictadoRef.current === dictado || !dictado) {
        dictadoRef.current = null
        setEstadoDictado(null)
      }
    }
  }

  const guardar = conv => {
    setActual(conv)
    setConversaciones(cs => [conv, ...cs.filter(c => c.id !== conv.id)])
  }

  async function enviar(msg, conv = actual) {
    const limpio = msg.trim()
    if (!limpio || pensando) return
    cancelarDictado()
    setTexto('')
    const base = { ...conv, creada: conv.creada ?? new Date(), mensajes: [...conv.mensajes, { rol: 'comercial', texto: limpio }] }
    guardar(base)
    setPensando(true)
    try {
      const recomendacion = detectarUso(limpio) && recomendarPorUso(limpio)
      if (recomendacion) {
        const { valores } = await consultarValores('grado', filtrosConsulta('grado', limpio, conv.ultima?.especificacion))
        const { textoBot, uso } = construirUso(limpio, recomendacion, valores)
        guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: textoBot, uso, reintento: limpio }] })
        if (vozActiva) leerEnAlto(textoBot)
        return
      }
      const pregunta = detectarConsulta(limpio)
      if (pregunta) {
        const c = await consultarValores(pregunta.campo, filtrosConsulta(pregunta.campo, limpio, conv.ultima?.especificacion))
        const textoBot = textoConsulta(c, interpretarTexto(limpio).avisos)
        guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: textoBot, consulta: c, reintento: limpio }] })
        if (vozActiva) leerEnAlto(textoBot)
        return
      }
      const r = await enviarMensaje(conv.id, limpio)
      const textoBot = r.tipo === 'error' ? r.error : (r.pregunta ?? r.texto)
      const msgBot = { rol: 'asistente', texto: textoBot, respuesta: r, error: r.tipo === 'error', reintento: limpio }
      guardar({ ...base, mensajes: [...base.mensajes, msgBot], ultima: r })
      if (vozActiva && r.tipo !== 'error') leerEnAlto(textoBot)
    } catch (e) {
      const msgErr = { rol: 'asistente', texto: `No he podido responder (${e.message}). Puedes reintentar o reformular la petición.`, error: true, reintento: limpio }
      guardar({ ...base, mensajes: [...base.mensajes, msgErr] })
    } finally {
      setPensando(false)
    }
  }

  function reintentar(msg) {
    enviar(msg, { ...actual, mensajes: actual.mensajes.slice(0, -2) })
  }

  function nuevaConsulta() {
    cancelarDictado()
    window.speechSynthesis?.cancel()
    setActual({ id: nuevoId(), mensajes: [], ultima: null })
    setTexto('')
    setDetalle(null)
    setComparar([])
  }

  function alternarComparar(tipo, item) {
    setComparar(cs => cs.some(c => c.item.id === item.id)
      ? cs.filter(c => c.item.id !== item.id)
      : [...cs, { tipo, item }].slice(-4))
  }

  const anadirATexto = f => { setTexto(t => `${[t.trimEnd(), f].filter(Boolean).join(' ')} `); entradaRef.current?.focus() }

  async function pasoDemo(i) {
    const paso = DEMO[i]
    if (!paso) { setDemo(null); return }
    setDemo({ paso: i, nota: null })
    let conv = actualRef.current
    if (paso.nueva || i === 0) {
      cancelarDictado()
      conv = { id: nuevoId(), mensajes: [], ultima: null }
      setActual(conv)
      setComparar([])
    }
    for (let n = 1; n <= paso.texto.length; n++) {
      setTexto(paso.texto.slice(0, n))
      await espera(35)
    }
    await espera(400)
    await enviar(paso.texto, conv)
    setDemo({ paso: i, nota: paso.nota })
  }

  const noServidas = conversaciones.filter(c => c.ultima?.tipo === 'respuesta'
    && !c.ultima.exactos.length && !c.ultima.transformables.length).length
  const esp = actual.ultima?.especificacion
  const vacio = actual.mensajes.length === 0
  const totalBultos = stock.reduce((n, s) => n + s.bultos, 0)
  const hoy = new Date().toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })
  const previa = vacio && texto.trim() ? interpretarTexto(texto) : null

  return (
    <div className={`app ${vacio ? 'portada' : ''}`}>
      <header className="cabecera">
        <div className="fondo-video" aria-hidden>
          <video src="/video/cabecera.mp4" autoPlay muted loop playsInline
            onError={e => { e.currentTarget.style.display = 'none' }} />
        </div>
        <div className="utilidades">
          <span className="estado" title="Consultas de esta sesión para las que no había stock ni transformación posible">
            Demanda no servida: <b>{noServidas}</b>
          </span>
          <label className="interruptor" title="Leer en voz alta cada respuesta del asistente">
            <input type="checkbox" checked={vozActiva}
              onChange={e => { setVozActiva(e.target.checked); window.speechSynthesis?.cancel() }} />
            <span className="interruptor-pista" aria-hidden />
            Leer respuestas en voz alta
          </label>
          <div className="utilidades-derecha">
            <span><b>INOX·STOCK</b> | {hoy}{totalBultos > 0 && <> | <span className="resalte">{totalBultos.toLocaleString('es-ES')} bultos disponibles</span></>}</span>
          </div>
        </div>
        <div className="principal-cabecera">
          <div className="marca">
            <span className="logo-luna" aria-hidden />
            <span className="logo-texto">INOX<span className="punto">·</span>STOCK</span>
          </div>
          <div className="acciones">
            <button className="demo-boton" onClick={() => pasoDemo(0)} disabled={pensando || demo !== null}
              title="Reproduce la conversación de la demo paso a paso">▶ Demo guiada</button>
            <button className="nueva" onClick={nuevaConsulta}>+ Nueva consulta</button>
          </div>
        </div>
        <div className="lema">
          <p>Asistente de inventario comercial</p>
          <span>Acero inoxidable · stock real · transformaciones según las reglas de AcerIA</span>
        </div>
      </header>

      <div className="ticker" aria-label="Resumen de stock">
        <div className="ticker-pista">
          {[...stock, ...stock, ...stock].map((s, i) => (
            <span key={i} className="ticker-item">
              {s.etiqueta} <em>{plural(s.bultos, 'bulto')} · {s.toneladas.toFixed(1).replace('.', ',')} t</em>
            </span>
          ))}
        </div>
      </div>

      <div className="cuerpo">
        <aside className="lateral">
          <div className="lateral-titulo">Recientes ⌄</div>
          {conversaciones.map(c => (
            <button key={c.id} className={`reciente ${c.id === actual.id ? 'activa' : ''}`}
              onClick={() => { cancelarDictado(); setActual(c); setDetalle(null) }}>
              <span className="reciente-texto">{c.mensajes[0]?.texto}</span>
              {c.creada && <span className="reciente-hora">{cuando(c.creada)}</span>}
            </button>
          ))}
        </aside>

        <main className="principal">
          {vacio ? (
            <section className="inicio">
              <div className="inicio-acero" aria-hidden>
                <Dibujo formato={previa?.formato} acabado={previa?.acabado ?? previa?.opciones.acabado?.[0]} id="inicio" />
              </div>
              <div className="inicio-texto">
                <h1>¿Qué quieres buscar?</h1>
                <div className="inicio-nombre">
                  {previa && [previa.grado, previa.acabado ?? previa.opciones.acabado?.join('/'), previa.formato].filter(Boolean).join(' · ')}
                </div>
                <p className="ayuda-inicio">Escribe o dicta lo que pide el cliente. Si no sabes qué pedir, pregunta qué hay: «¿qué grosores hay de 304?» o «¿qué acero recomiendas para hornos?»</p>
              </div>
            </section>
          ) : (
            <section className="conversacion">
              <div className="mensajes">
                {actual.mensajes.map((m, i) => (
                  <div key={i} className={`mensaje ${m.rol} ${m.error ? 'error' : ''}`}>
                    <p>{m.texto}</p>
                    {m.error && i === actual.mensajes.length - 1 && (
                      <button className="reintentar" onClick={() => reintentar(m.reintento)}>Reintentar</button>
                    )}
                    {m.rol === 'asistente' && !m.error && (
                      <button className="altavoz" onClick={() => leerEnAlto(m.texto)} title="Leer en voz alta">🔊</button>
                    )}
                    {Array.isArray(m.respuesta?.opciones) && m.respuesta.opciones.length > 0 && i === actual.mensajes.length - 1 && (
                      <div className="opciones">
                        {m.respuesta.opciones.map(o => (
                          <button key={o} type="button" className="opcion" disabled={pensando} onClick={() => enviar(o)}>{o}</button>
                        ))}
                      </div>
                    )}
                    {m.consulta && <Consulta consulta={m.consulta} deshabilitado={pensando} onElegir={anadirATexto} />}
                    {m.uso && <Uso uso={m.uso} deshabilitado={pensando} onElegir={anadirATexto} />}
                    {m.respuesta?.especificacion && <Acero esp={m.respuesta.especificacion} id={i} />}
                    {m.respuesta && (
                      <Resultados r={m.respuesta} onAbrir={setDetalle}
                        comparar={comparar} onComparar={alternarComparar} />
                    )}
                    {i === actual.mensajes.length - 1 && m.respuesta?.tipo === 'respuesta' && m.respuesta.especificacion
                      && !m.respuesta.exactos?.length && !m.respuesta.transformables?.length && (
                      <Cercanos esp={m.respuesta.especificacion} onElegir={enviar} deshabilitado={pensando} />
                    )}
                  </div>
                ))}
                {pensando && (
                  <div className="mensaje asistente pensando">
                    <p>Pensando<span className="puntos" />{lento && <small> El primer mensaje puede tardar unos segundos.</small>}</p>
                  </div>
                )}
                <div ref={finRef} />
              </div>
              <Panel esp={esp} onCorregir={enviar} deshabilitado={pensando} />
            </section>
          )}

          {demo && (
            <div className="demo-barra" role="status">
              <span className="demo-paso">Demo · paso {demo.paso + 1} de {DEMO.length}</span>
              <span className="demo-nota">{demo.nota ?? 'Escribiendo…'}</span>
              {demo.nota && (
                <button className="demo-siguiente" onClick={() => pasoDemo(demo.paso + 1)} disabled={pensando}>
                  {demo.paso + 1 < DEMO.length ? 'Siguiente ▶' : 'Terminar'}
                </button>
              )}
              <button className="demo-salir" onClick={() => setDemo(null)}>Salir</button>
            </div>
          )}
          {comparar.length > 0 && (
            <div className="comparar-barra">
              <span>{comparar.length} {comparar.length === 1 ? 'propuesta marcada' : 'propuestas marcadas'}</span>
              <button className="opcion" onClick={() => setVerComparacion(true)} disabled={comparar.length < 2}
                title={comparar.length < 2 ? 'Marca al menos dos tarjetas' : undefined}>Comparar</button>
              <button className="demo-salir" onClick={() => setComparar([])}>Limpiar</button>
            </div>
          )}
          <form className="entrada" onSubmit={e => { e.preventDefault(); enviar(texto) }}>
            <input ref={entradaRef} value={texto} onChange={e => setTexto(e.target.value)}
              placeholder="Escribe o dicta: grado, espesor, formato…"
              aria-label="Escribe tu petición" disabled={pensando} />
            <button type="button" className={`microfono ${estadoDictado ? 'escuchando' : ''}`}
              title={estadoDictado ? 'Detener dictado' : 'Dictar la petición'}
              aria-pressed={Boolean(estadoDictado)} disabled={pensando || estadoDictado === 'procesando'}
              onClick={alternarDictado}>
              <span className="microfono-icono" aria-hidden>{estadoDictado ? '■' : '🎙'}</span>
              {estadoDictado === 'escuchando' ? 'Escuchando…' : estadoDictado === 'procesando' ? 'Transcribiendo…' : 'Hablar'}
            </button>
            <button type="submit" className="icono" title="Enviar" disabled={pensando || !texto.trim()}>→</button>
          </form>
          <div className="estado-dictado" role="status">{estadoDictado ? '' : mensajeDictado}</div>
          <Casillas texto={texto} base={esp} />
        </main>
      </div>

      {detalle && <Detalle item={detalle} esp={esp} onCerrar={() => setDetalle(null)} />}
      {verComparacion && comparar.length > 1 && (
        <Comparador seleccion={comparar} onQuitar={t => alternarComparar(t.tipo, t.item)} onCerrar={() => setVerComparacion(false)} />
      )}
    </div>
  )
}

function descartarDictado(ref) {
  const dictado = ref.current
  ref.current = null
  dictado?.cancelar()
}

function Resultados({ r, onAbrir, comparar, onComparar }) {
  const n = { exactos: r.exactos?.length ?? 0, transformables: r.transformables?.length ?? 0, alternativas: r.alternativas?.length ?? 0 }
  if (!n.exactos && !n.transformables && !n.alternativas) return null
  const resumen = [
    n.exactos && `${n.exactos} que cumple${n.exactos === 1 ? '' : 'n'}`,
    n.transformables && `${n.transformables} transformable${n.transformables === 1 ? '' : 's'}`,
    n.alternativas && `${n.alternativas} alternativa${n.alternativas === 1 ? '' : 's'}`,
  ].filter(Boolean).join(' · ')
  return (
    <>
    <div className="tarjetas-resumen">
      <span>{resumen}</span>
      {r.criterio_orden && n.exactos + n.transformables > 1 && <span className="criterio">Orden: {r.criterio_orden}</span>}
    </div>
    <div className="tarjetas">
      {[['exacto', r.exactos], ['transformable', r.transformables], ['alternativa', r.alternativas]].flatMap(([tipo, lista]) =>
        (lista ?? []).map(item => (
          <Tarjeta key={`${tipo}-${item.id}`} tipo={tipo} item={item} onClick={() => onAbrir({ tipo, item })}
            comparando={comparar.some(c => c.item.id === item.id)} onComparar={() => onComparar(tipo, item)} />
        )))}
    </div>
    </>
  )
}
