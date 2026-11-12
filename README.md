# EGON Creative — video-first local pilot

An additive Python video-production module for the existing EGON Coffee AI Business System. It produces original 3D educational animation, Indonesian narration, burned-in captions and a 1080×1920 H264/AAC MP4. Business ledgers, credentials, integration IDs and existing modules are not moved into this repository.

**Status: local engineering pilot, not deployed.** The full local render has been exercised. The owner supplied the canonical logo during implementation; its original PNG and hash are retained in `assets/brand/`. No Instagram publisher or active production schedule is included.

**Latest direction:** the owner rejected the dark 36-second pilot, requested a colourful cartoon explainer for Gen Z, then clarified that a 12-second study is insufficient. Use the [full 44-second cartoon example](examples/coffee-fruit.cartoon.fixture.json) for a complete episode. The retained short study is historical review material; no renderer or technical result implies owner aesthetic/publication approval.

## Start locally

Requirements: Python 3.10+ (pilot tested with 3.12), official Blender 4.5+, FFmpeg/FFprobe, a local TrueType font, and local Indonesian speech. The current TTS adapter supports macOS `say` with Damayanti (`id_ID`). Linux/Windows need a local Indonesian TTS adapter; they do not fall back to a paid API.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/egon-creative doctor
.venv/bin/egon-creative plan --blocks 1
.venv/bin/egon-creative register-logo assets/brand/EGON_WORDMARK_ORIGINAL.png \
  --sha256 301dc7c06831daad76a849775ecd7bab2711af7b0ec335ee9c33f9caff1159ad \
  --owner-confirmed --source-ref "Owner supplied complete EGON wordmark, 12 November 2026"
.venv/bin/egon-creative enqueue examples/coffee-fruit.cartoon.fixture.json
.venv/bin/egon-creative work
.venv/bin/egon-creative serve --port 8765
```

Dashboard: <http://127.0.0.1:8765>. It is read-only and binds only to the local computer. State defaults to `~/.local/share/egon-creative/production.sqlite3`. Override paths using the documented `EGON_*` environment variables in [.env.example](.env.example); the app reads the process environment, not an arbitrary credentials file.

The fixture is marked **ENGINEERING_FIXTURE** and cannot be approved for publication. The generic legacy fixture shows a missing-logo banner when no canonical asset is registered; the focus-style fixture requires the exact complete-logo hash. It does not count as a published lesson, a novel production angle, or measured marketing performance.

For the owner-supplied branded Gen Z pilot, register the unchanged `assets/brand/EGON_WORDMARK_ORIGINAL.png` using the SHA-256 in `assets/brand/canonical.json`, then enqueue `examples/coffee-fruit.genz.fixture.json`. Generic fixtures show the missing-logo banner only when no canonical asset is registered; branded fixtures require the exact supplied hash. The complete owner-supplied wordmark is the current canonical asset. Earlier symbol-only assets and fixture snapshots are retained as history in `assets/brand/` and `examples/archive/`.

## Workflow and seven agents

Creative Director → Coffee Research → Scriptwriting → Visual Director → Animation → Audio & Editing → owner review → Performance after publication. [Seven role contracts](agents/) and [runtime registry](src/egon_creative/agents.py) define responsibilities and permissions. These are logical components of the local workflow, not seven already-deployed autonomous cloud accounts. Reviewed scripts are consumed locally; optional model drafting does not independently verify facts or approve its own work.

The mix planner produces **7 animated / 2 real-footage / 1 static** unit per block of ten. No daily publishing quota is inferred. Real-footage jobs require owned registered clips with adequate duration; they cannot silently substitute animation or loop brewing evidence. Static work emits an explicit handoff to the existing Creative workflow, without invoking a paid image API.

## Architecture

| Component | Role |
|---|---|
| `storyboard.py` | Reviewed schema, public editorial gates, 70/20/10 planner |
| `store.py` | Separate creative SQLite database, immutable input snapshots, atomic queue, cumulative budget and approvals |
| `blender/render_scene.py` | Original Nara character and reusable studio `.blend` library, headless native 3D frames |
| `media.py` | Local Indonesian speech, measured caption timing, original SFX, native FFmpeg composition |
| `pipeline.py` | Bounded worker, asset checks, 1080×1920 / 30–60s / decode / motion QA |
| `dashboard.py` | Read-only local production, cost and metric dashboard |
| `performance.py` | Observed retention/reach/saves/shares/completion and evidence-backed sales snapshots |
| `gemini.py` | Optional free-only, source-unverified drafting; disabled by default |
| `manual_flow.py` | Manual brief export and provenance-tagged clip import; no Flow API |

Storyboard, narration, scene instructions, source mappings and input versions are frozen by content hash. Revisions create new job versions sharing the same stable `production_id`; cost ceilings include earlier versions and retries. The default visual preset uses **Eevee soft lighting and 24 native frames per second**, encoded at 24 fps. Workbench is an explicit engineering option, not the visual release standard. The legacy studio renderer remains available. The additive `focus_explainer_v2` style adds closer object framing, purposeful motion, short animated caption groups and a schematic grinding scene. Six scene types are available; a history or trend requiring other assets still needs reviewed scene code/assets.

The owner's latest direction is **coffee history, insights, industry developments and knowledge for Gen Z**. Teach one useful, surprising fact with a confident warm Indonesian voice and original visuals. Do not turn the media brief into a product-advertising or hard-sell requirement. See [editorial direction and Flow adaptation](docs/GEN_Z_EDITORIAL_AND_FLOW.md).

For the owner's object-led motion reference, see [motion standard](docs/MOTION_EXPLAINER_STANDARD_V1.md) and `examples/coffee-fruit.motion.fixture.json`. Its new renderer is additive and retains all older clips. The local pilot's visual/voice/pacing quality still needs owner review.

## Logo, sources, and publication

Only a file explicitly confirmed by the owner can be registered as the canonical logo:

```sh
egon-creative register-logo /absolute/path/original-logo.png \
  --sha256 ORIGINAL_FILE_SHA256 --owner-confirmed \
  --source-ref "Owner-provided canonical asset, date/reference"
```

The original master bytes are hashed and retained unchanged. Embedded ICC profiles are honoured through an sRGB display copy for FFmpeg, preserving geometry and transparency; an untagged source is read directly. Only proportional layout scaling is used, with no artistic recolouring, redraw or cropping. A changed file fails the gate. Never crop a logo from an AI-generated poster. A missing logo blocks real production before render spend. Fixtures may exercise the renderer with a prominent test banner but cannot be approved.

Research verification remains a named upstream review backed by opened primary evidence; Python validates the evidence structure, not scientific truth. Production also requires a semantic novelty review with actual ledger/draft comparisons. Blank gates and unverified source/novelty state stop rendering. See [migration plan](docs/MIGRATION_PLAN.md) and [sources](docs/SOURCES.md).

Human approval is explicit and hash-bound:

```sh
egon-creative approve JOB_ID --by "Owner identity" --ack-human --ack-visual
```

This requires the human to review the entire final video, voice, captions and pacing, and records a local approval only. **It does not post to Instagram.** Technical QA never awards aesthetic approval. The current release has no publisher, so no connected account, OAuth success or role contract implies a live `@kopiegon` posting path.

## Cost controls

- Default paid API spend: **IDR 0**. Blender, speech, SFX and editing run locally.
- Ceiling: **IDR 25,000 per video**, including attempts and revisions sharing the same production ID.
- A reservation covers the configured bounded process deadline before render work starts. Retries keep past costs. Over-budget work is blocked.
- `record-cost JOB_ID --amount-idr AMOUNT --category manual_local_preview --basis ESTIMATE --source-ref "Evidence/assumption"` reconciles auxiliary preview costs without calling/paying a provider. External generation can be logged separately as `manual_external_generation`, with its actual or estimated basis. Repeated evidence references are idempotent and share the ceiling.
- Known API charges, estimates, reservations and released reservations are recorded separately. Local power is an explicit configurable estimate (pilot assumptions: 300 W and IDR 3,000/kWh), not a metered bill; labour, depreciation and pre-existing subscription costs are not claimed as measured.
- `EGON_GEMINI_ENABLED=free-only` is optional. An OAuth token, explicit project/model, today's model free-tier check and a live unbilled-project check are required before a generation request. Quota/errors stop this path; no paid fallback, billing setup or key changes occur. Live Gemini has not been exercised without authorised credentials.

## Manual Flow and real media

```sh
egon-creative register-footage /absolute/path/owned-brewing.mp4 --source-ref "Owned filming log"
egon-creative flow-export reviewed-storyboard.json /new/manual-handoff-folder
egon-creative flow-import /absolute/path/owned-flow-output.mp4 --source-ref "Manual generation provenance"
```

Flow is a manual asset inbox; no automatic Flow generation or accessible API is assumed. Imported generated clips are tagged as generated and cannot pass as real brewing footage. External paid generation needs its own authorised and reconciled cost record; the default worker uses local Blender and does not silently spend Flow credits.

## Performance and integration

```sh
egon-creative metrics JOB_ID observed-instagram-export.json
```

Measurements need `source_ref`, `observed_at`, and nullable observed counts: `reach`, `plays`, `saves`, `shares`, `completed_plays`, `attributed_orders`, `attributed_sales_idr`, `average_watch_seconds`, `video_seconds`, and optionally an observed `retention_curve`. Sales need `attribution_evidence`. Completion is completed plays / plays; average watch ratio is separate and may exceed 1 with replays. Missing metrics stay null. No Instagram analytics connection or sales uplift is fabricated.

`tools/migrate_legacy_creative.py LEGACY_ROOT --backup-dir PRIVATE_BACKUP_DIR` appends the V5 Creative handoff once and saves the original hash/backup. It never opens financial ledgers or changes Notion/Sheets/Make schemas, credentials, sharing or live schedules. The original V1 documentation remains historical. Review the pilot and choose cadence before cutting over the old poster automation.

See the [production and review runbook](docs/PRODUCTION_RUNBOOK.md) for the complete local handoff and failure procedure.

## Verification

```sh
python -m unittest discover -s tests -v
```

Guards cover queue concurrency, idempotency, revision/retry budgets, missing-source/logo gates, fixture publication blocking, free-tier fail-closed behaviour, metric denominators and repeat-safe legacy migration. Full local acceptance uses the fixture command above and checks actual decoded pixels, voice signal, file decoding, codec, dimensions, duration and saved `QA.json`. See [actual test report](docs/TEST_REPORT.md) for exercised versions and remaining limits.
