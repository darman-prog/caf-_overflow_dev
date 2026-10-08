"""Puertos de persistencia definidos por el dominio (contratos, sin SQL).

La capa de persistencia implementa estas interfaces; los servicios de negocio
solo dependen de ellas (inversión de dependencias). Los métodos compuestos
(registrar/entregar) se ejecutan en una sola transacción en la implementación.
"""

from abc import ABC, abstractmethod

from negocio.entidades import Cliente, Pedido, Producto
from negocio.enums import EstadoPedido


class ProductoDAO(ABC):
    """Acceso a los productos del menú."""

    @abstractmethod
    def obtener_por_id(self, producto_id: int) -> Producto | None:
        """Devuelve el producto o None si no existe."""

    @abstractmethod
    def listar_todos(self) -> list[Producto]:
        """Devuelve todos los productos del menú."""


class ClienteDAO(ABC):
    """Acceso a los clientes del programa de lealtad."""

    @abstractmethod
    def obtener_por_id(self, cliente_id: int) -> Cliente | None:
        """Devuelve el cliente o None si no existe."""

    @abstractmethod
    def obtener_por_correo(self, correo: str) -> Cliente | None:
        """Devuelve el cliente con ese correo o None si no existe."""

    @abstractmethod
    def crear(self, cliente: Cliente) -> Cliente:
        """Guarda un cliente nuevo y lo devuelve con su identificador asignado."""

    @abstractmethod
    def actualizar(self, cliente: Cliente) -> None:
        """Persiste los cambios de nivel, DevPoints y acumulado de un cliente."""


class PedidoDAO(ABC):
    """Acceso a los pedidos y a las operaciones transaccionales del negocio."""

    @abstractmethod
    def obtener_por_id(self, pedido_id: int) -> Pedido | None:
        """Devuelve el pedido con sus ítems o None si no existe."""

    @abstractmethod
    def listar(self, estado: EstadoPedido | None = None) -> list[Pedido]:
        """Lista pedidos, opcionalmente filtrados por estado."""

    @abstractmethod
    def existe_pendiente(self, cliente_id: int) -> bool:
        """Indica si el cliente tiene un pedido en Pendiente de pago."""

    @abstractmethod
    def registrar_pedido_completo(self, pedido: Pedido, cliente: Cliente) -> Pedido:
        """Registra el pedido con sus ítems en una sola transacción.

        Además descuenta el stock de cada producto y los DevPoints canjeados
        del cliente. Si alguna guarda de integridad falla, no persiste nada.
        """

    @abstractmethod
    def avanzar_estado(
        self, pedido_id: int, origen: EstadoPedido, destino: EstadoPedido
    ) -> None:
        """Avanza el estado del pedido solo si aún está en el estado origen."""

    @abstractmethod
    def entregar_pedido_completo(self, pedido_id: int, cliente: Cliente) -> None:
        """Pasa el pedido a Entregado y acredita la compra en una transacción.

        Actualiza el acumulado, el nivel y los DevPoints del cliente junto con
        el estado del pedido; si el pedido ya no está Listo, no persiste nada.
        """