/* personal.js — panel del personal: pedidos por estado con acciones.
   Desktop-first (kanban 4 columnas); bajo 1024px degrada a lista con filtro.
   Transiciones inválidas (409) muestran el mensaje del servidor en un toast. */
import { api, ApiError } from "../api.js";
import {
  badgeEstado, botonCargando, cop, el, etiquetasEstado,
  pipeline, skeletonLinea, estadoError, toast,
} from "../ui.js";

const ESTADOS = ["PENDIENTE_DE_PAGO", "EN_PREPARACION", "LISTO", "ENTREGADO"];

// Acción que corresponde a cada columna; ENTREGADO es terminal.
const ACCION_POR_ESTADO = {
  PENDIENTE_DE_PAGO: { texto: "Confirmar pago", siguiente: null, modo: "pago" },
  EN_PREPARACION: { texto: "Marcar listo", siguiente: "LISTO", modo: "estado" },
  LISTO: { texto: "Marcar entregado", siguiente: "ENTREGADO", modo: "estado" },
  ENTREGADO: null,
};

function tarjetaPersonal(pedido) {
  const card = el("article", { clase: "pedido-card" });
  // IDs en dataset para el buscador (comparación de texto, sin HTML).
  card.dataset.pedido = String(pedido.id);
  card.dataset.cliente = String(pedido.cliente_id);
  const cab = el("div", { clase: "pedido-card__cabecera" });
  cab.appendChild(el("span", { clase: "pedido-id", texto: `#${pedido.id}` }));
  cab.appendChild(badgeEstado(pedido.estado));
  card.appendChild(cab);
  card.appendChild(el("p", { clase: "texto-secundario", texto: `Cliente ${pedido.cliente_id} · ${pedido.items.length} productos · Total ${cop(pedido.total)}` }));
  card.appendChild(pipeline(pedido.estado));
  const accion = ACCION_POR_ESTADO[pedido.estado];
  if (accion) {
    const btn = el("button", { clase: "btn btn--primary", texto: accion.texto, attrs: { type: "button" } });
    btn.addEventListener("click", () => avanzar(pedido, accion, btn));
    card.appendChild(btn);
  }
  return card;
}

async function avanzar(pedido, accion, boton) {
  const texto = boton.textContent;
  botonCargando(boton, true);
  try {
    if (accion.modo === "pago") await api.confirmarPago(pedido.id);
    else await api.cambiarEstado(pedido.id, accion.siguiente);
    toast(`Pedido ${pedido.id} actualizado.`, "success");
    cargar();
  } catch (error) {
    toast(error instanceof ApiError ? error.message : "No se pudo actualizar el pedido.", "error");
  } finally {
    botonCargando(boton, false, texto);
  }
}

// Bulk por columna: confirmación, avance en secuencia y resumen con tolerancia a 409.
let bulkPendiente = null;
let focoBulk = null;

function pedirBulk(estado, boton) {
  const pedidos = grupoVisible(estado);
  if (pedidos.length === 0) {
    toast("No hay pedidos visibles para avanzar.", "info");
    return;
  }
  bulkPendiente = { estado, pedidos };
  const etiquetas = etiquetasEstado();
  // Conteo y estado en texto plano; el resumen final llega por toast (aria-live).
  document.getElementById("bulk-descripcion").textContent =
    `Se avanzarán ${pedidos.length} ${pedidos.length === 1 ? "pedido" : "pedidos"} de «${etiquetas[estado]}». Los que fallen se omiten y se resumen al final.`;
  focoBulk = boton;
  const dialogo = document.getElementById("dialogo-bulk");
  if (dialogo && !dialogo.open) dialogo.showModal();
  document.getElementById("bulk-confirmar")?.focus();
}

async function ejecutarBulk(boton) {
  if (!bulkPendiente) return;
  const { pedidos } = bulkPendiente;
  const accion = ACCION_POR_ESTADO[bulkPendiente.estado];
  const texto = boton.textContent;
  botonCargando(boton, true);
  let ok = 0;
  const errores = [];
  for (const pedido of pedidos) {
    try {
      if (accion.modo === "pago") await api.confirmarPago(pedido.id);
      else await api.cambiarEstado(pedido.id, accion.siguiente);
      ok += 1;
    } catch (error) {
      // Se tolera el fallo por ítem (p. ej. 409) y se sigue con el siguiente.
      errores.push(error instanceof ApiError ? error.message : "No se pudo actualizar el pedido.");
    }
  }
  const fallos = pedidos.length - ok;
  bulkPendiente = null;
  document.getElementById("dialogo-bulk")?.close();
  botonCargando(boton, false, texto);
  if (fallos === 0) toast(`${ok} ${ok === 1 ? "pedido avanzado" : "pedidos avanzados"}.`, "success");
  else toast(`${ok} listos, ${fallos} con error: ${errores[0]}`, "error");
  cargar();
}

// En móvil se ocultan las columnas que no coinciden con el filtro.
function aplicarFiltroMovil() {
  const filtro = document.getElementById("personal-filtro")?.value || "TODOS";
  const esDesktop = window.matchMedia("(min-width: 1024px)").matches;
  for (const estado of ESTADOS) {
    const col = document.getElementById(`col-${estado}`);
    if (!col) continue;
    col.hidden = !esDesktop && filtro !== "TODOS" && filtro !== estado;
  }
}

// Buscador por texto visible (id de pedido / id de cliente), sin refetch.
let busqueda = "";
let cachePedidos = [];

function aplicarBusqueda() {
  const campo = document.getElementById("personal-buscar");
  busqueda = campo ? campo.value.trim() : "";
  let visibles = 0;
  for (const card of document.querySelectorAll("#personal-board article.pedido-card")) {
    // includes sobre texto del DOM: los IDs son dígitos, otro texto no coincide.
    const coincide = !busqueda || card.dataset.pedido.includes(busqueda) || card.dataset.cliente.includes(busqueda);
    card.hidden = !coincide;
    if (coincide) visibles += 1;
  }
  return visibles;
}

// Subconjunto visible de una columna (respeta el buscador) para el bulk.
function grupoVisible(estado) {
  const grupo = cachePedidos.filter((p) => p.estado === estado);
  if (!busqueda) return grupo;
  return grupo.filter((p) => String(p.id).includes(busqueda) || String(p.cliente_id).includes(busqueda));
}

async function cargar() {
  const board = document.getElementById("personal-board");
  const estado = document.getElementById("personal-estado");
  estado.textContent = "";
  estado.appendChild(skeletonLinea("cargando pedidos"));
  board.setAttribute("aria-busy", "true");
  try {
    const pedidos = await api.listarPedidos();
    estado.textContent = "";
    // Caché para el buscador y el bulk (sin refetch al filtrar).
    cachePedidos = pedidos;
    for (const nombre of ESTADOS) {
      const lista = document.getElementById(`lista-${nombre}`);
      const conteo = document.getElementById(`conteo-${nombre}`);
      lista.textContent = "";
      // Orden estable por id para lectura predecible en cada columna.
      const grupo = pedidos.filter((p) => p.estado === nombre).sort((a, b) => a.id - b.id);
      conteo.textContent = `(${grupo.length})`;
      if (grupo.length === 0) {
        lista.appendChild(el("p", { clase: "texto-secundario", texto: "Sin pedidos aquí." }));
      } else {
        for (const p of grupo) lista.appendChild(tarjetaPersonal(p));
      }
    }
    // Tras pintar se reaplican buscador y filtro móvil sobre lo nuevo.
    aplicarBusqueda();
    aplicarFiltroMovil();
  } catch (error) {
    estado.textContent = "";
    estado.appendChild(estadoError({ titulo: error.message, alReintentar: () => cargar() }));
  } finally {
    board.removeAttribute("aria-busy");
  }
}

function init() {
  // Filtro por estado con options construidas desde el contrato (textos en español).
  const filtro = document.getElementById("personal-filtro");
  if (filtro && filtro.options.length === 0) {
    filtro.appendChild(new Option("Todos los estados", "TODOS"));
    const etiquetas = etiquetasEstado();
    for (const nombre of ESTADOS) filtro.appendChild(new Option(etiquetas[nombre], nombre));
  }
  filtro?.addEventListener("change", () => aplicarFiltroMovil());
  window.matchMedia("(min-width: 1024px)").addEventListener?.("change", () => aplicarFiltroMovil());
  document.getElementById("personal-actualizar")?.addEventListener("click", () => cargar());
  // Buscador: Enter aplica y anuncia coincidencias (toast en región aria-live).
  const buscar = document.getElementById("personal-buscar");
  buscar?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const n = aplicarBusqueda();
    toast(n === 0 ? "Sin coincidencias para esa búsqueda." : `${n} ${n === 1 ? "pedido visible" : "pedidos visibles"}.`, "info");
  });
  // Bulk por columna con su diálogo de confirmación.
  document.querySelectorAll("[data-bulk]").forEach((btn) => {
    btn.addEventListener("click", () => pedirBulk(btn.dataset.bulk, btn));
  });
  document.getElementById("bulk-confirmar")?.addEventListener("click", (e) => ejecutarBulk(e.currentTarget));
  document.getElementById("bulk-cancelar")?.addEventListener("click", () => document.getElementById("dialogo-bulk")?.close());
  document.getElementById("dialogo-bulk")?.addEventListener("close", () => {
    // Esc o Cancelar devuelven el foco al botón que abrió el bulk.
    if (focoBulk?.isConnected) focoBulk.focus({ preventScroll: true });
    focoBulk = null;
  });
  // Atajos mínimos: "/" al buscador; nunca dentro de escritura ni con diálogo abierto.
  document.addEventListener("keydown", (e) => {
    const enBuscador = e.target?.id === "personal-buscar";
    if (e.key === "Escape" && enBuscador) {
      // Esc limpia la búsqueda sin secuestrar nada más.
      e.target.value = "";
      aplicarBusqueda();
      e.target.blur();
      return;
    }
    const enEdicion = e.target instanceof HTMLElement && e.target.closest("input, select, textarea");
    const dialogoAbierto = document.querySelector("dialog[open]");
    if (e.key !== "/" || enEdicion || dialogoAbierto) return;
    e.preventDefault();
    document.getElementById("personal-buscar")?.focus();
  });
  cargar();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
