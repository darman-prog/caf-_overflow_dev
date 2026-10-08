/* menu.js — vista Menú: tarjetas estilo snippet con badge de stock y botón Agregar.
   El stock y el precio vienen del servidor; la UI solo los presenta. */
import { api } from "../api.js";
import { agregarAlCarrito, badgeStock, cop, el, estadoError, estadoVacio, skeletonLinea, toast } from "../ui.js";

let productos = [];
let filtro = "";

function tarjetaProducto(producto) {
  const item = el("li", { clase: "card-producto" });
  const agotado = producto.disponibilidad === "agotado";
  if (agotado) item.classList.add("card-producto--agotado");
  // Barra de ventana: puntos decorativos + badge de stock a la derecha.
  const barra = el("div", { clase: "card-producto__ventana" });
  barra.appendChild(el("span", { clase: "card-producto__puntos", attrs: { "aria-hidden": "true" } }));
  barra.appendChild(badgeStock(producto.disponibilidad, producto.stock));
  item.appendChild(barra);
  // Foto local con marco que recorta el zoom; si falta, se retira y listo.
  const marco = el("figure", { clase: "card-producto__marco" });
  const foto = document.createElement("img");
  foto.className = "card-producto__foto";
  foto.setAttribute("src", `img/producto-${producto.id}.png`);
  foto.setAttribute("alt", producto.nombre);
  foto.setAttribute("loading", "lazy");
  foto.addEventListener("error", () => foto.remove());
  marco.appendChild(foto);
  item.appendChild(marco);
  // Nombre y precio: textContent, jamás innerHTML con datos del servidor.
  item.appendChild(el("h3", { clase: "card-producto__nombre", texto: producto.nombre }));
  item.appendChild(el("p", { clase: "card-producto__precio", texto: cop(producto.precio_base) }));
  const acciones = el("div", { clase: "card-producto__acciones" });
  const boton = el("button", {
    clase: "btn btn--primary",
    texto: agotado ? "Agotado" : "Agregar",
    attrs: { type: "button", "aria-label": agotado ? `${producto.nombre}: agotado` : `Agregar ${producto.nombre} al carrito` },
  });
  if (agotado) boton.disabled = true;
  boton.addEventListener("click", () => {
    agregarAlCarrito(producto.id, 1);
    toast(`${producto.nombre} agregado al carrito.`, "success");
  });
  acciones.appendChild(boton);
  item.appendChild(acciones);
  return item;
}

// Molde de tarjeta para la carga: estructura sin datos ni acciones.
function tarjetaEsqueleto() {
  const item = el("li", { clase: "card-producto", attrs: { "aria-hidden": "true" } });
  item.appendChild(el("div", { clase: "skeleton-bloque skeleton-bloque--foto" }));
  item.appendChild(el("div", { clase: "skeleton-bloque skeleton-bloque--texto" }));
  item.appendChild(el("div", { clase: "skeleton-bloque skeleton-bloque--precio" }));
  item.appendChild(el("div", { clase: "skeleton-bloque skeleton-bloque--boton" }));
  return item;
}

// El filtro por nombre es solo presentación; no toca precios ni totales.
function aplicarFiltro(lista) {
  const q = filtro.trim().toLowerCase();
  if (!q) return lista;
  return lista.filter((p) => p.nombre.toLowerCase().includes(q));
}

function pintar() {
  const grid = document.getElementById("menu-grid");
  const estado = document.getElementById("menu-estado");
  grid.textContent = "";
  estado.textContent = "";
  const visibles = aplicarFiltro(productos);
  if (visibles.length === 0) {
    estado.appendChild(
      estadoVacio({
        titulo: productos.length === 0 ? "Aún no hay productos en el menú." : "Ningún producto coincide con la búsqueda.",
        accionTexto: "Actualizar",
        alAccion: () => cargar(),
      })
    );
    return;
  }
  for (const p of visibles) grid.appendChild(tarjetaProducto(p));
}

async function cargar() {
  const grid = document.getElementById("menu-grid");
  const estado = document.getElementById("menu-estado");
  const seccion = document.getElementById("seccion-menu");
  grid.textContent = "";
  estado.textContent = "";
  // Carga accesible: skeleton visible + aria-busy en la sección.
  seccion.setAttribute("aria-busy", "true");
  estado.appendChild(skeletonLinea("cargando menú"));
  for (let i = 0; i < 6; i++) grid.appendChild(tarjetaEsqueleto());
  try {
    productos = await api.listarProductos();
    pintar();
  } catch (error) {
    // Sin menú no hay tarjetas que mostrar: se retiran los esqueletos.
    grid.textContent = "";
    estado.appendChild(estadoError({ titulo: error.message, alReintentar: () => cargar() }));
  } finally {
    seccion.removeAttribute("aria-busy");
    // Si hubo éxito, pintar() ya reemplazó el skeleton.
    if (productos.length > 0) estado.textContent = "";
  }
}

function init() {
  const buscador = document.getElementById("menu-buscar");
  buscador?.addEventListener("input", () => {
    filtro = buscador.value;
    pintar();
  });
  // Tras confirmar un pedido el stock cambia: refrescar el menú.
  window.addEventListener("pedidos:actualizado", () => cargar());
  cargar();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
