/* carrito.js — carrito con vista-previa del servidor.
   REGLA DE ORO: subtotal, descuentos y total llegan de POST /api/pedidos/vista-previa.
   La UI solo formatea con Intl; jamás suma ni multiplica dinero. */
import { api, ApiError } from "../api.js";
import {
  abrirRegistro, badgePuntos, botonCargando, cop, el, getClienteId, guardarCarrito,
  leerCarrito, toast, vaciarCarrito,
} from "../ui.js";

let catalogo = new Map();
let devpointsEditados = "";
let temporizadorPrevia = null;

function cuerpoPedido() {
  const items = leerCarrito().map((r) => ({ producto_id: r.producto_id, cantidad: r.cantidad }));
  // El input solo admite dígitos; lo inválido se trata como 0 y el servidor decide.
  const canje = /^\d+$/.test(devpointsEditados.trim()) ? Number(devpointsEditados.trim()) : 0;
  return { items, canje };
}

function filaResumen(dt, valorTexto) {
  const fila = el("div", { clase: "resumen__fila" });
  fila.appendChild(el("dt", { texto: dt }));
  fila.appendChild(el("dd", { texto: valorTexto }));
  return fila;
}

// Pinta el desglose tal cual lo devuelve la vista-previa (sin tocar los números).
function pintarResumen(totales) {
  const caja = document.getElementById("carrito-resumen");
  caja.textContent = "";
  const lista = el("dl", { clase: "resumen" });
  lista.appendChild(filaResumen("Subtotal", cop(totales.subtotal)));
  lista.appendChild(filaResumen("Descuento por nivel", `− ${cop(totales.descuento_nivel)}`));
  lista.appendChild(filaResumen("Descuento por DevPoints", `− ${cop(totales.descuento_puntos)}`));
  const total = el("div", { clase: "resumen__fila resumen__fila--total" });
  total.appendChild(el("dt", { texto: "Total" }));
  total.appendChild(el("dd", { texto: cop(totales.total) }));
  lista.appendChild(total);
  caja.appendChild(lista);
  const barra = document.getElementById("carrito-total-barra");
  barra.textContent = cop(totales.total);
}

function pintarVacio(mensaje) {
  const caja = document.getElementById("carrito-resumen");
  caja.textContent = "";
  caja.appendChild(el("p", { clase: "texto-secundario", texto: mensaje }));
  document.getElementById("carrito-total-barra").textContent = "—";
}

// Pide la vista-previa al servidor con debounce para no saturarlo al editar.
function programarPrevia() {
  clearTimeout(temporizadorPrevia);
  temporizadorPrevia = setTimeout(() => previa(), 350);
}

async function previa() {
  const { items, canje } = cuerpoPedido();
  const clienteId = getClienteId();
  if (items.length === 0) {
    pintarVacio("El carrito está vacío. Agrega algo del menú.");
    return;
  }
  if (!clienteId) {
    pintarVacio("Regístrate para ver el total con tus descuentos.");
    return;
  }
  try {
    const totales = await api.vistaPrevia({ cliente_id: Number(clienteId), items, devpoints_a_canjear: canje });
    pintarResumen(totales);
  } catch (error) {
    // El 409 (p. ej. puntos insuficientes) muestra el mensaje del servidor.
    pintarVacio(error instanceof ApiError ? error.message : "No se pudo calcular el total.");
  }
}

function lineaCarrito(renglon) {
  const producto = catalogo.get(renglon.producto_id);
  const nombre = producto ? producto.nombre : `Producto ${renglon.producto_id}`;
  const fila = el("div", { clase: "carrito-item" });
  fila.appendChild(el("span", { clase: "carrito-item__nombre", texto: nombre }));
  if (producto) {
    fila.appendChild(el("span", { clase: "carrito-item__precio", texto: `${cop(producto.precio_base)} c/u` }));
  }
  // Stepper limitado por el stock que informó el servidor (el negocio valida).
  const max = producto ? producto.stock : 99;
  const stepper = el("div", { clase: "stepper" });
  const menos = el("button", { clase: "stepper__btn", texto: "−", attrs: { type: "button", "aria-label": `Quitar uno de ${nombre}` } });
  const valor = el("span", { clase: "stepper__value", texto: String(renglon.cantidad), attrs: { "aria-label": `Cantidad de ${nombre}` } });
  const mas = el("button", { clase: "stepper__btn", texto: "+", attrs: { type: "button", "aria-label": `Agregar uno de ${nombre}` } });
  menos.addEventListener("click", () => cambiarCantidad(renglon.producto_id, renglon.cantidad - 1));
  mas.addEventListener("click", () => cambiarCantidad(renglon.producto_id, renglon.cantidad + 1, max));
  if (renglon.cantidad >= max) mas.disabled = true;
  stepper.append(menos, valor, mas);
  fila.appendChild(stepper);
  const quitar = el("button", {
    clase: "btn btn--ghost", texto: "Quitar",
    attrs: { type: "button", "aria-label": `Quitar ${nombre} del carrito` },
  });
  quitar.addEventListener("click", () => cambiarCantidad(renglon.producto_id, 0));
  fila.appendChild(quitar);
  return fila;
}

function cambiarCantidad(producto_id, nueva, max = 99) {
  let items = leerCarrito();
  if (nueva <= 0) items = items.filter((r) => r.producto_id !== producto_id);
  else items = items.map((r) => (r.producto_id === producto_id ? { ...r, cantidad: Math.min(nueva, max) } : r));
  guardarCarrito(items);
}

async function pintarDisponibles() {
  const ayuda = document.getElementById("devpoints-ayuda");
  const clienteId = getClienteId();
  if (!clienteId) {
    ayuda.textContent = "Regístrate para canjear DevPoints.";
    return;
  }
  try {
    // El saldo disponible siempre viene del servidor, nunca de un cálculo local.
    const cuenta = await api.obtenerCliente(clienteId);
    ayuda.textContent = "";
    ayuda.appendChild(el("span", { texto: `Disponibles: ${cuenta.devpoints} ` }));
    ayuda.appendChild(badgePuntos(`${cuenta.devpoints} pts`));
  } catch {
    ayuda.textContent = "No se pudo cargar tu saldo de DevPoints.";
  }
}

function pintarItems() {
  const lista = document.getElementById("carrito-items");
  lista.textContent = "";
  const items = leerCarrito();
  // La barra sticky solo existe cuando hay algo que confirmar.
  document.getElementById("sticky-bar").hidden = items.length === 0;
  if (items.length === 0) {
    lista.appendChild(el("p", { clase: "texto-secundario", texto: "Aún no tienes pedidos en el carrito. Explora el menú." }));
  } else {
    for (const r of items) lista.appendChild(lineaCarrito(r));
  }
  programarPrevia();
}

function refrescar() {
  pintarItems();
  pintarDisponibles();
}

// Revisión previa al envío: el modal pinta el desglose fresco del servidor.
let revisionPendiente = null;
let focoAlCerrar = null;

function pintarDesglose(contenedor, totales, lineas) {
  contenedor.textContent = "";
  // Solo cuenta líneas del carrito; el dinero llega intacto del servidor.
  contenedor.appendChild(el("p", {
    clase: "texto-secundario",
    texto: `${lineas} ${lineas === 1 ? "producto" : "productos"} en el carrito`,
  }));
  const lista = el("dl", { clase: "resumen" });
  lista.appendChild(filaResumen("Subtotal", cop(totales.subtotal)));
  lista.appendChild(filaResumen("Descuento por nivel", `− ${cop(totales.descuento_nivel)}`));
  lista.appendChild(filaResumen("Descuento por DevPoints", `− ${cop(totales.descuento_puntos)}`));
  const total = el("div", { clase: "resumen__fila resumen__fila--total" });
  total.appendChild(el("dt", { texto: "Total" }));
  total.appendChild(el("dd", { texto: cop(totales.total) }));
  lista.appendChild(total);
  contenedor.appendChild(lista);
}

async function revisar(boton) {
  const clienteId = getClienteId();
  if (!clienteId) {
    abrirRegistro();
    return;
  }
  const { items, canje } = cuerpoPedido();
  if (items.length === 0) {
    toast("El carrito está vacío.", "info");
    return;
  }
  const texto = boton.textContent;
  botonCargando(boton, true);
  try {
    // Desglose fresco justo antes de enviar; si algo cambió, el servidor lo dice.
    const totales = await api.vistaPrevia({ cliente_id: Number(clienteId), items, devpoints_a_canjear: canje });
    revisionPendiente = { items, canje, clienteId: Number(clienteId) };
    pintarDesglose(document.getElementById("revision-desglose"), totales, items.length);
    const dialogo = document.getElementById("dialogo-revision");
    focoAlCerrar = boton;
    if (dialogo && !dialogo.open) dialogo.showModal();
    document.getElementById("revision-confirmar")?.focus();
  } catch (error) {
    toast(error instanceof ApiError ? error.message : "No se pudo revisar el pedido.", "error");
  } finally {
    botonCargando(boton, false, texto);
  }
}

async function enviarRevision(boton) {
  if (!revisionPendiente) return;
  const { items, canje, clienteId } = revisionPendiente;
  const texto = boton.textContent;
  botonCargando(boton, true);
  try {
    // El total definitivo lo calcula y persiste el servidor; aquí solo se muestra.
    const pedido = await api.crearPedido({ cliente_id: clienteId, items, devpoints_a_canjear: canje });
    revisionPendiente = null;
    document.getElementById("dialogo-revision")?.close();
    vaciarCarrito();
    devpointsEditados = "";
    const input = document.getElementById("devpoints-input");
    if (input) input.value = "";
    toast(`Pedido ${pedido.id} registrado. Total ${cop(pedido.total)}.`, "success");
    window.dispatchEvent(new CustomEvent("pedidos:actualizado"));
    refrescar();
  } catch (error) {
    // El 409 conserva el carrito y muestra el mensaje del servidor.
    document.getElementById("dialogo-revision")?.close();
    toast(error instanceof ApiError ? error.message : "No se pudo registrar el pedido.", "error");
  } finally {
    botonCargando(boton, false, texto);
  }
}

async function cargarCatalogo() {
  try {
    const productos = await api.listarProductos();
    catalogo = new Map(productos.map((p) => [p.id, p]));
  } catch {
    catalogo = new Map();
  }
  pintarItems();
}

function init() {
  const input = document.getElementById("devpoints-input");
  input?.addEventListener("input", () => {
    devpointsEditados = input.value;
    // Validación solo sintáctica: se aceptan dígitos; el negocio valida el saldo.
    input.setAttribute("aria-invalid", /^\d*$/.test(input.value) ? "false" : "true");
    programarPrevia();
  });
  document.getElementById("carrito-confirmar")?.addEventListener("click", (e) => revisar(e.currentTarget));
  document.getElementById("revision-confirmar")?.addEventListener("click", (e) => enviarRevision(e.currentTarget));
  document.getElementById("revision-cancelar")?.addEventListener("click", () => document.getElementById("dialogo-revision")?.close());
  document.getElementById("dialogo-revision")?.addEventListener("close", () => {
    // Esc o Cancelar devuelven el foco a quien abrió la revisión.
    if (focoAlCerrar?.isConnected) focoAlCerrar.focus({ preventScroll: true });
    focoAlCerrar = null;
  });
  document.getElementById("carrito-vaciar")?.addEventListener("click", (e) => {
    if (leerCarrito().length === 0) {
      toast("El carrito ya está vacío.", "info");
      return;
    }
    const dialogo = document.getElementById("dialogo-vaciar");
    focoAlCerrar = e.currentTarget;
    if (dialogo && !dialogo.open) dialogo.showModal();
    document.getElementById("vaciar-confirmar")?.focus();
  });
  document.getElementById("vaciar-confirmar")?.addEventListener("click", () => {
    vaciarCarrito();
    document.getElementById("dialogo-vaciar")?.close();
    toast("Carrito vaciado.", "info");
  });
  document.getElementById("vaciar-cancelar")?.addEventListener("click", () => document.getElementById("dialogo-vaciar")?.close());
  document.getElementById("dialogo-vaciar")?.addEventListener("close", () => {
    if (focoAlCerrar?.isConnected) focoAlCerrar.focus({ preventScroll: true });
    focoAlCerrar = null;
  });
  // La barra sticky navega al resumen; la única confirmación primaria vive en el panel.
  document.getElementById("carrito-ir-resumen")?.addEventListener("click", () => {
    document.getElementById("carrito-resumen")?.scrollIntoView({ block: "nearest" });
    document.getElementById("carrito-confirmar")?.focus({ preventScroll: true });
  });
  window.addEventListener("carrito:actualizado", () => refrescar());
  window.addEventListener("pedidos:actualizado", () => pintarDisponibles());
  window.addEventListener("cliente:actualizado", () => {
    // Al cambiar de sesión se limpia el canje escrito y se recalcula la vista.
    if (!getClienteId()) {
      devpointsEditados = "";
      const campo = document.getElementById("devpoints-input");
      if (campo) {
        campo.value = "";
        campo.removeAttribute("aria-invalid");
      }
    }
    refrescar();
  });
  cargarCatalogo();
  pintarDisponibles();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
