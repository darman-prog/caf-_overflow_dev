"""Enumeraciones del dominio: niveles de lealtad y estados del pedido."""

from enum import Enum


class NivelLealtad(Enum):
    """Categoria de desarrollo del cliente dentro del programa de lealtad."""

    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"


class EstadoPedido(Enum):
    """Estados del ciclo de vida de un pedido, listados en orden de avance."""

    PENDIENTE_DE_PAGO = "PENDIENTE_DE_PAGO"
    EN_PREPARACION = "EN_PREPARACION"
    LISTO = "LISTO"
    ENTREGADO = "ENTREGADO"