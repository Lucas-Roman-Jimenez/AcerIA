// Abanico de planchas de acero inoxidable mate en la parte derecha de la portada (decorativo).
// Cada plancha gira un poco más que la anterior; el conjunto se balancea muy despacio.
const N = 9

export function Planchas() {
  return (
    <div className="planchas" aria-hidden>
      <div className="planchas-abanico">
        {Array.from({ length: N }, (_, i) => (
          <div key={i} className="plancha" style={{ '--i': i, '--n': N }} />
        ))}
      </div>
    </div>
  )
}
