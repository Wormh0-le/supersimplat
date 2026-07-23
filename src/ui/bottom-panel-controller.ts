export type BottomPanelId = 'timeline' | 'splatData' | 'aiSelect';

type BottomPanelListener = (panel: BottomPanelId | null) => void;

/** Owns the mutually exclusive state of the editor's bottom work surfaces. */
export class BottomPanelController {
    private readonly listeners = new Set<BottomPanelListener>();
    private panel: BottomPanelId | null = null;

    get activePanel(): BottomPanelId | null {
        return this.panel;
    }

    setActivePanel(panel: BottomPanelId | null): void {
        if (this.panel === panel) {
            return;
        }
        this.panel = panel;
        this.listeners.forEach(listener => listener(panel));
    }

    toggle(panel: BottomPanelId): void {
        this.setActivePanel(this.panel === panel ? null : panel);
    }

    subscribe(listener: BottomPanelListener): () => void {
        this.listeners.add(listener);
        listener(this.panel);
        return () => this.listeners.delete(listener);
    }
}
