/* main.js — Punto de entrada consolidado para la vista cliente.
   Cada vista se importa aislada en su propio try/catch: si un módulo falla,
   los demás siguen vivos (incluido perfil/registro). */
const VISTAS = [
  "./vistas/menu.js",
  "./vistas/carrito.js",
  "./vistas/pedidos.js",
  "./vistas/perfil.js",
  "./vistas/nav.js",
];

// La importación dinámica permite atrapar el fallo por módulo (el import
// estático tumbaría el punto único completo ante el primer error).
for (const ruta of VISTAS) {
  try {
    await import(ruta);
  } catch (error) {
    console.error(`[cafe-overflow] no se pudo cargar ${ruta}:`, error);
  }
}
