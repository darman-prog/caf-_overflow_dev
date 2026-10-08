"""Entidades del dominio: datos con tipos estrictos, sin validaciones de negocio.

Las referencias entre entidades son por identificador (estilo llave foránea):
mantiene el dominio simple y coincide con el modelo de datos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from negocio.enums import EstadoPedido, NivelLealtad


@dataclass
class Producto:
    """Producto del menú con precio base y existencias."""

    id: int | None
    nombre: str
    precio_base: Decimal
    stock: int


@dataclass
class Cliente:
    """Cliente del café con su nivel, saldo de DevPoints y acumulado de compras."""

    id: int | None
    nombre: str
    correo: str
    nivel: NivelLealtad = NivelLealtad.JUNIOR
    devpoints: int = 0
    acumulado_compras: Decimal = field(default_factory=lambda: Decimal(0))


@dataclass
class ItemPedido:
    """Renglón de un pedido: producto, cantidad y precio vigente al pedir."""

    producto_id: int
    cantidad: int
    precio_unitario: Decimal


@dataclass
class Pedido:
    """Pedido de un cliente con sus ítems, estado y total calculado por negocio."""

    id: int | None
    cliente_id: int
    items: list[ItemPedido] = field(default_factory=list)
    estado: EstadoPedido = EstadoPedido.PENDIENTE_DE_PAGO
    total: Decimal = field(default_factory=lambda: Decimal(0))
    devpoints_canjeados: int = 0
    fecha: datetime | None = None


@dataclass
class Totales:
    """Desglose del cálculo de un pedido: subtotal, descuentos y total final."""

    subtotal: Decimal
    descuento_nivel: Decimal
    descuento_puntos: Decimal
    total: Decimal