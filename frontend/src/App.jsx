import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, resumenStock } from './api.js'
import { escuchar, leerEnAlto } from './voz.js'
import { Panel } from './Panel.jsx'
import { Tarjeta, Detalle } from './Tarjetas.jsx'
import { Acero, Dibujo } from './Acero.jsx'
import { Casillas } from './Casillas.jsx'
import { interpretarTexto } from './previa.js'

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
  const [escuchando, setEscuchando] = useState(false)
  const [vozActiva, setVozActiva] = useState(false)
  const [detalle, setDetalle] = useState(null)
  const [stock, setStock] = useState([])
  const finRef = useRef(null)
  const entradaRef = useRef(null)

  useEffect(() => { resumenStock().then(setStock).catch(() => setStock([])) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [actual.mensajes, pensando])
  const [lento, setLento] = useState(false)
  useEffect(() => {
    setLento(false)
    if (!pensando) return
    const t = setTimeout(() => setLento(true), 2500)
    return () => clearTimeout(t)
  }, [pensando])

  const guardar = conv => {
    setActual(conv)
    setConversaciones(cs => [conv, ...cs.filter(c => c.id !== conv.id)])
  }

  async function enviar(msg, conv = actual) {
    const limpio = msg.trim()
    if (!limpio || pensando) return
    setTexto('')
    const base = { ...conv, creada: conv.creada ?? new Date(), mensajes: [...conv.mensajes, { rol: 'comercial', texto: limpio }] }
    guardar(base)
    setPensando(true)
    try {
      const r = await enviarMensaje(actual.id, limpio)
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
    window.speechSynthesis?.cancel()
    setActual({ id: nuevoId(), mensajes: [], ultima: null })
    setTexto('')
    setDetalle(null)
  }

  async function dictar() {
    if (escuchando) return
    setEscuchando(true)
    try {
      await escuchar(t => { setTexto(t); entradaRef.current?.focus() }, msg => alert(msg))
    } finally {
      setEscuchando(false)
    }
  }

  const noServidas = conversaciones.filter(c => c.ultima?.tipo === 'respuesta'
    && !c.ultima.exactos.length && !c.ultima.transformables.length).length
  const esp = actual.ultima?.especificacion
  const vacio = actual.mensajes.length === 0
  const previa = vacio && texto.trim() ? interpretarTexto(texto) : null

  return (
    <div className="app">
      <header className="cabecera">
        <div className="marca">
          <span className="logo-bobina" aria-hidden />
          <span className="logo-texto">INOX<span className="punto">·</span>STOCK</span>
          <span className="sublogo">Asistente de inventario<br />comercial · Acero inoxidable</span>
        </div>
        <div className="franjas" aria-hidden />
        <div className="acciones">
          <span className="estado" title="Consultas de esta sesión para las que no había stock ni transformación posible">
            Demanda no servida: <b>{noServidas}</b>
          </span>
          <label className="interruptor" title="Leer en voz alta cada respuesta del asistente">
            <input type="checkbox" checked={vozActiva}
              onChange={e => { setVozActiva(e.target.checked); window.speechSynthesis?.cancel() }} />
            <span className="interruptor-pista" aria-hidden />
            Leer respuestas en voz alta
          </label>
          <button className="nueva" onClick={nuevaConsulta}>+ Nueva consulta</button>
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
              onClick={() => { setActual(c); setDetalle(null) }}>
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
              <div className="inicio-nombre">
                {previa && [previa.grado, previa.acabado ?? previa.opciones.acabado?.join('/'), previa.formato].filter(Boolean).join(' · ')}
              </div>
              <h1>¿Qué quieres buscar?</h1>
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
                    {m.respuesta?.especificacion && <Acero esp={m.respuesta.especificacion} id={i} />}
                    {m.respuesta && <Resultados r={m.respuesta} onAbrir={setDetalle} />}
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

          <form className="entrada" onSubmit={e => { e.preventDefault(); enviar(texto) }}>
            <input ref={entradaRef} value={texto} onChange={e => setTexto(e.target.value)}
              placeholder="Escribe o dicta: grado, espesor, formato…"
              aria-label="Escribe tu petición" disabled={pensando} />
            <button type="button" className={`microfono ${escuchando ? 'escuchando' : ''}`} onClick={dictar}
              title="Dictar la petición" aria-pressed={escuchando}>
              <span className="microfono-icono" aria-hidden>🎙</span>
              {escuchando ? 'Escuchando…' : 'Hablar'}
            </button>
            <button type="submit" className="icono" title="Enviar" disabled={pensando || !texto.trim()}>→</button>
          </form>
          <Casillas texto={texto} base={esp} />
        </main>
      </div>

      {detalle && <Detalle item={detalle} onCerrar={() => setDetalle(null)} />}
    </div>
  )
}

function Resultados({ r, onAbrir }) {
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
      {r.exactos?.map(b => <Tarjeta key={b.id} tipo="exacto" item={b} onClick={() => onAbrir({ tipo: 'exacto', item: b })} />)}
      {r.transformables?.map(t => <Tarjeta key={t.id} tipo="transformable" item={t} onClick={() => onAbrir({ tipo: 'transformable', item: t })} />)}
      {r.alternativas?.map(b => <Tarjeta key={b.id} tipo="alternativa" item={b} onClick={() => onAbrir({ tipo: 'alternativa', item: b })} />)}
    </div>
    </>
  )
}
