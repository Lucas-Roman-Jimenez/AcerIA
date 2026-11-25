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

## Normalizar una copia del inventario

Con `openpyxl` instalado en el entorno de importación:

```bash
python -m datos.importar_inventario "/ruta/al/inventario.xlsx" datos/inventario.json
```

El importador conserva encabezados y textos, convierte el formato decimal del
Excel y trata `-` como ausente en las columnas numéricas. La copia generada
queda local en `datos/inventario.json`. La carga y el esquema que consume el
buscador se gestionan en el backend.
