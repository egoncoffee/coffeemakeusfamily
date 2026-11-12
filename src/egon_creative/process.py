import json
from pathlib import Path
import signal
import subprocess
import time


class Deadline:
    """One wall-clock budget for all subprocesses in an attempt, including retries."""
    def __init__(self, seconds):
        self.started = time.monotonic()
        self.ends = self.started + seconds

    def remaining(self):
        remaining = self.ends - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Bounded local production deadline exceeded")
        return remaining

    @property
    def elapsed(self):
        return time.monotonic() - self.started

    def run(self, args, log=None):
        # Arguments are a list, never shell interpolation. Logs must not include credentials.
        handle = Path(log).open("ab") if log else subprocess.DEVNULL
        proc = subprocess.Popen([str(x) for x in args], stdout=handle, stderr=handle, start_new_session=True)
        try:
            code = proc.wait(timeout=self.remaining())
            if code:
                raise RuntimeError(f"{Path(str(args[0])).name} failed ({code}); see local job log")
        except BaseException:
            if proc.poll() is None:
                proc.kill() if not hasattr(signal, "SIGKILL") else __import__("os").killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise
        finally:
            if log:
                handle.close()


def probe(ffprobe, path, deadline=None):
    result = subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                            check=True, capture_output=True, text=True,
                            timeout=min(30, deadline.remaining()) if deadline else 30)
    return json.loads(result.stdout)
