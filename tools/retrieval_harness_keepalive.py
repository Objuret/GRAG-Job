"""Keep a retrieval-harness run going across crashes, sleeps and lost sessions.

This wrapper never touches the runner's files or its plan hashes. It starts
`tools/retrieval_harness.py run` as a child in its own process group, keeps the
machine from idle-sleeping while the child runs, tees the child's output to
run.log, writes heartbeat.json with the shard rate and an estimated finish, and
relaunches the child if it exits without a final status (a crash, a kill). A
child that ends with status "failed" stops the loop; a run that ends "complete"
stops it too.

Lock contract of this wrapper (stricter than a human, looser than the runner):
the runner refuses to start over an existing writer.lock. The wrapper removes a
lock only when (a) the lock names this host and (b) the recorded PID is not a
running process, or the PID is the wrapper's own child that has already exited.
Every removal is printed with the lock's contents. `--no-lock-recovery` turns
this off. PID reuse on Windows is possible; a live process with that PID whose
image is not python.exe is treated as dead.

Stop: `python tools/retrieval_harness_keepalive.py stop --run NAME` writes a
STOP file; the wrapper sends Ctrl-Break to the child's group, the runner's own
finally-block removes the lock, in-flight shards finish or are left as orphan
.npz files the runner adopts on resume, and the wrapper exits without relaunch.

Detached start (survives the terminal or editor closing):
  powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath .venv\\Scripts\\python.exe -ArgumentList '-B','-X','utf8','tools\\retrieval_harness_keepalive.py','start','--run','NAME','--workers','4'"
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'output/research/retrieval-harness-runs'
PYTHON = Path(sys.executable)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def now():
    return datetime.now(timezone.utc)


def keep_awake(on):
    if os.name != 'nt':
        return False
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
    return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))


def pid_alive(pid):
    """True when a python.exe process with this PID is running on this host."""
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return False
        size = ctypes.c_ulong(1024)
        name = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            return True
        return Path(name.value).name.lower().startswith('python')
    finally:
        kernel32.CloseHandle(handle)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def run_dir(name):
    path = RUNS / name
    if not (path / 'plan.json').exists():
        raise SystemExit(f'no run named {name!r} under {RUNS}')
    return path


def recover_lock(out, own_child_pid, allow):
    lock = out / 'writer.lock'
    if not lock.exists():
        return
    info = read_json(lock) or {}
    pid, host = info.get('pid'), info.get('host')
    reason = None
    if pid == own_child_pid:
        reason = 'lock belongs to this wrapper\'s exited child'
    elif not allow:
        raise SystemExit(f'writer.lock present and lock recovery disabled: {info}')
    elif host != socket.gethostname():
        raise SystemExit(f'writer.lock names another host, not touching it: {info}')
    elif isinstance(pid, int) and not pid_alive(pid):
        reason = 'lock names a PID that is not a running python process on this host'
    else:
        raise SystemExit(f'writer.lock names a live process, not touching it: {info}')
    print(json.dumps({'phase': 'lock_removed', 'reason': reason, 'lock': info, 'utc': now().isoformat()}), flush=True)
    lock.unlink()


class Heartbeat:
    def __init__(self, out, expected, window_s=600):
        self.path = out / 'heartbeat.json'
        self.expected = expected
        self.window = window_s
        self.samples = []  # (monotonic, completed)
        self.started = now()
        self.relaunches = 0
        self.last_write = 0.

    def update(self, completed, force=False):
        t = time.monotonic()
        self.samples.append((t, completed))
        while self.samples and t - self.samples[0][0] > self.window:
            self.samples.pop(0)
        if not force and t - self.last_write < 15:
            return
        rate = None
        if len(self.samples) >= 2 and self.samples[-1][0] > self.samples[0][0]:
            rate = (self.samples[-1][1] - self.samples[0][1]) / (self.samples[-1][0] - self.samples[0][0])
        remaining = self.expected - completed
        eta = None if not rate else (now() + timedelta(seconds=remaining / rate)).isoformat()
        write_json(self.path, {
            'utc': now().isoformat(), 'wrapper_started_utc': self.started.isoformat(),
            'completed_shards': completed, 'expected_shards': self.expected,
            'shards_per_second_last_10min': None if rate is None else round(rate, 3),
            'estimated_finish_utc': eta,
            'hours_remaining': None if not rate else round(remaining / rate / 3600, 2),
            'relaunches': self.relaunches, 'wrapper_pid': os.getpid()})
        self.last_write = t


def launch_child(out, name, workers, runner, log):
    # The runner file is hashed into the plan and must not change; a bootstrap in
    # front of it maps Ctrl-Break (the only console signal a new process group
    # accepts) to KeyboardInterrupt so the runner's own finally-block runs.
    # The runner's code is executed inside the real __main__ with __file__ set, so
    # multiprocessing's spawn re-imports the runner in the workers as usual.
    boot = ('import os, signal, sys; '
            'hasattr(signal, "SIGBREAK") and signal.signal(signal.SIGBREAK, signal.default_int_handler); '
            'sys.argv = sys.argv[1:]; __file__ = sys.argv[0]; sys.path.insert(0, os.path.dirname(__file__)); '
            'exec(compile(open(__file__, encoding="utf-8").read(), __file__, "exec"))')
    cmd = [str(PYTHON), '-B', '-X', 'utf8', '-c', boot, str(runner), 'run', '--run', name, '--workers', str(workers)]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    log.write(f'\n# launch {now().isoformat()} {" ".join(cmd)}\n'); log.flush()
    return subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', bufsize=1, creationflags=flags)


def interrupt(child):
    if os.name == 'nt':
        child.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        child.send_signal(signal.SIGINT)


def start(name, workers, runner, max_relaunches, lock_recovery):
    out = run_dir(name)
    plan = read_json(out / 'plan.json')
    expected = plan['expected_shards']
    stop_file = out / 'STOP'
    if stop_file.exists():
        stop_file.unlink()
    log = (out / 'run.log').open('a', encoding='utf-8')
    hb = Heartbeat(out, expected)
    write_json(out / 'keepalive.json', {'wrapper_pid': os.getpid(), 'host': socket.gethostname(),
                                        'started_utc': now().isoformat(), 'workers': workers, 'runner': str(runner)})
    awake = keep_awake(True)
    print(json.dumps({'phase': 'keepalive_start', 'run': name, 'workers': workers, 'keep_awake': awake, 'log': str(out / 'run.log')}), flush=True)
    last_child_pid = None
    last_failure = None
    backoff = 10
    try:
        while True:
            recover_lock(out, last_child_pid, lock_recovery)
            markers_before = len(list((out / 'shards').glob('*.json')))
            child = launch_child(out, name, workers, runner, log)
            last_child_pid = child.pid
            completed = markers_before
            hb.update(completed, force=True)
            stopping = False
            for line in child.stdout:
                log.write(line)
                log.flush()
                if line.startswith('{"phase": "progress"'):
                    try:
                        completed = json.loads(line)['completed_shards']
                    except ValueError:
                        pass
                    hb.update(completed)
                if stop_file.exists() and not stopping:
                    stopping = True
                    log.write(f'# stop requested {now().isoformat()}\n'); log.flush()
                    interrupt(child)
            code = child.wait()
            log.flush()
            hb.update(completed, force=True)
            status = read_json(out / 'status.json') or {}
            fresh = status and (out / 'status.json').stat().st_mtime >= time.time() - 120
            if stopping:
                print(json.dumps({'phase': 'stopped', 'exit_code': code, 'completed_shards': completed}), flush=True)
                return 0
            if fresh and status.get('status') == 'complete':
                print(json.dumps({'phase': 'complete', 'completed_shards': status.get('completed_shards')}), flush=True)
                return 0
            if fresh and status.get('status') == 'failed':
                # The runner marks the whole run failed on one shard's exception. A
                # transient error deserves one more try; the same shard failing
                # twice in a row is deterministic and stops the loop.
                key = tuple(sorted((e.get('case_id'), e.get('policy_index')) for e in status.get('errors', [])))
                if key == last_failure:
                    print(json.dumps({'phase': 'failed', 'errors': status.get('errors'), 'note': 'same shard failed twice; not relaunching'}), flush=True)
                    return 1
                last_failure = key
                log.write(f'# shard failure {status.get("errors")}; one relaunch\n'); log.flush()
            markers = len(list((out / 'shards').glob('*.json')))
            if markers <= markers_before:
                # A deterministic failure (changed input hash, corrupt shard, runtime
                # mismatch) exits without progress; retrying it would only re-hash.
                print(json.dumps({'phase': 'no_progress', 'exit_code': code, 'completion_markers': markers,
                                  'note': 'child exited without completing a shard; not relaunching. See run.log.'}), flush=True)
                return 2
            hb.relaunches += 1
            if hb.relaunches > max_relaunches:
                print(json.dumps({'phase': 'gave_up', 'relaunches': hb.relaunches, 'exit_code': code}), flush=True)
                return 2
            log.write(f'# child exited {code} without a final status; relaunch {hb.relaunches} in {backoff}s\n'); log.flush()
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
    finally:
        keep_awake(False)
        log.close()


def stop(name):
    out = run_dir(name)
    (out / 'STOP').write_text(now().isoformat(), encoding='utf-8')
    print(json.dumps({'phase': 'stop_requested', 'run': name, 'note': 'wrapper interrupts the child; watch heartbeat.json / status.json'}))


def show(name):
    out = run_dir(name)
    print(json.dumps({'heartbeat': read_json(out / 'heartbeat.json'), 'status': read_json(out / 'status.json'),
                      'writer_lock': read_json(out / 'writer.lock'), 'keepalive': read_json(out / 'keepalive.json'),
                      'completion_markers': len(list((out / 'shards').glob('*.json')))}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('start'); p.add_argument('--run', required=True); p.add_argument('--workers', type=int, default=4)
    p.add_argument('--runner', type=Path, default=ROOT / 'tools/retrieval_harness.py')
    p.add_argument('--max-relaunches', type=int, default=50); p.add_argument('--no-lock-recovery', action='store_true')
    p = sub.add_parser('stop'); p.add_argument('--run', required=True)
    p = sub.add_parser('show'); p.add_argument('--run', required=True)
    args = parser.parse_args()
    if args.command == 'start':
        sys.exit(start(args.run, args.workers, args.runner.resolve(), args.max_relaunches, not args.no_lock_recovery))
    elif args.command == 'stop':
        stop(args.run)
    else:
        show(args.run)


if __name__ == '__main__':
    main()
