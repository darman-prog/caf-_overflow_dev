"""Servicio de precios y descuentos: cálculo puro, sin acceso a persistencia.

Recibe el nivel y el saldo como parámetros; nunca consulta la base de datos.
Orden de aplicación: primero el descuento por nivel y después los DevPoints.
"""

from decimal import Decimal, ROUND_HALF_UP

from negocio.entidades import ItemPedido, Totales
from negocio.enums import NivelLealtad
from negocio.excepciones import DevPointsInsuficientesError

# Descuento sobre el total de la compra según el nivel de lealtad (RN-1).
DESCUENTO_POR_NIVEL = {
    NivelLealtad.JUNIOR: Decimal(5),
    NivelLealtad.MID: Decimal(10),
    NivelLealtad.SENIOR: Decimal(15),
}

# Valor en pesos de cada DevPoint canjeado (RN-3).
VALOR_DEVPOINT = 200


class ServicioPrecios:
    """Calcula subtotal, descuento por nivel, canje de DevPoints y total."""

    def calcular_totales(
        self,
        items: list[ItemPedido],
        nivel: NivelLealtad,
        saldo_devpoints: int,
        devpoints_a_canjear: int,
    ) -> Totales:
        """Devuelve el desglose del pedido; el total nunca es negativo."""
        if devpoints_a_canjear < 0:
            raise ValueError("los DevPoints a canjear no pueden ser negativos")
        # El canje no puede superar el saldo disponible (RN-3 y S-5).
        if devpoints_a_canjear > saldo_devpoints:
            raise DevPointsInsuficientesError(
                "el cliente no tiene DevPoints suficientes para el canje"
            )
        subtotal = sum(
            (item.precio_unitario * item.cantidad for item in items), Decimal(0)
        )
        # Los pesos son enteros: el descuento se redondea mitad hacia arriba (S-11).
        descuento_nivel = (
            subtotal * DESCUENTO_POR_NIVEL[nivel] / Decimal(100)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        base_tras_nivel = subtotal - descuento_nivel
        # El descuento por puntos se limita al valor restante (nunca negativo).
        descuento_puntos = min(
            Decimal(devpoints_a_canjear * VALOR_DEVPOINT), base_tras_nivel
        )
        total = base_tras_nivel - descuento_puntos
        return Totales(
            subtotal=subtotal,
            descuento_nivel=descuento_nivel,
            descuento_puntos=descuento_puntos,
            total=total,
        )