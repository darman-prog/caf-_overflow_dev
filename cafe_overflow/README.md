# Café Overflow — Dev & Coffee Lounge

Aplicación web de pedidos en línea para un café temático de desarrolladores, con arquitectura de tres capas (Presentación, Negocio, Persistencia) en Python puro sin frameworks. Taller Modelo N-Tier · Arquitectura de Software · UNAB.

## Estructura por capas

- `presentation/` — aplicación web (`web/`: HTML/CSS/JS vanilla) y controladores HTTP/JSON (`api/`); solo valida sintaxis y muestra valores del servidor.
- `negocio/` — entidades, enums, excepciones, servicios (precios, lealtad, pedidos, catálogo) y puertos DAO; aquí viven todas las reglas de negocio.
- `persistencia/` — esquema SQL, datos iniciales 100% ficticios e implementación SQLite de los puertos.
- `pruebas/` — unitarias de negocio con DAO falsos en memoria (`negocio/`), integración con SQLite temporal (`persistencia/`) e integración HTTP (`integracion/`).
- `main.py` — punto de entrada; único módulo que conecta las tres capas.

## Cómo ejecutar

Requiere Python 3.10 o superior, solo biblioteca estándar (sin instalación de paquetes).

```powershell
cd cafe_overflow
python main.py
```

Abrir http://localhost:8000 (cliente) y http://localhost:8000/personal.html (personal).

Opciones: `python main.py --puerto 8080` · `python main.py --reiniciar` (recrea la base con datos iniciales).

## Cómo probar

```powershell
cd cafe_overflow
python -X utf8 -m unittest discover -v
```

89 pruebas: reglas de negocio y casos límite, persistencia transaccional y contrato HTTP.

## API HTTP/JSON (resumen)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/productos` | Menú con precio, stock y disponibilidad |
| `POST` | `/api/clientes` | Registra un cliente nuevo |
| `GET` | `/api/clientes/{id}` | Nivel, DevPoints y acumulado |
| `POST` | `/api/pedidos/vista-previa` | Desglose sin persistir (subtotal, descuentos, total) |
| `POST` | `/api/pedidos` | Registra un pedido en Pendiente de pago |
| `GET` | `/api/pedidos?estado=...` | Lista pedidos con filtro opcional |
| `GET` | `/api/pedidos/{id}` | Consulta un pedido |
| `POST` | `/api/pedidos/{id}/confirmar-pago` | Pendiente de pago → En preparación |
| `PATCH` | `/api/pedidos/{id}/estado` | `LISTO` o `ENTREGADO` (con acreditación) |

Errores con formato único `{"error": {"codigo", "mensaje"}}`: `400` entrada inválida, `404` inexistente, `409` conflicto de negocio, `500` inesperado.

## Reglas de negocio (resumen)

- Descuento por nivel: Junior 5%, Mid 10%, Senior 15%.
- Ascenso automático: Mid desde $500.000 y Senior desde $1.500.000 acumulados.
- DevPoints: 1 punto por cada $20.000 pagados; cada punto vale $200 de descuento.
- Sin stock suficiente o con pedido pendiente de pago no se registra.
- Los estados solo avanzan en orden, sin saltos ni retrocesos.

## Supuestos de diseño

1. "Pedido completado" = estado Entregado; el acumulado suma lo efectivamente pagado.
2. Descuento por nivel primero, DevPoints después; total nunca negativo.
3. Stock y DevPoints se descuentan al registrar; ascensos y acreditación al entregar.
4. El personal confirma el pago; sin cancelaciones en el alcance.
5. Datos iniciales 100% ficticios; diagramas C4 en documento aparte.

## Reglas arquitectónicas

- Presentación no calcula totales ni descuentos y no accede a la BD.
- Negocio no contiene JSON/HTML ni SQL.
- Persistencia no evalúa reglas de negocio (CHECK e índices son red de seguridad).