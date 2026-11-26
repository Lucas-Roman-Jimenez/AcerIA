import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, resumenStock, consultarValores, venderCarrito, reservarBultos, liberarBulto, vaciarReservas } from './api.js'
import { escuchar, leerEnAlto } from './voz.js'
import { Tarjeta, Detalle, Comparador } from './Tarjetas.jsx'
import { Acero } from './Acero.jsx'
import { Casillas } from './Casillas.jsx'
import { interpretarTexto, detectarConsulta, detectarUso, detectarUsoDeObra, recomendarPorUso } from './previa.js'
import { Consulta, textoConsulta } from './Consulta.jsx'
import { Uso, construirUso } from './Uso.jsx'
import { Cercanos } from './Cercanos.jsx'
import { sugerirCorreccion } from './sugerir.js'
import { pideBorrarConsulta, pideQuitar, frasesQuitar, textoNoSeleccionado } from './quitar.js'
import { Flujo, Carrito, analizar, textoAnalisis } from './Flujo.jsx'
import { Reportes } from './Reportes.jsx'
import { gradoVisible } from './grados.js'
import { Escritura } from './Escritura.jsx'
import { Planchas } from './Planchas.jsx'

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

// ID aleatorio (128 bits): con Date.now() se podía adivinar y escribir en la conversación de otro.
// getRandomValues funciona también fuera de HTTPS (randomUUID no).
const nuevoId = () => `c-${Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')}`
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
  const [carrito, setCarrito] = useState([])
  const [verCarrito, setVerCarrito] = useState(false)
  const [avisoInicio, setAvisoInicio] = useState(null)
  const [vistaReporte, setVistaReporte] = useState(null)
  const verReporte = vistaReporte !== null
  // Respuesta que acaba de llegar: es la única que se escribe letra a letra
  const [fresco, setFresco] = useState(null)
  const actualRef = useRef(actual)
  actualRef.current = actual
  const finRef = useRef(null)
  const entradaRef = useRef(null)
  const dictadoRef = useRef(null)

  useEffect(() => { resumenStock().then(setStock).catch(() => setStock([])) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [actual.mensajes, pensando, verReporte])
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
        setTexto(transcripcion)
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

  // Si el usuario ha salido a otro chat mientras se esperaba la respuesta, esta solo se guarda en «Recientes».
  const guardar = conv => {
    const ultimo = conv.mensajes.at(-1)
    if (ultimo?.rol === 'asistente') setFresco(ultimo)
    setActual(a => (a.id === conv.id ? conv : a))
    setConversaciones(cs => [conv, ...cs.filter(c => c.id !== conv.id)])
  }

  async function enviar(msg, conv = actual, { sinCorregir = false, mostrado } = {}) {
    const limpio = msg.trim()
    if (!limpio || pensando) return
    cancelarDictado()
    setTexto('')
    setAvisoInicio(null)
    const base = { ...conv, creada: conv.creada ?? new Date(), mensajes: [...conv.mensajes, { rol: 'comercial', texto: mostrado ?? limpio }] }
    // Erratas («bbbobina»): se pregunta antes de buscar, sin llamar al backend.
    const usoDeObra = detectarUsoDeObra(limpio)
    const sugerencia = !sinCorregir && !usoDeObra && sugerirCorreccion(limpio)
    const entendido = sugerencia?.corregido ?? limpio
    // «Borra la consulta», «empezar de nuevo», «olvídalo»…: se vuelve a la página principal.
    if (!sinCorregir && pideBorrarConsulta(entendido)) {
      salir()
      setAvisoInicio('He borrado la consulta. Puedes escribir una petición nueva.')
      return
    }
    // «Quita el espesor», «bórrame el 2B»…: solo se quita lo que está seleccionado.
    const quitar = sinCorregir ? null : pideQuitar(entendido, conv.ultima?.especificacion)
    if (quitar?.quitar?.length) return enviar(frasesQuitar(quitar.quitar).backend, conv, { sinCorregir: true, mostrado: limpio })
    if (quitar) {
      guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: textoNoSeleccionado(quitar.noSeleccionados) }] })
      return
    }
    // Si con las erratas corregidas es una pregunta (por lo que hay o por el uso), se responde directamente.
    const pregunta = sugerencia && (detectarUso(sugerencia.corregido) || detectarConsulta(sugerencia.corregido))
    if (pregunta) return enviar(sugerencia.corregido, conv, { sinCorregir: true, mostrado: limpio })
    if (sugerencia) {
      const lista = sugerencia.cambios.map(([mal, bien]) => `«${bien}» en vez de «${mal}»`).join(', ')
      const textoBot = `No estoy seguro de haberte entendido. ¿Querías decir ${lista}?`
      guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: textoBot, correccion: { ...sugerencia, original: limpio } }] })
      if (vozActiva) leerEnAlto(textoBot)
      return
    }
    guardar(base)
    setPensando(true)
    try {
      const recomendacion = !usoDeObra && detectarUso(limpio) && recomendarPorUso(limpio)
      // Lo que pregunta no aparece en las fichas técnicas: no se inventa (RNF-01), se manda a un comercial y se empieza de cero.
      if (recomendacion && !recomendacion.grados.length) {
        const textoBot = `Lo que preguntas («${limpio}») no aparece en las fichas técnicas de AcerIA, así que no puedo recomendarte nada fiable. Pregúntalo a un comercial. Mientras, puedes escribir una petición nueva.`
        nuevaConsulta()
        setConversaciones(cs => cs.filter(c => c.id !== base.id))
        setAvisoInicio(textoBot)
        if (vozActiva) leerEnAlto(textoBot)
        return
      }
      if (recomendacion) {
        const { valores } = await consultarValores('grado', filtrosConsulta('grado', limpio, conv.ultima?.especificacion))
        const { textoBot, uso } = construirUso(limpio, recomendacion, valores)
        guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: textoBot, uso, reintento: limpio }] })
        if (vozActiva) leerEnAlto(textoBot)
        return
      }
      const pregunta = detectarConsulta(limpio)
      if (pregunta && !usoDeObra) {
        await responderConsulta(limpio, pregunta, base, conv, false)
        return
      }
      const r = await enviarMensaje(conv.id, limpio)
      const analisis = r.tipo !== 'error' && r.especificacion ? await analizar(r).catch(() => null) : null
      // El backend descarta sin aviso los valores que no existen: si el mensaje traía medidas o números
      // y no se ha entendido ningún dato, también cuenta como «todo incorrecto».
      const e = r.especificacion ?? {}
      const sinNingunDato = r.tipo !== 'error' && !e.uso && !conv.ultima?.especificacion
        && ['grado', 'acabado', 'formato', 'espesor_mm', 'ancho_mm', 'largo_mm'].every(k => e[k] == null)
        && !Object.keys(e.opciones ?? {}).length && /\d/.test(limpio)
      if (analisis?.estado === 'todo_mal' || sinNingunDato) {
        nuevaConsulta()
        setConversaciones(cs => cs.filter(c => c.id !== base.id))
        setAvisoInicio(`Ningún dato de «${limpio}» existe o está en stock${analisis?.avisos?.length ? ` (${analisis.avisos.join(' ')})` : ''}. Escribe una nueva petición.`)
        return
      }
      const textoBot = r.tipo === 'error' ? r.error
        : analisis && !r.opciones?.length ? textoAnalisis(analisis) : (r.pregunta ?? r.texto)
      const msgBot = { rol: 'asistente', texto: textoBot, respuesta: r, analisis, error: r.tipo === 'error', reintento: limpio }
      guardar({ ...base, mensajes: [...base.mensajes, msgBot], ultima: r })
      if (vozActiva && r.tipo !== 'error') leerEnAlto(textoBot)
    } catch (e) {
      const msgErr = { rol: 'asistente', texto: `No he podido responder (${e.message}). Puedes reintentar o reformular la petición.`, error: true, reintento: limpio }
      guardar({ ...base, mensajes: [...base.mensajes, msgErr] })
    } finally {
      setPensando(false)
    }
  }

  // «¿Qué espesores hay de bobina?»: valores reales del stock, cada uno pulsable.
  async function responderConsulta(texto, pregunta, base, conv, propia = true) {
    if (propia) { guardar(base); setPensando(true) }
    try {
      const c = await consultarValores(pregunta.campo, filtrosConsulta(pregunta.campo, texto, conv.ultima?.especificacion))
      const textoBot = textoConsulta(c, interpretarTexto(texto).avisos)
      guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: textoBot, consulta: c, reintento: texto }] })
      if (vozActiva) leerEnAlto(textoBot)
    } catch (e) {
      if (!propia) throw e
      guardar({ ...base, mensajes: [...base.mensajes, { rol: 'asistente', texto: `No he podido responder (${e.message}). Puedes reintentar.`, error: true, reintento: texto }] })
    } finally {
      if (propia) setPensando(false)
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

  // Salir: desde cualquier punto del flujo se vuelve a la pantalla de inicio limpia. El carrito se conserva.
  function salir() {
    setDemo(null)
    setVerCarrito(false)
    setVerComparacion(false)
    setVistaReporte(null)
    setAvisoInicio(null)
    nuevaConsulta()
  }

  // Al añadir un material al carrito se reserva (si otro comercial lo tiene, lanza el error y la tarjeta
  // lo muestra) y se empieza un chat nuevo para la siguiente petición. Al quitarlo se suelta la reserva.
  async function alternarCarrito(tipo, item) {
    if (carrito.some(c => c.item.id === item.id)) {
      quitarDelCarrito(item.id)
      return
    }
    // Si otro comercial ya lo tiene reservado (o se ha vendido), se avisa en el chat y no se añade.
    try {
      await reservarBultos([item.id])
    } catch (e) {
      const conv = actualRef.current
      guardar({ ...conv, mensajes: [...conv.mensajes, { rol: 'asistente', texto: e.message, error: true }] })
      return
    }
    setCarrito(cs => cs.some(c => c.item.id === item.id) ? cs : [...cs, { tipo, item }])
    nuevaConsulta()
    const b = item.origen ?? item
    setAvisoInicio(`Añadido al carrito: bulto ${item.id}${b.grado ? ` (${[b.grado, b.acabado, b.formato].filter(Boolean).join(' ')})` : ''}. Puedes hacer una petición nueva.`)
  }

  function quitarDelCarrito(id) {
    setCarrito(cs => cs.filter(c => c.item.id !== id))
    liberarBulto(id)
  }

  function vaciarCarrito() {
    setCarrito([])
    vaciarReservas()
  }

  function alternarComparar(tipo, item) {
    setComparar(cs => cs.some(c => c.item.id === item.id)
      ? cs.filter(c => c.item.id !== item.id)
      : [...cs, { tipo, item }].slice(-4))
  }

  const anadirATexto = f => enviar(f)

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

  const esp = actual.ultima?.especificacion
  const vacio = actual.mensajes.length === 0
  const totalBultos = stock.reduce((n, s) => n + s.bultos, 0)
  const hoy = new Date().toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })
  const previa = vacio && texto.trim() ? interpretarTexto(texto) : null


  return (
    <div className={`app ${verReporte ? 'en-reportes' : vacio ? 'portada' : ''}`}>
      <aside className="lateral">
        <button type="button" className="marca" onClick={salir} title="Volver al inicio">
          <img className="logo-aceria" src="/logo-aceria.svg" alt="AcerIA" width="46" height="46" />
          <span className="logo-texto">ACERIA</span>
        </button>

        <nav className="lateral-menu" aria-label="Principal">
          <button type="button" className={`lateral-item ${verReporte ? '' : 'destacado'}`} onClick={salir}>
            <Icono nombre="nueva" /> Nueva consulta
          </button>
          <button type="button" className="lateral-item" onClick={() => { setVistaReporte(null); pasoDemo(0) }}
            disabled={pensando || demo !== null}
            title="Reproduce la conversación de la demo paso a paso">
            <Icono nombre="demo" /> Demo guiada
          </button>
          <button type="button" className="lateral-item carrito-cabecera" onClick={() => setVerCarrito(true)}>
            <Icono nombre="carrito" /> Carrito
            {carrito.length > 0 && <span className="contador">{carrito.length}</span>}
          </button>
          <button type="button" className={`lateral-item ${verReporte ? 'destacado' : ''}`}
            aria-current={verReporte ? 'page' : undefined}
            onClick={() => { cancelarDictado(); setVistaReporte('inventario') }}>
            <Icono nombre="reporte" /> Reportes
          </button>
          {!vacio && (
            <button type="button" className="lateral-item salir-flujo" onClick={salir}
              title="Salir de esta consulta y volver al inicio. El carrito se conserva.">
              <Icono nombre="salir" /> Salir de la consulta
            </button>
          )}
        </nav>


        <div className="lateral-lista">
          {conversaciones.length === 0 && <p className="lateral-vacio">Aquí aparecerán tus consultas.</p>}
          {conversaciones.map(c => (
            <button key={c.id} className={`reciente ${c.id === actual.id ? 'activa' : ''}`}
              onClick={() => { cancelarDictado(); setVistaReporte(null); setFresco(null); setActual(c); setDetalle(null) }}>
              <span className="reciente-texto">{c.mensajes[0]?.texto}</span>
              {c.creada && <span className="reciente-hora">{cuando(c.creada)}</span>}
            </button>
          ))}
        </div>
        <div className="lateral-pie">
          <label className="interruptor" title="Leer en voz alta cada respuesta del asistente">
            <input type="checkbox" checked={vozActiva}
              onChange={e => { setVozActiva(e.target.checked); window.speechSynthesis?.cancel() }} />
            <span className="interruptor-pista" aria-hidden />
            Leer respuestas en voz alta
          </label>
        </div>
      </aside>

      <div className="contenido">
      <div className="barra-superior">
        <div className="ticker" aria-label="Resumen de stock">
          <div className="ticker-pista">
            {[...stock, ...stock, ...stock].map((s, i) => (
              <span key={i} className="ticker-item">
                {s.etiqueta} <em>{plural(s.bultos, 'bulto')} · {s.toneladas.toFixed(1).replace('.', ',')} t</em>
              </span>
            ))}
          </div>
        </div>
      </div>

      {verReporte ? (
        <Reportes vista={vistaReporte} onCambiarVista={setVistaReporte} />
      ) : (
        <main className="principal">
          {vacio && <Planchas />}
          {vacio ? (
            <section className="inicio">
              <div className="inicio-texto">
                <Escritura as="h1" texto="¿Qué quieres buscar?" />
                <div className="inicio-nombre">
                  {previa && [gradoVisible(previa.grado), previa.acabado ?? previa.opciones.acabado?.join('/'), previa.formato].filter(Boolean).join(' · ')}
                </div>
                {avisoInicio && <p className="aviso-inicio" role="alert">{avisoInicio}</p>}
              </div>
            </section>
          ) : (
            <section className="conversacion">
              <div className="mensajes">
                {actual.mensajes.map((m, i) => (
                  <div key={i} className={`mensaje ${m.rol} ${m.error ? 'error' : ''}`}>
                    {m === fresco && !m.error
                      ? <Escritura as="p" texto={m.texto} inicio={200} velocidad={3.5} />
                      : <p>{m.texto}</p>}
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
                    {m.correccion && i === actual.mensajes.length - 1 && (
                      <div className="opciones">
                        <button type="button" className="opcion activa" disabled={pensando}
                          onClick={() => enviar(m.correccion.corregido, actual, { sinCorregir: true })}>
                          Sí: «{m.correccion.corregido}»
                        </button>
                        <button type="button" className="opcion" disabled={pensando}
                          onClick={() => enviar(m.correccion.original, actual, { sinCorregir: true })}>
                          No, buscar tal cual
                        </button>
                      </div>
                    )}
                    {m.consulta && <Consulta consulta={m.consulta} deshabilitado={pensando} onElegir={anadirATexto} />}
                    {m.uso && <Uso uso={m.uso} deshabilitado={pensando} onElegir={anadirATexto} />}
                    {m.respuesta?.especificacion && <Acero esp={m.respuesta.especificacion} id={i} />}
                    {m.analisis && (
                      <Flujo analisis={m.analisis} activo={i === actual.mensajes.length - 1} onEnviar={enviar}
                        onCancelar={nuevaConsulta} carrito={carrito} onCarrito={alternarCarrito}
                        onAbrir={setDetalle} deshabilitado={pensando} />
                    )}
                    {m.respuesta && !m.analisis && (
                      <Resultados r={m.respuesta} onAbrir={setDetalle}
                        comparar={comparar} onComparar={alternarComparar} />
                    )}
                    {i === actual.mensajes.length - 1 && !m.analisis && m.respuesta?.tipo === 'respuesta' && m.respuesta.especificacion
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
              <svg className="microfono-icono" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0" /><path d="M12 17.5V21" />
              </svg>
              {/* Solo icono en reposo; mientras dicta se dice qué está pasando */}
              {estadoDictado === 'escuchando' ? <span className="microfono-estado">Escuchando…</span>
                : estadoDictado === 'procesando' ? <span className="microfono-estado">Transcribiendo…</span>
                : <span className="solo-lectores">Hablar</span>}
            </button>
            <button type="submit" className="icono enviar" title="Enviar (Intro)" aria-label="Enviar" disabled={pensando || !texto.trim()}>
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M19 5v7a3 3 0 0 1-3 3H6" /><path d="m10 11-4 4 4 4" /></svg>
            </button>
          </form>
          <div className="estado-dictado" role="status">{estadoDictado ? '' : mensajeDictado}</div>
          <Casillas texto={texto} base={esp} onElegir={enviar} deshabilitado={pensando}
            onQuitar={k => { const f = frasesQuitar([k]); enviar(f.backend, actual, { sinCorregir: true, mostrado: f.visible }) }} />
        </main>
      )}
      </div>

      {detalle && <Detalle item={detalle} esp={esp} onCerrar={() => setDetalle(null)} />}
      {verCarrito && (
        <Carrito carrito={carrito} onQuitar={quitarDelCarrito}
          onVaciar={vaciarCarrito} onCerrar={() => setVerCarrito(false)}
          onVender={async ids => {
            const r = await venderCarrito(ids)
            setCarrito([])
            resumenStock().then(setStock).catch(() => {})     // la cinta de stock ya no los cuenta
            return r
          }} />
      )}
      {verComparacion && comparar.length > 1 && (
        <Comparador seleccion={comparar} onQuitar={t => alternarComparar(t.tipo, t.item)} onCerrar={() => setVerComparacion(false)} />
      )}
    </div>
  )
}

const ICONOS = {
  // Cuadrado con lápiz, como «Nuevo chat»
  nueva: <><path d="M11 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" /><path d="M17.6 3.6a1.9 1.9 0 0 1 2.8 2.8L12 14.8l-3.5.7.7-3.5Z" /></>,
  demo: <><rect x="3.5" y="3.5" width="17" height="17" rx="4" /><path d="M10 8.8v6.4l5.2-3.2Z" /></>,
  carrito: <><circle cx="9.5" cy="19.5" r="1.2" /><circle cx="17.5" cy="19.5" r="1.2" /><path d="M3 4h2.2l2.3 10.6a1.6 1.6 0 0 0 1.6 1.3h7.8a1.6 1.6 0 0 0 1.6-1.2L20 8H6" /></>,
  reporte: <><rect x="3.5" y="3.5" width="17" height="17" rx="4" /><path d="M8.5 16v-4" /><path d="M12 16V8" /><path d="M15.5 16v-2.5" /></>,
  salir: <><path d="M14 4h3.5A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14" /><path d="M10 16l-4-4 4-4" /><path d="M6 12h9" /></>,
}
function Icono({ nombre }) {
  return (
    <svg className="icono-lateral" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{ICONOS[nombre]}</svg>
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
