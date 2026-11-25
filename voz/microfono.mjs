export function microfonoDisponible() {
  return typeof (globalThis.SpeechRecognition ?? globalThis.webkitSpeechRecognition)
    === "function";
}

/**
 * Inicia un dictado en español desde una acción del usuario.
 * La promesa devuelve el texto final para el mismo flujo que una petición escrita.
 */
export function transcribirVoz() {
  if (!microfonoDisponible()) {
    throw new Error("Este navegador no admite el reconocimiento de voz.");
  }

  const Reconocimiento = globalThis.SpeechRecognition ?? globalThis.webkitSpeechRecognition;
  const microfono = new Reconocimiento();
  microfono.lang = "es-ES";
  microfono.continuous = false;
  microfono.interimResults = false;

  let activo = true;
  const texto = new Promise((resolver, rechazar) => {
    let transcripcion = "";
    microfono.onresult = ({ results }) => {
      transcripcion = Array.from(results)
        .filter((resultado) => resultado.isFinal)
        .map((resultado) => resultado[0].transcript)
        .join(" ")
        .trim();
    };
    microfono.onerror = ({ error }) => {
      activo = false;
      rechazar(new Error(`Error de reconocimiento de voz: ${error}`));
    };
    microfono.onend = () => {
      activo = false;
      resolver(transcripcion);
    };
    try {
      microfono.start();
    } catch (error) {
      activo = false;
      rechazar(error);
    }
  });

  return {
    texto,
    detener() {
      if (activo) {
        microfono.stop();
      }
    },
  };
}
