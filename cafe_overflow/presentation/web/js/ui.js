/* ui.js — helpers de presentación: formato, badges, pipeline, toasts.
   Formatear ≠ calcular: el único número que sale de aquí es texto ya calculado
   por el servidor. Sin innerHTML con datos del servidor. */

const formatoCOP = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

// Formatea pesos enteros del servidor como moneda colombiana.
export function cop(valor) {
  return formatoCOP.format(valor);
}

// Crea un elemento con texto seguro (textContent, nunca innerHTML).
export function el(tag, { clase = "", texto = "", attrs = {} } = {}) {
  const nodo = document.createElement(tag);
  if (clase) nodo.className = clase;
  if (texto) nodo.textContent = texto;
  for (const [k, v] of Object.entries(attrs)) nodo.setAttribute(k, v);
  return nodo;
}

const SVG_NS = "http://www.w3.org/2000/svg";

// Trazos mínimos por icono; el dibujo vive en el código, no en datos externos.
const TRAZOS = {
  taza: '<path d="M4 9h12v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V9z"/><path d="M16 10h2a2.5 2.5 0 0 1 0 5h-2"/><path d="M7 5c0-1 1-1 1-2M11 5c0-1 1-1 1-2"/>',
  moneda: '<circle cx="12" cy="12" r="8"/><path d="M12 8v8M9.5 10h4a1.5 1.5 0 0 1 0 3h-3a1.5 1.5 0 0 0 0 3h4"/>',
  reloj: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  engranaje: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
  check: '<path d="M4 12l5 5L20 7"/>',
  campana: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2.5h-15z"/><path d="M10 21a2 2 0 0 0 4 0"/>',
  caja: '<path d="M3 8l9-4 9 4v8l-9 4-9-4z"/><path d="M3 8l9 4 9-4M12 12v8"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  menos: '<path d="M5 12h14"/>',
  papelera: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  alerta: '<path d="M12 3l10 17H2z"/><path d="M12 10v4M12 17.5v.5"/>',
  equis: '<path d="M6 6l12 12M18 6L6 18"/>',
  actualizar: '<path d="M20 12a8 8 0 1 1-2.3-5.6M20 3v4h-4"/>',
};

// Icono SVG inline con currentColor; decorativo salvo aria-label explícito.
export function icono(nombre, { size = 16, label = null } = {}) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  if (label) {
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", label);
  } else {
    svg.setAttribute("aria-hidden", "true");
  }
  // Solo se inserta un trazo constante del mapa local, jamás datos del servidor.
  const contenedor = document.createElementNS(SVG_NS, "g");
  contenedor.innerHTML = TRAZOS[nombre] || "";
  svg.appendChild(contenedor);
  return svg;
}

const ETIQUETAS_ESTADO = {
  PENDIENTE_DE_PAGO: "Pendiente de pago",
  EN_PREPARACION: "En preparación",
  LISTO: "Listo",
  ENTREGADO: "Entregado",
};

const CLASE_ESTADO = {
  PENDIENTE_DE_PAGO: "badge--pendiente",
  EN_PREPARACION: "badge--preparacion",
  LISTO: "badge--listo",
  ENTREGADO: "badge--entregado",
};

export function etiquetasEstado() {
  return { ...ETIQUETAS_ESTADO };
}

// Badge de estado del pedido: texto explícito, nunca solo color.
export function badgeEstado(estado) {
  return el("span", {
    clase: `badge ${CLASE_ESTADO[estado] || "badge--entregado"}`,
    texto: ETIQUETAS_ESTADO[estado] || estado,
  });
}

// Badge de stock con el N que envía el servidor (bajo = "Quedan N").
export function badgeStock(disponibilidad, stock) {
  if (disponibilidad === "agotado") {
    return el("span", { clase: "badge badge--stock-agotado", texto: "Agotado" });
  }
  if (disponibilidad === "bajo") {
    return el("span", { clase: "badge badge--stock-bajo", texto: `Quedan ${stock}` });
  }
  return el("span", { clase: "badge badge--stock-ok", texto: "Disponible" });
}

const CLASE_NIVEL = { JUNIOR: "badge--junior", MID: "badge--mid", SENIOR: "badge--senior" };

// Badge de nivel de lealtad, independiente de estados y stock.
export function badgeNivel(nivel) {
  return el("span", {
    clase: `badge ${CLASE_NIVEL[nivel] || "badge--junior"}`,
    texto: nivel === "JUNIOR" ? "Junior" : nivel === "MID" ? "Mid" : nivel === "SENIOR" ? "Senior" : String(nivel),
  });
}

export function badgePuntos(texto) {
  return el("span", { clase: "badge badge--puntos", texto });
}

const PASOS_PIPELINE = ["PENDIENTE_DE_PAGO", "EN_PREPARACION", "LISTO", "ENTREGADO"];

// Pipeline de 4 pasos con labels siempre visibles y en español.
export function pipeline(estadoActual) {
  const actual = PASOS_PIPELINE.indexOf(estadoActual);
  const lista = el("ol", { clase: "pipeline", attrs: { "aria-label": `Progreso del pedido: ${ETIQUETAS_ESTADO[estadoActual] || estadoActual}` } });
  PASOS_PIPELINE.forEach((paso, i) => {
    if (i > 0) lista.appendChild(el("span", { clase: "pipeline__conector", attrs: { "aria-hidden": "true" } }));
    const clase = i < actual ? "pipeline__paso pipeline__paso--completo"
      : i === actual ? "pipeline__paso pipeline__paso--activo" : "pipeline__paso";
    const item = el("li", { clase, texto: ETIQUETAS_ESTADO[paso], attrs: { "data-estado": paso } });
    if (i === actual) item.setAttribute("aria-current", "step");
    lista.appendChild(item);
  });
  return lista;
}

// Estado de carga con texto terminal decorativo (el estado real va en aria-busy).
export function skeletonLinea(textoVisible) {
  const caja = el("div", { clase: "skeleton", attrs: { "aria-hidden": "true" } });
  caja.appendChild(el("p", { clase: "terminal-line", texto: `> ${textoVisible}…` }));
  return caja;
}

// Vacío: icono + frase corta + CTA con callback.
export function estadoVacio({ titulo, accionTexto, alAccion }) {
  const caja = el("div", { clase: "empty" });
  const iconoCaja = el("div", { clase: "empty__icono" });
  iconoCaja.appendChild(icono("taza", { size: 20 }));
  caja.appendChild(iconoCaja);
  caja.appendChild(el("p", { texto: titulo }));
  if (accionTexto && alAccion) {
    const btn = el("button", { clase: "btn btn--secondary", texto: accionTexto, attrs: { type: "button" } });
    btn.addEventListener("click", alAccion);
    caja.appendChild(btn);
  }
  return caja;
}

// Error de red: mensaje claro + Reintentar.
export function estadoError({ titulo, alReintentar }) {
  const caja = el("div", { clase: "error-box", attrs: { role: "alert" } });
  caja.appendChild(el("p", { clase: "error-box__titulo", texto: titulo }));
  const btn = el("button", { clase: "btn btn--secondary", texto: "Reintentar", attrs: { type: "button" } });
  btn.addEventListener("click", alReintentar);
  caja.appendChild(btn);
  return caja;
}

// Toast en la región aria-live; los errores usan assertive.
export function toast(mensaje, tipo = "info") {
  const region = document.getElementById("toasts");
  if (!region) return;
  const aviso = el("div", {
    clase: `toast toast--${tipo}`,
    attrs: { role: tipo === "error" ? "alert" : "status" },
  });
  aviso.appendChild(icono(tipo === "success" ? "check" : tipo === "error" ? "alerta" : "campana", { size: 16 }));
  aviso.appendChild(el("p", { clase: "toast__texto", texto: mensaje }));
  const cerrar = el("button", {
    clase: "toast__cerrar",
    texto: "×",
    attrs: { type: "button", "aria-label": "Cerrar aviso" },
  });
  cerrar.addEventListener("click", () => aviso.remove());
  aviso.appendChild(cerrar);
  region.appendChild(aviso);
  // Auto-descarte a los 5 s sin robar el foco.
  setTimeout(() => aviso.remove(), 5000);
}

// Loading accesible en botones: spinner + "Procesando…", sin perder foco.
export function botonCargando(boton, activo, textoOriginal) {
  if (activo) {
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
    boton.textContent = "";
    const spinner = el("span", { clase: "btn__spinner", attrs: { "aria-hidden": "true" } });
    boton.appendChild(spinner);
    boton.appendChild(el("span", { texto: "Procesando…" }));
  } else {
    boton.disabled = false;
    boton.removeAttribute("aria-busy");
    boton.textContent = textoOriginal;
  }
}

// Cliente actual: sin auth (fuera de alcance), solo id en localStorage.
const CLAVE_CLIENTE = "cafe_overflow_cliente_id";
export function getClienteId() {
  return localStorage.getItem(CLAVE_CLIENTE);
}
export function setClienteId(id) {
  localStorage.setItem(CLAVE_CLIENTE, String(id));
}
export function clearClienteId() {
  localStorage.removeItem(CLAVE_CLIENTE);
}

// Abre el diálogo de registro una sola vez (showModal falla si ya está abierto).
export function abrirRegistro() {
  const dialogo = document.getElementById("dialogo-registro");
  if (dialogo && !dialogo.open) dialogo.showModal();
}

// Carrito en localStorage: [{producto_id, cantidad}]. Sin dinero aquí.
const CLAVE_CARRITO = "cafe_overflow_carrito_v1";
export function leerCarrito() {
  try {
    const crudo = JSON.parse(localStorage.getItem(CLAVE_CARRITO) || "[]");
    if (!Array.isArray(crudo)) return [];
    // Solo renglones bien formados sobreviven a la lectura.
    return crudo.filter((r) => r && Number.isInteger(r.producto_id) && Number.isInteger(r.cantidad) && r.cantidad > 0);
  } catch {
    return [];
  }
}
export function guardarCarrito(items) {
  localStorage.setItem(CLAVE_CARRITO, JSON.stringify(items));
  window.dispatchEvent(new CustomEvent("carrito:actualizado"));
}
export function agregarAlCarrito(producto_id, cantidad = 1) {
  const items = leerCarrito();
  const linea = items.find((r) => r.producto_id === producto_id);
  if (linea) linea.cantidad += cantidad;
  else items.push({ producto_id, cantidad });
  guardarCarrito(items);
}
export function vaciarCarrito() {
  guardarCarrito([]);
}
