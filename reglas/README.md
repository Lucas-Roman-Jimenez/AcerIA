# reglas/ — Lucas (P4)

Reglas de transformación a partir del documento «Reglas de Transformación de
Bobinas y Chapas» de AcerIA.

`laminacion.permite_laminacion` comprueba las condiciones de laminación
del documento: bobina con acabado `2B` o `N1`, resultado `2B` y reducción
del espesor entre el 50 % y el 75 %, ambos incluidos.

`corte.cumple_condiciones_corte` comprueba los formatos y las dimensiones
conocidas. Si una bobina carece de largo, el chequeo de corte a chapa cubre
el formato y el ancho. La longitud utilizable y la merma requieren datos
adicionales.

`sustitucion.permite_sustituir_dimensiones` comprueba si se puede ofrecer una
chapa de ancho o largo alternativo cuando falta la medida exacta y coinciden
el grado, el acabado y el espesor.

Desde la raíz del proyecto:

```bash
python -m unittest discover -s reglas -v
```
