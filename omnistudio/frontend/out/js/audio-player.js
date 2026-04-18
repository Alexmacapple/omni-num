/**
 * audio-player.js — Composant player audio accessible.
 */
import { getAccessToken } from './auth.js';

/**
 * Ajoute les tokens d'auth en query params pour les balises <audio src>.
 */
export function authenticatedUrl(src) {
    if (!src) return '';
    const token = getAccessToken();
    const tid = localStorage.getItem('thread_id') || '';
    if (!tid) {
        console.warn('[audio-player] thread_id absent de localStorage — URL audio invalide');
        return '';
    }
    const sep = src.includes('?') ? '&' : '?';
    return `${src}${sep}token=${encodeURIComponent(token)}&tid=${encodeURIComponent(tid)}`;
}

/**
 * Nettoie les players audio dans un conteneur (libere memoire).
 * @param {HTMLElement} container
 */
export function cleanupAudioPlayers(container) {
    container.querySelectorAll('audio').forEach(audio => {
        audio.pause();
        audio.removeAttribute('src');
        audio.load();
    });
}

/**
 * Cree un player audio accessible.
 * @param {string} src - URL du fichier audio
 * @param {string} label - Label accessible
 * @returns {HTMLElement}
 */
export function createAudioPlayer(src, label) {
    const wrapper = document.createElement('div');
    wrapper.className = 'vx-audio-player';
    wrapper.setAttribute('role', 'group');
    wrapper.setAttribute('aria-label', label);

    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = authenticatedUrl(src);
    audio.setAttribute('aria-label', label);

    const caption = document.createElement('p');
    caption.className = 'fr-text--xs fr-mt-1v';
    caption.textContent = label;

    wrapper.appendChild(audio);
    wrapper.appendChild(caption);
    return wrapper;
}
