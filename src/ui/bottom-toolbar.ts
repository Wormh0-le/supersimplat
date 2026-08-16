import { Button, Element, Container } from '@playcanvas/pcui';

import { Events } from '../events';
import { ShortcutManager } from '../shortcut-manager';
import { i18n } from './localization';
import aiSelectCancelSvg from './svg/ai-select-cancel.svg';
import aiSelectToolSvg from './svg/ai-select-tool.svg';
import newSvg from './svg/new.svg';
import redoSvg from './svg/redo.svg';
import brushSvg from './svg/select-brush.svg';
import eyedropperSvg from './svg/select-eyedropper.svg';
import floodSvg from './svg/select-flood.svg';
import lassoSvg from './svg/select-lasso.svg';
import pickerSvg from './svg/select-picker.svg';
import polygonSvg from './svg/select-poly.svg';
import sphereSvg from './svg/select-sphere.svg';
import boxSvg from './svg/show-hide-splats.svg';
import undoSvg from './svg/undo.svg';
import { Tooltips } from './tooltips';
// import cropSvg from './svg/crop.svg';

const createSvg = (svgString: string) => {
    const decodedStr = decodeURIComponent(
        svgString.substring('data:image/svg+xml,'.length)
    );
    return new DOMParser().parseFromString(decodedStr, 'image/svg+xml')
        .documentElement;
};

class BottomToolbar extends Container {
    constructor(events: Events, tooltips: Tooltips, args = {}) {
        args = {
            ...args,
            id: 'bottom-toolbar'
        };

        super(args);

        this.dom.addEventListener('pointerdown', (event) => {
            event.stopPropagation();
        });

        const undo = new Button({
            id: 'bottom-toolbar-undo',
            class: 'bottom-toolbar-button',
            enabled: false
        });

        const redo = new Button({
            id: 'bottom-toolbar-redo',
            class: 'bottom-toolbar-button',
            enabled: false
        });

        const picker = new Button({
            id: 'bottom-toolbar-picker',
            class: 'bottom-toolbar-tool'
        });

        const polygon = new Button({
            id: 'bottom-toolbar-polygon',
            class: 'bottom-toolbar-tool'
        });

        const brush = new Button({
            id: 'bottom-toolbar-brush',
            class: 'bottom-toolbar-tool'
        });

        const flood = new Button({
            id: 'bottom-toolbar-flood',
            class: 'bottom-toolbar-tool'
        });

        const lasso = new Button({
            id: 'bottom-toolbar-lasso',
            class: 'bottom-toolbar-tool'
        });

        const sphere = new Button({
            id: 'bottom-toolbar-sphere',
            class: 'bottom-toolbar-tool'
        });

        const box = new Button({
            id: 'bottom-toolbar-box',
            class: 'bottom-toolbar-tool'
        });

        const aiSelect = new Button({
            id: 'bottom-toolbar-ai-select',
            class: 'bottom-toolbar-tool'
        });
        aiSelect.dom.appendChild(createSvg(aiSelectToolSvg));
        aiSelect.dom.setAttribute('aria-haspopup', 'menu');
        aiSelect.dom.setAttribute('aria-expanded', 'false');
        const aiSelectLifecycleGroup = new Container({
            id: 'bottom-toolbar-ai-select-lifecycle'
        });
        const aiSelectLifecycleMenu = new Container({
            id: 'bottom-toolbar-ai-select-menu',
            hidden: true
        });
        aiSelectLifecycleMenu.dom.setAttribute('role', 'menu');
        const chooseAnotherObject = new Button({
            id: 'bottom-toolbar-ai-select-choose-another',
            class: 'bottom-toolbar-ai-select-menu-item'
        });
        chooseAnotherObject.dom.setAttribute('role', 'menuitem');
        const exitAISelect = new Button({
            id: 'bottom-toolbar-ai-select-exit',
            class: 'bottom-toolbar-ai-select-menu-item'
        });
        exitAISelect.dom.setAttribute('role', 'menuitem');
        const renderAISelectLifecycleLabels = () => {
            aiSelect.dom.setAttribute('aria-label', i18n.t('ai-select.tool'));
            chooseAnotherObject.text = i18n.t(
                'ai-select.restart-current-target'
            );
            chooseAnotherObject.dom.prepend(createSvg(newSvg));
            chooseAnotherObject.dom.setAttribute(
                'aria-description',
                i18n.t('ai-select.restart-description')
            );
            chooseAnotherObject.dom.title = i18n.t(
                'ai-select.restart-description'
            );
            exitAISelect.text = i18n.t('ai-select.exit');
            exitAISelect.dom.prepend(createSvg(aiSelectCancelSvg));
        };
        i18n.onChange(renderAISelectLifecycleLabels, aiSelectLifecycleGroup);
        aiSelectLifecycleMenu.append(chooseAnotherObject);
        aiSelectLifecycleMenu.append(exitAISelect);
        aiSelectLifecycleGroup.append(aiSelect);
        aiSelectLifecycleGroup.append(aiSelectLifecycleMenu);

        const eyedropper = new Button({
            id: 'bottom-toolbar-eyedropper',
            class: 'bottom-toolbar-tool'
        });

        // const crop = new Button({
        //     id: 'bottom-toolbar-crop',
        //     class: ['bottom-toolbar-tool', 'disabled']
        // });

        const translate = new Button({
            id: 'bottom-toolbar-translate',
            class: 'bottom-toolbar-tool',
            icon: 'E111'
        });

        const rotate = new Button({
            id: 'bottom-toolbar-rotate',
            class: 'bottom-toolbar-tool',
            icon: 'E113'
        });

        const scale = new Button({
            id: 'bottom-toolbar-scale',
            class: 'bottom-toolbar-tool',
            icon: 'E112'
        });

        const measure = new Button({
            id: 'bottom-toolbar-measure',
            class: 'bottom-toolbar-tool',
            icon: 'E358'
        });

        const coordSpace = new Button({
            id: 'bottom-toolbar-coord-space',
            class: 'bottom-toolbar-toggle',
            icon: 'E118'
        });

        const origin = new Button({
            id: 'bottom-toolbar-origin',
            class: ['bottom-toolbar-toggle'],
            icon: 'E189'
        });

        undo.dom.appendChild(createSvg(undoSvg));
        redo.dom.appendChild(createSvg(redoSvg));
        picker.dom.appendChild(createSvg(pickerSvg));
        polygon.dom.appendChild(createSvg(polygonSvg));
        brush.dom.appendChild(createSvg(brushSvg));
        flood.dom.appendChild(createSvg(floodSvg));
        sphere.dom.appendChild(createSvg(sphereSvg));
        box.dom.appendChild(createSvg(boxSvg));
        lasso.dom.appendChild(createSvg(lassoSvg));
        eyedropper.dom.appendChild(createSvg(eyedropperSvg));
        // crop.dom.appendChild(createSvg(cropSvg));

        this.append(undo);
        this.append(redo);
        this.append(new Element({ class: 'bottom-toolbar-separator' }));
        this.append(picker);
        this.append(lasso);
        this.append(polygon);
        this.append(brush);
        this.append(flood);
        this.append(eyedropper);
        this.append(new Element({ class: 'bottom-toolbar-separator' }));
        this.append(sphere);
        this.append(box);
        this.append(aiSelectLifecycleGroup);
        // this.append(crop);
        this.append(new Element({ class: 'bottom-toolbar-separator' }));
        this.append(translate);
        this.append(rotate);
        this.append(scale);
        this.append(new Element({ class: 'bottom-toolbar-separator' }));
        this.append(measure);
        this.append(coordSpace);
        this.append(origin);

        undo.dom.addEventListener('click', () => events.fire('edit.undo'));
        redo.dom.addEventListener('click', () => events.fire('edit.redo'));
        polygon.dom.addEventListener('click', () =>
            events.fire('tool.polygonSelection')
        );
        lasso.dom.addEventListener('click', () =>
            events.fire('tool.lassoSelection')
        );
        brush.dom.addEventListener('click', () =>
            events.fire('tool.brushSelection')
        );
        flood.dom.addEventListener('click', () =>
            events.fire('tool.floodSelection')
        );
        picker.dom.addEventListener('click', () =>
            events.fire('tool.rectSelection')
        );
        eyedropper.dom.addEventListener('click', () =>
            events.fire('tool.eyedropperSelection')
        );
        sphere.dom.addEventListener('click', () =>
            events.fire('tool.sphereSelection')
        );
        box.dom.addEventListener('click', () =>
            events.fire('tool.boxSelection')
        );
        let aiSelectActive = false;
        const closeAISelectLifecycleMenu = (restoreFocus: boolean) => {
            if (aiSelectLifecycleMenu.hidden) {
                return;
            }
            aiSelectLifecycleMenu.hidden = true;
            aiSelect.dom.setAttribute('aria-expanded', 'false');
            if (restoreFocus) {
                aiSelect.dom.focus();
            }
        };
        const openAISelectLifecycleMenu = () => {
            if (!aiSelectActive) {
                return;
            }
            aiSelectLifecycleMenu.hidden = false;
            aiSelect.dom.setAttribute('aria-expanded', 'true');
            chooseAnotherObject.dom.focus();
        };
        aiSelect.dom.addEventListener('click', () => {
            if (!aiSelectActive) {
                events.fire('tool.aiSelect');
                return;
            }
            if (aiSelectLifecycleMenu.hidden) {
                openAISelectLifecycleMenu();
            } else {
                closeAISelectLifecycleMenu(true);
            }
        });
        aiSelect.dom.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown' && aiSelectActive) {
                openAISelectLifecycleMenu();
                event.preventDefault();
            }
        });
        chooseAnotherObject.on('click', () => {
            closeAISelectLifecycleMenu(true);
            events.fire('aiSelect.chooseAnotherObject');
        });
        exitAISelect.on('click', () => {
            closeAISelectLifecycleMenu(true);
            events.fire('tool.deactivate');
        });
        const menuItems = [chooseAnotherObject, exitAISelect];
        for (const [index, item] of menuItems.entries()) {
            item.dom.addEventListener('keydown', (event) => {
                if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                    const delta = event.key === 'ArrowDown' ? 1 : -1;
                    menuItems[
                        (index + delta + menuItems.length) % menuItems.length
                    ].dom.focus();
                    event.preventDefault();
                }
            });
        }
        document.addEventListener(
            'pointerdown',
            (event) => {
                if (
                    !aiSelectLifecycleGroup.dom.contains(event.target as Node)
                ) {
                    closeAISelectLifecycleMenu(false);
                }
            },
            true
        );
        window.addEventListener(
            'keydown',
            (event) => {
                if (event.key === 'Escape' && !aiSelectLifecycleMenu.hidden) {
                    closeAISelectLifecycleMenu(true);
                    event.preventDefault();
                    event.stopPropagation();
                }
            },
            true
        );
        translate.dom.addEventListener('click', () => events.fire('tool.move'));
        rotate.dom.addEventListener('click', () => events.fire('tool.rotate'));
        scale.dom.addEventListener('click', () => events.fire('tool.scale'));
        measure.dom.addEventListener('click', () =>
            events.fire('tool.measure')
        );
        coordSpace.dom.addEventListener('click', () =>
            events.fire('tool.toggleCoordSpace')
        );
        origin.dom.addEventListener('click', () =>
            events.fire('pivot.toggleOrigin')
        );

        events.on('edit.canUndo', (value: boolean) => {
            undo.enabled = value;
        });
        events.on('edit.canRedo', (value: boolean) => {
            redo.enabled = value;
        });

        events.on('tool.activated', (toolName: string) => {
            picker.class[toolName === 'rectSelection' ? 'add' : 'remove'](
                'active'
            );
            brush.class[toolName === 'brushSelection' ? 'add' : 'remove'](
                'active'
            );
            flood.class[toolName === 'floodSelection' ? 'add' : 'remove'](
                'active'
            );
            polygon.class[toolName === 'polygonSelection' ? 'add' : 'remove'](
                'active'
            );
            lasso.class[toolName === 'lassoSelection' ? 'add' : 'remove'](
                'active'
            );
            sphere.class[toolName === 'sphereSelection' ? 'add' : 'remove'](
                'active'
            );
            box.class[toolName === 'boxSelection' ? 'add' : 'remove']('active');
            aiSelect.class[toolName === 'aiSelect' ? 'add' : 'remove'](
                'active'
            );
            aiSelectActive = toolName === 'aiSelect';
            if (!aiSelectActive) {
                closeAISelectLifecycleMenu(false);
            }
            translate.class[toolName === 'move' ? 'add' : 'remove']('active');
            rotate.class[toolName === 'rotate' ? 'add' : 'remove']('active');
            scale.class[toolName === 'scale' ? 'add' : 'remove']('active');
            measure.class[toolName === 'measure' ? 'add' : 'remove']('active');
            eyedropper.class[
                toolName === 'eyedropperSelection' ? 'add' : 'remove'
            ]('active');
        });
        events.on('tool.deactivated', () => {
            aiSelectActive = false;
            closeAISelectLifecycleMenu(false);
        });

        events.on('tool.coordSpace', (space: 'local' | 'world') => {
            coordSpace.dom.classList[space === 'local' ? 'add' : 'remove'](
                'active'
            );
        });

        events.on('pivot.origin', (o: 'center' | 'boundCenter') => {
            origin.dom.classList[o === 'boundCenter' ? 'add' : 'remove'](
                'active'
            );
        });

        // Helper to compose localized tooltip text with shortcut
        const shortcutManager: ShortcutManager =
            events.invoke('shortcutManager');
        const tooltip = (localeKey: string, shortcutId?: string) => () => {
            const text = i18n.t(localeKey);
            if (shortcutId) {
                const shortcut = shortcutManager.formatShortcut(shortcutId);
                if (shortcut) {
                    return i18n.formatTooltipWithShortcut(text, shortcut);
                }
            }
            return text;
        };

        // register tooltips
        tooltips.register(
            undo,
            tooltip('tooltip.bottom-toolbar.undo', 'edit.undo')
        );
        tooltips.register(
            redo,
            tooltip('tooltip.bottom-toolbar.redo', 'edit.redo')
        );
        tooltips.register(
            picker,
            tooltip('tooltip.bottom-toolbar.rect', 'tool.rectSelection')
        );
        tooltips.register(
            lasso,
            tooltip('tooltip.bottom-toolbar.lasso', 'tool.lassoSelection')
        );
        tooltips.register(
            polygon,
            tooltip('tooltip.bottom-toolbar.polygon', 'tool.polygonSelection')
        );
        tooltips.register(
            brush,
            tooltip('tooltip.bottom-toolbar.brush', 'tool.brushSelection')
        );
        tooltips.register(
            flood,
            tooltip('tooltip.bottom-toolbar.flood', 'tool.floodSelection')
        );
        tooltips.register(sphere, tooltip('tooltip.bottom-toolbar.sphere'));
        tooltips.register(box, tooltip('tooltip.bottom-toolbar.box'));
        tooltips.register(aiSelect, tooltip('ai-select.tool'));
        tooltips.register(
            chooseAnotherObject,
            tooltip('ai-select.restart-description')
        );
        tooltips.register(
            translate,
            tooltip('tooltip.bottom-toolbar.translate', 'tool.move')
        );
        tooltips.register(
            rotate,
            tooltip('tooltip.bottom-toolbar.rotate', 'tool.rotate')
        );
        tooltips.register(
            scale,
            tooltip('tooltip.bottom-toolbar.scale', 'tool.scale')
        );
        tooltips.register(measure, tooltip('tooltip.bottom-toolbar.measure'));
        tooltips.register(
            coordSpace,
            tooltip(
                'tooltip.bottom-toolbar.local-space',
                'tool.toggleCoordSpace'
            )
        );
        tooltips.register(
            origin,
            tooltip('tooltip.bottom-toolbar.bound-center')
        );
        tooltips.register(
            eyedropper,
            tooltip(
                'tooltip.bottom-toolbar.eyedropper',
                'tool.eyedropperSelection'
            )
        );
    }
}

export { BottomToolbar };
