import type { SelectionServiceCapabilities } from "../selection-service-readiness";

type SelectionServiceModelOption = {
  readonly v: string;
  readonly t: string;
};

const selectionServiceModelOptions = (
  capabilities: SelectionServiceCapabilities | null
): SelectionServiceModelOption[] => {
  if (capabilities === null) {
    return [{ v: "", t: "Check Companion to list models" }];
  }

  return [
    ...capabilities.modelManifests.map((manifest) => ({
      v: manifest.digest,
      t: `${manifest.modelName} (${manifest.digest})`,
    })),
    { v: "", t: "Select an installed model" },
  ];
};

export { selectionServiceModelOptions };

export type { SelectionServiceModelOption };
