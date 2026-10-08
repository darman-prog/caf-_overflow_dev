# Café Overflow — Dev & Coffee Lounge
Aplicación web de pedidos en línea para un café temático de desarrolladores, con arquitectura de tres capas (Presentación, Negocio, Persistencia) en Python puro sin frameworks. Taller Modelo N-Tier · Arquitectura de Software · UNAB.
## Estructura por capas
- `presentation/` — aplicación web (HTML/CSS/JS) y controladores HTTP/JSON; solo valida sintaxis.
- `negocio/` — entidades, servicios (precios, lealtad, pedidos, catálogo) y puertos DAO; aquí viven todas las reglas de negocio.
- `persistencia/` — esquema SQL, datos iniciales e implementación SQLite de los puertos.
- `pruebas/` — unitarias de negocio (con DAO falsos) e integración de persistencia y API.
## Cómo ejecutar
Requiere Python 3.10 o superior, solo biblioteca estándar.
```powershell
cd cafe_overflow
python main.py
```
Abrir http://localhost:8000 en el navegador.
## Cómo probar
```powershell
cd cafe_overflow
python -X utf8 -m unittest discover -v
```
## Supuestos de diseño (resumen)
1. "Pedido completado" = estado Entregado; el acumulado suma lo efectivamente pagado.
2. Descuento por nivel primero, DevPoints después; total nunca negativo.
3. Stock y DevPoints se descuentan al registrar el pedido; ascensos y acreditación al entregar.
4. El personal confirma el pago (Pendiente de pago → En preparación); sin saltos ni retrocesos.