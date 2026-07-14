import {
    Button,
    Container,
    Label,
    SelectInput,
    TextInput
} from '@playcanvas/pcui';

import type {
    SelectionServiceReadinessInterface,
    SelectionServiceReadinessState,
    SelectionServiceTransportProfile
} from '../selection-service-readiness';

class SelectionServiceReadinessSettings extends Container {
    private synchronizing = false;

    constructor(readiness: SelectionServiceReadinessInterface, args = {}) {
        args = {
            ...args,
            class: 'selection-service-readiness-settings'
        };

        super(args);

        const heading = new Label({
            class: 'selection-service-readiness-heading',
            text: 'Selection Service Companion'
        });

        const profileRow = new Container({
            class: 'selection-service-readiness-row'
        });
        const profileLabel = new Label({
            class: 'selection-service-readiness-label',
            text: 'Profile'
        });
        const profile = new SelectInput({
            class: 'selection-service-readiness-select',
            options: [
                { v: 'loopback', t: 'Loopback (this machine)' },
                { v: 'trustedLan', t: 'Trusted LAN (HTTPS)' }
            ],
            defaultValue: 'loopback'
        });
        profileRow.append(profileLabel);
        profileRow.append(profile);

        const endpointRow = new Container({
            class: 'selection-service-readiness-row'
        });
        const endpointLabel = new Label({
            class: 'selection-service-readiness-label',
            text: 'Endpoint'
        });
        const endpoint = new TextInput({
            class: 'selection-service-readiness-endpoint',
            placeholder: 'http://127.0.0.1:8787'
        });
        endpointRow.append(endpointLabel);
        endpointRow.append(endpoint);

        const modelRow = new Container({
            class: 'selection-service-readiness-row'
        });
        const modelLabel = new Label({
            class: 'selection-service-readiness-label',
            text: 'Model'
        });
        const model = new SelectInput({
            class: 'selection-service-readiness-select',
            allowNull: true,
            options: [{ v: '', t: 'Check Companion to list models' }]
        });
        modelRow.append(modelLabel);
        modelRow.append(model);

        const controls = new Container({
            class: 'selection-service-readiness-controls'
        });
        const check = new Button({
            class: 'selection-service-readiness-check',
            text: 'Check readiness'
        });
        controls.append(check);

        const status = new Label({ class: 'selection-service-readiness-status' });
        const diagnostic = new Label({
            class: 'selection-service-readiness-diagnostic'
        });

        this.append(heading);
        this.append(profileRow);
        this.append(endpointRow);
        this.append(modelRow);
        this.append(controls);
        this.append(status);
        this.append(diagnostic);

        profile.on('change', (value: SelectionServiceTransportProfile) => {
            if (this.synchronizing) {
                return;
            }
            readiness.updateConfiguration({ profile: value });
        });
        endpoint.on('change', (value: string) => {
            if (this.synchronizing) {
                return;
            }
            readiness.updateConfiguration({ endpoint: value.trim() });
        });
        model.on('change', (value: string | null) => {
            if (this.synchronizing) {
                return;
            }
            readiness.updateConfiguration({ modelManifestDigest: value || null });
        });
        check.on('click', () => {
            readiness.refresh().catch(error => console.error(error));
        });

        readiness.subscribe((state) => {
            this.update(state, {
                profile,
                endpoint,
                model,
                check,
                status,
                diagnostic
            });
        });
    }

    private update(
        state: SelectionServiceReadinessState,
        controls: {
      profile: SelectInput;
      endpoint: TextInput;
      model: SelectInput;
      check: Button;
      status: Label;
      diagnostic: Label;
    }
    ) {
        this.synchronizing = true;
        try {
            controls.profile.value = state.configuration.profile;
            controls.endpoint.value = state.configuration.endpoint;
            controls.model.options = state.capabilities ?
                [
                    { v: '', t: 'Select an installed model' },
                    ...state.capabilities.modelManifests.map(manifest => ({
                        v: manifest.digest,
                        t: `${manifest.modelName} (${manifest.digest})`
                    }))
                ] :
                [{ v: '', t: 'Check Companion to list models' }];
            controls.model.value = state.configuration.modelManifestDigest ?? '';
            controls.check.enabled = state.status !== 'checking';
            controls.status.text = `Object Selection: ${state.status}`;
            controls.diagnostic.text =
        `${state.diagnostic.message} ${state.diagnostic.action}`.trim();
        } finally {
            this.synchronizing = false;
        }
    }
}

export { SelectionServiceReadinessSettings };
