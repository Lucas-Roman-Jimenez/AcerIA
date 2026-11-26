-- Esquema del inventario de AcerIA (muestra IndesIAhack 2026)
-- Unidades: mm y kg. Un valor que no viene en el Excel se guarda como NULL, nunca inventado.

DROP TABLE IF EXISTS bultos;

CREATE TABLE bultos (
    id                 TEXT PRIMARY KEY,         -- columna ID
    peso_kg            REAL NOT NULL,            -- Weight
    aisi               TEXT,                     -- AISI tal cual, p. ej. '304L/304' (doble certificado)
    euronorma          TEXT,                     -- Euronorma normalizada, p. ej. '1.4301/1.4307'
    acabado            TEXT NOT NULL,            -- Euronorma Sup.Finish (cara superior)
    acabado_inf        TEXT,                     -- Euronorma Inf.Finish (cara inferior)
    codigo_acabado_inf TEXT,                     -- Inf. Finish (código interno, p. ej. '022')
    papel              INTEGER,                  -- Paper: 1 = Y, 0 = N
    espesor_mm         REAL NOT NULL,            -- Gauge (nominal)
    espesor_min_mm     REAL,                     -- Gauge Min (medido), NULL si '-'
    espesor_max_mm     REAL,                     -- Gauge Max (medido), NULL si '-'
    ancho_mm           REAL NOT NULL,            -- Width
    largo_mm           REAL,                     -- Lenght (solo chapas), NULL si '-'
    cantidad           INTEGER,                  -- Quantity (significado POR CONFIRMAR)
    formato            TEXT NOT NULL
                       CHECK (formato IN ('chapa', 'bobina', 'fleje')),   -- deducido, no viene en el Excel
    estado             TEXT NOT NULL DEFAULT 'disponible'
                       CHECK (estado IN ('disponible', 'reservado', 'bloqueado', 'vendido'))  -- no viene en el Excel; «vendido» lo pone POST /compras
);

CREATE INDEX idx_busqueda ON bultos (estado, formato, espesor_mm);

CREATE TABLE IF NOT EXISTS compras (
    id              TEXT PRIMARY KEY NOT NULL,
    comprada_en_ms  INTEGER NOT NULL,
    material_json   TEXT NOT NULL CHECK (json_valid(material_json)),
    cantidad        REAL NOT NULL CHECK (cantidad > 0),
    unidad          TEXT NOT NULL CHECK (unidad IN ('kg', 't', 'bultos', 'piezas'))
);

CREATE INDEX IF NOT EXISTS idx_compras_semana ON compras (comprada_en_ms, id);

-- Reservas del carrito (tarea 4): un bulto reservado no sale en /buscar ni en /chat y solo lo vende su titular.
-- Se vacía en cada arranque, como bultos: el carrito vive en el navegador y se pierde al reiniciar.
-- Una reserva vale mientras expira_en_ms > ahora; las caducadas se ignoran y se borran al escribir.
DROP TABLE IF EXISTS reservas;

CREATE TABLE reservas (
    bulto_id      TEXT PRIMARY KEY NOT NULL,   -- un bulto, como mucho una reserva
    titular       TEXT NOT NULL,               -- quién reserva: cabecera X-Carrito (provisional hasta el login)
    creada_en_ms  INTEGER NOT NULL,
    expira_en_ms  INTEGER NOT NULL CHECK (expira_en_ms > creada_en_ms)
);

CREATE INDEX idx_reservas_titular ON reservas (titular, expira_en_ms);
