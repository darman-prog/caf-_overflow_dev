"""Servicio de lealtad: clientes, niveles, DevPoints y acumulado de compras."""

from decimal import Decimal

from negocio.entidades import Cliente
from negocio.enums import NivelLealtad
from negocio.excepciones import (
    ClienteNoEncontradoError,
    CorreoDuplicadoError,
    DevPointsInsuficientesError,
)
from negocio.puertos import ClienteDAO

# Acumulado histórico que dispara cada ascenso automático (RN-2).
UMBRAL_MID = Decimal(500000)
UMBRAL_SENIOR = Decimal(1500000)

# Pesos consumidos que acreditan un DevPoint (RN-3).
PESOS_POR_DEVPOINT = Decimal(20000)


class ServicioLealtad:
    """Administra el programa de lealtad usando un DAO de clientes."""

    def __init__(self, clientes: ClienteDAO):
        self._clientes = clientes

    def registrar_cliente(self, nombre: str, correo: str) -> Cliente:
        """Crea un cliente nuevo como Junior con acumulado y saldo en cero."""
        # El correo identifica al cliente: no puede repetirse.
        if self._clientes.obtener_por_correo(correo) is not None:
            raise CorreoDuplicadoError("ese correo ya está registrado")
        return self._clientes.crear(Cliente(id=None, nombre=nombre, correo=correo))

    def obtener_cuenta(self, cliente_id: int) -> Cliente:
        """Devuelve nivel, saldo de DevPoints y acumulado del cliente."""
        cliente = self._clientes.obtener_por_id(cliente_id)
        if cliente is None:
            raise ClienteNoEncontradoError("el cliente no existe")
        return cliente

    def aplicar_canje(self, cliente: Cliente, devpoints: int) -> None:
        """Descuenta del saldo los DevPoints que el cliente decide canjear (S-5, S-6)."""
        if devpoints < 0:
            raise ValueError("los DevPoints a canjear no pueden ser negativos")
        if devpoints > cliente.devpoints:
            raise DevPointsInsuficientesError(
                "el cliente no tiene DevPoints suficientes para el canje"
            )
        cliente.devpoints -= devpoints

    def acreditar_entrega(self, cliente: Cliente, total_pagado: Decimal) -> None:
        """Suma la compra al acumulado, evalúa el ascenso y acredita DevPoints (S-8)."""
        cliente.acumulado_compras += total_pagado
        # El nivel nuevo aplica desde esta compra en adelante; nunca baja (RN-2).
        if cliente.acumulado_compras >= UMBRAL_SENIOR:
            cliente.nivel = NivelLealtad.SENIOR
        elif cliente.acumulado_compras >= UMBRAL_MID:
            cliente.nivel = NivelLealtad.MID
        # Cada fracción de $20.000 suma un punto; el resto se pierde (RN-3).
        cliente.devpoints += int(total_pagado // PESOS_POR_DEVPOINT)