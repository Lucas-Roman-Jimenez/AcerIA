import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, resumenStock } from './api.js'
import { escuchar, leerEnAlto } from './voz.js'
import { Panel } from './Panel.jsx'
import { Tarjeta, Detalle } from './Tarjetas.jsx'
import { Acero } from './Acero.jsx'
import { sugerir, completar } from './sugerencias.js'

const nuevoId = () => `c-${Date.now().toString(36)}`

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
  const finRef = useRef(null)
  const entradaRef = useRef(null)
  const dictadoRef = useRef(null)
  const sugerencias = sugerir(texto, stock)

  function elegir(s) {
    setTexto(completar(texto, s))
    entradaRef.current?.focus()
  }

  useEffect(() => { resumenStock().then(setStock).catch(() => setStock([])) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [actual.mensajes, pensando])
  useEffect(() => () => descartarDictado(dictadoRef), [])

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
    const base = { ...conv, mensajes: [...conv.mensajes, { rol: 'comercial', texto: limpio }] }
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
    cancelarDictado()
    window.speechSynthesis?.cancel()
    setActual({ id: nuevoId(), mensajes: [], ultima: null })
    setTexto('')
    setDetalle(null)
  }

  const sinServir = conversaciones.filter(c => c.ultima?.tipo === 'respuesta'
    && !c.ultima.exactos.length && !c.ultima.transformables.length).length
  const esp = actual.ultima?.especificacion
  const vacio = actual.mensajes.length === 0

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
          <span className="estado">Sin servir <b>{sinServir}</b></span>
          <button className="estado boton-texto" onClick={() => { setVozActiva(v => !v); window.speechSynthesis?.cancel() }}
            title="Leer las respuestas en voz alta">
            Voz: {vozActiva ? 'sí' : 'no'}
          </button>
          <button className="nueva" onClick={nuevaConsulta}>+ Nueva consulta</button>
        </div>
      </header>

      <div className="ticker" aria-label="Resumen de stock">
        <div className="ticker-pista">
          {[...stock, ...stock, ...stock].map((s, i) => (
            <span key={i} className="ticker-item">
              {s.etiqueta} <em>{s.bultos} bultos · {s.toneladas.toFixed(1).replace('.', ',')} t</em>
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
              {c.mensajes[0]?.texto}
            </button>
          ))}
        </aside>

        <main className="principal">
          {vacio ? (
            <section className="inicio">
              <div>
                <h1>¿Qué quieres buscar?</h1>
                <div className="sugerencias">
                  {sugerencias.map(s => (
                    <button key={s.tipo + s.texto} type="button" className="sugerencia" onClick={() => elegir(s)}>
                      <span className="sug-tipo">{s.tipo}</span>
                      {s.texto}
                      {s.detalle && <span className="sug-detalle">{s.detalle}</span>}
                    </button>
                  ))}
                  {!sugerencias.length && <p className="tenue">No hay nada parecido en stock ni en el catálogo. Sigue escribiendo.</p>}
                </div>
              </div>
              <div className="bobina" aria-hidden>
                <div className="bobina-cuerpo" />
                <div className="bobina-cara"><div className="bobina-hueco" /></div>
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
                    {m.respuesta?.especificacion && <Acero esp={m.respuesta.especificacion} id={i} />}
                    {m.respuesta && <Resultados r={m.respuesta} onAbrir={setDetalle} />}
                  </div>
                ))}
                {pensando && <div className="mensaje asistente pensando"><p>Pensando<span className="puntos" /></p></div>}
                <div ref={finRef} />
              </div>
              <Panel esp={esp} onCorregir={enviar} deshabilitado={pensando} />
            </section>
          )}

          {!vacio && texto.trim() && sugerencias.length > 0 && (
            <div className="chips">
              {sugerencias.map(s => (
                <button key={s.tipo + s.texto} type="button" className="chip" onClick={() => elegir(s)} title={s.detalle}>
                  {s.texto}
                </button>
              ))}
            </div>
          )}
          <form className="entrada" onSubmit={e => { e.preventDefault(); enviar(texto) }}>
            <input ref={entradaRef} value={texto} onChange={e => setTexto(e.target.value)} placeholder="«bobina 304 BA de 2 mm»"
              aria-label="Escribe tu petición" disabled={pensando} />
            <button type="button" className="icono" title={estadoDictado ? 'Detener dictado' : 'Hablar'}
              aria-label={estadoDictado ? 'Detener dictado' : 'Hablar'}
              aria-pressed={Boolean(estadoDictado)} disabled={pensando || estadoDictado === 'procesando'}
              onClick={alternarDictado}>{estadoDictado ? '■' : '🎙'}</button>
            <button type="submit" className="icono" title="Enviar" disabled={pensando || !texto.trim()}>→</button>
          </form>
          <div className="estado-dictado" role="status">
            {estadoDictado === 'escuchando' ? 'Escuchando…' :
              estadoDictado === 'procesando' ? 'Transcribiendo…' : mensajeDictado}
          </div>
        </main>
      </div>

      {detalle && <Detalle item={detalle} onCerrar={() => setDetalle(null)} />}
    </div>
  )
}

function descartarDictado(ref) {
  const dictado = ref.current
  ref.current = null
  dictado?.cancelar()
}

function Resultados({ r, onAbrir }) {
  const hay = r.exactos?.length || r.transformables?.length || r.alternativas?.length
  if (!hay) return null
  return (
    <div className="tarjetas">
      {r.exactos?.map(b => <Tarjeta key={b.id} tipo="exacto" item={b} onClick={() => onAbrir({ tipo: 'exacto', item: b })} />)}
      {r.transformables?.map(t => <Tarjeta key={t.id} tipo="transformable" item={t} onClick={() => onAbrir({ tipo: 'transformable', item: t })} />)}
      {r.alternativas?.map(b => <Tarjeta key={b.id} tipo="alternativa" item={b} onClick={() => onAbrir({ tipo: 'alternativa', item: b })} />)}
    </div>
  )
}
