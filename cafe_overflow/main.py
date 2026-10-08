"""Punto de entrada de Café Overflow: conecta las capas e inicia el servidor.

Es el único módulo que conoce presentación, negocio y persistencia
(inyección manual de dependencias).
"""

import argparse
import sqlite3
from pathlib import Path

from negocio.servicios.catalogo import ServicioCatalogo
from negocio.servicios.lealtad import ServicioLealtad
from negocio.servicios.pedidos import ServicioPedidos
from negocio.servicios.precios import ServicioPrecios
from persistencia.sqlite_dao import (
    SqliteClienteDAO,
    SqlitePedidoDAO,
    SqliteProductoDAO,
)
from presentation.api.servidor import Controladores, crear_servidor

RAIZ = Path(__file__).resolve().parent
RUTA_BD = RAIZ / "cafe_overflow.db"
PUERTO = 8000


def inicializar_bd(ruta_bd, reiniciar=False):
    """Crea el esquema y carga los datos iniciales si la base no existe."""
    ruta_bd = Path(ruta_bd)
    if reiniciar and ruta_bd.exists():
        ruta_bd.unlink()
    if ruta_bd.exists():
        return False
    esquema = (RAIZ / "persistencia" / "esquema.sql").read_text(encoding="utf-8")
    semillas = (RAIZ / "persistencia" / "datos_iniciales.sql").read_text(
        encoding="utf-8"
    )
    conexion = sqlite3.connect(ruta_bd)
    try:
        conexion.executescript(esquema)
        conexion.executescript(semillas)
        conexion.commit()
    finally:
        conexion.close()
    return True


def construir_controladores(ruta_bd):
    """Conecta los DAO con los servicios (inyección manual)."""
    productos = SqliteProductoDAO(ruta_bd)
    clientes = SqliteClienteDAO(ruta_bd)
    pedidos = SqlitePedidoDAO(ruta_bd)
    precios = ServicioPrecios()
    lealtad = ServicioLealtad(clientes)
    return Controladores(
        catalogo=ServicioCatalogo(productos),
        lealtad=lealtad,
        pedidos=ServicioPedidos(pedidos, clientes, productos, precios, lealtad),
        precios=precios,
    )


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Servidor de Café Overflow.")
    parser.add_argument(
        "--reiniciar", action="store_true", help="recrea la base con datos iniciales"
    )
    parser.add_argument("--puerto", type=int, default=PUERTO)
    args = parser.parse_args(argumentos)
    
    creada = inicializar_bd(RUTA_BD, reiniciar=args.reiniciar)
    print(f"Base de datos {'creada' if creada else 'existente'}: {RUTA_BD}")
    
    controladores = construir_controladores(RUTA_BD)
    servidor = crear_servidor(controladores, "127.0.0.1", args.puerto)
    
    print(f"Sirviendo en http://127.0.0.1:{args.puerto} — Ctrl+C para detener")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor…")
    finally:
        servidor.shutdown()
        servidor.server_close()
    print("Servidor detenido.")


if __name__ == "__main__":
    main()