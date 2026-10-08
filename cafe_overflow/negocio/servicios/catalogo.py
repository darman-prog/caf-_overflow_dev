"""Servicio de catálogo: entrega el menú con precio y disponibilidad."""

from negocio.entidades import Producto
from negocio.excepciones import ProductoNoEncontradoError
from negocio.puertos import ProductoDAO

# Stock igual o inferior a este umbral se muestra como "bajo" en la UI (P-2).
UMBRAL_STOCK_BAJO = 5


def disponibilidad_stock(stock: int) -> str:
    """Clasifica el stock para su exhibición: disponible, bajo o agotado."""
    if stock <= 0:
        return "agotado"
    if stock <= UMBRAL_STOCK_BAJO:
        return "bajo"
    return "disponible"


class ServicioCatalogo:
    """Consulta los productos a través del DAO, sin reglas de negocio."""

    def __init__(self, productos: ProductoDAO):
        self._productos = productos

    def listar_menu(self) -> list[Producto]:
        """Devuelve todos los productos del menú."""
        return self._productos.listar_todos()

    def obtener_producto(self, producto_id: int) -> Producto:
        """Devuelve un producto o rechaza si no existe."""
        producto = self._productos.obtener_por_id(producto_id)
        if producto is None:
            raise ProductoNoEncontradoError("el producto no existe")
        return producto