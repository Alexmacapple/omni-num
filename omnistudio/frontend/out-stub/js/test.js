// JavaScript de test pour Phase 0bis.
// Si vous voyez #status en vert avec "JavaScript chargé", le JS est bien servi.

(function () {
  'use strict';

  const statusEl = document.getElementById('status');
  if (statusEl) {
    statusEl.textContent = '✓ JavaScript chargé — assets statiques OK';
    statusEl.classList.add('ok');
  }

  // Test fetch relatif vers /api/health
  // Sous /omni/, le fetch("api/health") doit résoudre vers /omni/api/health
  fetch('api/health')
    .then((r) => r.json())
    .then((data) => {
      console.log('Health check OK:', data);
      const jsCheck = document.getElementById('js-check');
      if (jsCheck) {
        jsCheck.innerHTML = `✓ fetch relatif OK — <code>root_path="${data.root_path}"</code>`;
      }
    })
    .catch((err) => {
      console.error('Health check KO:', err);
      const jsCheck = document.getElementById('js-check');
      if (jsCheck) {
        jsCheck.innerHTML = `✗ fetch relatif KO : ${err.message}`;
      }
    });
})();
