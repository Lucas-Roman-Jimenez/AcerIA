# reglas/ — Lucas (P4)

Reglas de transformación a partir del documento «Reglas de Transformación de
Bobinas y Chapas» de AcerIA.

`laminacion.permite_laminacion` comprueba las condiciones de laminación
del documento: bobina con acabado `2B` o `N1`, resultado `2B` y reducción
del espesor entre el 50 % y el 75 %, ambos incluidos.

Desde la raíz del proyecto:

```bash
python -m unittest reglas.test_laminacion -v
```
