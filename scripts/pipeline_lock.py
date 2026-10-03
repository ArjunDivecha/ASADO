"""Shared exclusion for ASADO daily/monthly producers and repair publication."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import sys

LOCK_PATH = Path(__file__).resolve().parents[1] / 'Data' / '.pipeline.lock'
ENV_FD = 'ASADO_PIPELINE_LOCK_FD'

@contextmanager
def pipeline_lock(path=LOCK_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    inherited = os.environ.get(ENV_FD)
    if inherited is not None:
        fd = int(inherited)
        stat = os.fstat(fd)
        expected = path.stat()
        if (stat.st_dev, stat.st_ino) != (expected.st_dev, expected.st_ino):
            raise RuntimeError('Invalid inherited ASADO pipeline lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
        return
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another ASADO producer or repair holds the pipeline lock') from exc
        yield handle.fileno()

if __name__ == '__main__':
    command = sys.argv[1:]
    if not command:
        raise SystemExit('Usage: pipeline_lock.py COMMAND [ARGS...]')
    with pipeline_lock() as fd:
        os.set_inheritable(fd, True)
        env = dict(os.environ, ASADO_PIPELINE_LOCK_FD=str(fd))
        os.execvpe(command[0], command, env)
