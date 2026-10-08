"""Validación sintáctica de entradas: requeridos, tipos y formato de correo.

No evalúa reglas de negocio; solo la forma de los datos que llegan por HTTP.
"""

import re

# Correo con forma válida: algo@dominio.ext (solo sintaxis, sin reglas).
PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def exigir_texto(valor, campo):
    """Valida texto no vacío o rechaza con ValueError."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"el campo {campo} es requerido")
    return valor.strip()


def exigir_correo(correo):
    """Valida el formato del correo o rechaza con ValueError."""
    if not isinstance(correo, str) or not PATRON_CORREO.match(correo):
        raise ValueError("el correo no tiene un formato válido")
    return correo


def exigir_entero_positivo(valor, campo):
    """Valida entero mayor que cero o rechaza con ValueError."""
    # bool es subclase de int: se excluye para no aceptar true/false.
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ValueError(f"el campo {campo} debe ser un entero mayor que cero")
    return valor


def exigir_entero_no_negativo(valor, campo):
    """Valida entero mayor o igual que cero o rechaza con ValueError."""
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ValueError(
            f"el campo {campo} debe ser un entero mayor o igual que cero"
        )
    return valor