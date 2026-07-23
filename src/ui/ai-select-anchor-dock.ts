import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import {
    type AISelectAnchorController,
    type AISelectAnchorState
} from '../ai-select/anchor-controller';

export interface AISelectAnchorDockOptions {
    readonly onReconnect: () => Promise<void>;
    readonly onOpenSettings: () => void;
}

/** The first AI View Dock: it displays only one Companion-authored Anchor. */
export class AISelectAnchorDock extends Container {
    private readonly status: Label;
    private readonly image: HTMLImageElement;
    private readonly failureActions: Container;
    private state: AISelectAnchorState = { context: null, anchor: null };

    constructor(
        controller: AISelectAnchorController,
        options: AISelectAnchorDockOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-anchor-dock'
        });
        this.dom.addEventListener('pointerdown', event => event.stopPropagation()
        );

        const title = new Label({ id: 'ai-select-anchor-dock-title' });
        i18n.bindText(title, 'ai-select.panel.title');
        this.status = new Label({ id: 'ai-select-anchor-dock-status' });
        this.image = document.createElement('img');
        this.image.id = 'ai-select-anchor-dock-image';
        this.image.alt = '';
        this.image.hidden = true;

        this.failureActions = new Container({
            id: 'ai-select-anchor-dock-failure-actions',
            hidden: true
        });
        const reconnect = new Button({ id: 'ai-select-anchor-dock-reconnect' });
        const settings = new Button({ id: 'ai-select-anchor-dock-settings' });
        i18n.bindText(reconnect, 'ai-select.reconnect');
        i18n.bindText(settings, 'ai-select.open-settings');
        reconnect.on('click', () => {
            options.onReconnect().catch(error => console.error(error));
        });
        settings.on('click', () => options.onOpenSettings());
        this.failureActions.append(reconnect);
        this.failureActions.append(settings);

        this.append(title);
        this.append(this.status);
        this.dom.appendChild(this.image);
        this.append(this.failureActions);

        controller.subscribe((state) => {
            this.state = state;
            this.render();
        });
        i18n.onChange(() => this.render(), this);
    }

    private render(): void {
        const { context, anchor } = this.state;
        if (context === null || anchor === null) {
            this.status.text = i18n.t('ai-select.panel.idle');
            this.image.hidden = true;
            this.failureActions.hidden = true;
            return;
        }
        if (anchor.renderStatus === 'rendering') {
            this.status.text = i18n.t('ai-select.anchor.rendering');
            this.image.hidden = true;
            this.failureActions.hidden = true;
            return;
        }
        if (anchor.renderStatus === 'ready' && anchor.rgb) {
            this.status.text = i18n.t('ai-select.anchor.ready');
            this.image.src = `data:image/png;base64,${anchor.rgb.pngBase64}`;
            this.image.hidden = false;
            this.failureActions.hidden = true;
            return;
        }
        this.status.text = i18n.t('ai-select.anchor.failed');
        this.image.hidden = true;
        this.failureActions.hidden = false;
    }
}
