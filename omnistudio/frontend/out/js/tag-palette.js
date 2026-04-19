/**
 * tag-palette.js — Palette de marqueurs émotionnels OmniVoice (13 tags non verbaux).
 *
 * Charge les tags via GET /api/voices/tags, rend une palette de boutons DSFR,
 * et insère le tag choisi à la position du curseur dans le dernier textarea/input
 * (sélecteur `.vx-tag-target`) qui a eu le focus.
 */
import { apiGet } from './api-client.js';
import { escapeHtml } from './dom-utils.js';

const TARGET_SELECTOR = '.vx-tag-target, textarea.vx-tts-edit, input.vx-tag-target';

let cachedTags = null;
let lastFocused = null;

function trackFocus() {
    document.addEventListener('focusin', (event) => {
        const el = event.target;
        if (el && el.matches && el.matches(TARGET_SELECTOR)) {
            lastFocused = el;
        }
    });
}

function insertAtCursor(el, tag) {
    if (!el) return;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, start);
    const after = el.value.slice(end);
    el.value = `${before}${tag}${after}`;
    const pos = start + tag.length;
    el.setSelectionRange(pos, pos);
    el.focus();
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
}

function renderPalette(container, tags) {
    if (!tags || tags.length === 0) {
        container.innerHTML = '<p class="fr-text--sm fr-text--mention-grey">Aucun tag disponible.</p>';
        return;
    }
    const buttons = tags.map((t) => {
        const tag = typeof t === 'string' ? t : t.tag || t.name;
        const label = typeof t === 'string' ? t : (t.label || t.tag || t.name);
        const safeTag = escapeHtml(tag);
        const safeLabel = escapeHtml(label);
        return `<button type="button" class="fr-btn fr-btn--secondary fr-btn--sm vx-tag-btn"
                        data-tag="${safeTag}"
                        title="Insérer ${safeTag} à la position du curseur">
                    ${safeLabel}
                </button>`;
    }).join('');
    container.innerHTML = `
        <p class="fr-text--sm fr-text--bold fr-mb-1w">Marqueurs émotionnels</p>
        <p class="fr-hint-text fr-mb-1w">Cliquez dans une cellule « Texte TTS » puis sur un marqueur pour l'insérer à la position du curseur.</p>
        <div class="fr-btns-group fr-btns-group--inline-sm fr-btns-group--sm" role="group" aria-label="Palette de marqueurs émotionnels">
            ${buttons}
        </div>`;
    container.querySelectorAll('.vx-tag-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const tag = btn.getAttribute('data-tag');
            if (!lastFocused || !document.body.contains(lastFocused)) {
                container.querySelector('.fr-hint-text')?.classList.add('fr-text-default--warning');
                return;
            }
            container.querySelector('.fr-hint-text')?.classList.remove('fr-text-default--warning');
            insertAtCursor(lastFocused, tag);
        });
    });
}

async function loadTags() {
    if (cachedTags) return cachedTags;
    try {
        const response = await apiGet('/api/voices/tags');
        const tags = response?.data?.tags || response?.tags || [];
        cachedTags = Array.isArray(tags) ? tags : [];
        return cachedTags;
    } catch {
        return [];
    }
}

export async function mountTagPalette(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '<p class="fr-text--sm fr-text--mention-grey">Chargement des marqueurs émotionnels…</p>';
    const tags = await loadTags();
    renderPalette(container, tags);
}

export function initTagPalette() {
    trackFocus();
}
