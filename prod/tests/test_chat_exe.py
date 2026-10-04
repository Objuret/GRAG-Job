"""`chat._resolve_claude_exe`: an npm `.cmd` shim resolves to the native binary it wraps (cmd.exe
cuts a multi-line argv element at its first newline, so the shim cannot carry a system prompt);
a bare exe and an absent binary are left as they were."""
from pathlib import Path

from harness import chat


def test_cmd_shim_resolves_to_native_binary(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off\r\n", encoding="ascii")
    native = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"MZ")
    monkeypatch.setattr(chat.shutil, "which", lambda name: str(shim))
    assert chat._resolve_claude_exe() == str(native)


def test_cmd_shim_without_native_binary_is_kept(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off\r\n", encoding="ascii")
    monkeypatch.setattr(chat.shutil, "which", lambda name: str(shim))
    assert chat._resolve_claude_exe() == str(shim)


def test_native_exe_on_path_is_kept(tmp_path, monkeypatch):
    exe = tmp_path / "claude.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(chat.shutil, "which", lambda name: str(exe))
    assert chat._resolve_claude_exe() == str(exe)


def test_nothing_on_path_falls_back_to_local_bin(monkeypatch):
    monkeypatch.setattr(chat.shutil, "which", lambda name: None)
    assert chat._resolve_claude_exe().endswith(str(Path(".local") / "bin" / "claude.exe"))
