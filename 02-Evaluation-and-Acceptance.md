# Face POC — Evaluation and Acceptance

**Date:** 31 October 2026  
**Status:** Experiment specification; all empirical outcomes are **NOT MEASURED**.  
**Read with:** [01-Architecture-and-Decisions.md](01-Architecture-and-Decisions.md) and [03-Codex-Build-Prompt.md](03-Codex-Build-Prompt.md).

## 1. What this POC must establish

Determine whether authorized wedding photographs can be assigned to the correct enrolled guests, with useful recall, acceptable cost and reproducible evidence. A working gallery is an engineering milestone; it does not establish production accuracy.

Start with YuNet detection and the approved AuraFace adapter, with SFace as a compact comparison. AdaFace and licensed alternatives remain permission-gated candidates. Model availability is not permission: the registry must record approval for the intended activity before execution.

Compare **direct matching first**, then **group-assisted candidate selection with member verification**. Never release every photo in a cluster because its representative matched. Fewer cluster comparisons do not by themselves mean fewer wrong photos: one mistaken cluster can release many wrong links. A correct representative also cannot certify a mixed cluster. The inherited 95% cluster-purity target is insufficient for bulk release at 99% precision.

## 2. Data progression and holdouts

**Optional starter:** 200–500 photographs containing 20–40 consenting adults, plus separately captured enrollment images. Include group shots, absent enrolled people, authorized non-enrolled subjects, poor lighting and difficult poses. This is a convenient engineering scope, not a minimum sample proving quality. Restrict collection and processing to the documented permission scope. Begin with trusted, operator-assisted enrollment; public enrollment is a separate security gate.

**Validation planning minimum:** three or more independent events with at least 1,000 evaluated photographs per event, when obtainable. Reserve separate events for development, threshold calibration and sealed testing. These counts provide a practical diversity target, **not statistical proof**. More independent events and people will be needed for strong subgroup or rare-error conclusions.

Split before running models. Keep identities, original images, crops, edited copies and burst/capture groups together wherever split independence requires it. Detect identity overlap between weddings; do not silently count the same family at two events as independent people. Several stages of one wedding are not independent weddings. Within each evaluation event, enrollment and gallery necessarily share enrolled identities, but must use separate captures and sessions.

Freeze the model, detector, preprocessing, quality gates and thresholds before opening the sealed set. Seeds make sampling repeatable; different seeds over the same people are not a holdout. Any change informed by sealed results requires a new test set or an explicitly labeled exploratory rerun.

Test N=300 and N=1,000 only with that many **distinct real, authorized enrollment identities**, including enrolled people absent from the gallery. Include gallery people who never enrolled. Do not duplicate identities, invent synthetic people or relabel one person to satisfy N. If data is missing, mark accuracy at that scale NOT MEASURED. Synthetic vectors remain useful for memory and throughput tests only. Public face-crop benchmarks are optional permission-gated diagnostics; they cannot validate full-frame wedding delivery.

## 3. Required manifests and ground truth

Keep photographs, private annotations and biometric outputs outside Git. Use opaque IDs and relative paths. Commit schemas and synthetic examples only.

| File | Required fields | Purpose |
|---|---|---|
| `media.csv` | `wedding_id, asset_id, path, canonical_photo_id, capture_group_id, stage_id, permission_record_id` | Canonical photo, source grouping and processing authorization |
| `face_annotations.csv` | `wedding_id, asset_id, annotation_face_id, person_id_or_unknown, bbox_xywh, recognisable, original_interocular_px, depiction_type, annotation_status` | Independent face-level truth and detector evaluation |
| `person_photo_labels.csv` | `wedding_id, person_id, canonical_photo_id, present, recognisable, annotation_status` | Evaluated person–photo truth; multiple faces can produce one link |
| `enrollments.csv` | `wedding_id, person_id, enrollment_id, capture_session_id, path, consent_record_id, consent_version` | Separate reference captures and active consent |
| `split_memberships.csv` | `wedding_id, person_id, capture_group_id, split, split_version` | Development/calibration/test membership and leakage checks |

Optional authorized annotation fields include pose, illumination, blur, occlusion and makeup. Do not infer age, gender, ethnicity or skin tone with a model. Subgroup analysis uses appropriately obtained labels or reports that the subgroup is unavailable.

Define recognisability before examining predictions. Use the original photograph's coordinate system, preserving orientation transforms; record effective detector input size separately. A missed detection must remain in the recall denominator. Human uncertainty is `unknown`, not a negative for every guest. Adjudicate unclear cases, preferably with two annotators, and report unresolved counts.

Fully label the selected evaluation frames for enrolled-person appearances and review every predicted delivery. A list of 200 positive pairs cannot establish full recall or classify all false positives. An absent annotation is not proof of absence. Near-duplicate photographs may be distinct memories: use duplicate grouping for evaluation and review, not destructive deduplication based solely on a perceptual hash.

## 4. Matching policies under test

**Direct baseline:** screen enrollment captures for quality; retain a small fixed set of reference vectors. Compare each gallery face to enrolled identities within its wedding. Accept only when the best identity clears a calibrated similarity threshold, quality gates and a best-versus-second-identity margin. Multiple references belonging to one person must be aggregated before computing that margin. Otherwise abstain. Never force a match.

**Enrollment ablation:** compare one, three and five captures, a normalized mean and a bounded set of prototypes. More references can raise false acceptance opportunities, so recalibrate each policy rather than reuse one threshold. Record capture time and failed/repeated captures.

**Group-assisted challenger:** form conservative anonymous groups; use exemplars to propose candidates. Verify every proposed face against the guest's enrollment references or another separately validated corroboration rule. Retain singleton faces and reject ambiguous merges. Do not average uncertain automatic matches into enrollment references or treat transitive similarity as proof of identity.

The old “rescue faces in photos already delivered” does not improve photo recall: those photographs are already in the guest's gallery. Disable it initially. Any later rescue must recover previously missed photos and pass the same disclosure gate.

Use exact, chunked scoring as the reference implementation. Embeddings from different model/preprocessing versions are incomparable. Managed-provider similarity scores are different score spaces: calibrate and report each provider separately. They are not cosine values or calibrated probabilities. Clustering is optional; direct matching winning on simplicity or quality is a valid outcome.

## 5. Metrics and uncertainty

The primary unit is a unique `(wedding_id, guest_id, canonical_photo_id)` link. A group photograph containing the guest plus non-enrolled bystanders is a correct match. “Stranger leakage” means assigning a photograph to an absent enrolled guest because another person's face matched; it does not prohibit co-present bystanders.

Let Y be adjudicated true links and D be delivered links:

- **Precision:** `|D ∩ Y| / |D|`.
- **Recall:** `|D ∩ Y| / |Y|`.
- **Recognisable recall:** the same calculation restricted to links where at least one appearance meets the predefined recognisability criterion.

Also score evidence-face correctness. A photograph may correctly contain the guest while the system used another person's face as evidence; photo precision alone conceals that defect.

Report micro totals, macro per-guest averages, worst guest, support counts, median and lower-tail performance. No delivered photos means undefined precision, not 100%; record empty-gallery coverage, and zero recall when true appearances existed. Count absolute wrong links, affected guests, maximum wrong-release burst, and events with any wrong link. Count previews and confirmation exposures separately: asking a guest about someone else's image is already a disclosure, even if final delivery is prevented.

Report detector recall by face size, pose and occlusion; full-pipeline miss attribution; open-set identification errors; cluster purity distribution and worst contamination; fragmentation; abstention; and confirmation prompts per guest. Do not substitute pairwise verification FMR for end-to-end identification precision.

Show raw counts and uncertainty. Prefer event/identity-aware resampling where supported; burst photographs and cluster releases are correlated. Under an independent-binomial illustration, about 299 error-free trials are needed for a one-sided 95% lower confidence bound above 99%, but 299 correlated photographs do not provide that evidence. Millions of pairs sharing identities likewise do not create millions of independent trials. Zero observed leakage does not prove zero future risk. Insufficient subgroup support means INCONCLUSIVE, not pass.

## 6. Experiment sequence

| Stage | Comparison | Required output |
|---|---|---|
| E0 | Permissions, artifact hashes, schema and preprocessing | Eligibility registry; reproducible inputs; reference/runtime parity |
| E1 | Detector resolutions and selective overlapping tiles | Full-frame recall, false detections and runtime; include completely missed crowds |
| E2 | Approved models and one/three/five references | Calibration curves; per-condition errors; capture burden |
| E3 | Direct versus group-assisted member verification | Same-data photo PR curves, wrong-link severity, grouping cost |
| E4 | Real distinct N=300/1,000; unknowns and lookalikes | Per-scale open-set results or explicit missing-data status |
| E5 | Frozen configuration on sealed events | Per-event and pooled results, counts, uncertainty, failures |
| E6 | CPU, GPU and eligible managed candidates | Measured total cost, wall time, cold starts and memory |
| E7 | Batch, live, ten-event burst and fault injection | Queue-inclusive latency, fairness, integrity and recovery |
| E8 | Enrollment attacks and disclosure races | Attack counts, bona fide rejection and withdrawal correctness |

Eliminate ineligible or incorrect candidates before expensive sweeps. Select operating points on calibration data; sealed-test curves are diagnostic, not permission to retune and still call the result held out.

## 7. Targets and release decisions

| Criterion | Proposed target / decision rule | Current evidence |
|---|---|---|
| Delivered precision | Initial product target ≥99%; worst guest ≥97%, with support counts | NOT MEASURED |
| Incorrect disclosures | Zero observed in sealed release evaluation, including previews; uncertainty disclosed | NOT MEASURED |
| Recognisable recall | ≥92%; report all-identifiable recall, initially aiming ≥78% | NOT MEASURED |
| Detection | ≥99% for ≥60 px inter-ocular; report smaller-face buckets | NOT MEASURED |
| Supported subgroup gap | Aim ≤2 percentage points; insufficient support is inconclusive | NOT MEASURED |
| First result | <90 seconds after enrollment when relevant photos were already processed | NOT MEASURED |
| Live delivery | Upload-complete to gallery ≤5 minutes p95, proposed SLO | NOT MEASURED |
| Batch | 5,000 photos/approximately 20,000 faces within 30 minutes | NOT MEASURED |
| Cost | Aim ≤₹50 recognition compute; all-in marginal face-pipeline ceiling ₹450 including liveness, licensing and face-data retention | NOT MEASURED |
| Scale | 15,000 photos; N=1,000; ten concurrent weddings | NOT MEASURED |
| Public enrollment security | Validated attack resistance; print/screen target ≥99% is provisional | NOT MEASURED |

**Engineering ready:** authorized fixtures run end to end, deterministic policy/metric tests pass, failures are visible. **Promising:** development results are useful but transfer, scale or permission evidence is missing. **Pilot candidate:** frozen independent evaluation meets the declared gates, privacy tests pass and enrollment mode matches validated security. **Rework:** a gate fails. A managed API is another candidate to evaluate, not an automatically accurate fallback.

## 8. Failure tests and cost accounting

| Failure | Required invariant |
|---|---|
| Ambiguous lookalikes | Threshold or margin failure produces abstention |
| Mixed cluster | Correct representative cannot release an incorrect member |
| Group photograph | Each present enrolled guest can receive it; absent guest cannot |
| Withdrawal during processing | Resume paused worker after withdrawal; final write and gallery read both deny stale access |
| “Not me” during retry | Old job cannot restore rejected link; unrelated correct links remain |
| Lease expiry / crash | Retry has one effective result; stale lease owner cannot overwrite newer state |
| Late enrollment / upload | Stored compatible vectors support new enrollment; new photos match active guests |
| Cross-wedding request | Queries, caches and media access preserve wedding boundaries |
| Model change / restore | Incompatible vectors never compare; deletion tombstones survive replay and migration |
| Corrupt/large/rotated image | Per-file error isolation, resource limits and correct coordinates |
| Test leakage / metric bug | Reject overlapping capture groups; toy cases cover empty sets, duplicates and wrong evidence |

Add enrollment attack tests for print, screen, replay and injection where applicable; a live movement challenge alone is not established proof. Report both attack acceptance and genuine-user rejection. Operator enrollment does not establish public anti-spoofing performance.

Measure actual worker-instance billed seconds and rates, including decode, tiles, embedding, matching, retries, cold starts and idle capacity. Separate marginal inference, shared infrastructure, licensing/API fees and media retention. A two-vCPU runtime's wall seconds are not automatically one vCPU-second. Compare reference load, high face density, 15,000 photos, ten-event bursts and quiet-month idle cost. All reports must identify hardware, concurrency, model hashes, dataset/split versions and configuration; no inherited estimate becomes “measured” without reproducible logs.
