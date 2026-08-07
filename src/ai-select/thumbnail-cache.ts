/**
 * Bounded LRU for Gallery card thumbnails, keyed by authoritative RGB digest.
 * Full-resolution PNG data URLs are the Gallery's dominant memory cost at
 * 10–20+ Views; cards keep only downscaled thumbnails, and eviction is
 * explicit so the Gallery stays resource-bounded (Ticket 09).
 */
export interface ThumbnailCache {
    get(digest: string): string | undefined;
    set(digest: string, dataUrl: string): void;
    readonly size: number;
}

export const createThumbnailCache = (options: {
    readonly capacity: number;
}): ThumbnailCache => {
    const { capacity } = options;
    if (!Number.isSafeInteger(capacity) || capacity < 1) {
        throw new Error('Thumbnail cache capacity must be a positive integer.');
    }
    // Map iteration order is insertion order; reinsertion refreshes recency.
    const entries = new Map<string, string>();
    return {
        get(digest: string): string | undefined {
            const value = entries.get(digest);
            if (value === undefined) {
                return undefined;
            }
            entries.delete(digest);
            entries.set(digest, value);
            return value;
        },
        set(digest: string, dataUrl: string): void {
            entries.delete(digest);
            entries.set(digest, dataUrl);
            while (entries.size > capacity) {
                const oldest = entries.keys().next();
                if (oldest.done === true) {
                    break;
                }
                entries.delete(oldest.value);
            }
        },
        get size(): number {
            return entries.size;
        }
    };
};
