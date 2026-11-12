# Colourful cartoon explainer — owner review

This page records the retained short study. The owner subsequently stated that 12 seconds is insufficient and requested a complete video. The full implementation is `cartoon_explainer_v3`, with `examples/coffee-fruit.cartoon.fixture.json` targeting 44 seconds across seven distinct shots. Complete the whole requested episode; the study is not the final delivery or an extra approval gate before production.

The owner rejected the 36-second pilot, then clarified: **explainer perspective, colourful cartoon motion, for Gen Z**. Technical checks on that older file remain valid; aesthetic acceptance was explicitly rejected. The new short proof explores a different treatment before any full episode is presented again.

This is a **12-second STYLE_STUDY**, not a completed daily episode, new daily insight, production deployment or publishing approval. The default 30–60-second production validation is unchanged. No extra daily quota is implied.

The original asset study uses a coral coffee fruit on lavender/lime, a yellow cutaway with pointers to its seeds, and a mint close. The fruit entrance, opening and seed reveal explain one beginner concept. Text enters in short groups; local Indonesian speech and original synthesised pops/swishes accompany the reveal. No third-party art, purchased course, generated product photograph, cloned voice or paid API is used.

The source fact remains the same engineering lesson: [NCA — What is coffee?](https://www.aboutcoffee.org/origins/what-is-coffee/), reopened on 12 November 2026. Beans are seeds in coffee fruit; the illustration is simplified and not an anatomical scale model, universal two-seed claim or EGON physical laboratory experiment. `egon_test_ref=null`. A new visual version is not a new topic for the novelty ledger.

## Local workflow

Run Blender headless with `src/egon_creative/blender/render_cartoon_study.py -- --output /absolute/study/folder --stills` to inspect the four review frames. Remove `--stills` for the actual motion study. The renderer streams frames to FFmpeg and retains one temporary PNG plus review stills, rather than storing hundreds of full-size images. Keep a bounded deadline, available disk headroom and the same video's cumulative cost lineage.

The local composition module `python -m egon_creative.cartoon_study --folder /absolute/study/folder --parent-job JOB_ID` expects an existing `BOUNDED_RUN.json` from the review runner, a verified parent in the pilot SQLite store and the canonical owner logo. It writes the actual MP4, grouped captions/narration, source/brief, provenance and technical QA, and registers the result as a `style_preview` asset. This is intentionally separate from the production queue. It cannot convert a 12-second proof into an approved episode.

Use the existing `EGON_VIDEO_STATE_DIR` for the pilot. Preserve the canonical PNG bytes and embedded profile, previous outputs and cost history. A conservative preview allowance must cover the combined render/composition/check deadline; known API spend remains zero. Inspect the encoded result and full voice/pacing, not only Blender stills. Owner review remains pending.
