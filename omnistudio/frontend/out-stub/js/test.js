// JavaScript de test pour Phase 0bis.
// Si vous voyez #status en vert avec "JavaScript chargé", le JS est bien servi.

(function () {
  'use strict';

  const statusEl = document.getElementById('status');
  if (statusEl) {
    statusEl.textContent = '✓ JavaScript chargé — assets statiques OK';
    statusEl.classList.add('ok');
  }

  function setJsCheck(message, codeText) {
    const jsCheck = document.getElementById('js-check');
    if (!jsCheck) {
      return;
    }

    jsCheck.replaceChildren(document.createTextNode(message));
    if (codeText) {
      const code = document.createElement('code');
      code.textContent = codeText;
      jsCheck.append(document.createTextNode(' '), code);
    }
  }

  // Test fetch relatif vers /api/health
  // Sous /omni/, le fetch("api/health") doit résoudre vers /omni/api/health
  fetch('api/health')
    .then((r) => r.json())
    .then((data) => {
      setJsCheck('✓ fetch relatif OK —', `root_path="${data.root_path || ''}"`);
    })
    .catch((err) => {
      setJsCheck(`✗ fetch relatif KO : ${err.message || 'erreur inconnue'}`);
    });
})();
