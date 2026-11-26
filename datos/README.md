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

En `catalogo.json`, `nomenclatura_grados.grados` agrupa el catálogo por código
AISI cuando existe una equivalencia documentada, como `304`, `301LN` o `316L`.
Los dúplex se muestran con su designación internacional documentada y se
conserva la EN cuando las fuentes no respaldan una equivalencia AISI.
`referencias_en` conserva las fichas y los UNS publicados. En el detalle,
el código MAT remite a AcerIA. El archivo y la página están en `fichas` y
`otras_fuentes` puede enlazar directamente a una publicación de AcerIA.

`designaciones_inventario` conserva lo que figura en la columna AISI de la hoja
DATA. Un bulto con dos certificaciones conserva ambas, como `1.4301/1.4307`.
El código `1.4310Mo` con etiqueta `301` figura en el inventario y queda registrado
en `codigos_inventario_sin_validacion_en` hasta disponer de respaldo documental.

La lista raíz `grados` contiene los códigos que acepta el intérprete. El glosario
resuelve las denominaciones de voz y los códigos MAT. Un alias comercial puede
apuntar a varias designaciones EN. Para identificar un bulto en pantalla,
usa su código AISI como título y su campo `euronorma` para acotar las fichas
MAT asociadas. Conserva los dos códigos si tiene doble certificación. Por
ejemplo, la entrada «316L» puede referirse a EN 1.4404, 1.4432 o 1.4435.

## Consultas de obra

`orientaciones_obra` registra las expresiones para identificar consultas
de fachada, cubierta, lluvia frecuente y humedad. Para fachada, la entrada
vincula al uso documentado «adornos arquitectónicos» en `usos`, con sus fichas
MAT y los grados EN. El asistente pregunta por el tipo de elemento y su
exposición antes de elegir un grado. La lluvia y la humedad tienen prioridad
si aparecen junto a «fachada» porque la aplicación de la ficha por sí sola
no acredita la aptitud en esas condiciones. Para la cubierta, la lluvia y
la humedad, la respuesta pide los datos que faltan.

## Normalizar una copia del inventario

Con `openpyxl` instalado en el entorno de importación:

```bash
python -m datos.importar_inventario "/ruta/al/inventario.xlsx" datos/inventario.json
```

El importador conserva encabezados y textos, convierte el formato decimal del
Excel y trata `-` como ausente en las columnas numéricas. La copia generada
queda local en `datos/inventario.json`. La carga y el esquema que consume el
buscador se gestionan en el backend.
