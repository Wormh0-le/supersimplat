import { Container, Label } from '@playcanvas/pcui';

import type {
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessStatus
} from '../selection-service-readiness';

const selectionServiceAvailabilityLabel = (
    status: SelectionServiceReadinessStatus
) => {
    switch (status) {
        case 'connecting':
            return 'Connecting';
        case 'available':
            return 'Available';
        case 'unavailable':
            return 'Unavailable';
    }
};

class SelectionServiceReadinessSettings extends Container {
    constructor(readiness: SelectionServiceReadinessInterface, args = {}) {
        super({
            ...args,
            class: 'selection-service-readiness-settings'
        });

        const heading = new Label({
            class: 'selection-service-readiness-heading',
            text: 'AI Select'
        });
        const status = new Label({
            class: 'selection-service-readiness-status',
            text: selectionServiceAvailabilityLabel(readiness.state.status)
        });
        status.dom.setAttribute('role', 'status');
        status.dom.setAttribute('aria-live', 'polite');

        this.append(heading);
        this.append(status);

        readiness.subscribe((state) => {
            status.text = selectionServiceAvailabilityLabel(state.status);
        });
    }
}

export { SelectionServiceReadinessSettings, selectionServiceAvailabilityLabel };
