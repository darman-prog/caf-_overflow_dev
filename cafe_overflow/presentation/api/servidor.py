"""Servidor HTTP y controladores: rutas, JSON y traducción de errores.

Los controladores validan formato, convierten JSON a objetos simples y
delegan en los servicios de negocio. No calculan, no acceden a la BD.
"""

import json
import re
import traceback
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from negocio.entidades import Cliente, Pedido, Producto, Totales
from negocio.enums import EstadoPedido
from negocio.excepciones import (
    ClienteNoEncontradoError,
    CorreoDuplicadoError,
    DevPointsInsuficientesError,
    ErrorDominio,
    PedidoNoEncontradoError,
    PedidoPendienteError,
    ProductoNoEncontradoError,
    StockInsuficienteError,
    TransicionEstadoInvalidaError,
)
from negocio.servicios.catalogo import ServicioCatalogo, disponibilidad_stock
from negocio.servicios.lealtad import ServicioLealtad
from negocio.servicios.pedidos import ServicioPedidos
from negocio.servicios.precios import ServicioPrecios
from presentation.validacion import (
    exigir_correo,
    exigir_entero_no_negativo,
    exigir_entero_positivo,
    exigir_texto,
)

# Carpeta con la aplicación web (se sirve tal cual, sin plantillas).
DIR_WEB = Path(__file__).resolve().parents[1] / "web"

# Dominio -> (estado HTTP, código público). Toda la API usa este mapa.
MAPA_ERRORES = {
    ClienteNoEncontradoError: (404, "CLIENTE_NO_ENCONTRADO"),
    ProductoNoEncontradoError: (404, "PRODUCTO_NO_ENCONTRADO"),
    PedidoNoEncontradoError: (404, "PEDIDO_NO_ENCONTRADO"),
    StockInsuficienteError: (409, "STOCK_INSUFICIENTE"),
    PedidoPendienteError: (409, "PEDIDO_PENDIENTE"),
    DevPointsInsuficientesError: (409, "DEVPOINTS_INSUFICIENTES"),
    TransicionEstadoInvalidaError: (409, "TRANSICION_INVALIDA"),
    CorreoDuplicadoError: (409, "CORREO_DUPLICADO"),
}


@dataclass
class Controladores:
    """Servicios disponibles para los controladores HTTP."""

    catalogo: ServicioCatalogo
    lealtad: ServicioLealtad
    pedidos: ServicioPedidos
    precios: ServicioPrecios


def _error(codigo: str, mensaje: str) -> dict:
    # Formato único de error de la API.
    return {"error": {"codigo": codigo, "mensaje": mensaje}}


def producto_a_json(producto: Producto) -> dict:
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "precio_base": int(producto.precio_base),
        "stock": producto.stock,
        "disponibilidad": disponibilidad_stock(producto.stock),
    }


def cliente_a_json(cliente: Cliente) -> dict:
    return {
        "id": cliente.id,
        "nombre": cliente.nombre,
        "correo": cliente.correo,
        "nivel": cliente.nivel.value,
        "devpoints": cliente.devpoints,
        "acumulado_compras": int(cliente.acumulado_compras),
    }


def pedido_a_json(pedido: Pedido) -> dict:
    return {
        "id": pedido.id,
        "cliente_id": pedido.cliente_id,
        "estado": pedido.estado.value,
        "total": int(pedido.total),
        "devpoints_canjeados": pedido.devpoints_canjeados,
        "fecha": pedido.fecha.isoformat() if pedido.fecha else None,
        "items": [
            {
                "producto_id": item.producto_id,
                "cantidad": item.cantidad,
                "precio_unitario": int(item.precio_unitario),
            }
            for item in pedido.items
        ],
    }


def totales_a_json(totales: Totales) -> dict:
    # El dinero viaja como entero (pesos), igual que en la base (S-11).
    return {
        "subtotal": int(totales.subtotal),
        "descuento_nivel": int(totales.descuento_nivel),
        "descuento_puntos": int(totales.descuento_puntos),
        "total": int(totales.total),
    }


class ManejadorCafe(SimpleHTTPRequestHandler):
    """Atiende la API bajo /api y sirve la web estática desde web/."""

    def __init__(self, *args, controladores=None, directorio_web=None, **kwargs):
        # Los servicios llegan inyectados con functools.partial al crear el servidor.
        self.controladores = controladores
        super().__init__(*args, directory=str(directorio_web), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path.startswith("/api/"):
            self._despachar("GET")
        else:
            super().do_GET()

    def do_HEAD(self):
        if urlparse(self.path).path.startswith("/api/"):
            self._responder(404, _error("NO_ENCONTRADO", "recurso no encontrado"))
        else:
            super().do_HEAD()

    def do_POST(self):
        if urlparse(self.path).path.startswith("/api/"):
            self._despachar("POST")
        else:
            self._responder(404, _error("NO_ENCONTRADO", "recurso no encontrado"))

    def do_PATCH(self):
        if urlparse(self.path).path.startswith("/api/"):
            self._despachar("PATCH")
        else:
            self._responder(404, _error("NO_ENCONTRADO", "recurso no encontrado"))

    def list_directory(self, ruta):
        # Sin listado de directorios: la web solo expone sus archivos.
        self.send_error(404)
        return None

    def _despachar(self, metodo):
        partes = urlparse(self.path)
        # parse_qs ignora parámetros vacíos; si se repite, vale el primero.
        consulta = {k: v[0] for k, v in parse_qs(partes.query).items()}
        cuerpo = self._leer_cuerpo() if metodo in ("POST", "PATCH") else {}
        try:
            if not isinstance(cuerpo, dict):
                raise ValueError("el cuerpo debe ser un objeto JSON")
            estado, carga = self._enrutar(metodo, partes.path, consulta, cuerpo)
        except ValueError as error:
            estado, carga = 400, _error("ENTRADA_INVALIDA", str(error))
        except ErrorDominio as error:
            estado, codigo = MAPA_ERRORES.get(type(error), (500, "ERROR_DOMINIO"))
            carga = _error(codigo, str(error))
        except LookupError:
            estado, carga = 404, _error("NO_ENCONTRADO", "recurso no encontrado")
        except Exception:
            # Lo inesperado se registra y se responde genérico (sin filtrar detalles).
            traceback.print_exc()
            estado, carga = 500, _error(
                "ERROR_INTERNO", "error inesperado del servidor"
            )
        self._responder(estado, carga)

    def _leer_cuerpo(self):
        longitud = int(self.headers.get("Content-Length") or 0)
        if longitud == 0:
            return {}
        datos = self.rfile.read(longitud).decode("utf-8")
        # Un JSON malformado es entrada inválida (400), no error interno.
        return json.loads(datos)

    def _responder(self, estado, carga):
        cuerpo = json.dumps(carga, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _enrutar(self, metodo, ruta, consulta, cuerpo):
        c = self.controladores
        if metodo == "GET" and ruta == "/api/productos":
            return 200, [producto_a_json(p) for p in c.catalogo.listar_menu()]
        if metodo == "POST" and ruta == "/api/clientes":
            nombre = exigir_texto(cuerpo.get("nombre"), "nombre")
            correo = exigir_correo(cuerpo.get("correo"))
            cliente = c.lealtad.registrar_cliente(nombre, correo)
            return 201, cliente_a_json(cliente)
        coincidencia = re.fullmatch(r"/api/clientes/(\d+)", ruta)
        if metodo == "GET" and coincidencia:
            cliente = c.lealtad.obtener_cuenta(int(coincidencia.group(1)))
            return 200, cliente_a_json(cliente)
        if metodo == "POST" and ruta == "/api/pedidos":
            cliente_id, renglones, canje = self._leer_solicitud_pedido(cuerpo)
            pedido = c.pedidos.registrar_pedido(cliente_id, renglones, canje)
            return 201, pedido_a_json(pedido)
        if metodo == "POST" and ruta == "/api/pedidos/vista-previa":
            cliente_id, renglones, canje = self._leer_solicitud_pedido(cuerpo)
            totales = c.pedidos.vista_previa(cliente_id, renglones, canje)
            return 200, totales_a_json(totales)
        if metodo == "GET" and ruta == "/api/pedidos":
            nombre = consulta.get("estado")
            estado = None
            if nombre is not None:
                if nombre not in (
                    "PENDIENTE_DE_PAGO",
                    "EN_PREPARACION",
                    "LISTO",
                    "ENTREGADO",
                ):
                    raise ValueError("estado de pedido inválido")
                estado = EstadoPedido(nombre)
            return 200, [pedido_a_json(p) for p in c.pedidos.listar_pedidos(estado)]
        coincidencia = re.fullmatch(r"/api/pedidos/(\d+)", ruta)
        if metodo == "GET" and coincidencia:
            pedido = c.pedidos.obtener_pedido(int(coincidencia.group(1)))
            return 200, pedido_a_json(pedido)
        coincidencia = re.fullmatch(r"/api/pedidos/(\d+)/confirmar-pago", ruta)
        if metodo == "POST" and coincidencia:
            pedido = c.pedidos.confirmar_pago(int(coincidencia.group(1)))
            return 200, pedido_a_json(pedido)
        coincidencia = re.fullmatch(r"/api/pedidos/(\d+)/estado", ruta)
        if metodo == "PATCH" and coincidencia:
            pedido_id = int(coincidencia.group(1))
            valor = cuerpo.get("estado")
            if valor not in ("LISTO", "ENTREGADO"):
                raise ValueError("el campo estado debe ser LISTO o ENTREGADO")
            # ENTREGADO acredita la compra en lealtad; no es un simple avance.
            if valor == "ENTREGADO":
                pedido = c.pedidos.entregar(pedido_id)
            else:
                pedido = c.pedidos.marcar_listo(pedido_id)
            return 200, pedido_a_json(pedido)
        # Ninguna ruta coincide: 404.
        raise LookupError(ruta)

    def _leer_solicitud_pedido(self, cuerpo):
        cliente_id = exigir_entero_positivo(cuerpo.get("cliente_id"), "cliente_id")
        crudo = cuerpo.get("items")
        # La lista de ítems es requerida y no puede venir vacía.
        if not isinstance(crudo, list) or not crudo:
            raise ValueError("el campo items es requerido y no puede estar vacío")
        renglones = []
        for renglon in crudo:
            if not isinstance(renglon, dict):
                raise ValueError("cada ítem debe traer producto_id y cantidad")
            producto_id = exigir_entero_positivo(
                renglon.get("producto_id"), "producto_id"
            )
            cantidad = exigir_entero_positivo(renglon.get("cantidad"), "cantidad")
            renglones.append((producto_id, cantidad))
        # Sin productos repetidos (el servicio lo vuelve a validar).
        ids = [producto_id for producto_id, _ in renglones]
        if len(set(ids)) != len(ids):
            raise ValueError("el pedido no puede repetir productos")
        canje = exigir_entero_no_negativo(
            cuerpo.get("devpoints_a_canjear", 0), "devpoints_a_canjear"
        )
        return cliente_id, renglones, canje


def crear_servidor(
    controladores, anfitrion="127.0.0.1", puerto=8000, directorio_web=DIR_WEB
):
    """Crea el servidor de hilos con los servicios inyectados (sin arrancar)."""
    manejador = partial(
        ManejadorCafe, controladores=controladores, directorio_web=directorio_web
    )
    return ThreadingHTTPServer((anfitrion, puerto), manejador)


def iniciar_servidor(controladores, anfitrion="127.0.0.1", puerto=8000):
    """Levanta el servidor y atiende hasta la interrupción."""
    crear_servidor(controladores, anfitrion, puerto).serve_forever()