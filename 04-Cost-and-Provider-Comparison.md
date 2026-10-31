# Cost and provider comparison

**Decision date:** 31 October 2026. **Status:** architecture and calculated scenarios; accuracy, throughput, and billed wedding costs are **NOT MEASURED**. No cloud resources or paid API calls were created during this review.

## 1. Budget decision

Keep **₹450 per wedding as the all-in face-pipeline ceiling**. Keep **₹50 for recognition compute as a separate optimization target**. Passing the latter does not pass the former: enrollment liveness, licenses, face-data retention, retries, and allocated infrastructure count too. Track the wider application's media storage and delivery separately without double-counting shared resources.

No candidate currently demonstrates compliance. Do not silently raise the ceiling, omit secure enrollment, or assume free credits in order to declare success. If measured compliant candidates cannot achieve the required accuracy, report the budget/quality conflict for an explicit product decision.

Recommendation: build a replaceable local recognition engine, measure a commercially cleared candidate, and use AWS Rekognition as an optional paid comparison. Separately evaluate managed liveness. A hybrid can improve operational simplicity, but enrollment may cost more than recognition.

## 2. Workloads and cost assumptions

| Input | Reference wedding | Maximum planning workload |
|---|---:|---:|
| Photos | 5,000 | 15,000 |
| Detected faces | 20,000 | 60,000 |
| Enrolled guests | 300 | 1,000 |
| Selfies per guest for comparison | 3 | 3 |
| Liveness checks, before retries | 300 | 1,000 |

Four faces per photo and three selfies are scenario assumptions, not findings. Benchmark one versus three versus five enrollment references; a live-video reference frame may reduce additional selfie work. Record actual detected/indexable faces, rejected captures, retries, tiles, and enrollment sessions.

The [AWS pricing page](https://aws.amazon.com/rekognition/pricing/) gives public examples of **$0.001 per Group 1 operation** and **$0.00001 per stored face/user vector-month**. Its **$0.015 per liveness check example explicitly uses US East**. The retrieved page did not expose a verified current Mumbai price table. These rates support illustrative calculations only; they are not a regional quote or measured bill.

## 3. Two materially different managed designs

**A. Index wedding photos; query using enrollment selfies.** Each gallery photo gets one `IndexFaces` call. Each selfie gets one `SearchFacesByImage` call; the application merges/calibrates results and maps FaceIds back to photos. Users API is unnecessary. This is an economical completed-album benchmark.

**B. Index wedding photos and enrolled references; search each incoming face against users.** Create each enrolled UserId, index its three reference images, explicitly associate those FaceIds, then call `SearchUsers(faceId)` for each newly indexed gallery face. Store the application’s resulting guest–photo links. This supports incremental processing without repeatedly searching all guests against the entire album.

| Initial processing, excluding retries | Reference | Maximum |
|---|---:|---:|
| A: gallery indexing + three selfie searches | 5,000 + 900 = **5,900** | 15,000 + 3,000 = **18,000** |
| B: gallery indexing + selfie indexing + associations + face searches | 5,000 + 900 + 300 + 20,000 = **26,200** | 15,000 + 3,000 + 1,000 + 60,000 = **79,000** |

These are Group 1 operation counts. B also creates 300/1,000 users; record management operations separately. Counts assume all listed faces are successfully indexed. Tiling, recovery, and retries add operations.

For B, late enrollment can query its three reference FaceIds against stored gallery faces using `SearchFaces`, adding three searches per late guest. Filter enrollment records out of gallery results. New photos still require indexing and one user search per face.

For A, a single final lookup does **not** satisfy live delivery. Requerying three references for every enrolled guest after each five-minute batch adds 900 searches per batch at reference size. Seventy-two batches add **64,800 searches**, plus indexing. Time-sharded collections help avoid old results and result caps; they do not eliminate guest-by-batch charges.

Repeated image queries also need the enrollment image bytes to remain available under explicit retention permission. Alternatively index the reference faces once and query by FaceId, adding reference-indexing and storage charges. The simple A table describes a completed-album lookup, not a design that simultaneously deletes all selfie bytes and repeatedly reuses them.

## 4. Illustrative economics

| Component at the example rates | Reference USD | Maximum USD |
|---|---:|---:|
| A recognition operations | $5.90 | $18.00 |
| B recognition operations | $26.20 | $79.00 |
| One liveness attempt per guest | $4.50 | $15.00 |
| Gallery vectors retained for 12 months | $2.40 | $7.20 |
| B gallery + reference + user vectors retained for 12 months | $2.544 | $7.68 |

The final row assumes all templates persist for twelve months; actual withdrawal/expiry reduces storage. Retention charges are lifetime obligations, not event-day cash costs. Liveness retries multiply the relevant line: 1.2 attempts per reference guest means 360 checks and $5.40 at the illustrative rate.

**Currency sensitivity only:** ₹90/USD and ₹100/USD below are planning assumptions, **not current exchange rates or forecasts**.

| Partial pipeline subtotal | USD | At ₹90/USD | At ₹100/USD |
|---|---:|---:|---:|
| A reference: recognition + liveness + gallery retention | $12.80 | ₹1,152 | ₹1,280 |
| A maximum: same components | $40.20 | ₹3,618 | ₹4,020 |
| B reference: recognition + liveness + full vector retention | $33.244 | ₹2,991.96 | ₹3,324.40 |
| B maximum: same components | $101.68 | ₹9,151.20 | ₹10,168 |

These subtotals still exclude taxes, infrastructure, retries, and ordinary media storage. At ₹100/USD, 300 liveness checks alone consume ₹450. Accordingly, the managed scenarios do not establish compliance with the ceiling, even before accuracy is tested.

Reproduce these arithmetic scenarios with `python3 tools/cost_scenarios.py`. Its JSON explicitly labels all rates as illustrative; it does not measure recognition performance or fetch current prices.

For ten simultaneous reference weddings, illustrative recognition plus one-attempt liveness totals **$104 for A's final-batch scenario** or **$307 for B**. Add retention and infrastructure separately. A's figure does not purchase five-minute live updates.

## 5. API correctness and provider constraints

- [Image face search](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_SearchFacesByImage.html) searches the **largest face only**. One group-photo search cannot identify everyone. Its 4,096-result cap has no documented search pagination; shard larger albums and flag truncation.
- [IndexFaces](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_IndexFaces.html) indexes at most 100 faces per image with newer models. Record unindexed faces and reasons; crowded frames may require extra work. Indexing is not equivalent to matching.
- [AssociateFaces](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_AssociateFaces.html) consumes explicit FaceIds for an existing user. It is not automatic clustering. It limits associations to 100 faces per user; inspect unsuccessful associations and wait for active status. Never automatically promote arbitrary predicted matches into enrollment references.
- [SearchUsers](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_SearchUsers.html) accepts FaceId or UserId; its maximum 500 returned candidates does not limit collection enrollment to 500 users. Top-two comparisons can work at N=1,000, but low-threshold candidate lists may be incomplete.
- Provider similarity scores are not calibrated probabilities. Record collection/model versions and calibrate thresholds independently. Do not promise portable embeddings: migrating usually requires re-embedding source images and possibly re-enrollment if original references were deleted.

## 6. Production prerequisites

[Mumbai supports Face Liveness](https://docs.aws.amazon.com/rekognition/latest/dg/face-liveness-faq.html). Confirm the account's actual [regional quotas](https://docs.aws.amazon.com/general/latest/gr/rekognition.html) and endpoint-specific availability before a multi-wedding load test. Bind a one-time liveness session to the authenticated guest and wedding; enroll from its verified reference frame. A liveness result must not authorize an unrelated uploaded selfie.

AWS's [encryption documentation](https://docs.aws.amazon.com/rekognition/latest/dg/security-data-encryption.html) states that inputs may be retained and used for service improvement unless opted out. Configure and verify the [Organizations AI-services opt-out policy](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_ai-opt-out_syntax.html) before participant uploads. Keep processing, templates, database, logs, and backups in approved India regions; an endpoint alone does not establish every residency property.

Preserve C5: do not request age, gender, ethnicity, or emotion predictions. Use `IndexFaces` default attributes and prefer FaceId-based search. Verify real response fields and vendor guarantees; simply discarding unwanted predictions does not satisfy a strict requirement that they never be computed. Keep credentials, images, identifiers, and signed URLs out of public repository/report outputs.

## 7. Local versus production cost measurement

A laptop run can incur no new cloud bill while still consuming electricity and developer time. It does not establish production unit economics. Instrument stage latency for diagnosis, but calculate billing from allocated resources:

`compute_cost = sum(billed_instance_seconds / 3600 × instance_hourly_price)`

Include startup, idle capacity, interruptions and retries. If using per-vCPU-hour rates, multiply allocated wall-hours by allocated vCPUs **once**. A two-thread inference's wall time is not automatically its vCPU time. Do not sum workers and then multiply by worker count again.

Benchmark CPU and batched GPU on the same held-out workload. GPU becomes cheaper when its speedup exceeds its hourly-price ratio, after overhead. Measure end-to-end throughput, RAM, cold start, and event-level p95 latency. Share workers across wedding queues only with strict tenant isolation and fair scheduling.

The cost report must contain region, hardware, rate source/date, measured billed hours/API counts, licenses, liveness attempts, retention, allocated queue/database/security costs, tax, credits shown separately, and total INR. Keep paid execution disabled until credentials, data terms, current regional rates, and a hard request-count budget are configured. A billing alert is not a spending stop.
