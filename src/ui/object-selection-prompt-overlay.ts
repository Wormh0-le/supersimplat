import type {
    ObjectSelectionSessionInterface,
    ObjectSelectionSessionState
} from '../object-selection-session';
import { i18n } from './localization';

// Pending prompts are deliberately a screen-space UI affordance. They are
// derived from the session state and disappear before a preview is submitted;
// they are never a second editor selection or a persisted scene annotation.
class ObjectSelectionPromptOverlay {
    private dom: HTMLDivElement;
    private unsubscribe: () => void;

    constructor(
        session: ObjectSelectionSessionInterface,
        parent: HTMLElement
    ) {
        this.dom = document.createElement('div');
        this.dom.id = 'object-selection-prompt-overlay';
        parent.appendChild(this.dom);
        this.unsubscribe = session.subscribe(state => this.render(state));
    }

    destroy() {
        this.unsubscribe();
        this.dom.remove();
    }

    private render(state: ObjectSelectionSessionState) {
        const markers = state.pendingPrompts.flatMap((entry, index) => {
            const prompt = entry.prompt;
            if (prompt.frameWidth <= 0 || prompt.frameHeight <= 0) {
                return [];
            }
            const marker = document.createElement('span');
            marker.className = [
                'object-selection-prompt-marker',
                `object-selection-prompt-marker-${prompt.polarity}`
            ].join(' ');
            marker.style.left = `${(prompt.xPx / prompt.frameWidth) * 100}%`;
            marker.style.top = `${(prompt.yPx / prompt.frameHeight) * 100}%`;
            marker.textContent = prompt.polarity === 'include' ? '+' : '−';
            marker.title = `${i18n.t('object-selection.pending-prompt')} ${index + 1}`;
            marker.setAttribute('aria-label', marker.title);
            return [marker];
        });
        this.dom.replaceChildren(...markers);
    }
}

export { ObjectSelectionPromptOverlay };
