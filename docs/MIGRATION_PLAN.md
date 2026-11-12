# EGON Creative video migration — 12 November 2026

## Audit findings

The provided repository `egoncoffee/coffeemakeusfamily` contains only a 20-byte README on `main`. No application code, Git worktree attachment, AGENTS.md, database, logo, credentials, or integrations were present in that repository at audit time. The existing operational system is the adjacent `EGON_AI_BUSINESS_SYSTEM_V1` workspace, with Sheets as business ledger, Notion as knowledge/calendar/approval records, Drive as asset storage, and Make drafts. Its Creative instruction and current editorial V4 policy were inspected. Local Python content-registration utilities and 8–11 November content archives already exist.

The working folder was not itself a Git repository. The connected GitHub identity has read-only permission on the supplied repository. A fork and review PR are the appropriate delivery route; no default-branch overwrite is planned.

## Additive scope

1. Add the independent Python `egon_creative` package here. Keep sales, finance, operations, inventory, commission rules, business schemas, credentials, and existing integration IDs outside this public repository.
2. Keep SQLite confined to creative production records in a separate local state directory. It does not replace Sheets, Notion, or any financial ledger.
3. Extend the existing local Creative instruction by appending a versioned V5 handoff, with a pre-change backup and repeat-safe migration helper. Preserve previous instructions as historical context; V5 supersedes the daily 50-poster priority only for the new video workflow.
4. Add seven logical agent contracts, 70/20/10 planning in blocks of ten content units, immutable storyboard/prompt snapshots, an asset registry, an atomic queue, budget reservations, local Blender scenes, local Indonesian TTS, FFmpeg editing, captions, and read-only dashboard.
5. Local real-footage inputs and Flow imports require provenance. Flow is a manual inbox/export path only. No Flow API is assumed or called.
6. Gemini stays disabled by default. Optional calls require an explicitly selected model and an unbilled project checked using Google's billing API; missing verification or quota errors stop the cloud path. No paid fallback or image/video API is wired.
7. Human approval is bound to exact input and output hashes. No Instagram publisher is installed or activated. Fixture content cannot be approved or exported for publication.

## Asset and factual gates

No canonical EGON logo was found locally or in the supplied repository. Generated poster logos are not canonical assets. Production branding fails closed until a canonical file, its hash, and owner provenance are registered. A clearly marked engineering fixture can test the full local render without pretending to contain an official logo.

Resolved during implementation: the owner supplied an RGBA PNG in this chat. Its original bytes and SHA-256 are now versioned in `assets/brand/`; the branded engineering fixture uses that exact file. This resolves the logo dependency without changing the initial audit findings or activating publishing.

Only the product names and roast levels explicitly supplied by the owner in this request are accepted in the creative catalogue: Flores Wae Rebo — Medium Roast; Flores Inerie — Full City Roast; Komodo Dragon Blend — Espresso Roast. Blend percentages, tasting notes, processing method, price, availability, packaging, certification, and health claims remain unset. This does not activate or edit any SKU in Sheets.

CTMVerse could not be reliably identified from its name in the available web search. Its reference is recorded as unverified; no artwork, character, audio, or scene is downloaded or copied. The original procedural bean character and studio use EGON's established purple/orange/cream direction.

## Cost and acceptance

Default paid API allowance is IDR 0. Every video has an aggregate IDR 25,000 ceiling, including retries. Local power cost is a labelled estimate using configurable watts and IDR/kWh, with a bounded process deadline; it is not a metered electricity bill or a labour/depreciation figure. Estimates, actual known API charges, reservations, attempts, durations, and failures remain separate.

Acceptance requires a real local 1080×1920 MP4 lasting 30–60 seconds, Indonesian voiceover, burned-in captions, non-static original 3D animation, correct sources, valid encoding/audio, and a saved QA report. Publication additionally requires canonical-brand verification and explicit human approval. Passing an engineering fixture does not mark the system deployed.

## Cutover and rollback

Existing Make scenarios, daily automation, Notion/Sheets schemas, credentials and sharing remain unchanged during this PR. Review the rendered pilot and canonical logo, then choose the production cadence and cut over the existing creative schedule explicitly. No new video volume is inferred from a percentage mix.

Rollback: stop the new local worker/dashboard, retain the SQLite audit data, and restore the backed-up Creative instruction only if its current hash matches the migrated version. No business database rollback is needed because none is migrated.
