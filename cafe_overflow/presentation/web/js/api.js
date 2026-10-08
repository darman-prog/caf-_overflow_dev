/* api.js — cliente HTTP de la API Café Overflow.
   Solo transporta JSON; nunca calcula dinero ni valida reglas de negocio. */

// Error con el mensaje exacto del servidor para mostrarlo en un toast.
export class ApiError extends Error {
  constructor(mensaje, { codigo = "ERROR_DESCONOCIDO", http = 0 } = {}) {
    super(mensaje);
    this.name = "ApiError";
    this.codigo = codigo;
    this.http = http;
  }
}

// Lee la respuesta: la API siempre devuelve JSON (datos o {error:{codigo,mensaje}}).
async function leerRespuesta(respuesta) {
  // Un 204 sin cuerpo no ocurre en este contrato, pero se tolera.
  if (respuesta.status === 204) return null;
  return respuesta.json();
}

async function request(ruta, { metodo = "GET", cuerpo } = {}) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    // Sin conexión o servidor caído: mensaje accionable, no técnico.
    throw new ApiError("No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.", {
      codigo: "ERROR_RED",
      http: 0,
    });
  }
  let datos = null;
  try {
    datos = await leerRespuesta(respuesta);
  } catch {
    throw new ApiError("El servidor devolvió una respuesta inválida.", {
      codigo: "RESPUESTA_INVALIDA",
      http: respuesta.status,
    });
  }
  if (!respuesta.ok) {
    // El contrato promete {error:{codigo, mensaje}} en 400/404/409/500.
    const error = datos && typeof datos === "object" ? datos.error : null;
    throw new ApiError(
      (error && error.mensaje) || "Ocurrió un error inesperado.",
      { codigo: (error && error.codigo) || "ERROR_DESCONOCIDO", http: respuesta.status }
    );
  }
  return datos;
}

export const api = {
  listarProductos() {
    return request("/api/productos");
  },
  registrarCliente({ nombre, correo }) {
    return request("/api/clientes", { metodo: "POST", cuerpo: { nombre, correo } });
  },
  obtenerCliente(id) {
    return request(`/api/clientes/${encodeURIComponent(id)}`);
  },
  // Vista previa: calcula en el servidor sin persistir (el carrito la usa).
  vistaPrevia({ cliente_id, items, devpoints_a_canjear = 0 }) {
    return request("/api/pedidos/vista-previa", {
      metodo: "POST",
      cuerpo: { cliente_id, items, devpoints_a_canjear },
    });
  },
  crearPedido({ cliente_id, items, devpoints_a_canjear = 0 }) {
    return request("/api/pedidos", {
      metodo: "POST",
      cuerpo: { cliente_id, items, devpoints_a_canjear },
    });
  },
  listarPedidos(estado) {
    const qs = estado ? `?estado=${encodeURIComponent(estado)}` : "";
    return request(`/api/pedidos${qs}`);
  },
  confirmarPago(id) {
    return request(`/api/pedidos/${encodeURIComponent(id)}/confirmar-pago`, { metodo: "POST" });
  },
  // Solo LISTO o ENTREGADO acepta el servidor; no se valida nada más aquí.
  cambiarEstado(id, estado) {
    return request(`/api/pedidos/${encodeURIComponent(id)}/estado`, {
      metodo: "PATCH",
      cuerpo: { estado },
    });
  },
};
