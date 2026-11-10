import os
import tempfile
import threading
import unittest
from unittest import mock

from ahflip import config, db, prices
from ahflip.web import jobs


class Stop(Exception):
    pass


def wait_idle(test):
    test.assertTrue(jobs.JOB.acquire(timeout=5))
    jobs.JOB.release()


class Jobs(unittest.TestCase):
    def setUp(self):
        jobs.STATE.update(job=None, error=None, last=None)
        self.addCleanup(jobs.STATE.update, {"job": None, "error": None, "last": None})

    def test_stamp(self):
        with mock.patch.object(jobs.time, "strftime", return_value="12:34"):
            self.assertEqual(jobs.stamp("hi"), "12:34 hi")

    def test_run_job_ok_and_busy(self):
        gate = threading.Event()

        def fn():
            self.assertEqual(jobs.STATE["job"], "test")
            gate.wait(5)
            return "done"

        self.assertTrue(jobs.run_job("test", fn))
        self.assertFalse(jobs.run_job("other", fn))  # one job at a time
        gate.set()
        wait_idle(self)
        self.assertTrue(jobs.STATE["last"].endswith(" done"))
        self.assertIsNone(jobs.STATE["error"])
        self.assertIsNone(jobs.STATE["job"])

    def test_run_job_error(self):
        jobs.STATE["error"] = "old"

        def fn():
            raise RuntimeError("boom")

        with mock.patch("sys.stderr"):
            self.assertTrue(jobs.run_job("test", fn))
            wait_idle(self)
        self.assertTrue(jobs.STATE["error"].endswith("test failed: boom"))
        self.assertIsNone(jobs.STATE["job"])

    def test_start_snapshot_and_retry(self):
        with mock.patch.object(jobs, "blizzard") as bz:
            bz.snap.return_value = "snap ok"
            bz.retry.return_value = "retry ok"
            self.assertTrue(jobs.start_snapshot({"rs": 1, "house": 113}))
            wait_idle(self)
            bz.snap.assert_called_once_with(1, 113)
            self.assertTrue(jobs.STATE["last"].endswith("snap ok"))
            self.assertTrue(jobs.start_retry())
            wait_idle(self)
            bz.retry.assert_called_once_with()
            self.assertTrue(jobs.STATE["last"].endswith("retry ok"))

    def test_check_scans(self):
        s = {"house": 113}
        with (
            mock.patch.object(jobs.scans, "changed", return_value=[("addon", "a.lua"), ("scan", "s.lua")]),
            mock.patch.object(jobs.scans, "import_one", side_effect=["imported 5", RuntimeError("bad file")]) as imp,
            mock.patch.object(jobs.scans, "mark_seen") as seen,
        ):
            jobs.check_scans(s)
        imp.assert_any_call(s, "addon", "a.lua")
        seen.assert_called_once_with("scan", "s.lua")
        self.assertTrue(jobs.STATE["last"].endswith("imported 5"))
        self.assertTrue(jobs.STATE["error"].endswith("Auctionator scan import failed: bad file"))


class Scheduler(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, path)
        for p in (mock.patch.object(config, "DB_PATH", path), mock.patch.object(jobs.blizzard, "configured", return_value=True)):
            p.start()
            self.addCleanup(p.stop)

    def run_scheduler(self, times, check=None):
        """Run the loop once per entry in times (time.time values), then stop it."""
        with (
            mock.patch.object(jobs, "time") as t,
            mock.patch.object(jobs, "check_scans", side_effect=check) as cs,
            mock.patch.object(jobs, "start_snapshot") as snap,
            mock.patch.object(jobs, "start_retry") as retry,
            mock.patch("sys.stderr") as err,
        ):
            t.sleep.side_effect = [None] * len(times) + [Stop()]
            t.time.side_effect = times
            with self.assertRaises(Stop):
                jobs.scheduler()
        return cs, snap, retry, err

    def test_snapshot_due(self):
        _, snap, retry, _ = self.run_scheduler([600])  # never attempted: last = 0
        snap.assert_called_once()
        retry.assert_not_called()

    def test_no_api_keys_scans_only(self):
        with mock.patch.object(jobs.blizzard, "configured", return_value=False):
            cs, snap, retry, _ = self.run_scheduler([600])
        cs.assert_called_once()
        snap.assert_not_called()
        retry.assert_not_called()

    def test_snapshot_not_due_retry_due(self):
        with db.session() as c:
            prices.store(c, 113, {1: (10, 1)}, 1000, "addon")  # last falls back to the newest snapshot
            db.set_meta(c, "retried", 0)
            db.save_settings(c, {"snap_minutes": 1440})
        _, snap, retry, _ = self.run_scheduler([1100, 24 * 3600])
        snap.assert_not_called()
        retry.assert_called_once()

    def test_nothing_due(self):
        with db.session() as c:
            db.save_settings(c, {"snap_minutes": 0})
            db.set_meta(c, "attempt:113", 50)
            db.set_meta(c, "retried", 100)
        cs, snap, retry, _ = self.run_scheduler([200])
        cs.assert_called_once()
        snap.assert_not_called()
        retry.assert_not_called()

    def test_error_keeps_running(self):
        cs, snap, _, err = self.run_scheduler([1, 2], check=RuntimeError("disk"))
        self.assertEqual(cs.call_count, 2)
        snap.assert_not_called()
        self.assertIn("scheduler: disk", "".join(c.args[0] for c in err.write.call_args_list))


if __name__ == "__main__":
    unittest.main()
