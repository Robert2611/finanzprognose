// ------------------------------------------------------------ Start
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, load, render } from './core.js';
import { refreshBackupPill } from './backup.js';
import { refreshUpdatePill } from './update.js';

// B-014: page-scrolling tables stick their column headers right below the (wrapping) app header
const header = document.querySelector('header');
new ResizeObserver(() => document.documentElement.style.setProperty('--header-h', `${header.offsetHeight}px`)).observe(header);

(async () => {
  try { await load(); await render(); } catch (ex) { renderLit(html`<div class="banner err">${ex.message}</div>`, $('#main')); }
  refreshBackupPill(); setInterval(refreshBackupPill, 5 * 60 * 1000);
  refreshUpdatePill(); setInterval(refreshUpdatePill, 5 * 60 * 1000);
})();
