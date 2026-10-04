"""The keep-alive wrapper must never guess a lock and never retry a dead run."""
import json
import os
import socket
import subprocess
import sys

import pytest
import retrieval_harness_keepalive as K


def make_run(tmp_path, monkeypatch, expected=3):
    monkeypatch.setattr(K, 'RUNS', tmp_path)
    out = tmp_path / 'r'
    (out / 'shards').mkdir(parents=True)
    (out / 'plan.json').write_text(json.dumps({'expected_shards': expected}), encoding='utf-8')
    return out


def lock(out, pid, host=None):
    (out / 'writer.lock').write_text(json.dumps({'pid': pid, 'host': host or socket.gethostname()}), encoding='utf-8')


def test_pid_alive_sees_self_and_not_a_dead_pid():
    assert K.pid_alive(os.getpid())
    assert not K.pid_alive(2 ** 22 + 12345)


def test_lock_of_dead_pid_on_this_host_is_removed(tmp_path, monkeypatch, capsys):
    out = make_run(tmp_path, monkeypatch)
    lock(out, 2 ** 22 + 12345)
    K.recover_lock(out, None, True)
    assert not (out / 'writer.lock').exists()
    assert json.loads(capsys.readouterr().out.strip())['phase'] == 'lock_removed'


def test_lock_of_live_pid_is_kept(tmp_path, monkeypatch):
    out = make_run(tmp_path, monkeypatch)
    lock(out, os.getpid())
    with pytest.raises(SystemExit):
        K.recover_lock(out, None, True)
    assert (out / 'writer.lock').exists()


def test_lock_of_other_host_is_kept(tmp_path, monkeypatch):
    out = make_run(tmp_path, monkeypatch)
    lock(out, 2 ** 22 + 12345, host='elsewhere')
    with pytest.raises(SystemExit):
        K.recover_lock(out, None, True)
    assert (out / 'writer.lock').exists()


def test_recovery_off_never_removes(tmp_path, monkeypatch):
    out = make_run(tmp_path, monkeypatch)
    lock(out, 2 ** 22 + 12345)
    with pytest.raises(SystemExit):
        K.recover_lock(out, None, False)
    assert (out / 'writer.lock').exists()


def test_own_exited_child_lock_is_removed_even_with_recovery_off(tmp_path, monkeypatch):
    out = make_run(tmp_path, monkeypatch)
    lock(out, 4242)
    K.recover_lock(out, 4242, False)
    assert not (out / 'writer.lock').exists()


class FakeChild:
    def __init__(self, lines, code=1):
        self.stdout = iter(lines)
        self.code = code
        self.pid = 99

    def wait(self):
        return self.code


def test_no_progress_exit_is_not_relaunched(tmp_path, monkeypatch, capsys):
    out = make_run(tmp_path, monkeypatch)
    launches = []
    monkeypatch.setattr(K, 'launch_child', lambda *a: launches.append(a) or FakeChild(['Traceback: frozen input changed\n']))
    monkeypatch.setattr(K, 'keep_awake', lambda on: True)
    assert K.start('r', 1, K.ROOT / 'tools/retrieval_harness.py', 50, True) == 2
    assert len(launches) == 1
    assert 'no_progress' in capsys.readouterr().out


def test_progress_then_crash_relaunches_and_complete_stops(tmp_path, monkeypatch, capsys):
    out = make_run(tmp_path, monkeypatch)
    launches = []

    def launch(*a):
        launches.append(a)
        n = len(launches)
        (out / 'shards' / f'case_{n}__policy_00000.json').write_text('{}', encoding='utf-8')
        if n == 1:
            return FakeChild([json.dumps({'phase': 'progress', 'completed_shards': 1, 'expected_shards': 3, 'errors': 0}) + '\n'], code=-1)
        (out / 'status.json').write_text(json.dumps({'status': 'complete', 'completed_shards': 3}), encoding='utf-8')
        return FakeChild([json.dumps({'phase': 'progress', 'completed_shards': 3, 'expected_shards': 3, 'errors': 0}) + '\n'], code=0)

    monkeypatch.setattr(K, 'launch_child', launch)
    monkeypatch.setattr(K, 'keep_awake', lambda on: True)
    monkeypatch.setattr(K.time, 'sleep', lambda s: None)
    assert K.start('r', 1, K.ROOT / 'tools/retrieval_harness.py', 50, True) == 0
    assert len(launches) == 2
    beat = json.loads((out / 'heartbeat.json').read_text(encoding='utf-8'))
    assert beat['relaunches'] == 1 and beat['completed_shards'] == 3


def test_same_shard_failing_twice_stops_after_one_relaunch(tmp_path, monkeypatch, capsys):
    out = make_run(tmp_path, monkeypatch)
    launches = []

    def launch(*a):
        launches.append(a)
        (out / 'shards' / f'case_{len(launches)}__policy_00000.json').write_text('{}', encoding='utf-8')
        (out / 'status.json').write_text(json.dumps({'status': 'failed', 'errors': [{'case_id': 'case_x', 'policy_index': 7, 'error': 'x'}]}), encoding='utf-8')
        return FakeChild([], code=1)

    monkeypatch.setattr(K, 'launch_child', launch)
    monkeypatch.setattr(K, 'keep_awake', lambda on: True)
    monkeypatch.setattr(K.time, 'sleep', lambda s: None)
    assert K.start('r', 1, K.ROOT / 'tools/retrieval_harness.py', 50, True) == 1
    assert len(launches) == 2


def has_console():
    if os.name != 'nt':
        return False
    import ctypes
    return bool(ctypes.windll.kernel32.GetConsoleWindow())


@pytest.mark.skipif(not has_console(), reason='Ctrl-Break needs an attached Windows console (not mintty/Git Bash)')
def test_bootstrap_maps_ctrl_break_to_keyboard_interrupt(tmp_path):
    script = tmp_path / 'sleeper.py'
    script.write_text('import time\ntry:\n    time.sleep(30)\nexcept KeyboardInterrupt:\n    print("interrupted", flush=True)\n', encoding='utf-8')
    boot = ('import os, signal, sys; '
            'hasattr(signal, "SIGBREAK") and signal.signal(signal.SIGBREAK, signal.default_int_handler); '
            'sys.argv = sys.argv[1:]; __file__ = sys.argv[0]; sys.path.insert(0, os.path.dirname(__file__)); '
            'exec(compile(open(__file__, encoding="utf-8").read(), __file__, "exec"))')
    child = subprocess.Popen([sys.executable, '-c', boot, str(script)], stdout=subprocess.PIPE, text=True,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    import time
    time.sleep(2)
    K.interrupt(child)
    out, _ = child.communicate(timeout=20)
    assert 'interrupted' in out
