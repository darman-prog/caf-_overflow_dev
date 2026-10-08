/* perfil.js — perfil y lealtad + registro de cliente.
   Nivel, saldo y acumulado vienen de GET /api/clientes/{id}.
   Sin barra de progreso calculada: los umbrales los define el servidor y la UI
   no opera con dinero (muestra programa como texto informativo fijo). */
import { api, ApiError } from "../api.js";
import {
  abrirRegistro, badgeNivel, badgePuntos, botonCargando, cop, el, getClienteId,
  setClienteId, clearClienteId, estadoError, skeletonLinea, toast, vaciarCarrito,
} from "../ui.js";

function stat(dt, valorTexto, clase = "") {
  const item = el("div", { clase: "perfil-stats__item" });
  item.appendChild(el("dt", { texto: dt }));
  item.appendChild(el("dd", { clase, texto: valorTexto }));
  return item;
}

async function cargar() {
  const clienteId = getClienteId();
  const caja = document.getElementById("perfil-contenido");
  const chip = document.getElementById("cliente-chip");
  caja.textContent = "";
  if (!clienteId) {
    chip.textContent = "Sin registro";
    const vacio = el("div", { clase: "empty" });
    vacio.appendChild(el("p", { texto: "Aún no tienes cuenta. Regístrate para acumular DevPoints." }));
    const btn = el("button", { clase: "btn btn--primary", texto: "Registrarme", attrs: { type: "button" } });
    btn.addEventListener("click", () => abrirRegistro());
    vacio.appendChild(btn);
    caja.appendChild(vacio);
    return;
  }
  caja.setAttribute("aria-busy", "true");
  caja.appendChild(skeletonLinea("cargando perfil"));
  try {
    const cuenta = await api.obtenerCliente(clienteId);
    caja.textContent = "";
    const card = el("div", { clase: "perfil-card" });
    const nivel = el("div", { clase: "perfil-card__nivel" });
    nivel.appendChild(el("strong", { texto: cuenta.nombre }));
    nivel.appendChild(badgeNivel(cuenta.nivel));
    nivel.appendChild(badgePuntos(`${cuenta.devpoints} DevPoints`));
    card.appendChild(nivel);
    const stats = el("dl", { clase: "perfil-stats" });
    // Todos los valores se muestran tal cual los entrega el servidor.
    stats.appendChild(stat("Saldo DevPoints", String(cuenta.devpoints), "saldo-puntos"));
    stats.appendChild(stat("Acumulado de compras", cop(cuenta.acumulado_compras)));
    stats.appendChild(stat("Correo", cuenta.correo));
    card.appendChild(stats);
    card.appendChild(el("p", {
      clase: "texto-secundario",
      texto: "El nivel lo asigna el servidor según tu acumulado: Junior, Mid desde $500.000 y Senior desde $1.500.000. Cada $20.000 pagados acreditan 1 DevPoint y cada punto canjeado descuenta $200.",
    }));
    const salir = el("button", { clase: "btn btn--ghost", texto: "Cerrar sesión en este equipo", attrs: { type: "button" } });
    salir.addEventListener("click", () => {
      // Cierra la sesión sin dejar rastro: olvida el id, vacía el carrito
      // (re-renderiza carrito y sticky) y avisa para re-pintar perfil y pedidos.
      clearClienteId();
      vaciarCarrito();
      toast("Sesión local cerrada.", "info");
      window.dispatchEvent(new CustomEvent("cliente:actualizado"));
      window.dispatchEvent(new CustomEvent("pedidos:actualizado"));
      cargar();
    });
    card.appendChild(salir);
    caja.appendChild(card);
    chip.textContent = "";
    chip.appendChild(el("span", { texto: cuenta.nombre }));
    chip.appendChild(badgeNivel(cuenta.nivel));
  } catch (error) {
    // Si el id guardado ya no existe, se ofrece registrarse de nuevo.
    if (error instanceof ApiError && error.http === 404) clearClienteId();
    caja.textContent = "";
    caja.appendChild(estadoError({ titulo: error.message, alReintentar: () => cargar() }));
  } finally {
    caja.removeAttribute("aria-busy");
  }
}

// Mensajes de error junto a cada campo, anunciados vía aria-describedby.

function mostrarErrorCampo(input, mensajeId, mensaje) {
  const mensajeEl = document.getElementById(mensajeId);
  if (mensaje) {
    input.setAttribute("aria-invalid", "true");
    mensajeEl.textContent = mensaje;
  } else {
    input.removeAttribute("aria-invalid");
    mensajeEl.textContent = "";
  }
}

function init() {
  const dialogo = document.getElementById("dialogo-registro");
  const form = document.getElementById("registro-form");
  const inputNombre = document.getElementById("registro-nombre");
  const inputCorreo = document.getElementById("registro-correo");
  document.getElementById("abrir-registro")?.addEventListener("click", () => abrirRegistro());
  document.getElementById("registro-cancelar")?.addEventListener("click", () => {
    if (dialogo?.open) dialogo.close();
  });
  window.addEventListener("cliente:actualizado", () => cargar());

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    // Validación solo sintáctica y por campo: cada mensaje vive bajo su input.
    const nombreVacio = !inputNombre.value.trim();
    const correoVacio = !inputCorreo.value.trim();
    // Patrón simple de forma user@dominio.tld; el servidor valida el resto.
    const correoMal = !correoVacio && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inputCorreo.value.trim());
    mostrarErrorCampo(inputNombre, "registro-nombre-error", nombreVacio ? "El nombre es requerido." : "");
    mostrarErrorCampo(inputCorreo, "registro-correo-error", correoVacio ? "El correo es requerido." : (correoMal ? "Escribe un correo válido, por ejemplo nombre@ejemplo.com." : ""));
    if (nombreVacio || correoVacio || correoMal) {
      // El foco va al primer campo con error para anunciarlo.
      (!inputNombre.value.trim() ? inputNombre : inputCorreo).focus();
      return;
    }
    const boton = document.getElementById("registro-enviar");
    const texto = boton.textContent;
    botonCargando(boton, true);
    try {
      const cliente = await api.registrarCliente({ nombre: inputNombre.value.trim(), correo: inputCorreo.value.trim() });
      setClienteId(cliente.id);
      dialogo.close();
      form.reset();
      toast(`Bienvenido, ${cliente.nombre}. Tu cuenta quedó registrada.`, "success");
      window.dispatchEvent(new CustomEvent("cliente:actualizado"));
      window.dispatchEvent(new CustomEvent("pedidos:actualizado"));
      cargar();
    } catch (error) {
      // El 409 de correo duplicado muestra el mensaje del servidor.
      toast(error instanceof ApiError ? error.message : "No se pudo registrar la cuenta.", "error");
    } finally {
      botonCargando(boton, false, texto);
    }
  });
  cargar();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
