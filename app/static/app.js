// ------------------------------------------------------------ Start
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, load, render } from './core.js';
import { refreshBackupPill } from './backup.js';

(async () => {
  try { await load(); await render(); } catch (ex) { renderLit(html`<div class="banner err">${ex.message}</div>`, $('#main')); }
  refreshBackupPill(); setInterval(refreshBackupPill, 5 * 60 * 1000);
})();
