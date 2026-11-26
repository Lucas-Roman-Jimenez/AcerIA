export function descargarJson(datos, nombre) {
  const contenido = JSON.stringify(datos, null, 2)
  const url = URL.createObjectURL(new Blob([contenido], { type: 'application/json' }))
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  enlace.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
