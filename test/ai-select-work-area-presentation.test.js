const assert = require('node:assert/strict');
const test = require('node:test');

const {
    mapWorkAreaActions
} = require('../.test-dist/src/ai-select/work-area-presentation.js');

const emptyReadiness = Object.freeze({
    status: 'empty',
    readiness: null,
    observationCoverage: null,
    viewDiversity: null,
    reasons: [],
    recommendation: null,
    source: null
});

const readiness = (level, status = 'current') =>
    Object.freeze({
        status,
        readiness: level,
        observationCoverage: {
            status: 'pending-formal-evidence',
            totalCoreGaussianCount: 1
        },
        viewDiversity: {
            status: 'pending-formal-evidence',
            usefulViewCount: 0,
            maximumAngularSeparationDegrees: 0
        },
        reasons: level === 'ready' ? [] : ['formal-evidence-pending'],
        recommendation: level === 'ready' ? 'none' : 'add-view',
        source: 'low-cost-diagnostic'
    });

const input = (overrides = {}) => ({
    targetActive: true,
    serviceAvailable: true,
    hasUsableIncludedStableInput: true,
    hasUnconfirmedIncludedMask: false,
    candidateStatus: 'empty',
    correctionMode: 'candidate',
    correctionStatus: 'idle',
    liftReadiness: readiness('ready'),
    canConfirmMask: false,
    canConfirmReview: false,
    anchorNeedsConfirmation: false,
    ...overrides
});

test('Re-Lift maps absent-input, current, stale, updating and failed Candidate states', () => {
    assert.deepEqual(
        mapWorkAreaActions(
            input({
                hasUsableIncludedStableInput: false
            })
        ).reLift,
        {
            visible: true,
            enabled: false,
            emphasis: 'normal',
            state: 'idle',
            reason: 'no-usable-included-stable-input'
        }
    );
    assert.equal(
        mapWorkAreaActions(input({ candidateStatus: 'current' })).reLift
            .visible,
        false
    );
    assert.equal(
        mapWorkAreaActions(input({ candidateStatus: 'stale' })).reLift.enabled,
        true
    );
    assert.deepEqual(
        mapWorkAreaActions(
            input({
                candidateStatus: 'stale',
                correctionStatus: 'updating'
            })
        ).reLift,
        {
            visible: true,
            enabled: false,
            emphasis: 'normal',
            state: 'updating',
            reason: 'candidate-updating'
        }
    );
    assert.equal(
        mapWorkAreaActions(
            input({
                candidateStatus: 'stale',
                correctionStatus: 'failed'
            })
        ).reLift.enabled,
        true
    );
});

test('Re-Lift evaluates missing/stale readiness before Candidate publication', () => {
    assert.equal(
        mapWorkAreaActions(input({ liftReadiness: emptyReadiness })).reLift
            .enabled,
        true
    );
    assert.equal(
        mapWorkAreaActions(
            input({ liftReadiness: readiness('ready', 'stale') })
        ).reLift.enabled,
        true
    );
    assert.equal(
        mapWorkAreaActions(input({ liftReadiness: readiness('not-ready') }))
            .reLift.reason,
        'readiness-not-ready'
    );
    assert.deepEqual(
        mapWorkAreaActions(input({ liftReadiness: readiness('limited') }))
            .reLift,
        {
            visible: true,
            enabled: true,
            emphasis: 'warning',
            state: 'idle',
            reason: 'readiness-limited'
        }
    );
    assert.deepEqual(
        mapWorkAreaActions(input({ liftReadiness: readiness('ready') })).reLift,
        {
            visible: true,
            enabled: true,
            emphasis: 'normal',
            state: 'idle',
            reason: null
        }
    );
});

test('target, service and unconfirmed Included Mask gates always fail closed', () => {
    assert.equal(
        mapWorkAreaActions(input({ targetActive: false })).reLift.reason,
        'missing-target'
    );
    assert.equal(
        mapWorkAreaActions(input({ serviceAvailable: false })).reLift.reason,
        'service-unavailable'
    );
    assert.equal(
        mapWorkAreaActions(input({ hasUnconfirmedIncludedMask: true })).reLift
            .reason,
        'unconfirmed-included-mask'
    );
});

test('the palette confirmation slot has stable Mask, Review, Anchor priority', () => {
    assert.equal(
        mapWorkAreaActions(
            input({
                canConfirmMask: true,
                canConfirmReview: true,
                anchorNeedsConfirmation: true
            })
        ).palette.confirmation,
        'confirm-mask'
    );
    assert.equal(
        mapWorkAreaActions(
            input({
                canConfirmReview: true,
                anchorNeedsConfirmation: true
            })
        ).palette.confirmation,
        'confirm-review'
    );
    assert.equal(
        mapWorkAreaActions(
            input({
                anchorNeedsConfirmation: true
            })
        ).palette.confirmation,
        'confirm-anchor'
    );
});

test('the palette contextual slot enters Correction or returns to Candidate without touching drafts', () => {
    assert.equal(
        mapWorkAreaActions(input({ candidateStatus: 'current' })).palette
            .context,
        'enter-correction'
    );
    assert.equal(
        mapWorkAreaActions(
            input({
                candidateStatus: 'current',
                correctionMode: 'correcting'
            })
        ).palette.context,
        'back-to-candidate'
    );
    assert.equal(
        mapWorkAreaActions(input({ candidateStatus: 'stale' })).palette.context,
        'none'
    );
});
