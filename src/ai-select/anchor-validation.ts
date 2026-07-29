import { analyzeMaskArtifact, type MaskBitmapAnalysis } from './mask-analysis';
import type { MaskAnnotation } from './mask-annotation';
import type { AnchorSupportProbeSupport } from './support-probe';

/**
 * The versioned Anchor Validation policy (Final Spec v1.1 §12). Validation
 * evaluates computational suitability — never semantic target confidence —
 * so its thresholds describe computability, not quality scores.
 */
export const aiSelectAnchorValidationPolicyVersion = 'anchor-validation/v1';

/** Below this foreground area the Mask is not computably meaningful. */
export const anchorValidationMinForegroundPixels = 16;
/** Coverage below this ratio warns about a very small target. */
export const anchorValidationSmallCoverageRatio = 0.005;
/** Coverage above this ratio warns about a very large target. */
export const anchorValidationLargeCoverageRatio = 0.9;
/** More 4-connected components than this warns about fragmentation. */
export const anchorValidationMaxComponents = 8;
/** Fewer observed Gaussians than this warns about weak visible support. */
export const anchorValidationWeakSupportGaussians = 25;

export type AnchorHardBlock =
    | 'authoritative-rgb-unavailable'
    | 'camera-binding-stale'
    | 'stable-mask-missing'
    | 'mask-empty'
    | 'mask-below-minimum-area'
    | 'camera-rgb-mask-mismatch'
    | 'mask-revision-pending'
    | 'proposal-decision-unresolved'
    | 'stable-id-mapping-unavailable'
    | 'render-working-set-unavailable'
    | 'gaussian-support-unproven'
    | 'no-computable-gaussian-support';

export type AnchorSoftWarning =
    | 'image-boundary-contact'
    | 'target-very-small'
    | 'target-very-large'
    | 'fragmented-mask'
    | 'weak-visible-support';

export interface AnchorValidationInput {
    /** The final authoritative RGB for the current CameraBinding is ready. */
    readonly rgbReady: boolean;
    readonly rgbDigest: string | null;
    readonly rgbWidth: number;
    readonly rgbHeight: number;
    /** The Anchor CameraBinding still matches the live editor dependency. */
    readonly cameraBindingCurrent: boolean;
    readonly stableMask: MaskAnnotation | null;
    /** The latest Mask/SAM revision is still computing. */
    readonly maskRevisionPending: boolean;
    /** Any ambiguous pre-Stable proposal was accepted or manually replaced. */
    readonly proposalDecisionResolved: boolean;
    readonly stableIdMappingValid: boolean;
    readonly renderWorkingSetValid: boolean;
    /**
     * The current support-probe verdict for this exact Camera/RGB/Mask
     * identity, or null when no current probe has completed.
     */
    readonly support: AnchorSupportProbeSupport | null;
}

export interface AnchorValidationResult {
    readonly policyVersion: typeof aiSelectAnchorValidationPolicyVersion;
    readonly hardBlocks: readonly AnchorHardBlock[];
    readonly softWarnings: readonly AnchorSoftWarning[];
    readonly canConfirm: boolean;
    readonly maskAnalysis?: MaskBitmapAnalysis;
}

const mismatch = (input: AnchorValidationInput): boolean => {
    const mask = input.stableMask;
    if (mask === null || input.rgbDigest === null) {
        return false;
    }
    return (
        mask.createdFromRgbDigest !== input.rgbDigest ||
        mask.artifact.width !== input.rgbWidth ||
        mask.artifact.height !== input.rgbHeight
    );
};

/**
 * Evaluate Anchor computational suitability. Hard blocks fail closed: an
 * unproven dependency (RGB, CameraBinding, Stable ID mapping, Render Working
 * Set, Gaussian support) blocks Confirm rather than assuming computability.
 * Soft warnings are informational and stay user-overridable.
 */
export const evaluateAnchorValidation = (
    input: AnchorValidationInput
): AnchorValidationResult => {
    const hardBlocks: AnchorHardBlock[] = [];
    const softWarnings: AnchorSoftWarning[] = [];
    if (!input.rgbReady) {
        hardBlocks.push('authoritative-rgb-unavailable');
    }
    if (!input.cameraBindingCurrent) {
        hardBlocks.push('camera-binding-stale');
    }
    if (input.stableMask === null) {
        hardBlocks.push('stable-mask-missing');
    } else if (mismatch(input)) {
        hardBlocks.push('camera-rgb-mask-mismatch');
    }
    if (input.maskRevisionPending) {
        hardBlocks.push('mask-revision-pending');
    }
    if (!input.proposalDecisionResolved) {
        hardBlocks.push('proposal-decision-unresolved');
    }
    if (!input.stableIdMappingValid) {
        hardBlocks.push('stable-id-mapping-unavailable');
    }
    if (!input.renderWorkingSetValid) {
        hardBlocks.push('render-working-set-unavailable');
    }

    let maskAnalysis: MaskBitmapAnalysis | undefined;
    if (input.stableMask !== null && !mismatch(input)) {
        maskAnalysis = analyzeMaskArtifact(input.stableMask.artifact);
        if (maskAnalysis.foregroundPixels === 0) {
            hardBlocks.push('mask-empty');
        } else if (
            maskAnalysis.foregroundPixels < anchorValidationMinForegroundPixels
        ) {
            hardBlocks.push('mask-below-minimum-area');
        }
        if (maskAnalysis.touchesImageBoundary) {
            softWarnings.push('image-boundary-contact');
        }
        if (
            maskAnalysis.coverageRatio > 0 &&
            maskAnalysis.coverageRatio < anchorValidationSmallCoverageRatio
        ) {
            softWarnings.push('target-very-small');
        }
        if (maskAnalysis.coverageRatio > anchorValidationLargeCoverageRatio) {
            softWarnings.push('target-very-large');
        }
        if (maskAnalysis.connectedComponents > anchorValidationMaxComponents) {
            softWarnings.push('fragmented-mask');
        }
    }

    if (input.support === null) {
        hardBlocks.push('gaussian-support-unproven');
    } else if (!input.support.computable) {
        hardBlocks.push('no-computable-gaussian-support');
    } else if (
        input.support.observedGaussianCount <
        anchorValidationWeakSupportGaussians
    ) {
        softWarnings.push('weak-visible-support');
    }

    return Object.freeze({
        policyVersion: aiSelectAnchorValidationPolicyVersion,
        hardBlocks: Object.freeze(hardBlocks),
        softWarnings: Object.freeze(softWarnings),
        canConfirm: hardBlocks.length === 0,
        ...(maskAnalysis === undefined ? {} : { maskAnalysis })
    });
};
