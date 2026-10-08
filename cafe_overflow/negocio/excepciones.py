"""Excepciones de dominio de Café Overflow.

Los servicios de negocio las lanzan cuando una regla se incumple; la capa de
presentación las traduce a códigos HTTP sin conocer la lógica que las produjo.
"""


class ErrorDominio(Exception):
    """Base de todos los errores de dominio."""


class StockInsuficienteError(ErrorDominio):
    """La cantidad pedida de un producto supera su stock disponible."""


class PedidoPendienteError(ErrorDominio):
    """El cliente ya tiene un pedido en estado Pendiente de pago."""


class DevPointsInsuficientesError(ErrorDominio):
    """El cliente intenta canjear más DevPoints de los que tiene."""


class TransicionEstadoInvalidaError(ErrorDominio):
    """El cambio de estado pedido no sigue el orden permitido."""


class ClienteNoEncontradoError(ErrorDominio):
    """No existe un cliente con el identificador indicado."""


class ProductoNoEncontradoError(ErrorDominio):
    """No existe un producto con el identificador indicado."""


class PedidoNoEncontradoError(ErrorDominio):
    """No existe un pedido con el identificador indicado."""


class CorreoDuplicadoError(ErrorDominio):
    """Ya existe un cliente registrado con ese correo electrónico."""