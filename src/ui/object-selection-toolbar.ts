import { Button, Container } from '@playcanvas/pcui';

import { ObjectSelectionSessionInterface, ObjectSelectionSessionStart } from '../object-selection-session';

interface ObjectSelectionToolbarOptions {
    // The production workflow owns Target Splat lookup and initial point
    // capture, while tests/future callers may still provide a raw session start.
    startNew?: () => Promise<void>;
    getNewSessionStart?: () => ObjectSelectionSessionStart | null;
    onError?: (error: unknown) => void;
}

class ObjectSelectionToolbar extends Container {
    constructor(session: ObjectSelectionSessionInterface, options: ObjectSelectionToolbarOptions, args = {}) {
        args = {
            ...args,
            id: 'object-selection-toolbar'
        };

        super(args);

        this.dom.addEventListener('pointerdown', (event) => {
            event.stopPropagation();
        });

        const startNew = new Button({
            id: 'object-selection-toolbar-new',
            text: 'New'
        });

        this.append(startNew);

        startNew.on('click', () => {
            if (options.startNew) {
                this.run(options.startNew, options);
                return;
            }
            const start = options.getNewSessionStart?.();
            if (!start) {
                return;
            }
            this.run(() => session.startNew(start), options);
        });

        session.subscribe((state) => {
            startNew.enabled = state.status === 'idle';
        });
    }

    private run(action: () => Promise<void>, options: ObjectSelectionToolbarOptions) {
        action().catch(error => this.reportError(error, options));
    }

    private reportError(error: unknown, options: ObjectSelectionToolbarOptions) {
        if (options.onError) {
            options.onError(error);
        } else {
            console.error(error);
        }
    }
}

export { ObjectSelectionToolbar };

export type { ObjectSelectionToolbarOptions };
