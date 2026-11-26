import { useEffect, useRef, useState } from 'react'

// Cabecera con los vídeos de la acería: muestra uno a todo el ancho y pasa al siguiente cada 30 s
// con un fundido. Cada vídeo tiene su encuadre: con la cabecera baja se enseña la franja más interesante. Las rayitas de abajo a la derecha indican cuál se ve y permiten cambiarlo.
export const VIDEOS_CABECERA = [
  { src: '/video/tira-a.mp4', titulo: 'Planta siderúrgica', encuadre: '50% 55%' },
  { src: '/video/cabecera.mp4', titulo: 'Laminación en caliente', encuadre: '50% 62%' },
  { src: '/video/tira-b.mp4', titulo: 'Instalaciones industriales', encuadre: '50% 58%' },
]
const CADA_MS = 30000

export function CabeceraVideos() {
  const [actual, setActual] = useState(0)
  const videos = useRef([])

  // Cambio automático cada 30 s; si se elige uno a mano, el contador vuelve a empezar desde ahí.
  useEffect(() => {
    const id = setTimeout(() => setActual(a => (a + 1) % VIDEOS_CABECERA.length), CADA_MS)
    return () => clearTimeout(id)
  }, [actual])

  // El que entra empieza desde el principio; los demás se pausan para no gastar recursos.
  useEffect(() => {
    videos.current.forEach((v, i) => {
      if (!v) return
      if (i === actual) { v.currentTime = 0; v.play().catch(() => {}) }
      else setTimeout(() => v.pause(), 1200)
    })
  }, [actual])

  return (
    <header className="cabecera-videos">
      {VIDEOS_CABECERA.map((v, i) => (
        <video key={v.src} ref={el => { videos.current[i] = el }} className={i === actual ? 'visible' : ''}
          style={{ objectPosition: v.encuadre }} src={v.src} muted loop playsInline autoPlay={i === 0} preload={i === 0 ? 'auto' : 'metadata'} aria-hidden />
      ))}
      <div className="cabecera-videos-velo" aria-hidden />
      <div className="cabecera-videos-selector" role="tablist" aria-label="Vídeo de la cabecera">
        {VIDEOS_CABECERA.map((v, i) => (
          <button key={v.src} type="button" role="tab" aria-selected={i === actual} aria-label={v.titulo} title={v.titulo}
            className={i === actual ? 'activo' : ''} onClick={() => setActual(i)}>
            {i === actual && <span className="cabecera-videos-progreso" style={{ animationDuration: `${CADA_MS}ms` }} />}
          </button>
        ))}
      </div>
    </header>
  )
}
