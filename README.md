# Café Overflow — Dev & Coffee Lounge

Aplicación web de pedidos en línea para un café temático de desarrolladores, con arquitectura de tres capas (Presentación, Negocio, Persistencia) en Python puro sin frameworks. Taller Modelo N-Tier · Arquitectura de Software · UNAB.

## Estructura por capas

- `cafe_overflow/presentation/` — aplicación web (HTML/CSS/JS) y controladores HTTP/JSON.
- `cafe_overflow/negocio/` — entidades, servicios y puertos DAO con las reglas de negocio.
- `cafe_overflow/persistencia/` — esquema SQL, datos iniciales e implementación SQLite.
- `cafe_overflow/main.py` — punto de entrada que conecta las tres capas.

## Cómo probar la app

Desde la carpeta `cafe_overflow`, ejecuta:

```powershell
python main.py
```

Abre en el navegador la dirección que muestra la terminal (http://127.0.0.1:8000): la vista cliente está en `/` y el panel del personal en `/personal.html`.

## API HTTP/JSON

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/productos` | Menú |
| `POST` | `/api/clientes` | Registra cliente |
| `GET` | `/api/clientes/{id}` | Cuenta: nivel, DevPoints, acumulado |
| `POST` | `/api/pedidos/vista-previa` | Desglose sin guardar |
| `POST` | `/api/pedidos` | Registra pedido |
| `GET` | `/api/pedidos` | Lista pedidos (`?estado=`, `?cliente_id=`) |
| `GET` | `/api/pedidos/{id}` | Consulta pedido |
| `POST` | `/api/pedidos/{id}/confirmar-pago` | Confirma pago |
| `PATCH` | `/api/pedidos/{id}/estado` | Avanza a `LISTO`/`ENTREGADO` |

Errores `{"error": ...}`: `400` entrada inválida, `404` inexistente, `409` conflicto, `500` inesperado.

## Reglas de negocio

- Descuentos Junior 5% · Mid 10% · Senior 15%; ascenso a Mid ($500.000) y Senior ($1.500.000).
- DevPoints: 1 punto por cada $20.000; cada punto descuenta $200.
- Sin stock o con pedido pendiente no se registra; los estados solo avanzan en orden.

## Supuestos

- Completado = Entregado (acumulado sobre lo pagado); nivel primero, puntos después, total ≥ 0.
- Stock y puntos se descuentan al registrar; ascensos y puntos al entregar; confirma el personal; datos ficticios.

## Reglas arquitectónicas

- Presentación no calcula ni accede a la BD; negocio sin JSON/SQL; persistencia sin reglas de negocio.
