import {
  SelectionServiceTransportError,
  type SelectionServiceCapabilities,
  type SelectionServiceHealth,
  type SelectionServiceReadinessProbe,
  type SelectionServiceReadinessRequest,
  type SelectionServiceTransportProfile,
} from "./selection-service-readiness";

type LocalNetworkPermissionState = "granted" | "prompt" | "denied" | "unknown";

interface SelectionServiceLocalNetworkPermissions {
  query(
    profile: SelectionServiceTransportProfile
  ): Promise<LocalNetworkPermissionState>;
}

interface FetchResponse {
  readonly ok: boolean;
  readonly status: number;
  json(): Promise<unknown>;
}

interface SelectionServiceFetchInit {
  method: "GET";
  headers: Record<string, string>;
  mode: "cors";
  credentials: "omit";
  cache: "no-store";
}

type SelectionServiceFetch = (
  url: string,
  init: SelectionServiceFetchInit
) => Promise<FetchResponse>;

interface FetchSelectionServiceReadinessProbeOptions {
  fetch?: SelectionServiceFetch;
  localNetworkPermissions?: SelectionServiceLocalNetworkPermissions;
  isSecureContext?: () => boolean | undefined;
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const isLoopbackOrigin = (origin: string) => {
  try {
    const host = new URL(origin).hostname.toLowerCase().replace(/^\[|\]$/g, "");
    return host === "127.0.0.1" || host === "::1" || host === "localhost";
  } catch (error) {
    return false;
  }
};

const browserLocalNetworkPermissions: SelectionServiceLocalNetworkPermissions =
  {
    async query(profile) {
      const permissions = globalThis.navigator?.permissions as
        | {
            query?: (descriptor: {
              name: string;
            }) => Promise<{ state: LocalNetworkPermissionState }>;
          }
        | undefined;
      if (!permissions?.query) {
        return "unknown";
      }

      try {
        const permission = await permissions.query({
          name: profile === "loopback" ? "loopback-network" : "local-network",
        });
        return permission.state;
      } catch (error) {
        // Browsers that do not expose Chromium's permission names still
        // enforce their own network policy at Fetch time. Do not bypass it.
        return "unknown";
      }
    },
  };

const browserFetch: SelectionServiceFetch = (url, init) => {
  if (typeof globalThis.fetch !== "function") {
    throw new SelectionServiceTransportError(
      "browserTransport",
      "Fetch is unavailable in this editor context."
    );
  }
  return globalThis.fetch(url, init);
};

const browserSecureContext = () => {
  return typeof globalThis.isSecureContext === "boolean"
    ? globalThis.isSecureContext
    : undefined;
};

// The Companion process owns its routes. This browser probe only implements
// the two lifecycle control-plane requests; later scene and session requests
// remain behind the same Adapter seam.
class FetchSelectionServiceReadinessProbe implements SelectionServiceReadinessProbe {
  private fetch: SelectionServiceFetch;
  private localNetworkPermissions: SelectionServiceLocalNetworkPermissions;
  private isSecureContext: () => boolean | undefined;

  constructor(options: FetchSelectionServiceReadinessProbeOptions = {}) {
    this.fetch = options.fetch ?? browserFetch;
    this.localNetworkPermissions =
      options.localNetworkPermissions ?? browserLocalNetworkPermissions;
    this.isSecureContext = options.isSecureContext ?? browserSecureContext;
  }

  async checkHealth(
    request: SelectionServiceReadinessRequest
  ): Promise<SelectionServiceHealth> {
    const response = await this.getJson("/health", request);
    return response as unknown as SelectionServiceHealth;
  }

  async getCapabilities(
    request: SelectionServiceReadinessRequest
  ): Promise<SelectionServiceCapabilities> {
    const response = await this.getJson("/capabilities", request);
    return response as unknown as SelectionServiceCapabilities;
  }

  private async getJson(
    path: string,
    request: SelectionServiceReadinessRequest
  ) {
    await this.requireBrowserTransport(request);

    let response: FetchResponse;
    try {
      response = await this.fetch(new URL(path, request.endpoint).toString(), {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        mode: "cors",
        credentials: "omit",
        cache: "no-store",
      });
    } catch (error) {
      if (error instanceof SelectionServiceTransportError) {
        throw error;
      }
      throw new SelectionServiceTransportError(
        "browserTransport",
        "The browser blocked or could not reach the Selection Service Companion."
      );
    }

    if (!response.ok) {
      throw new SelectionServiceTransportError(
        "http",
        `The Selection Service Companion returned HTTP ${response.status}.`
      );
    }

    try {
      const body = await response.json();
      if (!isRecord(body)) {
        throw new SelectionServiceTransportError(
          "invalidResponse",
          "The Selection Service Companion returned a non-object JSON response."
        );
      }
      return body;
    } catch (error) {
      if (error instanceof SelectionServiceTransportError) {
        throw error;
      }
      throw new SelectionServiceTransportError(
        "invalidResponse",
        "The Selection Service Companion returned invalid JSON."
      );
    }
  }

  private async requireBrowserTransport(
    request: SelectionServiceReadinessRequest
  ) {
    if (
      this.isSecureContext() === false &&
      !isLoopbackOrigin(request.editorOrigin)
    ) {
      throw new SelectionServiceTransportError(
        "insecureEditorContext",
        "A public HTTP editor cannot request a local Selection Service Companion."
      );
    }

    const permission = await this.localNetworkPermissions.query(
      request.profile
    );
    if (permission === "denied") {
      throw new SelectionServiceTransportError(
        "localNetworkPermissionDenied",
        "Chromium denied Local Network Access for the Selection Service Companion."
      );
    }
  }
}

export { FetchSelectionServiceReadinessProbe, SelectionServiceTransportError };

export type {
  FetchSelectionServiceReadinessProbeOptions,
  LocalNetworkPermissionState,
  SelectionServiceFetch,
  SelectionServiceLocalNetworkPermissions,
};
