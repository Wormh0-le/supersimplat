import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import type { AISelectAnchorController } from '../ai-select/anchor-controller';

export interface AISelectToolbarOptions {
    readonly onRestart: () => Promise<void>;
    readonly onExit: () => void;
}

/** Contextual controls for the v1 Anchor-only shell. */
export class AISelectToolbar extends Container {
    constructor(
        controller: AISelectAnchorController,
        options: AISelectToolbarOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-toolbar',
            hidden: true
        });
        this.dom.addEventListener('pointerdown', event => event.stopPropagation());

        const tool = new Label({ id: 'ai-select-toolbar-tool' });
        const anchor = new Label({ id: 'ai-select-toolbar-anchor' });
        const adjust = new Button({
            id: 'ai-select-toolbar-adjust-anchor',
            enabled: false
        });
        const more = new Button({
            id: 'ai-select-toolbar-more',
            text: '⋯'
        });
        const overflow = new Container({
            id: 'ai-select-toolbar-overflow',
            hidden: true
        });
        const restart = new Button({ id: 'ai-select-toolbar-restart' });
        const exit = new Button({ id: 'ai-select-toolbar-exit' });
        i18n.bindText(tool, 'ai-select.tool');
        i18n.bindText(anchor, 'ai-select.anchor.current-view');
        i18n.bindText(adjust, 'ai-select.adjust-anchor');
        i18n.bindText(restart, 'ai-select.restart-current-target');
        i18n.bindText(exit, 'ai-select.exit');
        const setMoreLabel = () => {
            more.dom.setAttribute('aria-label', i18n.t('ai-select.more'));
        };
        setMoreLabel();
        i18n.onChange(setMoreLabel, this);
        restart.on('click', () => options.onRestart().catch(error => console.error(error)));
        exit.on('click', () => options.onExit());
        more.on('click', () => {
            overflow.hidden = !overflow.hidden;
        });

        this.append(tool);
        this.append(anchor);
        this.append(adjust);
        this.append(more);
        overflow.append(restart);
        overflow.append(exit);
        this.append(overflow);
        controller.subscribe((state) => {
            this.hidden = state.context === null;
            restart.enabled = state.context !== null;
            if (state.context === null) {
                overflow.hidden = true;
            }
        });
    }
}
