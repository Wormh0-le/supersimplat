import { Button, Container, Label } from '@playcanvas/pcui';

import { Events } from '../events';
import { ShortcutManager } from '../shortcut-manager';
import { Splat } from '../splat';
import {
    BottomPanelController,
    type BottomPanelId
} from './bottom-panel-controller';
import { i18n } from './localization';
import { Tooltips } from './tooltips';

class StatusBar extends Container {
    constructor(events: Events, tooltips: Tooltips, args = {}) {
        args = {
            ...args,
            id: 'status-bar'
        };

        super(args);

        const panelController = new BottomPanelController();

        // Toggle buttons for panels
        const timelineButton = new Button({
            class: 'status-bar-toggle'
        });
        i18n.bindText(timelineButton, () => i18n.t('status-bar.timeline').toUpperCase()
        );

        const splatDataButton = new Button({
            class: 'status-bar-toggle'
        });
        i18n.bindText(splatDataButton, () => i18n.t('status-bar.splat-data').toUpperCase()
        );

        const aiSelectButton = new Button({
            class: 'status-bar-toggle'
        });
        i18n.bindText(aiSelectButton, () => i18n.t('status-bar.ai-select').toUpperCase()
        );

        const setActivePanel = (panel: BottomPanelId | null) => {
            panelController.setActivePanel(panel);
        };

        panelController.subscribe((panel) => {
            timelineButton.dom.classList[
            panel === 'timeline' ? 'add' : 'remove'
            ]('active');
            splatDataButton.dom.classList[
            panel === 'splatData' ? 'add' : 'remove'
            ]('active');
            aiSelectButton.dom.classList[
            panel === 'aiSelect' ? 'add' : 'remove'
            ]('active');
            events.fire('statusBar.panelChanged', panel || null);
        });

        timelineButton.on('click', () => {
            panelController.toggle('timeline');
        });

        splatDataButton.on('click', () => {
            panelController.toggle('splatData');
        });

        aiSelectButton.on('click', () => {
            panelController.toggle('aiSelect');
        });

        // Right section: stats
        const statsContainer = new Container({
            class: 'status-bar-stats'
        });

        const createStat = (labelKey: string) => {
            const container = new Container({
                class: 'status-bar-stat'
            });
            const label = new Label({
                class: 'status-bar-stat-label'
            });
            i18n.bindText(label, labelKey);
            const value = new Label({
                class: 'status-bar-stat-value',
                text: '0'
            });
            container.append(label);
            container.append(value);
            statsContainer.append(container);
            return value;
        };

        const splatsValue = createStat('status-bar.splats');
        const selectedValue = createStat('status-bar.selected');
        const lockedValue = createStat('status-bar.locked');
        const deletedValue = createStat('status-bar.deleted');

        this.append(timelineButton);
        this.append(splatDataButton);
        this.append(aiSelectButton);
        this.append(statsContainer);

        // register tooltips
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

        tooltips.register(
            timelineButton,
            tooltip('tooltip.status-bar.timeline', 'timelinePanel.toggle'),
            'top'
        );
        tooltips.register(
            splatDataButton,
            tooltip('tooltip.status-bar.splat-data', 'dataPanel.toggle'),
            'top'
        );
        tooltips.register(
            aiSelectButton,
            tooltip('tooltip.status-bar.ai-select'),
            'top'
        );

        // Handle keyboard shortcuts for panel toggles
        events.on('dataPanel.toggle', () => {
            panelController.toggle('splatData');
        });

        events.on('timelinePanel.toggle', () => {
            panelController.toggle('timeline');
        });

        events.on('statusBar.setPanel', (panel: BottomPanelId | null) => {
            setActivePanel(panel);
        });

        // Update stats from splat state
        let splat: Splat;

        const updateStats = () => {
            if (!splat) return;
            const state = splat.splatData.getProp('state') as Uint8Array;
            if (state) {
                splatsValue.text = i18n.formatInteger(
                    state.length - splat.numDeleted
                );
                selectedValue.text = i18n.formatInteger(splat.numSelected);
                lockedValue.text = i18n.formatInteger(splat.numLocked);
                deletedValue.text = i18n.formatInteger(splat.numDeleted);
            }
        };

        events.on('splat.stateChanged', (splat_: Splat) => {
            splat = splat_;
            updateStats();
        });

        events.on('selection.changed', (selection: Element) => {
            if (selection instanceof Splat) {
                splat = selection;
                updateStats();
            }
        });
    }
}

export { StatusBar };
