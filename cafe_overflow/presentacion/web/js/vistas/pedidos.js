/* pedidos.js — "Mis pedidos" del cliente: pipeline, badge, total del servidor.
   Fuente única: el servidor filtra por ?cliente_id= de la sesión. */
import { api, ApiError } from "../api.js";
import {
  abrirRegistro, badgeEstado, botonCargando, cop, el, getClienteId,
  pipeline, skeletonLinea, estadoError, estadoVacio, toast,
} from "../ui.js";

const ORDEN = ["PENDIENTE_DE_PAGO", "EN_PREPARACION", "LISTO", "ENTREGADO"];

function tarjetaPedido(pedido) {
  const card = el("article", { clase: "pedido-card" });
  const cab = el("div", { clase: "pedido-card__cabecera" });
  cab.appendChild(el("span", { clase: "pedido-id", texto: `#${pedido.id}` }));
  cab.appendChild(badgeEstado(pedido.estado));
  card.appendChild(cab);
  card.appendChild(pipeline(pedido.estado));
  const meta = el("p", { clase: "texto-secundario", texto: `${pedido.items.length} productos · Total ${cop(pedido.total)}` });
  card.appendChild(meta);
  // El cliente solo puede confirmar el pago de sus pedidos pendientes.
  if (pedido.estado === "PENDIENTE_DE_PAGO") {
    const btn = el("button", { clase: "btn btn--secondary", texto: "Confirmar pago", attrs: { type: "button" } });
    btn.addEventListener("click", () => confirmarPago(pedido.id, btn));
    card.appendChild(btn);
  }
  return card;
}

function filaTabla(pedido, cuerpo) {
  const tr = document.createElement("tr");
  tr.appendChild(el("td", { clase: "pedido-id", texto: String(pedido.id) }));
  const tdEstado = document.createElement("td");
  tdEstado.appendChild(badgeEstado(pedido.estado));
  tr.appendChild(tdEstado);
  tr.appendChild(el("td", { texto: String(pedido.items.length) }));
  tr.appendChild(el("td", { clase: "mono", texto: cop(pedido.total) }));
  const tdAccion = document.createElement("td");
  if (pedido.estado === "PENDIENTE_DE_PAGO") {
    const btn = el("button", { clase: "btn btn--secondary", texto: "Confirmar pago", attrs: { type: "button" } });
    btn.addEventListener("click", () => confirmarPago(pedido.id, btn));
    tdAccion.appendChild(btn);
  } else {
    tdAccion.appendChild(el("span", { clase: "texto-secundario", texto: "—" }));
  }
  tr.appendChild(tdAccion);
  cuerpo.appendChild(tr);
}

async function confirmarPago(id, boton) {
  const texto = boton.textContent;
  botonCargando(boton, true);
  try {
    await api.confirmarPago(id);
    toast(`Pago del pedido ${id} confirmado.`, "success");
    window.dispatchEvent(new CustomEvent("pedidos:actualizado"));
    cargar();
  } catch (error) {
    toast(error instanceof ApiError ? error.message : "No se pudo confirmar el pago.", "error");
  } finally {
    botonCargando(boton, false, texto);
  }
}

async function cargar() {
  const clienteId = getClienteId();
  const cards = document.getElementById("pedidos-cards");
  const tabla = document.getElementById("pedidos-tabla-cuerpo");
  const estado = document.getElementById("pedidos-estado");
  const seccion = document.getElementById("seccion-pedidos");
  cards.textContent = "";
  estado.textContent = "";
  if (tabla) tabla.textContent = "";
  if (!clienteId) {
    estado.appendChild(
      estadoVacio({
        titulo: "Regístrate para ver tus pedidos.",
        accionTexto: "Registrarme",
        alAccion: () => abrirRegistro(),
      })
    );
    return;
  }
  seccion.setAttribute("aria-busy", "true");
  estado.appendChild(skeletonLinea("cargando pedidos"));
  try {
    // Fuente única: el servidor devuelve solo los pedidos de la sesión.
    const mios = await api.listarPedidos({ cliente_id: clienteId });
    estado.textContent = "";
    if (mios.length === 0) {
      estado.appendChild(
        estadoVacio({
          titulo: "Aún no tienes pedidos.",
          subtitulo: "Lo que agregas al carrito aparece aquí al confirmar el pedido.",
          accionTexto: "Ver menú",
          alAccion: () => document.getElementById("seccion-menu")?.scrollIntoView(),
        })
      );
      return;
    }
    // Orden de pipeline para lectura rápida del avance.
    mios.sort((a, b) => ORDEN.indexOf(a.estado) - ORDEN.indexOf(b.estado));
    for (const p of mios) {
      cards.appendChild(tarjetaPedido(p));
      if (tabla) filaTabla(p, tabla);
    }
  } catch (error) {
    estado.appendChild(estadoError({ titulo: error.message, alReintentar: () => cargar() }));
  } finally {
    seccion.removeAttribute("aria-busy");
  }
}

function init() {
  window.addEventListener("pedidos:actualizado", () => cargar());
  window.addEventListener("cliente:actualizado", () => cargar());
  cargar();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
