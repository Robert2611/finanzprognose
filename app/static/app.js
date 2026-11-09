// ------------------------------------------------------------ Start
import { $, esc, load, render } from './core.js';
import { refreshBackupPill } from './backup.js';

(async () => {
  try { await load(); await render(); } catch (ex) { $('#main').innerHTML = `<div class="banner err">${esc(ex.message)}</div>`; }
  refreshBackupPill(); setInterval(refreshBackupPill, 5 * 60 * 1000);
})();
