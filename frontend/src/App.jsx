import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, resumenStock } from './api.js'
import { escuchar, leerEnAlto } from './voz.js'
import { Panel } from './Panel.jsx'
import { Tarjeta, Detalle } from './Tarjetas.jsx'

const SUGERENCIAS = [
  { tipo: 'Chapa', texto: 'Chapa brillante de 2 mm, 1000 × 2000' },
  { tipo: 'Bobina', texto: 'Rollo de inox marino de 1,5 mm' },
  { tipo: 'Fleje', texto: 'Tira de 316L de 300 mm de ancho' },
  { tipo: 'Dúplex', texto: 'Dúplex en caliente de 6 mm' },
]

const nuevoId = () => `c-${Date.now().toString(36)}`

export default function App() {
  const [conversaciones, setConversaciones] = useState([])
  const [actual, setActual] = useState(() => ({ id: nuevoId(), mensajes: [], ultima: null }))
  const [texto, setTexto] = useState('')
  const [pensando, setPensando] = useState(false)
  const [vozActiva, setVozActiva] = useState(false)
  const [detalle, setDetalle] = useState(null)
  const [stock, setStock] = useState([])
  const finRef = useRef(null)

  useEffect(() => { resumenStock().then(setStock).catch(() => setStock([])) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [actual.mensajes, pensando])

  const guardar = conv => {
    setActual(conv)
    setConversaciones(cs => [conv, ...cs.filter(c => c.id !== conv.id)])
  }

  async function enviar(msg, conv = actual) {
    const limpio = msg.trim()
    if (!limpio || pensando) return
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
              onClick={() => { setActual(c); setDetalle(null) }}>
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
                  {SUGERENCIAS.map(s => (
                    <button key={s.texto} className="sugerencia" onClick={() => enviar(s.texto)}>
                      <span className="sug-tipo">{s.tipo}</span>
                      {s.texto}
                    </button>
                  ))}
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
                    {m.respuesta && <Resultados r={m.respuesta} onAbrir={setDetalle} />}
                  </div>
                ))}
                {pensando && <div className="mensaje asistente pensando"><p>Pensando<span className="puntos" /></p></div>}
                <div ref={finRef} />
              </div>
              <Panel esp={esp} onCorregir={enviar} deshabilitado={pensando} />
            </section>
          )}

          <form className="entrada" onSubmit={e => { e.preventDefault(); enviar(texto) }}>
            <input value={texto} onChange={e => setTexto(e.target.value)} placeholder="«rollo de inox marino de 1,5 mm»"
              aria-label="Escribe tu petición" disabled={pensando} />
            <button type="button" className="icono" title="Hablar"
              onClick={() => escuchar(t => setTexto(t), msg => alert(msg))}>🎙</button>
            <button type="submit" className="icono" title="Enviar" disabled={pensando || !texto.trim()}>→</button>
          </form>
        </main>
      </div>

      {detalle && <Detalle item={detalle} onCerrar={() => setDetalle(null)} />}
    </div>
  )
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
