-- Esquema de Café Overflow. Los CHECK son red de seguridad de integridad;
-- las reglas de negocio se evalúan en la capa de negocio, no aquí.

CREATE TABLE productos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT    NOT NULL,
    precio_base  INTEGER NOT NULL CHECK (precio_base >= 0),
    stock        INTEGER NOT NULL CHECK (stock >= 0)
);

CREATE TABLE clientes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre             TEXT    NOT NULL,
    correo             TEXT    NOT NULL UNIQUE,
    nivel              TEXT    NOT NULL DEFAULT 'JUNIOR'
                       CHECK (nivel IN ('JUNIOR', 'MID', 'SENIOR')),
    devpoints          INTEGER NOT NULL DEFAULT 0 CHECK (devpoints >= 0),
    acumulado_compras  INTEGER NOT NULL DEFAULT 0 CHECK (acumulado_compras >= 0)
);

CREATE TABLE pedidos (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id           INTEGER NOT NULL REFERENCES clientes(id),
    estado               TEXT    NOT NULL
                         CHECK (estado IN ('PENDIENTE_DE_PAGO', 'EN_PREPARACION', 'LISTO', 'ENTREGADO')),
    total                INTEGER NOT NULL CHECK (total >= 0),
    devpoints_canjeados  INTEGER NOT NULL DEFAULT 0 CHECK (devpoints_canjeados >= 0),
    fecha                TEXT    NOT NULL
);

CREATE TABLE items_pedido (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id        INTEGER NOT NULL REFERENCES pedidos(id),
    producto_id      INTEGER NOT NULL REFERENCES productos(id),
    cantidad         INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario  INTEGER NOT NULL CHECK (precio_unitario >= 0)
);

-- Un cliente no puede tener dos pedidos por pagar (respaldo de RN-4 en datos).
CREATE UNIQUE INDEX ux_pedido_pendiente_por_cliente
    ON pedidos(cliente_id)
    WHERE estado = 'PENDIENTE_DE_PAGO';