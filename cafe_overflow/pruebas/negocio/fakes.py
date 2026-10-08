"""DAO falsos en memoria para probar la capa de negocio sin base de datos.

Guardan y devuelven copias, como una base de datos real: lo que el servicio
modifica en sus objetos no afecta lo almacenado hasta que el DAO lo persiste.
Las operaciones compuestas validan todo antes de aplicar nada (todo o nada).
"""

import copy

from negocio.entidades import Cliente, Pedido, Producto
from negocio.enums import EstadoPedido
from negocio.excepciones import (
    DevPointsInsuficientesError,
    PedidoNoEncontradoError,
    StockInsuficienteError,
    TransicionEstadoInvalidaError,
)
from negocio.puertos import ClienteDAO, PedidoDAO, ProductoDAO


class BaseDatosFalsa:
    """Almacén compartido por los DAO falsos de una prueba."""

    def __init__(self):
        self.productos = {}
        self.clientes = {}
        self.pedidos = {}
        self.secuencia = 0

    def siguiente_id(self):
        # Identificadores crecientes, como AUTOINCREMENT.
        self.secuencia += 1
        return self.secuencia


class FalsoProductoDAO(ProductoDAO):
    """Catálogo en memoria para las pruebas."""

    def __init__(self, bd: BaseDatosFalsa):
        self._bd = bd

    def obtener_por_id(self, producto_id: int) -> Producto | None:
        producto = self._bd.productos.get(producto_id)
        return copy.deepcopy(producto) if producto is not None else None

    def listar_todos(self) -> list[Producto]:
        return copy.deepcopy(list(self._bd.productos.values()))

    def sembrar(self, producto: Producto) -> Producto:
        # Ayuda solo para pruebas: guarda un producto asignándole identificador.
        copia = copy.deepcopy(producto)
        copia.id = self._bd.siguiente_id()
        self._bd.productos[copia.id] = copia
        return copy.deepcopy(copia)


class FalsoClienteDAO(ClienteDAO):
    """Clientes en memoria para las pruebas."""

    def __init__(self, bd: BaseDatosFalsa):
        self._bd = bd

    def obtener_por_id(self, cliente_id: int) -> Cliente | None:
        cliente = self._bd.clientes.get(cliente_id)
        return copy.deepcopy(cliente) if cliente is not None else None

    def obtener_por_correo(self, correo: str) -> Cliente | None:
        for cliente in self._bd.clientes.values():
            if cliente.correo == correo:
                return copy.deepcopy(cliente)
        return None

    def crear(self, cliente: Cliente) -> Cliente:
        copia = copy.deepcopy(cliente)
        copia.id = self._bd.siguiente_id()
        self._bd.clientes[copia.id] = copia
        return copy.deepcopy(copia)

    def actualizar(self, cliente: Cliente) -> None:
        self._bd.clientes[cliente.id] = copy.deepcopy(cliente)


class FalsoPedidoDAO(PedidoDAO):
    """Pedidos en memoria con atomicidad de todo o nada."""

    def __init__(self, bd: BaseDatosFalsa):
        self._bd = bd

    def obtener_por_id(self, pedido_id: int) -> Pedido | None:
        pedido = self._bd.pedidos.get(pedido_id)
        return copy.deepcopy(pedido) if pedido is not None else None

    def listar(self, estado: EstadoPedido | None = None) -> list[Pedido]:
        pedidos = list(self._bd.pedidos.values())
        if estado is not None:
            pedidos = [p for p in pedidos if p.estado == estado]
        return copy.deepcopy(pedidos)

    def existe_pendiente(self, cliente_id: int) -> bool:
        return any(
            p.cliente_id == cliente_id and p.estado == EstadoPedido.PENDIENTE_DE_PAGO
            for p in self._bd.pedidos.values()
        )

    def registrar_pedido_completo(self, pedido: Pedido, cliente: Cliente) -> Pedido:
        # Primero valida todo contra lo almacenado; solo después aplica.
        for item in pedido.items:
            producto = self._bd.productos.get(item.producto_id)
            if producto is None or producto.stock < item.cantidad:
                raise StockInsuficienteError(
                    "un producto no tiene stock suficiente"
                )
        almacenado = self._bd.clientes.get(cliente.id)
        if almacenado is None or almacenado.devpoints < pedido.devpoints_canjeados:
            raise DevPointsInsuficientesError(
                "el cliente no tiene DevPoints suficientes para el canje"
            )
        nuevo = copy.deepcopy(pedido)
        nuevo.id = self._bd.siguiente_id()
        self._bd.pedidos[nuevo.id] = nuevo
        for item in pedido.items:
            self._bd.productos[item.producto_id].stock -= item.cantidad
        # Persiste el cliente ya actualizado por negocio (canje descontado).
        self._bd.clientes[cliente.id] = copy.deepcopy(cliente)
        return copy.deepcopy(nuevo)

    def avanzar_estado(
        self, pedido_id: int, origen: EstadoPedido, destino: EstadoPedido
    ) -> None:
        pedido = self._bd.pedidos.get(pedido_id)
        if pedido is None:
            raise PedidoNoEncontradoError("el pedido no existe")
        # Solo avanza si el pedido aún está en el estado origen (anti-carrera).
        if pedido.estado != origen:
            raise TransicionEstadoInvalidaError(
                "el pedido ya no está en el estado esperado"
            )
        pedido.estado = destino

    def entregar_pedido_completo(self, pedido_id: int, cliente: Cliente) -> None:
        pedido = self._bd.pedidos.get(pedido_id)
        if pedido is None:
            raise PedidoNoEncontradoError("el pedido no existe")
        # Solo un pedido Listo puede pasar a Entregado (anti-doble-acreditación).
        if pedido.estado != EstadoPedido.LISTO:
            raise TransicionEstadoInvalidaError(
                "solo un pedido Listo puede entregarse"
            )
        pedido.estado = EstadoPedido.ENTREGADO
        # Persiste el cliente ya actualizado por negocio (acumulado y puntos).
        self._bd.clientes[cliente.id] = copy.deepcopy(cliente)