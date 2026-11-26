# Demo de reportes

Las compras son ficticias. Los bultos, grados, acabados, medidas y pesos salen
del Excel del reto. El plan distribuye compras de chapas, bobinas y flejes
durante ocho semanas y agota algunas combinaciones en la semana actual.

Desde la raíz, con el entorno virtual activado:

```bash
python -m demo_reportes
```

La demo se abre en `http://127.0.0.1:5174/`. El backend de la demo usa el
puerto 8011 y lee exclusivamente `generados/inventario-demo.db`. En la app,
abre **Reportes** para ver los agotados y **Reporte semanal de compras** para
ver las compras y las tendencias.

`python -m demo_reportes --solo-generar` crea la base y los cuatro JSON sin
levantar servidores. Las fechas relativas se calculan en la primera
generación. Las siguientes ejecuciones conservan la base de la demo.

Para quitar la simulación, detén la demo con Ctrl+C y elimina
`demo_reportes/generados/`. La carpeta `demo_reportes/` incluye también el plan
y el lanzador, por si quieres retirar toda la demo del proyecto.
