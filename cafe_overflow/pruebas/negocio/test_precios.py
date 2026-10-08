"""Pruebas del servicio de precios y descuentos (RN-1 y RN-3). Sin base de datos."""

import unittest
from decimal import Decimal

from negocio.entidades import ItemPedido
from negocio.enums import NivelLealtad
from negocio.excepciones import DevPointsInsuficientesError
from negocio.servicios.precios import ServicioPrecios


def hacer_item(precio, cantidad=1):
    # Ítem de ejemplo con precio entero en pesos.
    return ItemPedido(
        producto_id=1, cantidad=cantidad, precio_unitario=Decimal(precio)
    )


class TestDescuentoPorNivel(unittest.TestCase):
    def setUp(self):
        self.precios = ServicioPrecios()

    def test_junior_descuenta_5_porciento(self):
        totales = self.precios.calcular_totales(
            [hacer_item(10000)], NivelLealtad.JUNIOR, 0, 0
        )
        self.assertEqual(totales.subtotal, Decimal(10000))
        self.assertEqual(totales.descuento_nivel, Decimal(500))
        self.assertEqual(totales.total, Decimal(9500))

    def test_mid_descuenta_10_porciento(self):
        totales = self.precios.calcular_totales(
            [hacer_item(10000)], NivelLealtad.MID, 0, 0
        )
        self.assertEqual(totales.descuento_nivel, Decimal(1000))
        self.assertEqual(totales.total, Decimal(9000))

    def test_senior_descuenta_15_porciento(self):
        totales = self.precios.calcular_totales(
            [hacer_item(10000)], NivelLealtad.SENIOR, 0, 0
        )
        self.assertEqual(totales.descuento_nivel, Decimal(1500))
        self.assertEqual(totales.total, Decimal(8500))

    def test_subtotal_suma_precio_por_cantidad(self):
        totales = self.precios.calcular_totales(
            [hacer_item(10000, 2), hacer_item(5000, 1)],
            NivelLealtad.JUNIOR,
            0,
            0,
        )
        self.assertEqual(totales.subtotal, Decimal(25000))
        self.assertEqual(totales.descuento_nivel, Decimal(1250))
        self.assertEqual(totales.total, Decimal(23750))

    def test_descuento_se_redondea_mitad_hacia_arriba(self):
        # 5% de 9999 son 499.95, que se redondea a 500 (S-11).
        totales = self.precios.calcular_totales(
            [hacer_item(9999)], NivelLealtad.JUNIOR, 0, 0
        )
        self.assertEqual(totales.descuento_nivel, Decimal(500))
        self.assertEqual(totales.total, Decimal(9499))


class TestCanjeDevPoints(unittest.TestCase):
    def setUp(self):
        self.precios = ServicioPrecios()

    def test_puntos_se_restan_despues_del_descuento_por_nivel(self):
        # 20000 menos 5% (1000) dejan 19000; 10 puntos restan 2000.
        totales = self.precios.calcular_totales(
            [hacer_item(20000)], NivelLealtad.JUNIOR, 10, 10
        )
        self.assertEqual(totales.descuento_nivel, Decimal(1000))
        self.assertEqual(totales.descuento_puntos, Decimal(2000))
        self.assertEqual(totales.total, Decimal(17000))

    def test_sin_canje_solo_aplica_descuento_por_nivel(self):
        totales = self.precios.calcular_totales(
            [hacer_item(20000)], NivelLealtad.MID, 5, 0
        )
        self.assertEqual(totales.descuento_puntos, Decimal(0))
        self.assertEqual(totales.total, Decimal(18000))

    def test_canje_mayor_al_saldo_se_rechaza(self):
        with self.assertRaises(DevPointsInsuficientesError):
            self.precios.calcular_totales(
                [hacer_item(20000)], NivelLealtad.JUNIOR, 3, 4
            )

    def test_canje_negativo_se_rechaza(self):
        with self.assertRaises(ValueError):
            self.precios.calcular_totales(
                [hacer_item(20000)], NivelLealtad.JUNIOR, 5, -1
            )

    def test_descuento_por_puntos_no_supera_el_valor_restante(self):
        # 1000 menos 5% (50) dejan 950; 100 puntos se limitan a 950.
        totales = self.precios.calcular_totales(
            [hacer_item(1000)], NivelLealtad.JUNIOR, 100, 100
        )
        self.assertEqual(totales.descuento_puntos, Decimal(950))
        self.assertEqual(totales.total, Decimal(0))

    def test_total_nunca_es_negativo(self):
        totales = self.precios.calcular_totales(
            [hacer_item(500)], NivelLealtad.SENIOR, 50, 50
        )
        self.assertGreaterEqual(totales.total, Decimal(0))


if __name__ == "__main__":
    unittest.main()