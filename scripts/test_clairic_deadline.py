"""Offline POSIX deadline regression; no provider calls."""

import signal
import threading
import time
import unittest

import clairic_smoke as smoke


@unittest.skipUnless(hasattr(signal, "setitimer"), "POSIX timers required")
class TotalDeadlineTests(unittest.TestCase):
    def test_trickling_work_cannot_extend_total_deadline(self):
        previous = signal.getsignal(signal.SIGALRM)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            with smoke.total_deadline(0.05):
                for _ in range(1000):
                    time.sleep(0.01)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0, 0))

    def test_success_and_exception_restore_handler(self):
        previous = signal.getsignal(signal.SIGALRM)
        with smoke.total_deadline(1):
            pass
        with self.assertRaises(ValueError):
            with smoke.total_deadline(1):
                raise ValueError("synthetic failure")
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0, 0))

    def test_existing_timer_is_not_overwritten(self):
        with smoke.total_deadline(2):
            with self.assertRaises(smoke.DeadlineUnavailable):
                with smoke.total_deadline(1):
                    self.fail("nested timer was installed")
            self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0], 0)

    def test_worker_thread_refuses_before_operation(self):
        outcomes = []

        def worker():
            try:
                with smoke.total_deadline(1):
                    outcomes.append("entered")
            except smoke.DeadlineUnavailable:
                outcomes.append("refused")

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcomes, ["refused"])


if __name__ == "__main__":
    unittest.main()
