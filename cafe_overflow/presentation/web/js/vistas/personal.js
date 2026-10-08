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

async function cargar() {
  const board = document.getElementById("personal-board");
  const estado = document.getElementById("personal-estado");
  estado.textContent = "";
  estado.appendChild(skeletonLinea("cargando pedidos"));
  board.setAttribute("aria-busy", "true");
  try {
    const pedidos = await api.listarPedidos();
    estado.textContent = "";
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
  cargar();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
