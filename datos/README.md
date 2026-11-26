# datos/ — Lucas (P4)

## Datos respaldados por los archivos disponibles

- `catalogo.json` recoge las combinaciones observadas en la hoja `DATA` con
  los campos y la normalización del backend. Cada medida se registra como
  un intervalo de un solo valor para conservar el par observado de espesor y
  ancho. Las 41 fichas técnicas de AcerIA aportan designaciones y
  aplicaciones. Cada ficha y aplicación registra su archivo y página.
- `glosario.json` recoge las equivalencias documentadas de voz, el código
  `N1` del Word, las designaciones MAT y la denominación `18/8` de MAT 120.

El intérprete carga ambos archivos por defecto. Las fichas consultadas
carecen de una tabla de fabricación por espesor, ancho, acabado y formato.
Por eso el intérprete valida los códigos y deja que el buscador compruebe
si hay una coincidencia o una transformación para las medidas pedidas.

## Nomenclatura de los grados

En `catalogo.json`, `nomenclatura_grados.grados` usa una clave por designación
EN. Es la referencia para mostrar los grados en el catálogo. Las fichas
relacionadas conservan la designación comercial y el UNS publicado. El código
MAT remite a la entrada de `fichas`, donde están el archivo y la página.
`otras_fuentes` incluye referencias directas a la web de AcerIA.

`designaciones_inventario` conserva lo que figura en la columna AISI de la hoja
DATA. Un bulto con dos certificaciones conserva ambas, como `1.4301/1.4307`.
El código `1.4310Mo` con etiqueta `301` figura en el inventario y queda registrado
en `codigos_inventario_sin_validacion_en` hasta disponer de respaldo documental.

La lista raíz `grados` contiene los códigos que acepta el intérprete. El glosario
resuelve las denominaciones de voz y los códigos MAT. Un alias comercial puede
apuntar a varias designaciones EN. Para identificar un bulto en pantalla,
usa su campo `euronorma` cuando esté documentado y conserva las dos designaciones
si tiene doble certificación. Por ejemplo, la entrada «316L» puede referirse
a EN 1.4404, 1.4432 o 1.4435.

## Normalizar una copia del inventario

Con `openpyxl` instalado en el entorno de importación:

```bash
python -m datos.importar_inventario "/ruta/al/inventario.xlsx" datos/inventario.json
```

El importador conserva encabezados y textos, convierte el formato decimal del
Excel y trata `-` como ausente en las columnas numéricas. La copia generada
queda local en `datos/inventario.json`. La carga y el esquema que consume el
buscador se gestionan en el backend.
