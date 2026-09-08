import os

import pytest  # noqa: F401

from aider.run_cmd import PROVIDER_ENV_KEYS, child_process_environ, run_cmd


def test_run_cmd_echo():
    command = "echo HelloWorld"
    exit_code, output = run_cmd(command)

    assert exit_code == 0
    assert "HelloWorld" in output



def test_child_process_environ_scrubs_provider_keys():
    """Issue #5658: child commands must not inherit provider credentials."""
    base = {
        "PATH": "/usr/bin",
        "OPENAI_API_KEY": "aider-provider-sentinel",
        "ANTHROPIC_API_KEY": "secret",
        "HOME": "/tmp",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
        "KEEP_ME": "yes",
    }
    scrubbed = child_process_environ(base=base)
    assert scrubbed["PATH"] == "/usr/bin"
    assert scrubbed["KEEP_ME"] == "yes"
    assert scrubbed["HOME"] == "/tmp"
    for key in PROVIDER_ENV_KEYS:
        assert key not in scrubbed
    # Extra overlays must win (e.g. GIT_EDITOR for /git).
    with_extra = child_process_environ(base=base, extra={"GIT_EDITOR": "true"})
    assert with_extra["GIT_EDITOR"] == "true"
    assert "OPENAI_API_KEY" not in with_extra


def test_run_cmd_subprocess_does_not_expose_openai_key(monkeypatch):
    """Presence-only check: /run-style subprocess must not see OPENAI_API_KEY."""
    monkeypatch.setenv("OPENAI_API_KEY", "aider-provider-sentinel")
    # Force subprocess path (no interactive pexpect).
    monkeypatch.setattr("aider.run_cmd.sys.stdin.isatty", lambda: False)
    if os.name == "nt":
        command = 'python -c "import os,sys; sys.exit(0 if os.environ.get(\'OPENAI_API_KEY\') else 1)"'
    else:
        command = 'test -n "$OPENAI_API_KEY"'
    exit_code, _output = run_cmd(command)
    # Key scrubbed => Windows python exits 1; Unix test -n fails with 1.
    assert exit_code != 0
