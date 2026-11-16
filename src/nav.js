const ROOT = new URL('../', import.meta.url);

export const PAGES = [
  { id: 'gallery', label: 'Gallery', href: 'index.html' },
  { id: 'sprites', label: 'Sprites', href: 'sprites.html' },
  { id: 'sticky', label: 'A · Sticky stage', href: 'mockups/sticky.html' },
  { id: 'orbit', label: 'B · Orbit ring', href: 'mockups/orbit.html' },
  { id: 'spotlight', label: 'C · Lights on', href: 'mockups/spotlight.html' },
];

/** Floating pill to swap between the gallery and the mockups. Arrow keys [ and ] also work. */
export function mountNav(current) {
  const nav = document.createElement('nav');
  nav.className = 'switcher';
  nav.setAttribute('aria-label', 'Mockup options');
  for (const p of PAGES) {
    const a = document.createElement('a');
    a.href = new URL(p.href, ROOT).href;
    a.textContent = p.label;
    if (p.id === current) a.setAttribute('aria-current', 'page');
    nav.appendChild(a);
  }
  document.body.appendChild(nav);
  const i = PAGES.findIndex((p) => p.id === current);
  window.addEventListener('keydown', (e) => {
    if (e.target.closest?.('input, textarea')) return;
    if (e.key === ']') location.href = new URL(PAGES[(i + 1) % PAGES.length].href, ROOT).href;
    if (e.key === '[') location.href = new URL(PAGES[(i - 1 + PAGES.length) % PAGES.length].href, ROOT).href;
  });
}
