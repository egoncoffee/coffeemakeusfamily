from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from egon_creative.config import Settings
from egon_creative.gemini import FreeTierBlocked, draft
from egon_creative.performance import ingest
from egon_creative.store import Store, file_hash
from egon_creative.storyboard import plan_mix, validate

ROOT = Path(__file__).parents[1]


def fixture():
    return json.loads((ROOT / "examples/coffee-fruit.fixture.json").read_text())


class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "creative.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_mix_is_70_20_10_without_daily_quota(self):
        units = plan_mix(2)
        self.assertEqual([sum(u["kind"] == k for u in units) for k in ["animated", "real_footage", "static"]], [14, 4, 2])

    def test_idempotent_inputs_and_immutable_versions(self):
        doc = fixture()
        one = self.store.enqueue(doc)
        self.assertEqual(one, self.store.enqueue(doc))
        doc["visual_asset_version"] = "next-original-character-revision"
        two = self.store.enqueue(doc)
        self.assertNotEqual(one, two)
        self.assertEqual(self.store.job(one)["video_id"], self.store.job(two)["video_id"])
        self.assertEqual(len(self.store.snapshot()["jobs"]), 2)

    def test_atomic_claim_no_duplicate_workers(self):
        for n in range(12):
            doc = fixture()
            doc["test_revision"] = n
            self.store.enqueue(doc)
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(lambda n: self.store.claim("worker-" + str(n)), range(16)))
        ids = [i for i in ids if i]
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)

    def spent_job(self):
        job = self.store.enqueue(fixture())
        self.store.claim("unit-test")
        self.store.reserve(job, 25000, 25000)
        self.store.settle(job, 3600, 1000, 25000)
        self.store.finish(job, "FAILED", error="synthetic local test")
        return job

    def test_ceiling_survives_retry(self):
        job = self.spent_job()
        self.store.retry(job)
        self.store.claim("unit-test-retry")
        with self.assertRaisesRegex(ValueError, "COST_CEILING"):
            self.store.reserve(job, 1, 25000)

    def test_ceiling_survives_storyboard_revision(self):
        job = self.spent_job()
        doc = fixture()
        doc["revision"] = "new script same video"
        other = self.store.enqueue(doc)
        self.store.claim("revised-video")
        with self.assertRaisesRegex(ValueError, "COST_CEILING"):
            self.store.reserve(other, 1, 25000)

    def test_manual_costs_are_idempotent_and_share_the_ceiling(self):
        job = self.store.enqueue(fixture())
        args = (job, 75, "manual_local_preview", "ESTIMATE", "isolated test preview allowance")
        self.assertEqual(self.store.record_expense(*args)["status"], "RECORDED")
        self.assertEqual(self.store.record_expense(*args)["status"], "ALREADY_RECORDED")
        self.assertEqual(len(self.store.snapshot()["costs"]), 1)
        with self.assertRaisesRegex(ValueError, "different immutable"):
            self.store.record_expense(job, 76, *args[2:])
        self.store.claim("test")
        with self.assertRaisesRegex(ValueError, "COST_CEILING"):
            self.store.reserve(job, 25000, 25000)

    def test_invalid_and_nan_budgets_rejected(self):
        for amount in [25001, 0, float("nan")]:
            with self.assertRaises(ValueError):
                Settings(self.root, max_cost_idr=amount)
        with self.assertRaises(ValueError):
            Settings(self.root, watts_estimate=float("nan"))
        job = self.store.enqueue(fixture())
        self.store.claim("test")
        with self.assertRaises(ValueError):
            self.store.reserve(job, float("nan"), 25000)

    def test_deadline_terminates_local_work(self):
        import subprocess
        import sys
        from egon_creative.process import Deadline
        deadline = Deadline(.15)
        with self.assertRaises(subprocess.TimeoutExpired):
            deadline.run([sys.executable, "-c", "import time; time.sleep(30)"])
        self.assertLess(deadline.elapsed, 3)

    def test_agents_cannot_approve_their_own_work(self):
        job = self.store.enqueue(fixture())
        self.store.claim("agent")
        with self.assertRaises(ValueError):
            self.store.finish(job, "APPROVED")
        with self.assertRaises(ValueError):
            self.store.approve(job, "owner", True)

    def reviewable_production(self):
        from PIL import Image
        from egon_creative.store import file_hash
        logo = self.root / "unit-fixture-only.png"
        Image.new("RGBA", (8, 8), (100, 50, 160, 255)).save(logo)
        self.store.register_asset(logo, "logo", "Synthetic unit-test asset in temporary isolated database", True)
        sha = file_hash(logo)
        doc = fixture()
        doc.update({"data_class": "PRODUCTION", "production_id": "isolated-unit-case", "canonical_logo_sha256": sha,
                    "novelty_review": {"reviewed_by": "synthetic test", "compared_records": ["synthetic test"], "reason": "temporary isolated fixture"}})
        job = self.store.enqueue(doc)
        self.store.claim("unit-test")
        output = self.root / "not-a-real-video.bin"
        output.write_bytes(b"isolated unit fixture for approval-integrity guards")
        self.store.finish(job, "DESIGN_REVIEW", output, {"status": "PASS", "brand_status": "PASS", "logo_sha256": sha})
        return job, logo, output

    def test_human_approval_binds_current_output_bytes(self):
        job, logo, output = self.reviewable_production()
        with self.assertRaises(ValueError): self.store.approve(job, "test human", False)
        output.write_bytes(b"changed after QA")
        with self.assertRaisesRegex(ValueError, "Artifact changed"):
            self.store.approve(job, "test human", True, True)

    def test_changed_logo_requires_new_review(self):
        job, logo, output = self.reviewable_production()
        logo.write_bytes(b"changed source asset")
        with self.assertRaisesRegex(ValueError, "Canonical logo has changed"):
            self.store.approve(job, "test human", True, True)

    def test_explicit_human_approval_is_hash_bound_without_publishing(self):
        job, logo, output = self.reviewable_production()
        with self.assertRaisesRegex(ValueError, "Explicit human review"):
            self.store.approve(job, "isolated synthetic test human", True)
        approval = self.store.approve(job, "isolated synthetic test human", True, True)
        self.assertTrue(approval.startswith("HUMAN-"))
        self.assertEqual(self.store.job(job)["status"], "APPROVED")
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot["approvals"][0]["output_sha256"], self.store.job(job)["output_sha256"])
        self.assertFalse(any(e["action"] == "PUBLISHED" for e in snapshot["events"]))

    def test_missing_logo_blocks_production_before_render_or_spend(self):
        from egon_creative.pipeline import worker_once
        doc = fixture()
        doc.update({"data_class": "PRODUCTION", "production_id": "test-only-production-case",
                    "novelty_review": {"reviewed_by": "test reviewer", "compared_records": ["test only"], "reason": "synthetic test"}})
        job = self.store.enqueue(doc)
        with patch("egon_creative.media.speech", side_effect=AssertionError("must not run")):
            result = worker_once(self.store, Settings(self.root))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("CANONICAL_LOGO", result["error"])
        self.assertEqual(self.store.snapshot()["costs"], [])

    def test_source_and_editorial_checks_fail_closed(self):
        for change in ["source", "gate", "claim", "duration", "lab"]:
            doc = fixture()
            if change == "source": doc["sources"][0]["opened"] = False
            elif change == "gate": doc["gates"]["NOVELTY"] = "UNVERIFIED"
            elif change == "claim": doc["shots"][0]["claim_ids"] = ["invented"]
            elif change == "duration": doc["target_seconds"] = 10
            else: doc["shots"][0]["narration"] = ["Sudah diuji EGON di hasil lab kami."]
            with self.assertRaises(ValueError): validate(doc)

    def test_no_fake_product_details(self):
        products = json.loads((ROOT / "config/products.json").read_text())["products"]
        self.assertEqual(len(products), 3)
        for product in products:
            self.assertEqual(set(product), {"id", "name", "roast"})

    def test_focus_style_needs_purposeful_motion_plans(self):
        doc = fixture()
        doc["visual_style"] = "focus_explainer_v2"
        with self.assertRaisesRegex(ValueError, "motion plan"):
            validate(doc)
        ready = json.loads((ROOT / "examples/coffee-fruit.motion.fixture.json").read_text())
        validate(ready)
        self.assertEqual(ready["data_class"], "ENGINEERING_FIXTURE")
        self.assertEqual(ready["production_id"], "VIDEO-2a4a0a918a3f129bcfee50ab")
        ready["kind"] = "real_footage"
        with self.assertRaisesRegex(ValueError, "requires animated content"):
            validate(ready)

    def test_short_visual_study_cannot_bypass_episode_duration_guards(self):
        for data_class in ['ENGINEERING_FIXTURE', 'PRODUCTION']:
            doc = fixture()
            doc['data_class'] = data_class
            doc['target_seconds'] = 12
            doc['delivery_scope'] = 'STYLE_STUDY'
            with self.assertRaisesRegex(ValueError, '30–60 seconds'):
                validate(doc)

    def test_full_cartoon_episode_has_complete_explicit_timing(self):
        doc=json.loads((ROOT/'examples/coffee-fruit.cartoon.fixture.json').read_text())
        validate(doc)
        self.assertEqual(sum(s['duration_seconds'] for s in doc['shots']),44)
        self.assertEqual(doc['production_id'],'VIDEO-2a4a0a918a3f129bcfee50ab')
        doc['kind']='real_footage'
        with self.assertRaisesRegex(ValueError,'requires animated content'):
            validate(doc)

    def test_partial_or_invalid_explicit_timing_fails_before_render(self):
        doc=json.loads((ROOT/'examples/coffee-fruit.cartoon.fixture.json').read_text())
        del doc['shots'][1]['duration_seconds']
        with self.assertRaisesRegex(ValueError,'every shot'):validate(doc)
        doc['shots'][1]['duration_seconds']=6
        with self.assertRaisesRegex(ValueError,'equal the episode target'):validate(doc)

    def test_cached_cartoon_opening_cannot_change_after_registration(self):
        from egon_creative.cartoon_full import opening_cache
        path=self.root/'opening.mp4';path.write_bytes(b'unit fixture, not an actual render')
        key=self.store.register_asset(path,'generated_animation','isolated immutable-cache guard fixture')
        doc={'opening_asset':{'asset_id':key,'sha256':file_hash(path),'source_in_seconds':0,'duration_seconds':8}}
        timeline={'shots':[{'scene':'cherry','end':3},{'scene':'cherry','end':8}]}
        self.assertEqual(opening_cache(self.store,doc,timeline,24)['id'],key)
        with self.assertRaisesRegex(ValueError,'does not match'):
            opening_cache(self.store,doc,{'shots':[{'scene':'cherry','end':4},{'scene':'cherry','end':8}]},24)
        path.write_bytes(b'changed after asset registration')
        with self.assertRaisesRegex(ValueError,'missing or changed'):opening_cache(self.store,doc,timeline,24)

    def test_grinding_does_not_silently_use_the_legacy_cup_scene(self):
        doc = fixture()
        doc["shots"][0]["scene"] = "grind"
        with self.assertRaisesRegex(ValueError, "focus explainer renderer"):
            validate(doc)

    def test_owner_wordmark_profile_keeps_master_and_transparency(self):
        from PIL import Image, ImageChops
        from egon_creative.media import logo_for_display
        from egon_creative.store import file_hash
        source = ROOT / "assets/brand/EGON_WORDMARK_ORIGINAL.png"
        sha = file_hash(source)
        display_path = logo_for_display({"path": str(source), "sha256": sha}, self.root)
        self.assertEqual(file_hash(source), sha)
        with Image.open(source) as original, Image.open(display_path) as display:
            self.assertEqual(display.size, original.size)
            self.assertIsNone(ImageChops.difference(original.getchannel("A"), display.getchannel("A")).getbbox())
            self.assertEqual(original.getpixel((300, 800)), (236, 97, 53, 255))
            red, green, blue, alpha = display.getpixel((300, 800))
            self.assertGreaterEqual(red, 250)
            self.assertTrue(65 <= green <= 95 and blue < 35 and alpha == 255)
        provenance = json.loads((self.root / "logo-display.json").read_text())
        self.assertEqual(provenance["source_profile"], "Display P3")
        self.assertTrue(provenance["canonical_master_unchanged"])

    def test_metrics_use_correct_denominator_and_evidence(self):
        job = self.store.enqueue(fixture())
        measurement = {"source_ref": "synthetic-unit-fixture", "observed_at": "2026-11-12T00:00:00+07:00", "reach": 6, "plays": 10, "completed_plays": 4,
                       "average_watch_seconds": 45, "video_seconds": 30}
        one = ingest(self.store, job, measurement)
        self.assertEqual(one, ingest(self.store, job, measurement))
        row = json.loads(self.store.snapshot()["metrics"][0]["document"])
        self.assertEqual(row["completion_rate"], .4)
        self.assertEqual(row["average_watch_ratio"], 1.5)
        with self.assertRaises(ValueError): ingest(self.store, job, {**measurement, "completed_plays": 11})
        with self.assertRaises(ValueError): ingest(self.store, job, {**measurement, "attributed_sales_idr": 1000})

    def test_default_gemini_never_contacts_network(self):
        def forbidden(*_): raise AssertionError("Network must not be used")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(FreeTierBlocked): draft("public coffee brief", forbidden)

    def test_paid_or_unknown_billing_stops_before_generation(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()
        env = {"EGON_GEMINI_ENABLED": "free-only", "EGON_GEMINI_PROJECT": "test-project", "EGON_GEMINI_MODEL": "gemini-test-model", "EGON_GOOGLE_OAUTH_TOKEN": "synthetic-test-token", "EGON_GEMINI_MODEL_FREE_VERIFIED_ON": today}
        for billing in [{"projectId": "test-project", "billingEnabled": True}, {}, {"projectId": "wrong-project", "billingEnabled": False}]:
            calls = []
            def transport(url, *_): calls.append(url); return billing
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(FreeTierBlocked): draft("public brief", transport)
            self.assertEqual(len(calls), 1)
            self.assertIn("billingInfo", calls[0])

    def test_legacy_migration_preserves_other_modules_and_is_repeat_safe(self):
        spec = importlib.util.spec_from_file_location("migrate", ROOT / "tools/migrate_legacy_creative.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        legacy = self.root / "legacy"
        agents = legacy / "03_AGENT_INSTRUCTIONS"
        agents.mkdir(parents=True)
        (agents / "CREATIVE.md").write_text("Original Creative contract\n")
        (agents / "FINANCE.md").write_text("Private business contract unchanged\n")
        result = module.migrate(legacy, self.root / "backups")
        self.assertEqual(result["status"], "APPLIED")
        self.assertTrue((agents / "CREATIVE.md").read_text().startswith("Original Creative contract\n"))
        self.assertEqual((agents / "FINANCE.md").read_text(), "Private business contract unchanged\n")
        self.assertEqual(module.migrate(legacy, self.root / "backups")["status"], "ALREADY_APPLIED")


if __name__ == "__main__":
    unittest.main()
