/**
 * toast.js — Notifications DSFR (fr-alert).
 */
import { escapeHtml } from './dom-utils.js';

let toastContainer = null;
let toastCounter = 0;

function getContainer() {
    if (!toastContainer) {
        toastContainer = document.getElementById('ov-toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'ov-toast-container';
            toastContainer.setAttribute('role', 'status');
            toastContainer.setAttribute('aria-live', 'polite');
            document.body.appendChild(toastContainer);
        }
    }
    return toastContainer;
}

function createToast(message, type, autoDismiss = 0) {
    const container = getContainer();
    const id = `ov-toast-${++toastCounter}`;

    const alert = document.createElement('div');
    alert.id = id;
    alert.className = `fr-alert fr-alert--${type} fr-alert--sm`;
    alert.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const title = type === 'error' ? 'Erreur' : type === 'success' ? 'Succès' : 'Attention';
    alert.innerHTML = `
        <h3 class="fr-alert__title">${title}</h3>
        <p>${escapeHtml(message)}</p>
        <button class="fr-btn--close fr-btn" title="Masquer le message" aria-label="Masquer le message" type="button">Masquer</button>
    `;

    const closeBtn = alert.querySelector('.fr-btn--close');
    closeBtn.addEventListener('click', () => {
        alert.remove();
    });

    container.appendChild(alert);

    if (autoDismiss > 0) {
        setTimeout(() => {
            if (alert.parentNode) alert.remove();
        }, autoDismiss);
    }

    return alert;
}

export function showSuccess(message) {
    return createToast(message, 'success', 5000);
}

export function showError(message) {
    return createToast(message, 'error', 0);
}

export function showWarning(message) {
    return createToast(message, 'warning', 8000);
}
