"""Pruebas de integración del DAO SQLite con base temporal en archivo.

Se usa un archivo temporal (no :memory:): el DAO abre una conexión por
operación y la memoria no se comparte entre conexiones.
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from negocio.entidades import Cliente, ItemPedido, Pedido
from negocio.enums import EstadoPedido, NivelLealtad
from negocio.excepciones import (
    CorreoDuplicadoError,
    DevPointsInsuficientesError,
    PedidoNoEncontradoError,
    PedidoPendienteError,
    StockInsuficienteError,
    TransicionEstadoInvalidaError,
)
from negocio.servicios.lealtad import ServicioLealtad
from negocio.servicios.pedidos import ServicioPedidos
from negocio.servicios.precios import ServicioPrecios
from persistencia.sqlite_dao import (
    SqliteClienteDAO,
    SqlitePedidoDAO,
    SqliteProductoDAO,
)

RAIZ = Path(__file__).resolve().parents[2]


def cargar_sql(ruta_bd, nombre):
    # Aplica un script .sql del paquete de persistencia.
    script = (RAIZ / "persistencia" / nombre).read_text(encoding="utf-8")
    # sqlite3.connect como 'with' no cierra: cerrar explícito o el .db
    # queda bloqueado en Windows y el tearDown falla al borrarlo.
    conexion = sqlite3.connect(ruta_bd)
    try:
        conexion.executescript(script)
        conexion.commit()
    finally:
        conexion.close()


class BaseSQLite(unittest.TestCase):
    def setUp(self):
        # Cada prueba parte de una base temporal vacía con el esquema aplicado.
        temporal = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temporal.close()
        self.ruta = temporal.name
        self.addCleanup(Path(self.ruta).unlink, missing_ok=True)
        cargar_sql(self.ruta, "esquema.sql")
        self.productos = SqliteProductoDAO(self.ruta)
        self.clientes = SqliteClienteDAO(self.ruta)
        self.pedidos = SqlitePedidoDAO(self.ruta)

    def sembrar_menu(self):
        cargar_sql(self.ruta, "datos_iniciales.sql")

    def crear_cliente(self, nombre="Ada", correo="ada@example.com", devpoints=0):
        cliente = self.clientes.crear(
            Cliente(id=None, nombre=nombre, correo=correo)
        )
        if devpoints:
            cliente.devpoints = devpoints
            self.clientes.actualizar(cliente)
        return cliente


class TestEsquema(BaseSQLite):
    def test_checks_rechazan_datos_invalidos(self):
        conexion = sqlite3.connect(self.ruta)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conexion.execute(
                    "INSERT INTO productos (nombre, precio_base, stock)"
                    " VALUES ('Malo', -1, 5)"
                )
        finally:
            conexion.close()

    def test_existe_indice_unico_de_pedido_pendiente(self):
        conexion = sqlite3.connect(self.ruta)
        try:
            fila = conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
                " AND name = 'ux_pedido_pendiente_por_cliente'"
            ).fetchone()
            self.assertIsNotNone(fila)
        finally:
            conexion.close()


class TestProductoDAO(BaseSQLite):
    def test_menu_dummy_se_carga_con_tipos_mapeados(self):
        self.sembrar_menu()
        menu = self.productos.listar_todos()
        self.assertEqual(len(menu), 6)
        primero = self.productos.obtener_por_id(1)
        self.assertEqual(primero.nombre, "Espresso StackTrace")
        self.assertEqual(primero.precio_base, Decimal(8500))
        self.assertIsInstance(primero.precio_base, Decimal)

    def test_producto_inexistente_devuelve_none(self):
        self.assertIsNone(self.productos.obtener_por_id(999))


class TestClienteDAO(BaseSQLite):
    def test_crear_asigna_id_y_mapea_tipos(self):
        cliente = self.clientes.crear(
            Cliente(id=None, nombre="Ada", correo="ada@example.com")
        )
        self.assertIsNotNone(cliente.id)
        obtenido = self.clientes.obtener_por_id(cliente.id)
        self.assertEqual(obtenido.nivel, NivelLealtad.JUNIOR)
        self.assertEqual(obtenido.acumulado_compras, Decimal(0))
        self.assertIsInstance(obtenido.acumulado_compras, Decimal)

    def test_obtener_por_correo(self):
        creado = self.crear_cliente()
        self.assertEqual(
            self.clientes.obtener_por_correo("ada@example.com").id, creado.id
        )
        self.assertIsNone(self.clientes.obtener_por_correo("nadie@example.com"))

    def test_correo_duplicado_se_rechaza(self):
        self.crear_cliente()
        with self.assertRaises(CorreoDuplicadoError):
            self.clientes.crear(
                Cliente(id=None, nombre="Otra", correo="ada@example.com")
            )

    def test_actualizar_persiste_nivel_puntos_y_acumulado(self):
        cliente = self.crear_cliente()
        cliente.nivel = NivelLealtad.MID
        cliente.devpoints = 7
        cliente.acumulado_compras = Decimal(600000)
        self.clientes.actualizar(cliente)
        obtenido = self.clientes.obtener_por_id(cliente.id)
        self.assertEqual(obtenido.nivel, NivelLealtad.MID)
        self.assertEqual(obtenido.devpoints, 7)
        self.assertEqual(obtenido.acumulado_compras, Decimal(600000))

    def test_cliente_inexistente_devuelve_none(self):
        self.assertIsNone(self.clientes.obtener_por_id(999))


class TestPedidoDAO(BaseSQLite):
    def setUp(self):
        super().setUp()
        self.sembrar_menu()
        self.cliente = self.crear_cliente(devpoints=10)

    def hacer_pedido(self, canje=0):
        # 2 espressos de 8500: subtotal 17000, descuento 850, total 16150.
        return Pedido(
            id=None,
            cliente_id=self.cliente.id,
            items=[
                ItemPedido(
                    producto_id=1, cantidad=2, precio_unitario=Decimal(8500)
                )
            ],
            estado=EstadoPedido.PENDIENTE_DE_PAGO,
            total=Decimal(16150),
            devpoints_canjeados=canje,
            fecha=datetime(2026, 10, 8, 12, 0, 0),
        )

    def test_registrar_persiste_pedido_items_y_descuentos(self):
        pedido = self.pedidos.registrar_pedido_completo(
            self.hacer_pedido(canje=4), self.cliente
        )
        self.assertIsNotNone(pedido.id)
        self.assertEqual(pedido.total, Decimal(16150))
        self.assertEqual(pedido.devpoints_canjeados, 4)
        self.assertEqual(pedido.fecha, datetime(2026, 10, 8, 12, 0, 0))
        self.assertEqual(len(pedido.items), 1)
        self.assertEqual(pedido.items[0].precio_unitario, Decimal(8500))
        self.assertEqual(self.productos.obtener_por_id(1).stock, 48)
        cuenta = self.clientes.obtener_por_id(self.cliente.id)
        self.assertEqual(cuenta.devpoints, 6)

    def test_registrar_sin_stock_no_persiste_nada(self):
        pedido = self.hacer_pedido()
        pedido.items = [
            ItemPedido(producto_id=1, cantidad=99, precio_unitario=Decimal(8500))
        ]
        with self.assertRaises(StockInsuficienteError):
            self.pedidos.registrar_pedido_completo(pedido, self.cliente)
        self.assertEqual(self.pedidos.listar(), [])
        self.assertEqual(self.productos.obtener_por_id(1).stock, 50)

    def test_registrar_canje_sin_saldo_no_persiste_nada(self):
        with self.assertRaises(DevPointsInsuficientesError):
            self.pedidos.registrar_pedido_completo(
                self.hacer_pedido(canje=99), self.cliente
            )
        self.assertEqual(self.pedidos.listar(), [])
        self.assertEqual(self.productos.obtener_por_id(1).stock, 50)

    def test_segundo_pendiente_se_rechaza(self):
        self.pedidos.registrar_pedido_completo(self.hacer_pedido(), self.cliente)
        with self.assertRaises(PedidoPendienteError):
            self.pedidos.registrar_pedido_completo(
                self.hacer_pedido(), self.cliente
            )
        self.assertEqual(len(self.pedidos.listar()), 1)

    def test_avanzar_estado_valido_e_invalido(self):
        pedido = self.pedidos.registrar_pedido_completo(
            self.hacer_pedido(), self.cliente
        )
        self.pedidos.avanzar_estado(
            pedido.id,
            EstadoPedido.PENDIENTE_DE_PAGO,
            EstadoPedido.EN_PREPARACION,
        )
        obtenido = self.pedidos.obtener_por_id(pedido.id)
        self.assertEqual(obtenido.estado, EstadoPedido.EN_PREPARACION)
        with self.assertRaises(TransicionEstadoInvalidaError):
            self.pedidos.avanzar_estado(
                pedido.id,
                EstadoPedido.PENDIENTE_DE_PAGO,
                EstadoPedido.EN_PREPARACION,
            )

    def test_avanzar_pedido_inexistente_se_rechaza(self):
        with self.assertRaises(PedidoNoEncontradoError):
            self.pedidos.avanzar_estado(
                999,
                EstadoPedido.PENDIENTE_DE_PAGO,
                EstadoPedido.EN_PREPARACION,
            )

    def test_entregar_acredita_todo_en_una_transaccion(self):
        pedido = self.pedidos.registrar_pedido_completo(
            self.hacer_pedido(), self.cliente
        )
        self.pedidos.avanzar_estado(
            pedido.id,
            EstadoPedido.PENDIENTE_DE_PAGO,
            EstadoPedido.EN_PREPARACION,
        )
        self.pedidos.avanzar_estado(
            pedido.id, EstadoPedido.EN_PREPARACION, EstadoPedido.LISTO
        )
        cliente = self.clientes.obtener_por_id(self.cliente.id)
        cliente.acumulado_compras = Decimal(16150)
        cliente.devpoints = 6
        self.pedidos.entregar_pedido_completo(pedido.id, cliente)
        obtenido = self.pedidos.obtener_por_id(pedido.id)
        self.assertEqual(obtenido.estado, EstadoPedido.ENTREGADO)
        cuenta = self.clientes.obtener_por_id(self.cliente.id)
        self.assertEqual(cuenta.acumulado_compras, Decimal(16150))
        self.assertEqual(cuenta.devpoints, 6)

    def test_entregar_fuera_de_listo_se_rechaza(self):
        pedido = self.pedidos.registrar_pedido_completo(
            self.hacer_pedido(), self.cliente
        )
        with self.assertRaises(TransicionEstadoInvalidaError):
            self.pedidos.entregar_pedido_completo(pedido.id, self.cliente)

    def test_existe_pendiente_y_listar_filtran(self):
        self.assertFalse(self.pedidos.existe_pendiente(self.cliente.id))
        self.pedidos.registrar_pedido_completo(self.hacer_pedido(), self.cliente)
        self.assertTrue(self.pedidos.existe_pendiente(self.cliente.id))
        self.assertEqual(
            len(self.pedidos.listar(EstadoPedido.PENDIENTE_DE_PAGO)), 1
        )
        self.assertEqual(self.pedidos.listar(EstadoPedido.LISTO), [])
        self.assertEqual(len(self.pedidos.listar()), 1)


class TestFlujoConSQLite(BaseSQLite):
    def test_flujo_completo_con_dao_real(self):
        self.sembrar_menu()
        lealtad = ServicioLealtad(self.clientes)
        pedidos = ServicioPedidos(
            self.pedidos,
            self.clientes,
            self.productos,
            ServicioPrecios(),
            lealtad,
        )
        cliente = lealtad.registrar_cliente("Ada", "ada@example.com")
        pedido = pedidos.registrar_pedido(cliente.id, [(1, 2)], 0)
        # 2 espressos de 8500: subtotal 17000, descuento 850, total 16150.
        self.assertEqual(pedido.total, Decimal(16150))
        pedidos.confirmar_pago(pedido.id)
        pedidos.marcar_listo(pedido.id)
        pedidos.entregar(pedido.id)
        cuenta = lealtad.obtener_cuenta(cliente.id)
        self.assertEqual(cuenta.acumulado_compras, Decimal(16150))
        self.assertEqual(cuenta.devpoints, 0)
        self.assertEqual(pedidos.obtener_pedido(pedido.id).estado,
                         EstadoPedido.ENTREGADO)
        self.assertEqual(self.productos.obtener_por_id(1).stock, 48)


if __name__ == "__main__":
    unittest.main()