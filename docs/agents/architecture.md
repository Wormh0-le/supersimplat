# Architecture and Change Routing

Read this file for runtime ownership, cross-runtime contracts, repository seams, or migration. [Domain authority](domain.md) determines current scope; old stage maps are historical.

## Runtime ownership

The Browser owns the editor's product state: Current Target Context, Views, published Mask versions, Participation, Candidate presentation/publication, user-authored CameraBindings, acquisition control, and Native Selection/EditHistory. It validates Companion-derived membership and readiness; it does not invent a Candidate independently of valid computation. Generated observations must not move the Editor Camera.

The operator-run Companion owns locked rendering, SAM inference, geometry hints, raw Evidence, and the computation actually adopted by the current slice. Derived caches are disposable and target/input-bound. The Companion does not autonomously advance a product session or become a persistent semantic-object database.

Use one numerical-update owner, one Scope/result commit-and-recompute coordinator, and one domain-to-UI projection at each relevant boundary. Keep a small independent reference oracle where it tests correctness; do not rebuild the same production update in multiple modules to satisfy old ticket headings.

## Existing seams

Browser AI Select code belongs under `src/ai-select/`; UI remains in its established surfaces. Reuse the serial controller/queue and explicit stale-result guards after checking their contracts. Native mutations stay in the existing selection/tool/EditHistory paths. Companion code and tests live under `selection-service-companion/`. Vendored sources under `thirdparty/` remain pinned.

The retained proposal wire envelope in `mask-service.ts` is a compatibility boundary, not permission to restore a multi-result product workflow. Discover actual callers and producers before defining a new interface or recording a path in an implementation issue.

## Cross-runtime changes

Follow the whole exercised boundary: TypeScript domain and wire types, runtime validation, transport, Python parsing, computation/artifact construction, identity migration, and tests on both sides. Reject incompatible input rather than making one side permissive. Do not create transport schemas for internal arrays that have no Browser consumer.

Prefer a small vertical slice with an actual input and inspectable output. Existing Scope/history machinery can be encapsulated; it need not be reimplemented by every consumer. Do not begin a wholesale rewrite merely to reduce line count.

## Migration and release

Keep development/reference/shadow identities separate from production. Preserve the existing path until the replacement is qualified. Coordinate product activation and rollback; internal capabilities must agree, but every helper does not need an independent product-level qualification framework.

Real source/runtime/ABI changes still require corresponding validation and identity rotation. Never reinterpret old artifacts under new policy or mix q/s computed for an old Scope with new roles. A Scope change invalidates dependent results and requires recomputation by the single coordinator.

Current request/state checks, bounded counters, and exportable diagnostics may implement lifecycle safety without a universal event-sourcing platform. Any stronger infrastructure promise must have a current requirement and evidence, not just a historical ticket.
