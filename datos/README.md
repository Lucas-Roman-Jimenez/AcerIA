# datos/ — Lucas (P4)

Datos reales: `catalogo.json` y `glosario.json` usan el formato de
`datos_ejemplo/`. El inventario normalizado conserva las columnas de la hoja
`DATA`.

Cuando estén el catálogo y el glosario, hay que apuntar `RUTA_DATOS` de
`llm/catalogo.py` a esta carpeta.

## Normalizar una copia del inventario

Con `openpyxl` instalado en el entorno de importación:

```bash
python -m datos.importar_inventario "/ruta/al/inventario.xlsx" datos/inventario.json
```

El importador conserva encabezados y textos, convierte el formato decimal del
Excel y trata `-` como ausente en las columnas numéricas. La copia generada
queda local en `datos/inventario.json`. La carga y el esquema que consume el
buscador se gestionan en el backend.
