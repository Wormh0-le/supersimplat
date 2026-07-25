import { decodeMaskArtifact, type MaskArtifact } from './mask-annotation';

export { maskBitsetByteLength } from './mask-annotation';

/**
 * The 2D measurements Anchor Validation (Final Spec v1.1 §12) derives from a
 * Stable Mask: area, image-boundary contact, and 4-connected fragmentation.
 * They describe computational suitability only — never semantic confidence.
 */
export interface MaskBitmapAnalysis {
    readonly foregroundPixels: number;
    readonly totalPixels: number;
    readonly coverageRatio: number;
    readonly touchesImageBoundary: boolean;
    readonly connectedComponents: number;
    readonly largestComponentPixels: number;
}

/**
 * Decode and measure one Mask artifact. The artifact is digest-verified on
 * decode, so a corrupt payload fails here instead of reaching validation.
 */
export const analyzeMaskArtifact = (
    artifact: MaskArtifact
): MaskBitmapAnalysis => {
    const bits = decodeMaskArtifact(artifact);
    const { width, height } = artifact;
    const totalPixels = width * height;
    const foreground = (x: number, y: number): boolean => {
        const index = y * width + x;
        return (bits[index >> 3] & (1 << (index % 8))) !== 0;
    };

    let foregroundPixels = 0;
    let touchesImageBoundary = false;
    // 4-connected components via union-find with path compression and union
    // by size: near-linear even for large fragmented masks.
    const parent = new Int32Array(totalPixels).fill(-1);
    const size = new Int32Array(totalPixels);
    const find = (start: number): number => {
        let root = start;
        while (parent[root] !== root) {
            root = parent[root];
        }
        let node = start;
        while (parent[node] !== node) {
            const next = parent[node];
            parent[node] = root;
            node = next;
        }
        return root;
    };
    const union = (left: number, right: number): void => {
        const leftRoot = find(left);
        const rightRoot = find(right);
        if (leftRoot === rightRoot) {
            return;
        }
        const [keep, drop] =
            size[leftRoot] >= size[rightRoot]
                ? [leftRoot, rightRoot]
                : [rightRoot, leftRoot];
        parent[drop] = keep;
        size[keep] += size[drop];
    };
    for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
            const index = y * width + x;
            if (!foreground(x, y)) {
                continue;
            }
            foregroundPixels += 1;
            if (x === 0 || y === 0 || x === width - 1 || y === height - 1) {
                touchesImageBoundary = true;
            }
            parent[index] = index;
            size[index] = 1;
            if (x > 0 && parent[index - 1] !== -1) {
                union(index, index - 1);
            }
            if (y > 0 && parent[index - width] !== -1) {
                union(index, index - width);
            }
        }
    }
    let connectedComponents = 0;
    let largestComponentPixels = 0;
    for (let index = 0; index < totalPixels; index += 1) {
        if (parent[index] === index) {
            connectedComponents += 1;
            largestComponentPixels = Math.max(
                largestComponentPixels,
                size[index]
            );
        }
    }
    return Object.freeze({
        foregroundPixels,
        totalPixels,
        coverageRatio: totalPixels === 0 ? 0 : foregroundPixels / totalPixels,
        touchesImageBoundary,
        connectedComponents,
        largestComponentPixels
    });
};
