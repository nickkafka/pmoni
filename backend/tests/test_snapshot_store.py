import unittest

from app.infrastructure.snapshot_store import InMemorySnapshotStore


class InMemorySnapshotStoreTests(unittest.TestCase):
    def test_returns_the_stored_capture(self) -> None:
        store = InMemorySnapshotStore()

        store.put(1, "261143", b"jpeg")

        self.assertEqual(store.get(1, "261143"), b"jpeg")

    def test_separates_devices_that_reuse_a_serial(self) -> None:
        store = InMemorySnapshotStore()

        store.put(1, "100", b"portaria")
        store.put(2, "100", b"saida")

        self.assertEqual(store.get(1, "100"), b"portaria")
        self.assertEqual(store.get(2, "100"), b"saida")

    def test_reports_a_capture_it_never_received(self) -> None:
        self.assertIsNone(InMemorySnapshotStore().get(1, "404"))

    def test_discards_the_oldest_when_full(self) -> None:
        store = InMemorySnapshotStore(capacity=2)

        store.put(1, "a", b"1")
        store.put(1, "b", b"2")
        store.put(1, "c", b"3")

        self.assertIsNone(store.get(1, "a"))
        self.assertEqual(store.get(1, "c"), b"3")

    def test_rejects_a_capacity_that_stores_nothing(self) -> None:
        with self.assertRaises(ValueError):
            InMemorySnapshotStore(capacity=0)
