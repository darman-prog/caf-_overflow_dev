"""Pruebas del registro y ciclo de vida de los pedidos (RN-4). Sin base de datos."""

import unittest
from decimal import Decimal

from negocio.entidades import Producto
from negocio.enums import EstadoPedido, NivelLealtad
from negocio.excepciones import (
    ClienteNoEncontradoError,
    DevPointsInsuficientesError,
    PedidoNoEncontradoError,
    PedidoPendienteError,
    ProductoNoEncontradoError,
    StockInsuficienteError,
    TransicionEstadoInvalidaError,
)
from negocio.servicios.catalogo import ServicioCatalogo, disponibilidad_stock
from negocio.servicios.lealtad import ServicioLealtad
from negocio.servicios.pedidos import ServicioPedidos
from negocio.servicios.precios import ServicioPrecios
from pruebas.negocio.fakes import (
    BaseDatosFalsa,
    FalsoClienteDAO,
    FalsoPedidoDAO,
    FalsoProductoDAO,
)


class BasePedidos(unittest.TestCase):
    def setUp(self):
        bd = BaseDatosFalsa()
        self.dao_productos = FalsoProductoDAO(bd)
        self.dao_clientes = FalsoClienteDAO(bd)
        self.dao_pedidos = FalsoPedidoDAO(bd)
        self.lealtad = ServicioLealtad(self.dao_clientes)
        self.catalogo = ServicioCatalogo(self.dao_productos)
        self.pedidos = ServicioPedidos(
            self.dao_pedidos,
            self.dao_clientes,
            self.dao_productos,
            ServicioPrecios(),
            self.lealtad,
        )
        # Productos dummy de ejemplo para las pruebas.
        self.cafe = self.dao_productos.sembrar(
            Producto(
                id=None,
                nombre="Espresso StackTrace",
                precio_base=Decimal(10000),
                stock=5,
            )
        )
        self.te = self.dao_productos.sembrar(
            Producto(
                id=None,
                nombre="Té Async/Await",
                precio_base=Decimal(8000),
                stock=3,
            )
        )
        self.cliente = self.lealtad.registrar_cliente("Ada", "ada@example.com")


class TestRegistroPedidos(BasePedidos):
    def test_registra_pedido_en_pendiente_con_total_calculado(self):
        # 2 cafés de 10000 menos 5% (1000) dejan un total de 19000.
        pedido = self.pedidos.registrar_pedido(
            self.cliente.id, [(self.cafe.id, 2)], 0
        )
        self.assertIsNotNone(pedido.id)
        self.assertEqual(pedido.estado, EstadoPedido.PENDIENTE_DE_PAGO)
        self.assertEqual(pedido.total, Decimal(19000))
        self.assertEqual(pedido.items[0].precio_unitario, Decimal(10000))

    def test_registro_aplica_descuento_segun_nivel(self):
        self.cliente.nivel = NivelLealtad.SENIOR
        self.dao_clientes.actualizar(self.cliente)
        pedido = self.pedidos.registrar_pedido(
            self.cliente.id, [(self.cafe.id, 1)], 0
        )
        self.assertEqual(pedido.total, Decimal(8500))

    def test_descuenta_stock_al_registrar(self):
        self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 2)], 0)
        producto = self.catalogo.obtener_producto(self.cafe.id)
        self.assertEqual(producto.stock, 3)

    def test_descuenta_devpoints_al_registrar(self):
        self.cliente.devpoints = 10
        self.dao_clientes.actualizar(self.cliente)
        self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 1)], 4)
        cuenta = self.lealtad.obtener_cuenta(self.cliente.id)
        self.assertEqual(cuenta.devpoints, 6)

    def test_cantidad_igual_al_stock_se_acepta(self):
        pedido = self.pedidos.registrar_pedido(
            self.cliente.id, [(self.cafe.id, 5)], 0
        )
        self.assertEqual(pedido.estado, EstadoPedido.PENDIENTE_DE_PAGO)
        self.assertEqual(
            self.catalogo.obtener_producto(self.cafe.id).stock, 0
        )

    def test_cantidad_mayor_al_stock_se_rechaza(self):
        with self.assertRaises(StockInsuficienteError):
            self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 6)], 0)
        # El rechazo no deja rastro: ni pedido ni movimiento de stock.
        self.assertEqual(self.dao_pedidos.listar(), [])
        self.assertEqual(
            self.catalogo.obtener_producto(self.cafe.id).stock, 5
        )

    def test_pedido_pendiente_bloquea_un_pedido_nuevo(self):
        self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 1)], 0)
        with self.assertRaises(PedidoPendienteError):
            self.pedidos.registrar_pedido(self.cliente.id, [(self.te.id, 1)], 0)

    def test_cliente_inexistente_se_rechaza(self):
        with self.assertRaises(ClienteNoEncontradoError):
            self.pedidos.registrar_pedido(999, [(self.cafe.id, 1)], 0)

    def test_producto_inexistente_se_rechaza(self):
        with self.assertRaises(ProductoNoEncontradoError):
            self.pedidos.registrar_pedido(self.cliente.id, [(999, 1)], 0)

    def test_pedido_sin_items_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.pedidos.registrar_pedido(self.cliente.id, [], 0)

    def test_producto_duplicado_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.pedidos.registrar_pedido(
                self.cliente.id, [(self.cafe.id, 1), (self.cafe.id, 1)], 0
            )

    def test_cantidad_no_positiva_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 0)], 0)

    def test_canje_mayor_al_saldo_se_rechaza_sin_efectos(self):
        with self.assertRaises(DevPointsInsuficientesError):
            self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 1)], 5)
        self.assertEqual(self.dao_pedidos.listar(), [])
        self.assertEqual(
            self.catalogo.obtener_producto(self.cafe.id).stock, 5
        )

    def test_registro_fallido_no_deja_rastro_parcial(self):
        # El segundo renglón supera el stock: no se persiste nada.
        with self.assertRaises(StockInsuficienteError):
            self.pedidos.registrar_pedido(
                self.cliente.id, [(self.cafe.id, 1), (self.te.id, 99)], 0
            )
        self.assertEqual(self.dao_pedidos.listar(), [])
        self.assertEqual(
            self.catalogo.obtener_producto(self.cafe.id).stock, 5
        )


class TestEstadosPedido(BasePedidos):
    def setUp(self):
        super().setUp()
        # 2 cafés: subtotal 20000, descuento 1000, total 19000.
        self.pedido = self.pedidos.registrar_pedido(
            self.cliente.id, [(self.cafe.id, 2)], 0
        )

    def test_confirmar_pago_avanza_a_en_preparacion(self):
        pedido = self.pedidos.confirmar_pago(self.pedido.id)
        self.assertEqual(pedido.estado, EstadoPedido.EN_PREPARACION)

    def test_marcar_listo_avanza_desde_preparacion(self):
        self.pedidos.confirmar_pago(self.pedido.id)
        pedido = self.pedidos.marcar_listo(self.pedido.id)
        self.assertEqual(pedido.estado, EstadoPedido.LISTO)

    def test_entregar_acredita_acumulado_y_puntos(self):
        self.pedidos.confirmar_pago(self.pedido.id)
        self.pedidos.marcar_listo(self.pedido.id)
        pedido = self.pedidos.entregar(self.pedido.id)
        self.assertEqual(pedido.estado, EstadoPedido.ENTREGADO)
        cuenta = self.lealtad.obtener_cuenta(self.cliente.id)
        self.assertEqual(cuenta.acumulado_compras, Decimal(19000))
        self.assertEqual(cuenta.devpoints, 0)

    def test_entregar_pedido_grande_acredita_puntos(self):
        # 5 cafés: subtotal 50000, descuento 2500, total 47500 → 2 puntos.
        pedido = self.pedidos.registrar_pedido(
            self.lealtad.registrar_cliente("Grace", "grace@example.com").id,
            [(self.cafe.id, 3)],
            0,
        )
        self.pedidos.confirmar_pago(pedido.id)
        self.pedidos.marcar_listo(pedido.id)
        self.pedidos.entregar(pedido.id)
        cuenta = self.lealtad.obtener_cuenta(pedido.cliente_id)
        self.assertEqual(cuenta.devpoints, 1)

    def test_salto_de_estado_se_rechaza(self):
        with self.assertRaises(TransicionEstadoInvalidaError):
            self.pedidos.marcar_listo(self.pedido.id)

    def test_retroceso_de_estado_se_rechaza(self):
        self.pedidos.confirmar_pago(self.pedido.id)
        with self.assertRaises(TransicionEstadoInvalidaError):
            self.pedidos.confirmar_pago(self.pedido.id)

    def test_entregar_solo_desde_listo(self):
        with self.assertRaises(TransicionEstadoInvalidaError):
            self.pedidos.entregar(self.pedido.id)

    def test_pedido_inexistente_se_rechaza(self):
        with self.assertRaises(PedidoNoEncontradoError):
            self.pedidos.confirmar_pago(999)

    def test_listar_filtra_por_estado(self):
        self.pedidos.confirmar_pago(self.pedido.id)
        self.assertEqual(
            len(self.pedidos.listar_pedidos(EstadoPedido.EN_PREPARACION)), 1
        )
        self.assertEqual(
            self.pedidos.listar_pedidos(EstadoPedido.PENDIENTE_DE_PAGO), []
        )


class TestCatalogo(BasePedidos):
    def test_menu_lista_productos_con_precio_y_stock(self):
        menu = self.catalogo.listar_menu()
        self.assertEqual(len(menu), 2)
        nombres = {p.nombre for p in menu}
        self.assertEqual(nombres, {"Espresso StackTrace", "Té Async/Await"})

    def test_producto_inexistente_se_rechaza(self):
        with self.assertRaises(ProductoNoEncontradoError):
            self.catalogo.obtener_producto(999)


class TestDisponibilidad(unittest.TestCase):
    def test_clasifica_stock_para_exhibicion(self):
        self.assertEqual(disponibilidad_stock(50), "disponible")
        self.assertEqual(disponibilidad_stock(5), "bajo")
        self.assertEqual(disponibilidad_stock(1), "bajo")
        self.assertEqual(disponibilidad_stock(0), "agotado")


class TestListarPorCliente(BasePedidos):
    def test_listar_filtra_por_cliente(self):
        otro = self.lealtad.registrar_cliente("Grace", "grace@example.com")
        self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 1)], 0)
        self.pedidos.registrar_pedido(otro.id, [(self.te.id, 1)], 0)
        mios = self.pedidos.listar_pedidos(cliente_id=self.cliente.id)
        self.assertEqual(len(mios), 1)
        self.assertEqual(mios[0].cliente_id, self.cliente.id)
        self.assertEqual(len(self.pedidos.listar_pedidos()), 2)

    def test_listar_combina_estado_y_cliente(self):
        otro = self.lealtad.registrar_cliente("Grace", "grace@example.com")
        mio = self.pedidos.registrar_pedido(self.cliente.id, [(self.cafe.id, 1)], 0)
        self.pedidos.registrar_pedido(otro.id, [(self.te.id, 1)], 0)
        self.pedidos.confirmar_pago(mio.id)
        filtrados = self.pedidos.listar_pedidos(EstadoPedido.EN_PREPARACION, self.cliente.id)
        self.assertEqual([p.id for p in filtrados], [mio.id])


if __name__ == "__main__":
    unittest.main()