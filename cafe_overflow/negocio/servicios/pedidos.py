"""Servicio de pedidos: registro, validaciones y gestión del estado."""

from datetime import datetime

from negocio.entidades import Cliente, ItemPedido, Pedido, Totales
from negocio.enums import EstadoPedido
from negocio.excepciones import (
    ClienteNoEncontradoError,
    PedidoNoEncontradoError,
    PedidoPendienteError,
    ProductoNoEncontradoError,
    StockInsuficienteError,
    TransicionEstadoInvalidaError,
)
from negocio.puertos import ClienteDAO, PedidoDAO, ProductoDAO
from negocio.servicios.lealtad import ServicioLealtad
from negocio.servicios.precios import ServicioPrecios


class ServicioPedidos:
    """Registra pedidos y controla su ciclo de vida con los demás servicios."""

    def __init__(
        self,
        pedidos: PedidoDAO,
        clientes: ClienteDAO,
        productos: ProductoDAO,
        precios: ServicioPrecios,
        lealtad: ServicioLealtad,
    ):
        self._pedidos = pedidos
        self._clientes = clientes
        self._productos = productos
        self._precios = precios
        self._lealtad = lealtad

    def registrar_pedido(
        self,
        cliente_id: int,
        renglones: list[tuple[int, int]],
        devpoints_a_canjear: int = 0,
    ) -> Pedido:
        """Valida, calcula el total y registra el pedido en Pendiente de pago.

        Cada renglón es una tupla (producto_id, cantidad). El precio de cada
        renglón es el vigente al momento del pedido.
        """
        cliente, pedido, _totales = self._preparar(
            cliente_id, renglones, devpoints_a_canjear
        )
        # Los puntos canjeados se descuentan del saldo al registrar (S-6).
        self._lealtad.aplicar_canje(cliente, devpoints_a_canjear)
        # La persistencia descuenta stock y puntos en la misma transacción (S-7).
        return self._pedidos.registrar_pedido_completo(pedido, cliente)

    def vista_previa(
        self,
        cliente_id: int,
        renglones: list[tuple[int, int]],
        devpoints_a_canjear: int = 0,
    ) -> Totales:
        """Calcula el desglose sin persistir nada; la UI solo lo muestra."""
        # Valida igual que el registro para que la vista previa sea fiel.
        _cliente, _pedido, totales = self._preparar(
            cliente_id, renglones, devpoints_a_canjear
        )
        return totales

    def _preparar(
        self,
        cliente_id: int,
        renglones: list[tuple[int, int]],
        devpoints_a_canjear: int,
    ) -> tuple[Cliente, Pedido, Totales]:
        """Valida y calcula; devuelve cliente, pedido sin persistir y totales."""
        cliente = self._clientes.obtener_por_id(cliente_id)
        if cliente is None:
            raise ClienteNoEncontradoError("el cliente no existe")
        # Un pedido necesita al menos un renglón válido.
        if not renglones:
            raise ValueError("el pedido requiere al menos un ítem")
        vistos = set()
        for producto_id, cantidad in renglones:
            # Cada producto aparece una sola vez y con cantidad positiva.
            if producto_id in vistos:
                raise ValueError("el pedido no puede repetir productos")
            vistos.add(producto_id)
            if cantidad < 1:
                raise ValueError("la cantidad debe ser mayor que cero")
        # Un cliente no puede tener dos pedidos por pagar (RN-4).
        if self._pedidos.existe_pendiente(cliente_id):
            raise PedidoPendienteError("el cliente tiene un pedido pendiente de pago")
        items = []
        for producto_id, cantidad in renglones:
            producto = self._productos.obtener_por_id(producto_id)
            if producto is None:
                raise ProductoNoEncontradoError("un producto del pedido no existe")
            # La cantidad no puede superar el stock disponible (RN-4).
            if cantidad > producto.stock:
                raise StockInsuficienteError("un producto no tiene stock suficiente")
            items.append(
                ItemPedido(
                    producto_id=producto_id,
                    cantidad=cantidad,
                    precio_unitario=producto.precio_base,
                )
            )
        totales = self._precios.calcular_totales(
            items, cliente.nivel, cliente.devpoints, devpoints_a_canjear
        )
        pedido = Pedido(
            id=None,
            cliente_id=cliente_id,
            items=items,
            estado=EstadoPedido.PENDIENTE_DE_PAGO,
            total=totales.total,
            devpoints_canjeados=devpoints_a_canjear,
            fecha=datetime.now(),
        )
        return cliente, pedido, totales

    def confirmar_pago(self, pedido_id: int) -> Pedido:
        """El personal confirma el pago: Pendiente de pago a En preparación (S-9)."""
        return self._avanzar(
            pedido_id,
            EstadoPedido.PENDIENTE_DE_PAGO,
            EstadoPedido.EN_PREPARACION,
        )

    def marcar_listo(self, pedido_id: int) -> Pedido:
        """La cocina termina la preparación: En preparación a Listo."""
        return self._avanzar(
            pedido_id, EstadoPedido.EN_PREPARACION, EstadoPedido.LISTO
        )

    def entregar(self, pedido_id: int) -> Pedido:
        """Entrega el pedido y acredita la compra en el programa de lealtad (S-8)."""
        pedido = self._obtener(pedido_id)
        # Solo un pedido Listo puede entregarse.
        if pedido.estado != EstadoPedido.LISTO:
            raise TransicionEstadoInvalidaError("solo un pedido Listo puede entregarse")
        cliente = self._clientes.obtener_por_id(pedido.cliente_id)
        if cliente is None:
            raise ClienteNoEncontradoError("el cliente no existe")
        self._lealtad.acreditar_entrega(cliente, pedido.total)
        # Estado y lealtad se persisten juntos en una transacción.
        self._pedidos.entregar_pedido_completo(pedido_id, cliente)
        pedido.estado = EstadoPedido.ENTREGADO
        return pedido

    def obtener_pedido(self, pedido_id: int) -> Pedido:
        """Devuelve un pedido o rechaza si no existe."""
        return self._obtener(pedido_id)

    def listar_pedidos(self, estado: EstadoPedido | None = None, cliente_id: int | None = None) -> list[Pedido]:
        """Lista pedidos con filtros opcionales de estado y cliente."""
        pedidos = self._pedidos.listar(estado)
        # El ámbito por cliente se aplica en negocio para no exponer pedidos ajenos.
        if cliente_id is None:
            return pedidos
        return [p for p in pedidos if p.cliente_id == cliente_id]

    def _obtener(self, pedido_id: int) -> Pedido:
        pedido = self._pedidos.obtener_por_id(pedido_id)
        if pedido is None:
            raise PedidoNoEncontradoError("el pedido no existe")
        return pedido

    def _avanzar(
        self, pedido_id: int, origen: EstadoPedido, destino: EstadoPedido
    ) -> Pedido:
        pedido = self._obtener(pedido_id)
        # El avance valida el estado actual antes de delegar al DAO.
        if pedido.estado != origen:
            raise TransicionEstadoInvalidaError(
                "el pedido no está en el estado esperado"
            )
        self._pedidos.avanzar_estado(pedido_id, origen, destino)
        pedido.estado = destino
        return pedido