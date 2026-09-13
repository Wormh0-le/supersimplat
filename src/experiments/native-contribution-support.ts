/**
 * Additional logical support budget, independent of evaluator/snapshot caps.
 * Export reserve covers one numeric support/position page and finite-number JSON
 * staging, not measured JS/GC, process or GPU peaks. Consumers must drain pages,
 * not retain all exports. No per-ID objects or indexes are retained here.
 */
export const SUPPORT_STORAGE_LIMITS = Object.freeze({ bytes: 256 * 1024 * 1024, exportBytes: 4 * 1024 * 1024, pageRows: 4096 });
export type SupportStorageOptions = {
    byteLimit?: number;
    /** ALL live A/B/AB columns, including the old result during atomic replacement. */
    retainedBytes?: number;
    signal?: AbortSignal;
    isCurrent?: () => boolean;
};
export type SupportRow = Readonly<{ id: number; sourceRow: number; positive: number; negative: number; visible: number; target: number }>;
export type SupportTable = Readonly<{
    length: number;
    byteLength: number;
    row: (index: number) => SupportRow;
    idAt: (index: number) => number;
    /** Clamps count at the end; offset may equal length. Returned values are copies. */
    page: (offset?: number, count?: number) => readonly SupportRow[];
}>;
type SupportStats = {
    touched: Uint8Array;
    sourceRows: Uint32Array;
    positive: Float64Array;
    negative: Float64Array;
    visible: Float64Array;
    target: Float64Array;
};
type Columns = Omit<SupportStats, 'touched'> & { ids: Uint32Array };
const ROW_BYTES = 40;
const UINT32_MAX = 0xffffffff;

const integer = (value: number, label: string) => {
    if (!Number.isSafeInteger(value) || value < 0) throw new Error(`Invalid support ${label}`);
};
const sum = (value: number) => {
    if (!Number.isFinite(value) || value < 0) throw new Error('Invalid support sum');
};
const guard = (options: SupportStorageOptions) => {
    if (options.signal?.aborted || (options.isCurrent && !options.isCurrent())) {
        throw new Error('Incomplete support: cancelled or stale');
    }
};

export function checkSupportBudget(additionalBytes: number, options: SupportStorageOptions = {}) {
    guard(options);
    const retainedBytes = options.retainedBytes === undefined ? 0 : options.retainedBytes;
    const byteLimit = options.byteLimit === undefined ? SUPPORT_STORAGE_LIMITS.bytes : options.byteLimit;
    const exportReserveBytes = SUPPORT_STORAGE_LIMITS.exportBytes;
    integer(additionalBytes, 'additional bytes');
    integer(retainedBytes, 'retained bytes');
    integer(byteLimit, 'byte limit');
    if (byteLimit > SUPPORT_STORAGE_LIMITS.bytes) throw new Error('Support byte limit exceeds hard ceiling');
    const peakBytes = retainedBytes + additionalBytes + exportReserveBytes;
    integer(peakBytes, 'peak bytes');
    if (peakBytes > byteLimit) throw new Error('Incomplete support: byte budget exceeded');
    return { retainedBytes, additionalBytes, exportReserveBytes, peakBytes, byteLimit };
}

const allocate = (length: number, options: SupportStorageOptions): Columns => {
    integer(length, 'length');
    checkSupportBudget(ROW_BYTES * length, options);
    return {
        ids: new Uint32Array(length),
        sourceRows: new Uint32Array(length),
        positive: new Float64Array(length),
        negative: new Float64Array(length),
        visible: new Float64Array(length),
        target: new Float64Array(length)
    };
};

// Only this closure owns the arrays. Neither the wrapper nor an export exposes buffers.
const tableFrom = (columns: Columns): SupportTable => {
    const { ids, sourceRows, positive, negative, visible, target } = columns;
    const length = ids.length;
    const indexCheck = (index: number) => {
        integer(index, 'index');
        if (index >= length) throw new Error('Support index out of range');
    };
    const row = (index: number): SupportRow => {
        indexCheck(index);
        return Object.freeze({ id: ids[index], sourceRow: sourceRows[index], positive: positive[index], negative: negative[index], visible: visible[index], target: target[index] });
    };
    return Object.freeze({
        length,
        byteLength: ROW_BYTES * length,
        row,
        idAt: (index: number) => {
            indexCheck(index);
            return ids[index];
        },
        page: (offset = 0, count = SUPPORT_STORAGE_LIMITS.pageRows): readonly SupportRow[] => {
            integer(offset, 'page offset');
            integer(count, 'page count');
            if (offset > length || count > SUPPORT_STORAGE_LIMITS.pageRows) throw new Error('Support page out of range');
            const rows: SupportRow[] = [];
            const end = offset + Math.min(count, length - offset);
            for (let index = offset; index < end; index++) rows.push(row(index));
            return Object.freeze(rows);
        }
    });
};

export function compactSupport(stats: SupportStats, options: SupportStorageOptions = {}): SupportTable {
    checkSupportBudget(0, options);
    const { touched, sourceRows, positive, negative, visible, target } = stats;
    if (!(touched instanceof Uint8Array) || !(sourceRows instanceof Uint32Array) ||
        !(positive instanceof Float64Array) || !(negative instanceof Float64Array) ||
        !(visible instanceof Float64Array) || !(target instanceof Float64Array)) throw new Error('Invalid support column type');
    const length = touched.length;
    integer(length, 'input length');
    if (length > UINT32_MAX + 1 || [sourceRows, positive, negative, visible, target].some(column => column.length !== length)) {
        throw new Error('Invalid support column dimensions');
    }
    let count = 0;
    for (let id = 0; id < length; id++) {
        if (id % SUPPORT_STORAGE_LIMITS.pageRows === 0) guard(options);
        sum(positive[id]); sum(negative[id]); sum(visible[id]); sum(target[id]);
        if (touched[id]) count++;
    }
    const columns = allocate(count, options);
    let index = 0;
    for (let id = 0; id < length; id++) {
        if (id % SUPPORT_STORAGE_LIMITS.pageRows === 0) guard(options);
        if (!touched[id]) continue;
        if (index >= count) throw new Error('Support input changed during compaction');
        sum(positive[id]); sum(negative[id]); sum(visible[id]); sum(target[id]);
        columns.ids[index] = id;
        columns.sourceRows[index] = sourceRows[id];
        columns.positive[index] = positive[id]; columns.negative[index] = negative[id];
        columns.visible[index] = visible[id]; columns.target[index] = target[id];
        index++;
    }
    if (index !== count) throw new Error('Support input changed during compaction');
    guard(options);
    return tableFrom(columns);
}

const validateRow = (row: SupportRow, previousId: number) => {
    integer(row.id, 'ID'); integer(row.sourceRow, 'source row');
    if (row.id > UINT32_MAX || row.sourceRow > UINT32_MAX || row.id <= previousId) throw new Error('Invalid support identity/order');
    sum(row.positive); sum(row.negative); sum(row.visible); sum(row.target);
};

/**
 * Two passes over ascending unique INSTANCE IDs. A then B float64 addition;
 * classification remains solely in the unchanged reference classifySupport.
 * Inputs must remain immutable; cancellation checks are synchronous, not yields.
 */
export function mergeSupport(a: SupportTable, b: SupportTable, options: SupportStorageOptions = {}): SupportTable {
    checkSupportBudget(0, options);
    if (a === b) throw new Error('Cannot merge the same support table twice');
    for (const table of [a, b]) {
        integer(table.length, 'table length'); integer(table.byteLength, 'table bytes');
        if (table.length > UINT32_MAX + 1 || table.byteLength !== ROW_BYTES * table.length) throw new Error('Invalid support table dimensions');
    }
    // At most two input rows and one summed row are transient, with no scene-sized scratch.
    const walk = (columns?: Columns) => {
        let ai = 0, bi = 0, count = 0;
        const next = (table: SupportTable, index: number, previousId: number) => {
            if (index === table.length) return undefined;
            const row = table.row(index);
            validateRow(row, previousId);
            if (table.idAt(index) !== row.id) throw new Error('Invalid support ID lookup');
            return row;
        };
        let ar = next(a, ai, -1), br = next(b, bi, -1);
        while (ar || br) {
            if (count % SUPPORT_STORAGE_LIMITS.pageRows === 0) guard(options);
            let row: SupportRow;
            if (ar && br && ar.id === br.id) {
                if (ar.sourceRow !== br.sourceRow) throw new Error('Support source row mismatch');
                row = {
                    id: ar.id,
                    sourceRow: ar.sourceRow,
                    positive: ar.positive + br.positive,
                    negative: ar.negative + br.negative,
                    visible: ar.visible + br.visible,
                    target: ar.target + br.target
                };
                sum(row.positive); sum(row.negative); sum(row.visible); sum(row.target);
                ar = next(a, ++ai, ar.id); br = next(b, ++bi, br.id);
            } else if (ar && (!br || ar.id < br.id)) {
                row = ar;
                ar = next(a, ++ai, ar.id);
            } else if (br) {
                row = br;
                br = next(b, ++bi, row.id);
            } else {
                throw new Error('Invalid support stream');
            }
            if (columns) {
                if (count >= columns.ids.length) throw new Error('Support input changed during merge');
                columns.ids[count] = row.id; columns.sourceRows[count] = row.sourceRow;
                columns.positive[count] = row.positive; columns.negative[count] = row.negative;
                columns.visible[count] = row.visible; columns.target[count] = row.target;
            }
            count++;
        }
        guard(options);
        return count;
    };
    const count = walk();
    const columns = allocate(count, options);
    if (walk(columns) !== count) throw new Error('Support input changed during merge');
    return tableFrom(columns);
}
