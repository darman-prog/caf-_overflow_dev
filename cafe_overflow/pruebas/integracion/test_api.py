"""Pruebas de integración de la API HTTP con base temporal en archivo."""

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from main import inicializar_bd
from negocio.servicios.catalogo import ServicioCatalogo
from negocio.servicios.lealtad import ServicioLealtad
from negocio.servicios.pedidos import ServicioPedidos
from negocio.servicios.precios import ServicioPrecios
from persistencia.sqlite_dao import (
    SqliteClienteDAO,
    SqlitePedidoDAO,
    SqliteProductoDAO,
)
from presentacion.api.servidor import MAX_CUERPO, Controladores, crear_servidor

RAIZ = Path(__file__).resolve().parents[2]


class BaseAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Base temporal con esquema y menú dummy, y servidor en un hilo.
        temporal = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temporal.close()
        cls.ruta = temporal.name
        cls.addClassCleanup(Path(cls.ruta).unlink, missing_ok=True)
        for nombre in ("esquema.sql", "datos_iniciales.sql"):
            script = (RAIZ / "persistencia" / nombre).read_text(encoding="utf-8")
            conexion = sqlite3.connect(cls.ruta)
            try:
                conexion.executescript(script)
                conexion.commit()
            finally:
                conexion.close()
        productos = SqliteProductoDAO(cls.ruta)
        clientes = SqliteClienteDAO(cls.ruta)
        pedidos = SqlitePedidoDAO(cls.ruta)
        precios = ServicioPrecios()
        lealtad = ServicioLealtad(clientes)
        controladores = Controladores(
            catalogo=ServicioCatalogo(productos),
            lealtad=lealtad,
            pedidos=ServicioPedidos(pedidos, clientes, productos, precios, lealtad),
            precios=precios,
        )
        # Puerto 0: el sistema asigna uno libre.
        cls.servidor = crear_servidor(controladores, "127.0.0.1", 0)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        cls.base = f"http://127.0.0.1:{cls.servidor.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        # Detiene el servidor de la prueba.
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def pedir(self, metodo, ruta, cuerpo=None):
        # Ayuda para llamar a la API y leer el JSON con su código de estado.
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        solicitud = urllib.request.Request(
            self.base + ruta,
            data=datos,
            method=metodo,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(solicitud) as respuesta:
                return respuesta.status, json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def nuevo_cliente(self, correo):
        estado, cliente = self.pedir(
            "POST", "/api/clientes", {"nombre": "Prueba", "correo": correo}
        )
        self.assertEqual(estado, 201)
        return cliente["id"]


class TestMenuYClientes(BaseAPI):
    def test_menu_lista_productos_dummy(self):
        estado, menu = self.pedir("GET", "/api/productos")
        self.assertEqual(estado, 200)
        self.assertEqual(len(menu), 6)
        self.assertEqual(menu[0]["nombre"], "Espresso StackTrace")
        self.assertEqual(menu[0]["precio_base"], 8500)
        self.assertEqual(menu[0]["disponibilidad"], "disponible")

    def test_registra_cliente_y_consulta_cuenta(self):
        estado, cliente = self.pedir(
            "POST",
            "/api/clientes",
            {"nombre": "Ada", "correo": "ada@example.com"},
        )
        self.assertEqual(estado, 201)
        self.assertEqual(cliente["nivel"], "JUNIOR")
        estado, cuenta = self.pedir("GET", f"/api/clientes/{cliente['id']}")
        self.assertEqual(estado, 200)
        self.assertEqual(cuenta["devpoints"], 0)
        self.assertEqual(cuenta["acumulado_compras"], 0)

    def test_correo_invalido_es_400(self):
        estado, cuerpo = self.pedir(
            "POST", "/api/clientes", {"nombre": "Ada", "correo": "no-es-correo"}
        )
        self.assertEqual(estado, 400)
        self.assertEqual(cuerpo["error"]["codigo"], "ENTRADA_INVALIDA")

    def test_correo_duplicado_es_409(self):
        self.pedir(
            "POST", "/api/clientes", {"nombre": "A", "correo": "dupli@example.com"}
        )
        estado, cuerpo = self.pedir(
            "POST", "/api/clientes", {"nombre": "B", "correo": "dupli@example.com"}
        )
        self.assertEqual(estado, 409)
        self.assertEqual(cuerpo["error"]["codigo"], "CORREO_DUPLICADO")

    def test_cliente_inexistente_es_404(self):
        estado, cuerpo = self.pedir("GET", "/api/clientes/999999")
        self.assertEqual(estado, 404)
        self.assertEqual(cuerpo["error"]["codigo"], "CLIENTE_NO_ENCONTRADO")


class TestPedidosAPI(BaseAPI):
    def test_registra_pedido_con_total_calculado(self):
        cliente_id = self.nuevo_cliente("registra@example.com")
        estado, pedido = self.pedir(
            "POST",
            "/api/pedidos",
            {
                "cliente_id": cliente_id,
                "items": [{"producto_id": 1, "cantidad": 2}],
                "devpoints_a_canjear": 0,
            },
        )
        self.assertEqual(estado, 201)
        # 2 espressos de 8500: subtotal 17000, descuento 850, total 16150.
        self.assertEqual(pedido["total"], 16150)
        self.assertEqual(pedido["estado"], "PENDIENTE_DE_PAGO")

    def test_descuenta_stock_del_menu(self):
        cliente_id = self.nuevo_cliente("stock@example.com")
        estado, _ = self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 6, "cantidad": 25}]},
        )
        self.assertEqual(estado, 201)
        _, menu = self.pedir("GET", "/api/productos")
        mocha = [p for p in menu if p["nombre"] == "Mocha Deploy a Producción"][0]
        self.assertEqual(mocha["stock"], 0)

    def test_flujo_completo_de_estados(self):
        cliente_id = self.nuevo_cliente("flujo@example.com")
        _, pedido = self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 3, "cantidad": 1}]},
        )
        pid = pedido["id"]
        # Té de 7000 menos 5% (350): total 6650.
        self.assertEqual(pedido["total"], 6650)
        estado, pedido = self.pedir("POST", f"/api/pedidos/{pid}/confirmar-pago")
        self.assertEqual(pedido["estado"], "EN_PREPARACION")
        estado, pedido = self.pedir(
            "PATCH", f"/api/pedidos/{pid}/estado", {"estado": "LISTO"}
        )
        self.assertEqual(pedido["estado"], "LISTO")
        estado, pedido = self.pedir(
            "PATCH", f"/api/pedidos/{pid}/estado", {"estado": "ENTREGADO"}
        )
        self.assertEqual(pedido["estado"], "ENTREGADO")
        _, cuenta = self.pedir("GET", f"/api/clientes/{cliente_id}")
        self.assertEqual(cuenta["acumulado_compras"], 6650)
        self.assertEqual(cuenta["devpoints"], 0)

    def test_stock_insuficiente_es_409(self):
        cliente_id = self.nuevo_cliente("sinstock@example.com")
        estado, cuerpo = self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 2, "cantidad": 99}]},
        )
        self.assertEqual(estado, 409)
        self.assertEqual(cuerpo["error"]["codigo"], "STOCK_INSUFICIENTE")

    def test_pedido_pendiente_bloquea_otro(self):
        cliente_id = self.nuevo_cliente("pendiente@example.com")
        self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 4, "cantidad": 1}]},
        )
        estado, cuerpo = self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 5, "cantidad": 1}]},
        )
        self.assertEqual(estado, 409)
        self.assertEqual(cuerpo["error"]["codigo"], "PEDIDO_PENDIENTE")

    def test_transicion_invalida_es_409(self):
        cliente_id = self.nuevo_cliente("transicion@example.com")
        _, pedido = self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 5, "cantidad": 1}]},
        )
        estado, cuerpo = self.pedir(
            "PATCH",
            f"/api/pedidos/{pedido['id']}/estado",
            {"estado": "ENTREGADO"},
        )
        self.assertEqual(estado, 409)
        self.assertEqual(cuerpo["error"]["codigo"], "TRANSICION_INVALIDA")

    def test_estado_invalido_en_filtro_es_400(self):
        estado, cuerpo = self.pedir("GET", "/api/pedidos?estado=MALO")
        self.assertEqual(estado, 400)

    def test_ruta_desconocida_es_404(self):
        estado, cuerpo = self.pedir("GET", "/api/no-existe")
        self.assertEqual(estado, 404)


class TestVistaPrevia(BaseAPI):
    def test_vista_previa_devuelve_desglose_sin_persistir(self):
        cliente_id = self.nuevo_cliente("previa1@example.com")
        # Conteo previo: la clase comparte BD; la vista no debe crear nada.
        _, previos = self.pedir("GET", "/api/pedidos")
        estado, totales = self.pedir(
            "POST",
            "/api/pedidos/vista-previa",
            {"cliente_id": cliente_id, "items": [{"producto_id": 1, "cantidad": 2}]},
        )
        self.assertEqual(estado, 200)
        self.assertEqual(totales["subtotal"], 17000)
        self.assertEqual(totales["descuento_nivel"], 850)
        self.assertEqual(totales["descuento_puntos"], 0)
        self.assertEqual(totales["total"], 16150)
        # Nada se persistió: ni pedidos ni movimiento de stock.
        _, pedidos = self.pedir("GET", "/api/pedidos")
        self.assertEqual(pedidos, previos)
        _, menu = self.pedir("GET", "/api/productos")
        espresso = [p for p in menu if p["id"] == 1][0]
        self.assertEqual(espresso["stock"], 50)

    def test_vista_previa_con_canje(self):
        cliente_id = self.nuevo_cliente("previa2@example.com")
        # Un combo de 25000 acredita 1 punto al entregarse (total 23750).
        _, pedido = self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 2, "cantidad": 1}]},
        )
        self.pedir("POST", f"/api/pedidos/{pedido['id']}/confirmar-pago")
        self.pedir(
            "PATCH", f"/api/pedidos/{pedido['id']}/estado", {"estado": "LISTO"}
        )
        self.pedir(
            "PATCH", f"/api/pedidos/{pedido['id']}/estado", {"estado": "ENTREGADO"}
        )
        estado, totales = self.pedir(
            "POST",
            "/api/pedidos/vista-previa",
            {
                "cliente_id": cliente_id,
                "items": [{"producto_id": 1, "cantidad": 2}],
                "devpoints_a_canjear": 1,
            },
        )
        self.assertEqual(estado, 200)
        self.assertEqual(totales["descuento_puntos"], 200)
        self.assertEqual(totales["total"], 15950)

    def test_vista_previa_canje_mayor_al_saldo_es_409(self):
        cliente_id = self.nuevo_cliente("previa3@example.com")
        estado, cuerpo = self.pedir(
            "POST",
            "/api/pedidos/vista-previa",
            {
                "cliente_id": cliente_id,
                "items": [{"producto_id": 1, "cantidad": 1}],
                "devpoints_a_canjear": 5,
            },
        )
        self.assertEqual(estado, 409)
        self.assertEqual(cuerpo["error"]["codigo"], "DEVPOINTS_INSUFICIENTES")

    def test_vista_previa_items_vacios_es_400(self):
        estado, _ = self.pedir(
            "POST",
            "/api/pedidos/vista-previa",
            {"cliente_id": 1, "items": []},
        )
        self.assertEqual(estado, 400)


class TestFiltroCliente(BaseAPI):
    def test_lista_solo_pedidos_del_cliente(self):
        ana = self.nuevo_cliente("ana@example.com")
        bob = self.nuevo_cliente("bob@example.com")
        self.pedir("POST", "/api/pedidos", {"cliente_id": ana, "items": [{"producto_id": 1, "cantidad": 1}]})
        self.pedir("POST", "/api/pedidos", {"cliente_id": bob, "items": [{"producto_id": 2, "cantidad": 1}]})
        estado, mios = self.pedir("GET", f"/api/pedidos?cliente_id={ana}")
        self.assertEqual(estado, 200)
        self.assertEqual(len(mios), 1)
        self.assertEqual(mios[0]["cliente_id"], ana)
        estado, todos = self.pedir("GET", "/api/pedidos")
        self.assertEqual(len(todos), 2)

    def test_filtro_invalido_es_400(self):
        estado, _ = self.pedir("GET", "/api/pedidos?cliente_id=mal")
        self.assertEqual(estado, 400)


class TestRobustezAPI(BaseAPI):
    def test_head_sin_cuerpo_con_misma_longitud(self):
        # El GET deja la referencia de longitud para comparar con el HEAD.
        estado, menu = self.pedir("GET", "/api/productos")
        self.assertEqual(estado, 200)
        referencia = json.dumps(menu, ensure_ascii=False).encode("utf-8")
        anfitrion, puerto = self.base.replace("http://", "").split(":")
        conexion = http.client.HTTPConnection(anfitrion, int(puerto), timeout=5)
        try:
            conexion.request("HEAD", "/api/productos")
            respuesta = conexion.getresponse()
            cuerpo = respuesta.read()
        finally:
            conexion.close()
        self.assertEqual(respuesta.status, 200)
        self.assertEqual(cuerpo, b"")
        self.assertEqual(int(respuesta.getheader("Content-Length")), len(referencia))

    def test_cuerpo_demasiado_grande_es_413(self):
        grande = "x" * (MAX_CUERPO + 1)
        datos = grande.encode("utf-8")
        anfitrion, puerto = self.base.replace("http://", "").split(":")
        conexion = http.client.HTTPConnection(anfitrion, int(puerto), timeout=5)
        try:
            conexion.request(
                "POST",
                "/api/clientes",
                body=datos,
                headers={"Content-Type": "application/json"},
            )
            respuesta = conexion.getresponse()
            estado = respuesta.status
            cuerpo = json.loads(respuesta.read().decode("utf-8"))
        finally:
            conexion.close()
        self.assertEqual(estado, 413)
        self.assertEqual(cuerpo["error"]["codigo"], "CUERPO_DEMASIADO_GRANDE")

    def test_json_malformado_es_400(self):
        anfitrion, puerto = self.base.replace("http://", "").split(":")
        conexion = http.client.HTTPConnection(anfitrion, int(puerto), timeout=5)
        try:
            conexion.request(
                "POST",
                "/api/clientes",
                body=b"{no-valido",
                headers={"Content-Type": "application/json"},
            )
            respuesta = conexion.getresponse()
            estado = respuesta.status
            cuerpo = json.loads(respuesta.read().decode("utf-8"))
        finally:
            conexion.close()
        self.assertEqual(estado, 400)
        self.assertEqual(cuerpo["error"]["codigo"], "ENTRADA_INVALIDA")

    def test_valueerror_crudo_es_500(self):
        # Un ValueError fuera de validación no debe exponerse como 400.
        with patch(
            "presentacion.api.servidor.ServicioCatalogo.listar_menu",
            side_effect=ValueError("fallo interno"),
        ):
            estado, cuerpo = self.pedir("GET", "/api/productos")
        self.assertEqual(estado, 500)
        self.assertEqual(cuerpo["error"]["codigo"], "ERROR_INTERNO")

    def test_filtro_estado_invalido_y_valido(self):
        estado, _ = self.pedir("GET", "/api/pedidos?estado=INVENTADO")
        self.assertEqual(estado, 400)
        cliente_id = self.nuevo_cliente("estado@example.com")
        self.pedir(
            "POST",
            "/api/pedidos",
            {"cliente_id": cliente_id, "items": [{"producto_id": 1, "cantidad": 1}]},
        )
        estado, filtrados = self.pedir("GET", "/api/pedidos?estado=PENDIENTE_DE_PAGO")
        self.assertEqual(estado, 200)
        self.assertTrue(all(p["estado"] == "PENDIENTE_DE_PAGO" for p in filtrados))
        estado, vacios = self.pedir("GET", "/api/pedidos?estado=LISTO")
        self.assertEqual(estado, 200)
        self.assertEqual(vacios, [])


class TestArranque(unittest.TestCase):
    def test_inicializar_bd_crea_esquema_y_semillas(self):
        temporal = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temporal.close()
        ruta = Path(temporal.name)
        ruta.unlink()
        try:
            self.assertTrue(inicializar_bd(ruta))
            self.assertFalse(inicializar_bd(ruta))
            conexion = sqlite3.connect(ruta)
            try:
                total = conexion.execute(
                    "SELECT COUNT(*) FROM productos"
                ).fetchone()[0]
            finally:
                conexion.close()
            self.assertEqual(total, 6)
            self.assertTrue(inicializar_bd(ruta, reiniciar=True))
        finally:
            ruta.unlink(missing_ok=True)


    def test_inicializar_bd_con_archivo_vacio_existente(self):
        # Un archivo vacío (p. ej. creado por una conexión interrumpida) se inicializa igual.
        temporal = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temporal.close()
        ruta = Path(temporal.name)
        try:
            self.assertTrue(inicializar_bd(ruta))
            conexion = sqlite3.connect(ruta)
            try:
                total = conexion.execute(
                    "SELECT COUNT(*) FROM productos"
                ).fetchone()[0]
            finally:
                conexion.close()
            self.assertEqual(total, 6)
        finally:
            ruta.unlink(missing_ok=True)

    def test_inicializar_bd_con_base_sana_no_toca_nada(self):
        temporal = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temporal.close()
        ruta = Path(temporal.name)
        ruta.unlink()
        try:
            self.assertTrue(inicializar_bd(ruta))
            conexion = sqlite3.connect(ruta)
            try:
                conexion.execute(
                    "INSERT INTO productos (nombre, precio_base, stock)"
                    " VALUES ('Prueba Temporal', 1000, 1)"
                )
                conexion.commit()
            finally:
                conexion.close()
            # Con las tablas presentes no se toca nada, ni siquiera con datos propios.
            self.assertFalse(inicializar_bd(ruta))
            conexion = sqlite3.connect(ruta)
            try:
                total = conexion.execute(
                    "SELECT COUNT(*) FROM productos"
                ).fetchone()[0]
            finally:
                conexion.close()
            self.assertEqual(total, 7)
        finally:
            ruta.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()