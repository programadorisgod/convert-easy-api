"""Behavior tests: blocking work must not run on the event loop.

The XML conversion strategies run subprocess and CPU-heavy work. That
must happen off the event loop (asyncio.to_thread), otherwise a single
conversion request freezes every other request in the process.
"""

import asyncio
import subprocess
import threading

from src.infrastructure.converters.xml.strategies.yaml_strategy import YamlStrategy

XML_CONTENT = b"<a><b>1</b></a>"


def test_yq_subprocess_runs_off_event_loop(monkeypatch):
    """subprocess.run must execute in a worker thread, never on the loop."""
    called_from_thread = []

    def fake_run(*args, **kwargs):
        # Record the thread id that ran the subprocess call.
        called_from_thread.append(threading.get_ident())
        return subprocess.CompletedProcess(args[0], 0, stdout="a: b\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    strategy = YamlStrategy()
    result = asyncio.run(
        strategy.convert(XML_CONTENT, {"indent": 2, "flow_style": False})
    )

    main_thread_id = threading.get_ident()
    assert len(called_from_thread) == 1
    # The subprocess call happened in a different thread than the test
    # (which runs on the event loop via asyncio.run).
    assert called_from_thread[0] != main_thread_id
    assert b"a: b" in result.content


def test_yaml_falls_back_to_pyyaml_without_yq(monkeypatch):
    """Without yq installed, conversion still works via pyyaml."""

    def missing_yq(*args, **kwargs):
        raise FileNotFoundError("yq not found")

    monkeypatch.setattr(subprocess, "run", missing_yq)

    strategy = YamlStrategy()
    result = asyncio.run(strategy.convert(XML_CONTENT, {"indent": 2}))

    assert b"b:" in result.content
    assert b"1" in result.content
