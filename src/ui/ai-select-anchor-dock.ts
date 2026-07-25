import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import {
    type AISelectAnchorController,
    type AISelectAnchorState
} from '../ai-select/anchor-controller';
import {
    getAnchorDockPresentation,
    type AnchorDockPresentation
} from '../ai-select/anchor-dock-presentation';
import { decodeMaskArtifact } from '../ai-select/mask-annotation';
import {
    type AISelectMaskController,
    type AISelectMaskState
} from '../ai-select/mask-controller';

export interface AISelectAnchorDockOptions {
    readonly onRetry: () => Promise<void>;
    readonly onReconnect: () => Promise<void>;
    readonly onOpenSettings: () => void;
}

interface ImagePixel {
    readonly xPx: number;
    readonly yPx: number;
}

const CLICK_TOLERANCE_PX = 4;

/** The first AI View Dock: authoritative RGB plus the Anchor Mask surface. */
export class AISelectAnchorDock extends Container {
    private readonly mask: AISelectMaskController;
    private readonly status: Label;
    private readonly maskStatus: Label;
    private readonly image: HTMLImageElement;
    private readonly overlay: HTMLCanvasElement;
    private readonly failureActions: Container;
    private readonly maskActions: Container;
    private readonly confirmMaskButton: Button;
    private readonly retryMaskButton: Button;
    private state: AISelectAnchorState = { context: null, anchor: null };
    private maskState: AISelectMaskState;
    private dragStart: { x: number; y: number } | null = null;
    private lastStrokePixel: ImagePixel | null = null;

    constructor(
        controller: AISelectAnchorController,
        mask: AISelectMaskController,
        options: AISelectAnchorDockOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-anchor-dock'
        });
        this.mask = mask;
        this.maskState = mask.state;
        this.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );

        const title = new Label({ id: 'ai-select-anchor-dock-title' });
        i18n.bindText(title, 'ai-select.panel.title');
        this.status = new Label({ id: 'ai-select-anchor-dock-status' });

        const imageWrap = document.createElement('div');
        imageWrap.id = 'ai-select-anchor-dock-image-wrap';
        this.image = document.createElement('img');
        this.image.id = 'ai-select-anchor-dock-image';
        this.image.alt = '';
        this.image.hidden = true;
        this.overlay = document.createElement('canvas');
        this.overlay.id = 'ai-select-anchor-dock-mask-overlay';
        this.overlay.hidden = true;
        imageWrap.appendChild(this.image);
        imageWrap.appendChild(this.overlay);
        imageWrap.addEventListener('pointerdown', (event) =>
            this.beginStroke(event)
        );
        imageWrap.addEventListener('pointermove', (event) =>
            this.continueStroke(event)
        );
        imageWrap.addEventListener('pointerup', (event) =>
            this.endStroke(event)
        );
        imageWrap.addEventListener('pointercancel', () => {
            this.dragStart = null;
            this.lastStrokePixel = null;
        });

        this.maskStatus = new Label({
            id: 'ai-select-anchor-dock-mask-status'
        });
        this.maskStatus.hidden = true;

        this.maskActions = new Container({
            id: 'ai-select-anchor-dock-mask-actions',
            hidden: true
        });
        this.confirmMaskButton = new Button({
            id: 'ai-select-anchor-dock-confirm-mask'
        });
        this.retryMaskButton = new Button({
            id: 'ai-select-anchor-dock-retry-mask'
        });
        i18n.bindText(this.confirmMaskButton, 'ai-select.mask.confirm');
        i18n.bindText(this.retryMaskButton, 'ai-select.mask.retry');
        this.confirmMaskButton.on('click', () => {
            try {
                this.mask.confirmEditingMask();
            } catch (error) {
                console.error(error);
            }
        });
        this.retryMaskButton.on('click', () => {
            this.mask.retryMaskRequest().catch((error) => console.error(error));
        });
        this.maskActions.append(this.confirmMaskButton);
        this.maskActions.append(this.retryMaskButton);

        this.failureActions = new Container({
            id: 'ai-select-anchor-dock-failure-actions',
            hidden: true
        });
        const retry = new Button({ id: 'ai-select-anchor-dock-retry' });
        const reconnect = new Button({ id: 'ai-select-anchor-dock-reconnect' });
        const settings = new Button({ id: 'ai-select-anchor-dock-settings' });
        i18n.bindText(retry, 'ai-select.retry');
        i18n.bindText(reconnect, 'ai-select.reconnect');
        i18n.bindText(settings, 'ai-select.open-settings');
        retry.on('click', () => {
            options.onRetry().catch((error) => console.error(error));
        });
        reconnect.on('click', () => {
            options.onReconnect().catch((error) => console.error(error));
        });
        settings.on('click', () => options.onOpenSettings());
        this.failureActions.append(retry);
        this.failureActions.append(reconnect);
        this.failureActions.append(settings);

        this.append(title);
        this.append(this.status);
        this.dom.appendChild(imageWrap);
        this.append(this.maskStatus);
        this.append(this.maskActions);
        this.append(this.failureActions);

        controller.subscribe((state) => {
            this.state = state;
            this.render();
        });
        mask.subscribe((maskState) => {
            this.maskState = maskState;
            this.render();
        });
        i18n.onChange(() => this.render(), this);
    }

    private render(): void {
        const presentation = getAnchorDockPresentation(
            this.state,
            this.maskState
        );
        if (presentation.rgb) {
            this.image.src = `data:image/png;base64,${presentation.rgb.pngBase64}`;
            this.image.hidden = false;
        } else {
            this.image.hidden = true;
        }
        const textKey = {
            idle: 'ai-select.panel.idle',
            ready: 'ai-select.anchor.ready',
            previewing: 'ai-select.anchor.previewing',
            rendering: 'ai-select.anchor.rendering',
            failed: 'ai-select.anchor.failed'
        }[presentation.status];
        this.status.text = i18n.t(textKey);
        this.failureActions.hidden = !presentation.showFailureActions;

        const mask = presentation.mask;
        if (mask.status === 'none' && presentation.status !== 'ready') {
            this.maskStatus.hidden = true;
        } else {
            this.maskStatus.hidden = false;
            this.maskStatus.text =
                mask.status === 'failed' && mask.errorMessage !== undefined
                    ? mask.errorMessage
                    : i18n.t(`ai-select.mask.${mask.status}`);
        }
        this.confirmMaskButton.hidden = !mask.showConfirm;
        this.retryMaskButton.hidden = !mask.showRetry;
        this.maskActions.hidden = !mask.showConfirm && !mask.showRetry;
        this.renderMaskOverlay(presentation);
    }

    private renderMaskOverlay(presentation: AnchorDockPresentation): void {
        const annotation =
            this.maskState.editingMask ?? this.maskState.stableMask;
        const rgb = presentation.rgb;
        if (
            presentation.status !== 'ready' ||
            annotation === null ||
            rgb === undefined ||
            annotation.artifact.width !== rgb.width ||
            annotation.artifact.height !== rgb.height
        ) {
            this.overlay.hidden = true;
            return;
        }
        const { width, height } = annotation.artifact;
        const bits = decodeMaskArtifact(annotation.artifact);
        const pixels = new Uint8ClampedArray(width * height * 4);
        const editing = this.maskState.editingMask !== null;
        for (let index = 0; index < width * height; index += 1) {
            if ((bits[index >> 3] & (1 << (index % 8))) === 0) {
                continue;
            }
            const offset = index * 4;
            if (editing) {
                pixels[offset] = 255;
                pixels[offset + 1] = 140;
                pixels[offset + 2] = 0;
            } else {
                pixels[offset + 1] = 190;
                pixels[offset + 2] = 255;
            }
            pixels[offset + 3] = 110;
        }
        this.overlay.width = width;
        this.overlay.height = height;
        const context = this.overlay.getContext('2d');
        if (context === null) {
            this.overlay.hidden = true;
            return;
        }
        context.putImageData(new ImageData(pixels, width, height), 0, 0);
        this.positionOverlay();
        this.overlay.hidden = false;
    }

    /** Align the overlay with the object-fit: contain painted image area. */
    private positionOverlay(): void {
        const rect = this.image.getBoundingClientRect();
        const painted = this.paintedRect(rect);
        if (painted === null) {
            this.overlay.hidden = true;
            return;
        }
        this.overlay.style.left = `${(painted.left / rect.width) * 100}%`;
        this.overlay.style.top = `${(painted.top / rect.height) * 100}%`;
        this.overlay.style.width = `${(painted.width / rect.width) * 100}%`;
        this.overlay.style.height = `${(painted.height / rect.height) * 100}%`;
    }

    private paintedRect(rect: DOMRect) {
        if (
            rect.width === 0 ||
            rect.height === 0 ||
            this.image.naturalWidth === 0 ||
            this.image.naturalHeight === 0
        ) {
            return null;
        }
        const scale = Math.min(
            rect.width / this.image.naturalWidth,
            rect.height / this.image.naturalHeight
        );
        const width = this.image.naturalWidth * scale;
        const height = this.image.naturalHeight * scale;
        return {
            left: (rect.width - width) / 2,
            top: (rect.height - height) / 2,
            width,
            height
        };
    }

    private toImagePixel(event: PointerEvent): ImagePixel | null {
        const rect = this.image.getBoundingClientRect();
        const painted = this.paintedRect(rect);
        if (painted === null) {
            return null;
        }
        const xPx = Math.floor(
            ((event.clientX - rect.left - painted.left) / painted.width) *
                this.image.naturalWidth
        );
        const yPx = Math.floor(
            ((event.clientY - rect.top - painted.top) / painted.height) *
                this.image.naturalHeight
        );
        if (
            xPx < 0 ||
            yPx < 0 ||
            xPx >= this.image.naturalWidth ||
            yPx >= this.image.naturalHeight
        ) {
            return null;
        }
        return { xPx, yPx };
    }

    private beginStroke(event: PointerEvent): void {
        if (
            event.button !== 0 ||
            getAnchorDockPresentation(this.state, this.maskState).status !==
                'ready'
        ) {
            return;
        }
        const pixel = this.toImagePixel(event);
        if (pixel === null) {
            return;
        }
        event.preventDefault();
        this.dragStart = { x: event.clientX, y: event.clientY };
        this.lastStrokePixel = pixel;
        this.image.setPointerCapture(event.pointerId);
    }

    private continueStroke(event: PointerEvent): void {
        if (this.dragStart === null) {
            return;
        }
        const moved =
            Math.abs(event.clientX - this.dragStart.x) +
            Math.abs(event.clientY - this.dragStart.y);
        if (moved <= CLICK_TOLERANCE_PX) {
            return;
        }
        const pixel = this.toImagePixel(event);
        if (
            pixel === null ||
            (this.lastStrokePixel !== null &&
                pixel.xPx === this.lastStrokePixel.xPx &&
                pixel.yPx === this.lastStrokePixel.yPx)
        ) {
            return;
        }
        this.lastStrokePixel = pixel;
        try {
            this.mask.applyBrushStroke({
                xPx: pixel.xPx,
                yPx: pixel.yPx,
                radiusPx: this.brushRadius(),
                mode: event.shiftKey ? 'erase' : 'add'
            });
        } catch (error) {
            console.error(error);
        }
    }

    private endStroke(event: PointerEvent): void {
        if (this.dragStart === null) {
            return;
        }
        const moved =
            Math.abs(event.clientX - this.dragStart.x) +
            Math.abs(event.clientY - this.dragStart.y);
        this.dragStart = null;
        this.lastStrokePixel = null;
        if (moved > CLICK_TOLERANCE_PX) {
            return;
        }
        const pixel = this.toImagePixel(event);
        if (pixel === null) {
            return;
        }
        this.mask
            .addPrompt({
                xPx: pixel.xPx,
                yPx: pixel.yPx,
                polarity: event.shiftKey ? 'exclude' : 'include'
            })
            .catch((error) => console.error(error));
    }

    private brushRadius(): number {
        return Math.max(3, Math.round(this.image.naturalWidth / 128));
    }
}
