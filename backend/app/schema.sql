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
                       CHECK (estado IN ('disponible', 'reservado', 'bloqueado'))  -- no viene en el Excel
);

CREATE INDEX idx_busqueda ON bultos (estado, formato, espesor_mm);