# Static editor → local Selection Service transport

Research date: 2026-07-13. This note covers a browser-hosted static SuperSplat editor whose
origin differs from the Python Companion by scheme, host, or port. It is evidence for the
Selection Service lifecycle decision, not a replacement for its editor-facing Interface.

## Conclusion for the PoC

The conservative transport shape is **Fetch over HTTP(S), with binary request/response bodies
where needed**, rather than treating a WebSocket as a way around browser-local-network controls.
The Companion must configure CORS for the actual editor origins and the client must handle a
local-network permission refusal as a normal unavailable-service result.

There are two materially different deployment profiles:

1. **Public HTTPS editor → same-machine Companion.** A Chromium-class browser treats a
   public-origin request to `127.0.0.1`/`::1` as local-network access: the editor must be a
   secure context and the user can be prompted for the loopback permission. Plain HTTP on a
   loopback literal is exempt from the standards mixed-content check, but that does not remove
   CORS or Local Network Access (LNA). It is a viable _explicitly tested browser-profile_ PoC
   shortcut, not a browser-neutral transport promise. [Secure Contexts](https://w3c.github.io/webappsec-secure-contexts/#is-origin-trustworthy), [Chrome LNA announcement](https://developer.chrome.com/blog/local-network-access)
2. **Trusted-LAN Companion.** Make the supported baseline `https://editor` →
   `https://configured-lan-host`. HTTPS avoids ordinary mixed-content blocking, but a public
   editor can still face the browser's LNA permission and must still satisfy CORS. A browser-trusted
   certificate is therefore a deployment prerequisite for the LAN profile. An HTTPS editor to an
   RFC1918 **HTTP** endpoint is a browser-specific LNA compatibility path, not the portable default.
   [Mixed Content](https://w3c.github.io/webappsec-mixed-content/#should-fetching-request-be-blocked-as-mixed-content), [Local Network Access draft](https://wicg.github.io/local-network-access/#mixed-content)

An ordinary public `http://` static editor is not a supported way to reach either endpoint:
LNA permits such requests only from a secure context. `http://127.0.0.1`, `http://[::1]`, and a
conformant `http://localhost` development origin are special potentially trustworthy cases, not
evidence that arbitrary HTTP deployment is safe to support. [Secure Contexts](https://w3c.github.io/webappsec-secure-contexts/#is-origin-trustworthy), [Local Network Access draft](https://wicg.github.io/local-network-access/#secure-context-restriction)

## Why an explicit browser profile is necessary

The old Chromium **Private Network Access** (PNA) experiment used target-server CORS preflights;
Chrome states that rollout was put on hold and replaced by permission-based **Local Network
Access**. Do not make `Access-Control-Allow-Private-Network` a required PoC header. Ordinary CORS
remains independent of LNA. [Chrome's LNA announcement](https://developer.chrome.com/blog/local-network-access)

Chrome says its LNA prompt launched in Chrome 142, and Chrome 145 split its permission into
`local-network` (LAN) and `loopback-network` (loopback). Firefox documents a progressive rollout
starting with Firefox 149/151, while WebKit's top-level LNA implementation issue remains open
(despite Safari 26.4 fixing a `targetAddressSpace: 'loopback'` fetch case). These facts do not
justify an untested all-browser guarantee. Record the exact browser/version in the PoC run record
and test permission grant, denial, and reconnect on the supported profile. [Chrome LNA](https://developer.chrome.com/blog/local-network-access), [Chrome 145 release notes](https://developer.chrome.com/release-notes/145#local-network-access-split-permissions), [Firefox LNA help](https://support.mozilla.org/en-US/kb/control-personal-device-local-network-permissions-firefox), [WebKit tracker](https://bugs.webkit.org/show_bug.cgi?id=250607), [Safari 26.4 notes](https://webkit.org/blog/17862/webkit-features-for-safari-26-4/)

The practical implication is:

- If this PoC names a current Chromium build as its reference browser, `https://editor` →
  `http://127.0.0.1:<port>` may be offered as a loopback-only compatibility profile after the
  explicit LNA prompt and CORS check.
- If the PoC needs a browser-neutral supported profile, require HTTPS for the Companion too.
- Do not depend on the current state of WebSocket gating. Chrome's original LNA launch note listed
  WebSockets as not yet gated, but the current LNA draft specifies that WebSocket handshakes should
  be subject to the same permission requirements. Establish health/capabilities over Fetch; any
  later streaming transport must preserve the same permission/error behavior. [Chrome LNA limitations](https://developer.chrome.com/blog/local-network-access#known-issues-and-limitations), [LNA WebSocket integration](https://wicg.github.io/local-network-access/#websockets)

## Browser gates by editor and endpoint

| Editor origin              | Companion endpoint                                | Required browser conditions                                                                                                          | Support posture                                                    |
| -------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| public `https://…`         | `http://127.0.0.1` / `http://[::1]`               | CORS; LNA loopback permission in supporting browsers. Loopback literals are potentially trustworthy for the mixed-content algorithm. | Explicitly tested Chromium compatibility profile only.             |
| public `https://…`         | `https://127.0.0.1` / trusted `https://localhost` | CORS; LNA loopback permission; certificate validation.                                                                               | Better transport integrity, but still needs permission handling.   |
| public `https://…`         | `http://192.168.x.x` or `http://host.local`       | CORS; LNA LAN permission; Chromium may relax mixed content for a private-IP literal or `.local` name after permission.               | Do not use as the portable trusted-LAN default.                    |
| public `https://…`         | trusted `https://lan-host`                        | CORS; LNA LAN permission in supporting browsers; certificate validation.                                                             | Supported trusted-LAN baseline.                                    |
| ordinary public `http://…` | either loopback or LAN                            | CORS cannot repair the missing secure-context prerequisite for LNA.                                                                  | Unsupported.                                                       |
| loopback development page  | a different loopback port                         | CORS if origins differ; current LNA draft excludes loopback-origin requests from LNA checks.                                         | Development-only; do not generalize this exception to public HTTP. |

LNA classifies `127.0.0.0/8` and `::1/128` as loopback, and RFC1918 ranges as local. A public
site reaching either is the first Chromium rollout scope; an LNA permission denial makes the fetch
fail. The draft says permission persistence and granularity are implementation-defined, so the
editor must not assume a grant survives a browser restart, profile change, or network change.
[LNA address spaces and scope](https://wicg.github.io/local-network-access/#ip-address-space), [LNA permission behavior](https://wicg.github.io/local-network-access/#local-network-request-permission-prompt)

For an HTTP LAN fallback, Chromium's `targetAddressSpace: 'local'` can declare that the requested
host is expected to resolve locally and can relax mixed-content handling only if the address-space
match succeeds. It is not a general mixed-content bypass and should be capability-tested, not
placed in the transport contract as a universal requirement. [LNA Fetch integration](https://wicg.github.io/local-network-access/#integration-with-fetch)

## CORS and origin policy required on the Companion

A different port is a different origin. The URL standard defines an origin using scheme, host, and
port, and Fetch CORS is the HTTP opt-in mechanism through which a server permits a cross-origin
response to be shared. [URL origin](https://url.spec.whatwg.org/#concept-url-origin), [Fetch CORS protocol](https://fetch.spec.whatwg.org/#cors-protocol)

For every browser-callable endpoint — including health and `getCapabilities()` — the Companion
should:

- accept an operator-configured, exact allowlist of editor origins rather than reflecting arbitrary
  `Origin` values or using `Access-Control-Allow-Origin: *`;
- return the matched `Access-Control-Allow-Origin` on the actual response and `Vary: Origin` when
  the value is dynamic;
- implement `OPTIONS` for the actual non-safelisted methods and headers used by binary
  snapshot/result calls, returning the corresponding `Access-Control-Allow-Methods` and
  `Access-Control-Allow-Headers`; and
- use `credentials: 'omit'` for this local service unless a later, separately designed credential
  scheme requires otherwise. With `credentials: 'include'`, `Access-Control-Allow-Origin: *` is
  invalid, and the server must explicitly allow credentials.

Fetch defines CORS preflight as an `OPTIONS` request, the response allow headers, the credential
rules, and the need for `Vary: Origin` when a server varies `Access-Control-Allow-Origin`.
[Fetch CORS protocol](https://fetch.spec.whatwg.org/#cors-protocol), [Fetch CORS caching guidance](https://fetch.spec.whatwg.org/#cors-protocol-and-http-caches)

**Important boundary:** CORS controls whether browser JavaScript may read a response; it is not
Companion authorization. The LNA design explicitly notes that CORS cannot stop a simple-request
CSRF attack when the attacker does not need to read the response. Therefore, binding only to
loopback in the default profile, restricting LAN exposure by operator configuration/firewall, and
validating the configured origin at the service are distinct layers; they cannot be replaced by a
single CORS wildcard. [LNA security rationale](https://wicg.github.io/local-network-access/#goals)

## Minimal browser verification before declaring a profile usable

1. Serve the actual editor origin (not a file URL) and configure the intended Companion endpoint.
2. Verify `getCapabilities()` triggers/uses the expected LNA permission path; record grant and
   denial behavior.
3. Verify CORS on success, error, and `OPTIONS`, including a binary Scene Snapshot request and
   a cancelled request.
4. Verify the Companion rejects an unlisted editor origin and that no result is accepted after a
   permission denial or endpoint switch.
5. Repeat using the declared browser/version and, for LAN, the real certificate and firewall
   configuration. Record the browser/version and endpoint scheme/host/port in the PoC Run Record.

This check is deliberately transport-only: it does not alter Scene Snapshot identity, prompt/mask
semantics, Gaussian lifting, or editor Selection Commit ownership.
