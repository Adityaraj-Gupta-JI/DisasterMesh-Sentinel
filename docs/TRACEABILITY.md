# Requirement Traceability

Every MVP requirement, where it lives, and the test that proves it. A requirement with
no test has an explicitly accepted limitation instead — there are no silent gaps.

Legend: **VERIFIED** (automated test passes) · **MANUAL** (documented manual run) ·
**ACCEPTED** (limitation recorded in KNOWN_LIMITATIONS.md)

## Critical requirements

| ID | Requirement | Implementation | Test | Status |
|---|---|---|---|---|
| R1 | Offline operation with no Internet | `dms/node.py`, `dms/transport/mock.py` | `test_10_the_whole_flow_ran_with_no_internet` | VERIFIED |
| R2 | P0 text is never blocked by media | `dms/sync/scheduler.py` sort key | `test_p0_text_beats_p0_image`, `test_text_arrives_before_the_image`, `test_property_p0_text_is_always_schedulable_under_media_load` | VERIFIED |
| R3 | Resumable, verified file transfer | `dms/files/transfer.py` | `test_interrupted_transfer_resumes_from_missing_chunks`, `test_hash_mismatch_never_commits` | VERIFIED |
| R4 | Duplicate handling is idempotent | store dedup + `Bundle` id | `test_duplicate_transfer_is_idempotent`, `test_repeated_acknowledgement_is_absorbed` | VERIFIED |
| R5 | Incident data is encrypted | `dms/crypto/sealing.py` | `test_3_incident_is_encrypted_and_stored_locally`, `test_ciphertext_does_not_contain_plaintext` | VERIFIED |
| R6 | Dispatch requires human confirmation | `dms/dispatch/service.py`, gateway `confirm=true` | `test_dispatch_requires_an_authorized_role`, `test_dispatch_without_confirmation_is_refused` | VERIFIED |
| R7 | AI failure falls back to rules | `MeshNode.analyze`, `PriorityInputs.ai_available` | `test_incident_reporting_works_with_ai_unavailable`, simulator scenario 9 | VERIFIED |
| R8 | Multilingual input (EN/HI/TA) | `dms/ai/lexicon.py`, `dms/ai/rules.py` | `test_multilingual_triage_reaches_the_same_verdict`, `test_exact_people_counts_are_extracted` | VERIFIED |
| R9 | Role-based governance | `dms/governance/authz.py` | 14 tests in `test_governance.py` | VERIFIED |
| R10 | Auditability | `dms/governance/audit.py` | `test_tampering_with_an_entry_is_detected`, `test_audit_chain_records_the_workflow` | VERIFIED |

## MVP acceptance criteria

| ID | Criterion | Test | Status |
|---|---|---|---|
| M1 | Reporter creates a text incident | `test_1_reporter_creates_a_text_incident` | VERIFIED |
| M2 | Incident receives a priority | `test_2_incident_receives_a_priority` | VERIFIED |
| M3 | Encrypted and stored locally | `test_3_incident_is_encrypted_and_stored_locally` | VERIFIED |
| M4 | A nearby relay receives it | `test_4_and_5_relay_receives_and_forwards_to_coordinator` | VERIFIED |
| M5 | Relay forwards to coordinator | same | VERIFIED |
| M6 | Coordinator sees the incident | `test_6_coordinator_sees_the_incident_with_original_text` | VERIFIED |
| M7 | An image can follow the text | `test_7_image_follows_the_text_and_is_verified` | VERIFIED |
| M8 | Coordinator acknowledges | `test_8_coordinator_acknowledges` | VERIFIED |
| M9 | Simulated dispatch can be created | `test_9_simulated_dispatch_can_be_created` | VERIFIED |
| M10 | Usable without Internet | `test_10_the_whole_flow_ran_with_no_internet` | VERIFIED |

## Protocol invariants

| ID | Invariant | Test | Status |
|---|---|---|---|
| P1 | Bundle ids immutable | `test_bundle_id_and_payload_hash_are_immutable` | VERIFIED |
| P2 | Payload hashes immutable | same | VERIFIED |
| P3 | Hop count never decreases | `test_property_hop_count_never_decreases` | VERIFIED |
| P4 | Expired bundles never forwarded | `test_expired_bundle_is_never_forwarded` | VERIFIED |
| P5 | No double acceptance | `test_duplicate_bundle_insertion_is_safe` | VERIFIED |
| P6 | Corrupted payload rejected | `test_corrupted_payload_is_rejected` | VERIFIED |
| P7 | Unknown version fails safely | `test_unknown_protocol_version_fails_closed` | VERIFIED |
| P8 | Text independent of attachments | `test_critical_text_is_independent_of_attachments` | VERIFIED |

## Sync engine guarantees

| ID | Guarantee | Test | Status |
|---|---|---|---|
| S1 | P0 text never blocked by media | `test_p0_text_beats_p0_image` | VERIFIED |
| S2 | Expired objects not scheduled | `test_expired_objects_are_never_scheduled` | VERIFIED |
| S3 | Restricted objects not offered to unauthorized roles | `test_restricted_object_is_not_offered_to_unauthorized_role` | VERIFIED |
| S4 | Completed object not retransmitted as new | `test_completed_object_is_not_retransmitted_as_new` | VERIFIED |
| S5 | Interrupted transfers resume | `test_interrupted_transfer_resumes_from_missing_chunks`, simulator 8 | VERIFIED |
| S6 | Low battery sheds non-critical first | `test_low_battery_defers_non_critical_traffic` | VERIFIED |
| S7 | Decisions observable and explainable | `test_every_decision_is_observable_and_explained` | VERIFIED |

## Safety properties

| ID | Property | Test | Status |
|---|---|---|---|
| A1 | AI uncertainty cannot downgrade a rule-triggered life threat | `test_ai_uncertainty_cannot_downgrade_a_rule_triggered_life_threat` | VERIFIED |
| A2 | Vague quantities never become numbers | `test_vague_quantities_never_become_numbers` | VERIFIED |
| A3 | Summaries never invent counts | `test_summary_never_invents_a_count_for_an_all_unknown_cluster` | VERIFIED |
| A4 | Summaries never dispatch | `test_summary_never_dispatches` | VERIFIED |
| A5 | Creating a dispatch order does not dispatch | `test_creating_an_order_does_not_dispatch` | VERIFIED |
| A6 | Only an authority publishes alerts | `test_only_authority_publishes_alerts` | VERIFIED |
| A7 | Relays carry but cannot read | `test_relay_carries_ciphertext_it_cannot_read` | VERIFIED |
| A8 | Original input preserved across every hop | `test_6_coordinator_sees_the_incident_with_original_text` | VERIFIED |
| A9 | Priority is deterministic for the same inputs | `test_evaluation_is_deterministic` | VERIFIED |
| A10 | Human overrides are recorded with a reason | `test_human_override_is_recorded_with_its_reason` | VERIFIED |
| A11 | The Python engine matches the frozen cross-language contract | `test_priority_contract.py` — 37 cases | VERIFIED |
| A12 | The Kotlin engine encodes the same tables, floors and coefficients | `test_engine_parity.py` — 17 checks, mutation-verified | VERIFIED |
| A13 | The Kotlin engine *combines* them identically | `PriorityContractTest.kt` | **BLOCKED** — needs the Android SDK (B1) |

## Requirements with no automated test

| ID | Requirement | Why | Where recorded |
|---|---|---|---|
| N1 | Nearby Connections radio behaviour | No Android SDK; no second device | KNOWN_LIMITATIONS §1 |
| N2 | Android UI behaviour | Never compiled | KNOWN_LIMITATIONS §1 |
| N3 | Dashboard in a real browser | Logic tested; interaction not | KNOWN_LIMITATIONS §6 |
| N4 | Docker Compose stack | docker not installed | KNOWN_LIMITATIONS §9 |
| N5 | Real model accuracy | No weights downloaded | KNOWN_LIMITATIONS §2 |
| N6 | Battery consumption in reality | Simulator uses a crude model | KNOWN_LIMITATIONS §9 |
| N7 | Behaviour above three nodes | Largest tested mesh is three | KNOWN_LIMITATIONS §9 |

**Coverage:** every MVP requirement is VERIFIED. Seven requirements are ACCEPTED
limitations, each tied to a missing tool, device, or model rather than to missing work.
