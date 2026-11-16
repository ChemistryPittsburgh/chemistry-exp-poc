/** Site header + footer approximating the Chemistry design (for mockups only). */

const LOGO = (() => {
  // Dot burst: concentric rings of dots shrinking outward.
  const dots = ['<circle cx="20" cy="20" r="3.2"/>'];
  const rings = [
    { r: 8.5, n: 8, size: 2.4, phase: 0 },
    { r: 15, n: 12, size: 1.6, phase: 0.26 },
  ];
  for (const ring of rings) {
    for (let i = 0; i < ring.n; i++) {
      const a = (i / ring.n) * Math.PI * 2 + ring.phase;
      const x = (20 + Math.cos(a) * ring.r).toFixed(2);
      const y = (20 + Math.sin(a) * ring.r).toFixed(2);
      dots.push(`<circle cx="${x}" cy="${y}" r="${ring.size}"/>`);
    }
  }
  return `<svg viewBox="0 0 40 40" width="34" height="34" fill="currentColor" aria-hidden="true">${dots.join('')}</svg>`;
})();

export function mountHeader() {
  const header = document.createElement('header');
  header.className = 'site-header';
  header.innerHTML = `
    <a class="brand" href="#top" aria-label="Chemistry home">${LOGO}<span>CHEMISTRY</span></a>
    <nav class="site-links" aria-label="Primary">
      <a href="#top">Work</a>
      <a href="#top" class="is-active">Expertise</a>
      <a href="#top">Insights</a>
      <a href="#top">About</a>
      <a href="#top" class="talk">Talk to Us</a>
    </nav>`;
  document.body.prepend(header);
  return header;
}

export function mountFooter(parent = document.body) {
  const footer = document.createElement('footer');
  footer.className = 'site-footer';
  footer.innerHTML = `
    <div class="footer-inner">
      <div class="brand">${LOGO}<span>CHEMISTRY</span></div>
      <p>Mockup for exploration. Not a production page.</p>
    </div>`;
  parent.appendChild(footer);
  return footer;
}
