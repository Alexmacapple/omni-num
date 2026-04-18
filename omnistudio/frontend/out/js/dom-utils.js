/**
 * dom-utils.js — Utilitaires DOM partages.
 * escapeHtml et escapeAttr sont UNIQUEMENT declares ici.
 */

/**
 * Echappe les caracteres HTML dangereux.
 * @param {string} text
 * @returns {string}
 */
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Echappe une valeur pour un attribut HTML.
 * @param {string} text
 * @returns {string}
 */
export function escapeAttr(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * Sanitise du HTML provenant du serveur (diff, etc.).
 * Conserve uniquement les balises et attributs surs.
 * @param {string} html
 * @returns {string}
 */
export function sanitizeHtml(html) {
    const ALLOWED_TAGS = new Set([
        'span', 'del', 'ins', 'em', 'strong', 'br', 'p', 'div',
        'mark', 'abbr', 'small', 'sub', 'sup',
    ]);
    const ALLOWED_ATTRS = new Set(['class', 'title', 'lang']);

    const template = document.createElement('template');
    template.innerHTML = html;
    const walker = document.createTreeWalker(
        template.content,
        NodeFilter.SHOW_ELEMENT,
    );

    const toRemove = [];
    while (walker.nextNode()) {
        const el = walker.currentNode;
        if (!ALLOWED_TAGS.has(el.localName)) {
            toRemove.push(el);
            continue;
        }
        for (const attr of [...el.attributes]) {
            if (!ALLOWED_ATTRS.has(attr.name)) {
                el.removeAttribute(attr.name);
            }
        }
    }

    for (const el of toRemove) {
        // Remplacer les elements non autorises par leur contenu texte
        el.replaceWith(document.createTextNode(el.textContent));
    }

    return template.innerHTML;
}
