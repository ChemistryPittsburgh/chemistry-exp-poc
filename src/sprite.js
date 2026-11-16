/**
 * Plays a turntable sprite sheet in a div: no WebGL, just two stacked background layers.
 * The second layer crossfades toward the next frame, which hides the stepping of
 * low frame counts at the cost of a slight ghost on fast-moving details.
 */
export class SpritePlayer {
  constructor(el) {
    this.el = el;
    this.el.classList.add('sprite');
    this.a = document.createElement('div');
    this.b = document.createElement('div');
    this.a.className = this.b.className = 'sprite-layer';
    el.append(this.a, this.b);
    this.frames = 0;
    this.crossfade = true;
    this.angle = 0; // in turns (1 = 360 degrees)
  }

  /** sheet: { url, frames, cols, rows } — resolves once the image is decoded. */
  async load(sheet) {
    const img = new Image();
    img.src = sheet.url;
    await img.decode();
    Object.assign(this, { frames: sheet.frames, cols: sheet.cols, rows: sheet.rows });
    for (const layer of [this.a, this.b]) {
      layer.style.backgroundImage = `url("${sheet.url}")`;
      layer.style.backgroundSize = `${sheet.cols * 100}% ${sheet.rows * 100}%`;
    }
    this.render();
  }

  place(layer, index) {
    const col = index % this.cols;
    const row = Math.floor(index / this.cols);
    layer.style.backgroundPosition = `${(col / (this.cols - 1)) * 100}% ${(row / Math.max(this.rows - 1, 1)) * 100}%`;
  }

  setAngle(turns) {
    this.angle = ((turns % 1) + 1) % 1;
    this.render();
  }

  render() {
    if (!this.frames) return;
    const f = this.angle * this.frames;
    const i = Math.floor(f) % this.frames;
    this.place(this.a, i);
    if (this.crossfade) {
      this.place(this.b, (i + 1) % this.frames);
      this.b.style.opacity = (f - Math.floor(f)).toFixed(3);
    } else {
      this.b.style.opacity = 0;
    }
  }
}
