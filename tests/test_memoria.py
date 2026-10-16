import unittest
from datetime import datetime, timezone

from znak_orient.contracts import MEMORIA_STATES
from znak_orient.memoria import MemoriaCache, checkpoint_cache_key, memoria_cache_key


class MemoriaContractTests(unittest.TestCase):
    def test_memoria_states_are_closed_and_exact(self):
        self.assertEqual(MEMORIA_STATES, {"HIT", "MISS", "STALE", "CORRUPT", "PURGE"})

    def test_cache_key_is_deterministic_and_content_bound(self):
        digest = "a" * 64
        self.assertEqual(memoria_cache_key("source-a", digest), memoria_cache_key("source-a", digest))
        self.assertNotEqual(memoria_cache_key("source-a", digest), memoria_cache_key("source-b", digest))

    def test_checkpoint_key_and_round_trip_are_content_bound(self):
        checkpoint = {"checkpoint_id": "cp:test", "city_position": "A"}
        cache = MemoriaCache()
        self.assertEqual(checkpoint_cache_key(checkpoint), checkpoint_cache_key(checkpoint))
        cache.put_checkpoint(checkpoint, source_ids=["src-a"])
        self.assertEqual(cache.get_checkpoint(checkpoint)[0], "HIT")
        changed = {**checkpoint, "city_position": "B"}
        self.assertNotEqual(checkpoint_cache_key(checkpoint), checkpoint_cache_key(changed))
        self.assertEqual(cache.get_checkpoint(changed)[0], "MISS")

    def test_fail_receipt_purges_only_entries_backed_by_its_sources(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = MemoriaCache()
        cache.put("checkpoint", "a" * 64, {"x": 1}, source_ids=["src-fail"], now=now)
        cache.put("checkpoint", "b" * 64, {"x": 2}, source_ids=["src-pass"], now=now)
        self.assertEqual(cache.purge_for_receipt({"status": "FAIL", "source_ids": ["src-fail"]}), 1)
        self.assertEqual(cache.size, 1)
        self.assertEqual(cache.get("checkpoint", "b" * 64, now=now)[0], "HIT")

    def test_cache_reports_stale_and_miss_without_mutating_unrelated_entries(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = MemoriaCache(ttl_seconds=60)
        cache.put("checkpoint", "c" * 64, {"x": 3}, now=now)
        self.assertEqual(cache.get("checkpoint", "c" * 64, now=now)[0], "HIT")
        self.assertEqual(cache.get("checkpoint", "c" * 64, now=now.replace(minute=2))[0], "STALE")
        self.assertEqual(cache.get("checkpoint", "d" * 64, now=now)[0], "MISS")

    def test_metrics_cover_all_lifecycle_states_and_are_defensive(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = MemoriaCache(ttl_seconds=60)
        key = cache.put("checkpoint", "e" * 64, {"x": 5}, source_ids=["src-fail"], now=now)
        cache.get("checkpoint", "e" * 64, now=now)
        cache.get("checkpoint", "f" * 64, now=now)
        cache.get("checkpoint", "e" * 64, now=now.replace(minute=2))
        cache._entries[key].value = {"x": 6}
        cache.get("checkpoint", "e" * 64, now=now)
        cache.put("checkpoint", "b" * 64, {"x": 7}, source_ids=["src-fail"], now=now)
        cache.purge_for_receipt({"status": "FAIL", "source_ids": ["src-fail"]})
        self.assertEqual(cache.metrics, {"corrupt": 1, "hit": 1, "miss": 1, "purge": 2, "stale": 1})
        snapshot = cache.metrics
        snapshot["hit"] = 999
        self.assertEqual(cache.metrics["hit"], 1)

    def test_conflict_opened_marks_related_entries_disputed(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = MemoriaCache()
        cache.put("checkpoint", "f" * 64, {"x": 8}, source_ids=["src-conflict"], now=now)
        cache.put("checkpoint", "a" * 64, {"x": 9}, source_ids=["src-safe"], now=now)
        self.assertEqual(cache.mark_conflict_opened(["src-conflict"]), 1)
        self.assertEqual(cache.get("checkpoint", "f" * 64, now=now)[0], "DISPUTED")
        self.assertEqual(cache.get("checkpoint", "a" * 64, now=now)[0], "HIT")

    def test_material_state_change_purges_related_entries_only(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = MemoriaCache()
        cache.put("checkpoint", "1" * 64, {"x": 1}, source_ids=["src-state"], now=now)
        cache.put("checkpoint", "2" * 64, {"x": 2}, source_ids=["src-safe"], now=now)
        self.assertEqual(cache.purge_for_state_change(["src-state"], material=False), 0)
        self.assertEqual(cache.purge_for_state_change(["src-state"], material=True), 1)
        self.assertEqual(cache.get("checkpoint", "1" * 64, now=now)[0], "MISS")
        self.assertEqual(cache.get("checkpoint", "2" * 64, now=now)[0], "HIT")


if __name__ == "__main__":
    unittest.main()
