# reglas/ — Lucas (P4)

Reglas de transformación a partir del documento «Reglas de Transformación de
Bobinas y Chapas» de AcerIA.

`motor.aplicar_reglas(bulto, objetivo, max_operaciones=2)` es el punto de
entrada acordado con el backend. Devuelve una lista de transformaciones
con acciones, resultado final, piezas y merma. Aplica corte y laminación,
y puede cortar después de laminar cuando el límite permite dos operaciones.

Los formatos permitidos, acabados de laminación y límites se cargan desde
`reglas.json` al importar el módulo. `NR.1` es el código del inventario
para el `N1` del Word. La laminación admite `2B` y `NR.1` y siempre
produce `2B`. Para el corte de bobina a chapa se estima el largo con el
peso, el espesor, el ancho y la densidad acordada de 7,9 kg/dm³. El
resultado marca esa estimación.

El motor necesita un espesor objetivo para proponer laminación y un largo
objetivo para proponer corte de bobina a chapa. Las alternativas por
sustitución de dimensiones son responsabilidad del backend.

Desde la raíz del proyecto:

```bash
python -m pytest tests/test_motor.py tests/test_laminacion.py tests/test_corte_sustitucion.py -q
```
