"""Implementación SQLite de los puertos de persistencia.

Solo lee y escribe entidades con SQL parametrizado; jamás evalúa reglas de
negocio. El dinero se guarda como entero (pesos) y se convierte a Decimal.
Cada operación abre su propia conexión: seguro con hilos y sin estado global.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from negocio.entidades import Cliente, ItemPedido, Pedido, Producto
from negocio.enums import EstadoPedido, NivelLealtad
from negocio.excepciones import (
    ClienteNoEncontradoError,
    CorreoDuplicadoError,
    DevPointsInsuficientesError,
    PedidoNoEncontradoError,
    PedidoPendienteError,
    StockInsuficienteError,
    TransicionEstadoInvalidaError,
)
from negocio.puertos import ClienteDAO, PedidoDAO, ProductoDAO


class _BaseSQLite:
    """Conexiones y pragmas compartidos por los DAO de SQLite."""

    def __init__(self, ruta_bd: str | Path):
        self._ruta = str(ruta_bd)

    @contextmanager
    def _transaccion(self):
        # Una conexión por operación: sin estado compartido entre hilos.
        conexion = sqlite3.connect(self._ruta, timeout=5.0)
        try:
            conexion.execute("PRAGMA foreign_keys = ON")
            conexion.execute("PRAGMA journal_mode = WAL")
            conexion.execute("PRAGMA busy_timeout = 5000")
            conexion.row_factory = sqlite3.Row
            # BEGIN IMMEDIATE al inicio: reserva la escritura y evita
            # abrir la transacción después de haber leído.
            conexion.execute("BEGIN IMMEDIATE")
            yield conexion
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    @contextmanager
    def _lectura(self):
        conexion = sqlite3.connect(self._ruta, timeout=5.0)
        try:
            conexion.execute("PRAGMA foreign_keys = ON")
            conexion.row_factory = sqlite3.Row
            yield conexion
        finally:
            conexion.close()


def _fila_a_producto(fila: sqlite3.Row) -> Producto:
    # El precio se guarda entero y se usa como Decimal (S-11).
    return Producto(
        id=fila["id"],
        nombre=fila["nombre"],
        precio_base=Decimal(fila["precio_base"]),
        stock=fila["stock"],
    )


def _fila_a_cliente(fila: sqlite3.Row) -> Cliente:
    return Cliente(
        id=fila["id"],
        nombre=fila["nombre"],
        correo=fila["correo"],
        nivel=NivelLealtad(fila["nivel"]),
        devpoints=fila["devpoints"],
        acumulado_compras=Decimal(fila["acumulado_compras"]),
    )


def _fila_a_item(fila: sqlite3.Row) -> ItemPedido:
    return ItemPedido(
        producto_id=fila["producto_id"],
        cantidad=fila["cantidad"],
        precio_unitario=Decimal(fila["precio_unitario"]),
    )


class SqliteProductoDAO(_BaseSQLite, ProductoDAO):
    """Productos del menú en SQLite."""

    def obtener_por_id(self, producto_id: int) -> Producto | None:
        with self._lectura() as conexion:
            fila = conexion.execute(
                "SELECT id, nombre, precio_base, stock FROM productos WHERE id = ?",
                (producto_id,),
            ).fetchone()
            return _fila_a_producto(fila) if fila is not None else None

    def listar_todos(self) -> list[Producto]:
        with self._lectura() as conexion:
            filas = conexion.execute(
                "SELECT id, nombre, precio_base, stock FROM productos ORDER BY id"
            ).fetchall()
            return [_fila_a_producto(f) for f in filas]


class SqliteClienteDAO(_BaseSQLite, ClienteDAO):
    """Clientes del programa de lealtad en SQLite."""

    def obtener_por_id(self, cliente_id: int) -> Cliente | None:
        with self._lectura() as conexion:
            fila = conexion.execute(
                "SELECT id, nombre, correo, nivel, devpoints, acumulado_compras"
                " FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
            return _fila_a_cliente(fila) if fila is not None else None

    def obtener_por_correo(self, correo: str) -> Cliente | None:
        with self._lectura() as conexion:
            fila = conexion.execute(
                "SELECT id, nombre, correo, nivel, devpoints, acumulado_compras"
                " FROM clientes WHERE correo = ?",
                (correo,),
            ).fetchone()
            return _fila_a_cliente(fila) if fila is not None else None

    def crear(self, cliente: Cliente) -> Cliente:
        with self._transaccion() as conexion:
            try:
                cursor = conexion.execute(
                    "INSERT INTO clientes (nombre, correo, nivel, devpoints,"
                    " acumulado_compras) VALUES (?, ?, ?, ?, ?)",
                    (
                        cliente.nombre,
                        cliente.correo,
                        cliente.nivel.value,
                        cliente.devpoints,
                        int(cliente.acumulado_compras),
                    ),
                )
            except sqlite3.IntegrityError:
                # La causa alcanzable es el correo repetido (UNIQUE).
                raise CorreoDuplicadoError("ese correo ya está registrado")
            cliente.id = cursor.lastrowid
            return cliente

    def actualizar(self, cliente: Cliente) -> None:
        with self._transaccion() as conexion:
            conexion.execute(
                "UPDATE clientes SET nombre = ?, nivel = ?, devpoints = ?,"
                " acumulado_compras = ? WHERE id = ?",
                (
                    cliente.nombre,
                    cliente.nivel.value,
                    cliente.devpoints,
                    int(cliente.acumulado_compras),
                    cliente.id,
                ),
            )


class SqlitePedidoDAO(_BaseSQLite, PedidoDAO):
    """Pedidos y operaciones transaccionales en SQLite."""

    def obtener_por_id(self, pedido_id: int) -> Pedido | None:
        with self._lectura() as conexion:
            return self._obtener_con(conexion, pedido_id)

    def listar(self, estado: EstadoPedido | None = None) -> list[Pedido]:
        with self._lectura() as conexion:
            if estado is None:
                filas = conexion.execute(
                    "SELECT id, cliente_id, estado, total,"
                    " devpoints_canjeados, fecha FROM pedidos ORDER BY id"
                ).fetchall()
            else:
                filas = conexion.execute(
                    "SELECT id, cliente_id, estado, total,"
                    " devpoints_canjeados, fecha FROM pedidos WHERE estado = ?"
                    " ORDER BY id",
                    (estado.value,),
                ).fetchall()
            if not filas:
                return []
            # Los ítems se traen en una sola consulta (evita N+1).
            marcadores = ", ".join("?" for _ in filas)
            filas_items = conexion.execute(
                "SELECT pedido_id, producto_id, cantidad, precio_unitario"
                f" FROM items_pedido WHERE pedido_id IN ({marcadores})"
                " ORDER BY pedido_id, id",
                [f["id"] for f in filas],
            ).fetchall()
            por_pedido: dict[int, list[ItemPedido]] = {}
            for fila_item in filas_items:
                por_pedido.setdefault(fila_item["pedido_id"], []).append(
                    _fila_a_item(fila_item)
                )
            return [
                self._armar_pedido(f, por_pedido.get(f["id"], [])) for f in filas
            ]

    def existe_pendiente(self, cliente_id: int) -> bool:
        with self._lectura() as conexion:
            fila = conexion.execute(
                "SELECT 1 FROM pedidos WHERE cliente_id = ? AND estado = ?"
                " LIMIT 1",
                (cliente_id, EstadoPedido.PENDIENTE_DE_PAGO.value),
            ).fetchone()
            return fila is not None

    def registrar_pedido_completo(
        self, pedido: Pedido, cliente: Cliente
    ) -> Pedido:
        with self._transaccion() as conexion:
            try:
                cursor = conexion.execute(
                    "INSERT INTO pedidos (cliente_id, estado, total,"
                    " devpoints_canjeados, fecha) VALUES (?, ?, ?, ?, ?)",
                    (
                        pedido.cliente_id,
                        pedido.estado.value,
                        int(pedido.total),
                        pedido.devpoints_canjeados,
                        (pedido.fecha or datetime.now()).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                # La causa alcanzable es el pedido pendiente duplicado.
                raise PedidoPendienteError(
                    "el cliente tiene un pedido pendiente de pago"
                )
            pedido_id = cursor.lastrowid
            for item in pedido.items:
                # Descuenta solo si queda stock suficiente (guarda anti-carrera).
                aplicado = conexion.execute(
                    "UPDATE productos SET stock = stock - ?"
                    " WHERE id = ? AND stock >= ?",
                    (item.cantidad, item.producto_id, item.cantidad),
                )
                if aplicado.rowcount != 1:
                    raise StockInsuficienteError(
                        "un producto no tiene stock suficiente"
                    )
                conexion.execute(
                    "INSERT INTO items_pedido (pedido_id, producto_id, cantidad,"
                    " precio_unitario) VALUES (?, ?, ?, ?)",
                    (
                        pedido_id,
                        item.producto_id,
                        item.cantidad,
                        int(item.precio_unitario),
                    ),
                )
            # Descuenta los puntos solo si el saldo alcanza (guarda anti-carrera).
            puntos = conexion.execute(
                "UPDATE clientes SET devpoints = devpoints - ?"
                " WHERE id = ? AND devpoints >= ?",
                (
                    pedido.devpoints_canjeados,
                    cliente.id,
                    pedido.devpoints_canjeados,
                ),
            )
            if puntos.rowcount != 1:
                raise DevPointsInsuficientesError(
                    "el cliente no tiene DevPoints suficientes para el canje"
                )
            return self._obtener_con(conexion, pedido_id)

    def avanzar_estado(
        self, pedido_id: int, origen: EstadoPedido, destino: EstadoPedido
    ) -> None:
        with self._transaccion() as conexion:
            fila = conexion.execute(
                "SELECT id FROM pedidos WHERE id = ?", (pedido_id,)
            ).fetchone()
            if fila is None:
                raise PedidoNoEncontradoError("el pedido no existe")
            # Avanza solo desde el estado origen (guarda anti-carrera).
            aplicado = conexion.execute(
                "UPDATE pedidos SET estado = ? WHERE id = ? AND estado = ?",
                (destino.value, pedido_id, origen.value),
            )
            if aplicado.rowcount != 1:
                raise TransicionEstadoInvalidaError(
                    "el pedido no está en el estado esperado"
                )

    def entregar_pedido_completo(self, pedido_id: int, cliente: Cliente) -> None:
        with self._transaccion() as conexion:
            fila = conexion.execute(
                "SELECT id FROM pedidos WHERE id = ?", (pedido_id,)
            ).fetchone()
            if fila is None:
                raise PedidoNoEncontradoError("el pedido no existe")
            # Solo un pedido Listo pasa a Entregado (anti-doble-acreditación).
            aplicado = conexion.execute(
                "UPDATE pedidos SET estado = ? WHERE id = ? AND estado = ?",
                (
                    EstadoPedido.ENTREGADO.value,
                    pedido_id,
                    EstadoPedido.LISTO.value,
                ),
            )
            if aplicado.rowcount != 1:
                raise TransicionEstadoInvalidaError(
                    "solo un pedido Listo puede entregarse"
                )
            actualizados = conexion.execute(
                "UPDATE clientes SET devpoints = ?, acumulado_compras = ?,"
                " nivel = ? WHERE id = ?",
                (
                    cliente.devpoints,
                    int(cliente.acumulado_compras),
                    cliente.nivel.value,
                    cliente.id,
                ),
            )
            if actualizados.rowcount != 1:
                raise ClienteNoEncontradoError("el cliente no existe")

    @staticmethod
    def _armar_pedido(fila: sqlite3.Row, items: list[ItemPedido]) -> Pedido:
        return Pedido(
            id=fila["id"],
            cliente_id=fila["cliente_id"],
            items=items,
            estado=EstadoPedido(fila["estado"]),
            total=Decimal(fila["total"]),
            devpoints_canjeados=fila["devpoints_canjeados"],
            fecha=datetime.fromisoformat(fila["fecha"]),
        )

    def _obtener_con(self, conexion, pedido_id: int) -> Pedido | None:
        fila = conexion.execute(
            "SELECT id, cliente_id, estado, total, devpoints_canjeados, fecha"
            " FROM pedidos WHERE id = ?",
            (pedido_id,),
        ).fetchone()
        if fila is None:
            return None
        filas_items = conexion.execute(
            "SELECT pedido_id, producto_id, cantidad, precio_unitario"
            " FROM items_pedido WHERE pedido_id = ? ORDER BY id",
            (pedido_id,),
        ).fetchall()
        return self._armar_pedido(fila, [_fila_a_item(f) for f in filas_items])