"""Pruebas del programa de lealtad (RN-2 y RN-3). Sin base de datos."""

import unittest
from decimal import Decimal

from negocio.entidades import Cliente
from negocio.enums import NivelLealtad
from negocio.excepciones import (
    ClienteNoEncontradoError,
    CorreoDuplicadoError,
    DevPointsInsuficientesError,
)
from negocio.servicios.lealtad import ServicioLealtad
from pruebas.negocio.fakes import BaseDatosFalsa, FalsoClienteDAO


def hacer_cliente(acumulado=0, nivel=NivelLealtad.JUNIOR, devpoints=0):
    # Cliente de ejemplo con acumulado entero en pesos.
    return Cliente(
        id=None,
        nombre="Ada",
        correo="ada@example.com",
        nivel=nivel,
        devpoints=devpoints,
        acumulado_compras=Decimal(acumulado),
    )


class TestRegistroClientes(unittest.TestCase):
    def setUp(self):
        self.lealtad = ServicioLealtad(FalsoClienteDAO(BaseDatosFalsa()))

    def test_cliente_nuevo_inicia_junior_sin_acumulado_ni_puntos(self):
        cliente = self.lealtad.registrar_cliente("Ada", "ada@example.com")
        self.assertIsNotNone(cliente.id)
        self.assertEqual(cliente.nivel, NivelLealtad.JUNIOR)
        self.assertEqual(cliente.acumulado_compras, Decimal(0))
        self.assertEqual(cliente.devpoints, 0)

    def test_correo_duplicado_se_rechaza(self):
        self.lealtad.registrar_cliente("Ada", "ada@example.com")
        with self.assertRaises(CorreoDuplicadoError):
            self.lealtad.registrar_cliente("Otra", "ada@example.com")

    def test_obtener_cuenta_devuelve_nivel_saldo_y_acumulado(self):
        creado = self.lealtad.registrar_cliente("Ada", "ada@example.com")
        cuenta = self.lealtad.obtener_cuenta(creado.id)
        self.assertEqual(cuenta.nivel, NivelLealtad.JUNIOR)
        self.assertEqual(cuenta.devpoints, 0)
        self.assertEqual(cuenta.acumulado_compras, Decimal(0))

    def test_cuenta_inexistente_se_rechaza(self):
        with self.assertRaises(ClienteNoEncontradoError):
            self.lealtad.obtener_cuenta(999)


class TestAscensos(unittest.TestCase):
    def setUp(self):
        self.lealtad = ServicioLealtad(FalsoClienteDAO(BaseDatosFalsa()))

    def acreditar(self, acumulado_inicial, total):
        cliente = hacer_cliente(acumulado=acumulado_inicial)
        self.lealtad.acreditar_entrega(cliente, Decimal(total))
        return cliente

    def test_acumulado_499999_mantiene_junior(self):
        self.assertEqual(
            self.acreditar(0, 499999).nivel, NivelLealtad.JUNIOR
        )

    def test_acumulado_500000_asciende_a_mid(self):
        cliente = self.acreditar(499999, 1)
        self.assertEqual(cliente.nivel, NivelLealtad.MID)
        self.assertEqual(cliente.acumulado_compras, Decimal(500000))

    def test_acumulado_1499999_mantiene_mid(self):
        cliente = hacer_cliente(acumulado=1499998, nivel=NivelLealtad.MID)
        self.lealtad.acreditar_entrega(cliente, Decimal(1))
        self.assertEqual(cliente.nivel, NivelLealtad.MID)

    def test_acumulado_1500000_asciende_a_senior(self):
        cliente = hacer_cliente(acumulado=1499999, nivel=NivelLealtad.MID)
        self.lealtad.acreditar_entrega(cliente, Decimal(1))
        self.assertEqual(cliente.nivel, NivelLealtad.SENIOR)

    def test_un_pedido_grande_sube_directo_a_senior(self):
        self.assertEqual(
            self.acreditar(0, 1500000).nivel, NivelLealtad.SENIOR
        )

    def test_nivel_nunca_baja(self):
        cliente = hacer_cliente(acumulado=2000000, nivel=NivelLealtad.SENIOR)
        self.lealtad.acreditar_entrega(cliente, Decimal(0))
        self.assertEqual(cliente.nivel, NivelLealtad.SENIOR)


class TestDevPointsLealtad(unittest.TestCase):
    def setUp(self):
        self.lealtad = ServicioLealtad(FalsoClienteDAO(BaseDatosFalsa()))

    def test_pedido_39999_acredita_1_punto(self):
        cliente = hacer_cliente()
        self.lealtad.acreditar_entrega(cliente, Decimal(39999))
        self.assertEqual(cliente.devpoints, 1)
        self.assertEqual(cliente.acumulado_compras, Decimal(39999))

    def test_pedido_40000_acredita_2_puntos(self):
        cliente = hacer_cliente()
        self.lealtad.acreditar_entrega(cliente, Decimal(40000))
        self.assertEqual(cliente.devpoints, 2)

    def test_canje_descuenta_del_saldo(self):
        cliente = hacer_cliente(devpoints=10)
        self.lealtad.aplicar_canje(cliente, 4)
        self.assertEqual(cliente.devpoints, 6)

    def test_canje_mayor_al_saldo_se_rechaza(self):
        with self.assertRaises(DevPointsInsuficientesError):
            self.lealtad.aplicar_canje(hacer_cliente(devpoints=3), 4)

    def test_canje_negativo_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.lealtad.aplicar_canje(hacer_cliente(devpoints=5), -1)


if __name__ == "__main__":
    unittest.main()