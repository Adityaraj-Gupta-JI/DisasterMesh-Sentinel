# Domain Glossary

Names must be identical across Kotlin, Python, and TypeScript. Expanded in Prompt 02.

| Term | Meaning |
|---|---|
| **Incident** | One reported emergency event, with original input preserved verbatim |
| **Bundle** | A signed, encrypted, self-describing unit of transfer (DMBP) |
| **DMBP** | DisasterMesh Bundle Protocol — transport-independent bundle format |
| **SyncObject** | A bundle queued for transfer, with scheduling state |
| **Node** | One device with an identity, a role, and a keypair |
| **Relay** | A node that stores and forwards bundles it cannot necessarily read |
| **Coordinator** | An authorized node that triages, acknowledges, and dispatches |
| **Gateway** | A node with backend connectivity that reconciles the mesh with the server |
| **Priority class** | P0 critical · P1 urgent · P2 operational · P3 routine |
| **Priority score** | Deterministic 0–100 value from the policy engine |
| **Policy version** | Identifier of the rule set that produced a decision |
| **Provenance** | Origin, path, timestamps, and hashes of a piece of data |
| **Acknowledgement** | An authorized human confirming an incident was seen |
| **Dispatch order** | A *simulated* resource assignment; never a real dispatch |
| **Cluster** | A set of incidents believed to describe the same event |
| **Access policy** | Rules deciding which roles may read which parts of an incident |
| **Hop count / limit** | Relays traversed / maximum permitted before a bundle stops |
| **TTL / expiry** | Wall-clock time after which a bundle must not be forwarded |
