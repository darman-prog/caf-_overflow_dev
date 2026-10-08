/* nav.js — resalta en la navegación la sección visible.
   Liviano: un IntersectionObserver, sin librerías; si el navegador no lo
   soporta, la navegación por anclas sigue funcionando igual. */
function init() {
  if (!("IntersectionObserver" in window)) return;
  // Solo enlaces internos a secciones; "Personal" apunta a otra página.
  const enlaces = [...document.querySelectorAll('.nav-principal a[href^="#seccion-"]')];
  if (enlaces.length === 0) return;
  const porId = new Map(enlaces.map((a) => [a.getAttribute("href").slice(1), a]));
  // La sección activa es la que cruza el centro del viewport.
  const observador = new IntersectionObserver(
    (entradas) => {
      for (const entrada of entradas) {
        if (!entrada.isIntersecting) continue;
        for (const [id, enlace] of porId) {
          if (id === entrada.target.id) enlace.setAttribute("aria-current", "location");
          else enlace.removeAttribute("aria-current");
        }
      }
    },
    { rootMargin: "-40% 0px -55% 0px" }
  );
  document.querySelectorAll("main .seccion[id]").forEach((s) => observador.observe(s));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
