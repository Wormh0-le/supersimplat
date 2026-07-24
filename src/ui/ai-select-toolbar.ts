import { Button, Container, Label } from '@playcanvas/pcui';

import { i18n } from './localization';
import type { AISelectAnchorController } from '../ai-select/anchor-controller';
import {
    getAnchorDockPresentation,
    type AnchorDockStatus
} from '../ai-select/anchor-dock-presentation';
import type { CameraInspectionController } from '../ai-select/camera-inspection';

export interface AISelectToolbarOptions {
    readonly onRestart: () => Promise<void>;
    readonly onExit: () => void;
    readonly onEnterInspection: () => void;
    readonly onReturnToSceneView: () => void;
    readonly onResetAnchor: () => Promise<void>;
    readonly onRetryPreview: () => Promise<void>;
}

const statusTextKeys: Record<AnchorDockStatus, string> = {
    idle: 'ai-select.panel.idle',
    ready: 'ai-select.anchor.ready',
    previewing: 'ai-select.anchor.previewing',
    rendering: 'ai-select.anchor.rendering',
    failed: 'ai-select.anchor.failed'
};

/** Contextual controls for the current Anchor and explicit Camera Inspection. */
export class AISelectToolbar extends Container {
    constructor(
        controller: AISelectAnchorController,
        inspection: CameraInspectionController,
        options: AISelectToolbarOptions,
        args = {}
    ) {
        super({
            ...args,
            id: 'ai-select-toolbar',
            hidden: true
        });
        this.dom.addEventListener('pointerdown', (event) =>
            event.stopPropagation()
        );

        const tool = new Label({ id: 'ai-select-toolbar-tool' });
        const anchor = new Label({ id: 'ai-select-toolbar-anchor' });
        const adjust = new Button({
            id: 'ai-select-toolbar-adjust-anchor',
            enabled: false
        });
        const move = new Button({
            id: 'ai-select-toolbar-move-anchor',
            hidden: true
        });
        const rotate = new Button({
            id: 'ai-select-toolbar-rotate-anchor',
            hidden: true
        });
        const returnToSceneView = new Button({
            id: 'ai-select-toolbar-return-to-scene-view',
            hidden: true
        });
        const resetAnchor = new Button({
            id: 'ai-select-toolbar-reset-anchor',
            hidden: true
        });
        const status = new Label({
            id: 'ai-select-toolbar-status',
            hidden: true
        });
        const retry = new Button({
            id: 'ai-select-toolbar-retry-preview',
            hidden: true
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

        adjust.on('click', () => options.onEnterInspection());
        move.on('click', () => inspection.setManipulation('move'));
        rotate.on('click', () => inspection.setManipulation('rotate'));
        returnToSceneView.on('click', () => options.onReturnToSceneView());
        resetAnchor.on('click', () => {
            options
                .onResetAnchor()
                .catch((error: unknown): void => console.error(error));
        });
        retry.on('click', () => {
            options
                .onRetryPreview()
                .catch((error: unknown): void => console.error(error));
        });
        restart.on('click', () => {
            options
                .onRestart()
                .catch((error: unknown): void => console.error(error));
        });
        exit.on('click', () => options.onExit());
        more.on('click', () => {
            overflow.hidden = !overflow.hidden;
        });

        this.append(tool);
        this.append(anchor);
        this.append(adjust);
        this.append(move);
        this.append(rotate);
        this.append(returnToSceneView);
        this.append(resetAnchor);
        this.append(status);
        this.append(retry);
        this.append(more);
        overflow.append(restart);
        overflow.append(exit);
        this.append(overflow);

        let anchorState = controller.state;
        let inspectionState = inspection.state;
        const render = () => {
            const hasContext = anchorState.context !== null;
            const hasAnchor = anchorState.anchor !== null;
            const contextIsActive = anchorState.context?.lifecycle === 'active';
            const inspecting = inspectionState.mode === 'active';
            const presentation = getAnchorDockPresentation(anchorState);
            this.hidden = !hasContext;
            tool.text = i18n.t(
                inspecting ? 'ai-select.camera-inspection' : 'ai-select.tool'
            );
            anchor.text = i18n.t('ai-select.anchor.current-view');
            adjust.text = i18n.t('ai-select.adjust-anchor');
            move.text = i18n.t('ai-select.move');
            rotate.text = i18n.t('ai-select.rotate');
            returnToSceneView.text = i18n.t('ai-select.return-to-scene-view');
            resetAnchor.text = i18n.t('ai-select.reset-anchor');
            status.text = i18n.t(statusTextKeys[presentation.status]);
            retry.text = i18n.t('ai-select.retry');
            restart.text = i18n.t('ai-select.restart-current-target');
            exit.text = i18n.t('ai-select.exit');
            more.dom.setAttribute('aria-label', i18n.t('ai-select.more'));

            anchor.hidden = inspecting;
            adjust.hidden = inspecting;
            // A suspended context remains read-only inspectable. Move/Rotate
            // and Reset stay gated below because they mutate the Anchor.
            adjust.enabled = hasAnchor && hasContext && !inspecting;
            move.hidden = !inspecting;
            rotate.hidden = !inspecting;
            returnToSceneView.hidden = !inspecting;
            resetAnchor.hidden = !inspecting;
            status.hidden = !inspecting;
            // The failed current preview keeps its true-Retry action next to
            // the status so the recovery path is visible from the toolbar.
            retry.hidden = !inspecting || presentation.status !== 'failed';
            move.enabled = inspecting && hasAnchor && contextIsActive;
            rotate.enabled = inspecting && hasAnchor && contextIsActive;
            returnToSceneView.enabled = inspecting;
            resetAnchor.enabled = inspecting && hasAnchor && contextIsActive;
            retry.enabled = contextIsActive;
            restart.enabled = hasContext;
            if (!hasContext) {
                overflow.hidden = true;
            }
        };
        controller.subscribe((state) => {
            anchorState = state;
            render();
        });
        inspection.subscribe((state) => {
            inspectionState = state;
            render();
        });
        i18n.onChange(render, this);
    }
}
