import { Events } from './events';
import {
    defaultSelectionServiceEndpoint,
    type SelectionServiceReadinessInterface,
    type SelectionServiceTransportProfile
} from './selection-service-readiness';

const registerSelectionServiceReadinessEvents = (
    events: Events,
    readiness: SelectionServiceReadinessInterface
) => {
    events.function('selectionService.readiness', () => readiness);

    events.on('selectionService.setEndpoint', (endpoint: string) => {
        readiness.updateConfiguration({ endpoint });
    });

    events.on(
        'selectionService.setProfile',
        (profile: SelectionServiceTransportProfile) => {
            readiness.updateConfiguration({ profile });
        }
    );

    events.on('selectionService.refresh', () => {
        readiness.refresh().catch(error => console.error(error));
    });

    // Endpoint and profile are ordinary non-secret editor preferences. A model
    // digest deliberately is not persisted: each editor load requires an
    // explicit selection from the Companion's currently installed manifests.
    readiness.subscribe((state) => {
        events.fire('selectionService.endpoint', state.configuration.endpoint);
        events.fire('selectionService.profile', state.configuration.profile);
        events.fire(
            'selectionService.modelManifestDigest',
            state.configuration.modelManifestDigest
        );
        events.fire('selectionService.readinessChanged', state);
    });

    events.on('preferences.reset', () => {
        readiness.updateConfiguration({
            endpoint: defaultSelectionServiceEndpoint,
            profile: 'loopback',
            modelManifestDigest: null
        });
    });
};

export { registerSelectionServiceReadinessEvents };
