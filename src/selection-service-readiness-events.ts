import { Events } from './events';
import type { SelectionServiceReadinessInterface } from './selection-service-readiness';

const registerSelectionServiceReadinessEvents = (
    events: Events,
    readiness: SelectionServiceReadinessInterface
) => {
    events.function('selectionService.readiness', () => readiness);

    events.on('selectionService.refresh', () => {
        readiness.refresh().catch((error) => console.error(error));
    });

    readiness.subscribe((state) => {
        events.fire('selectionService.readinessChanged', state);
    });
};

export { registerSelectionServiceReadinessEvents };
