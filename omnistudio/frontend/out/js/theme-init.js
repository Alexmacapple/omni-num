/* theme-init.js — Prevention flash theme (lecture de la cle DSFR native) */
(function() {
    var s = localStorage.getItem('scheme');
    if (s === 'dark' || s === 'light') {
        document.documentElement.setAttribute('data-fr-scheme', s);
        document.documentElement.setAttribute('data-fr-theme', s);
    }
})();
