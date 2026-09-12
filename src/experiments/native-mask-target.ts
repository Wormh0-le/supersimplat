// Deliberately only the two targets of the frozen cross-object experiment.
export type TaskId = 'easy-apple' | 'medium-plate';
export type MaskInput = Readonly<{ role: 'A' | 'B' | 'C'; task: TaskId; path: string; sha256: string; provenance: string }>;

export const taskId = (value: unknown): TaskId => {
    if (value !== 'easy-apple' && value !== 'medium-plate') throw new Error('Only easy-apple and medium-plate are supported');
    return value;
};

export const maskInputs = (value: unknown): readonly MaskInput[] => {
    if (!value || typeof value !== 'object' || !('masks' in value) || !Array.isArray(value.masks)) throw new Error('Invalid bundle Mask manifest');
    const inputs: MaskInput[] = [];
    for (const task of ['easy-apple', 'medium-plate'] as const) {
        for (const role of ['A', 'B', 'C'] as const) {
            const matches = value.masks.filter(row => row && row.task === task && row.role === role);
            if (matches.length !== 1) throw new Error(`Expected exactly one ${role}/${task} Mask`);
            const row = matches[0];
            if (typeof row.path !== 'string' || !/^[\w.-]+\.png$/.test(row.path) ||
                typeof row.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(row.sha256) ||
                typeof row.provenance !== 'string') throw new Error('Invalid Mask path/hash/provenance');
            inputs.push(Object.freeze({ role, task, path: row.path, sha256: row.sha256, provenance: row.provenance }));
        }
    }
    return Object.freeze(inputs);
};
