#!/usr/bin/env python3
"""Unit test for apps-update: apps that are still to be installed once are
retried within the same run (no restart needed), others are left alone.

    python3 tests/test_apps_update.py
"""
import importlib.machinery
import importlib.util
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "packages", "raiden-apps", "root",
                      "usr", "libexec", "raiden-os", "apps-update")
loader = importlib.machinery.SourceFileLoader("apps_update", SCRIPT)
spec = importlib.util.spec_from_loader("apps_update", loader)
au = importlib.util.module_from_spec(spec)
loader.exec_module(au)


class Fake:
    """A computer that is offline for OFFLINE tries, then installs everything."""

    def __init__(self, offline, installed=(), removed=()):
        self.tmp = tempfile.mkdtemp()
        au.STATE = os.path.join(self.tmp, "state")
        au.STATUS_FILE = os.path.join(self.tmp, "run", "status")
        os.makedirs(au.STATE)
        for app in removed:
            open(os.path.join(au.STATE, app), "w").close()
        self.installed = set(installed)
        self.offline = offline
        self.passes = []
        self.sleeps = []
        self.statuses = []
        au.installed_release = lambda app: "1.0" if app in self.installed else None
        au.online = lambda: self.offline <= 0
        au.time.sleep = self.sleep
        au.check_once = self.check_once
        real_set_status = au.set_status
        au.set_status = lambda text: (self.statuses.append(text), real_set_status(text))

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.offline -= 1

    def check_once(self, only=None):
        self.passes.append(None if only is None else sorted(only))
        if self.offline <= 0:
            for app in (only or au.APPS):
                if au.APPS[app]["kind"] != "deb":
                    self.installed.add(app)
        return []


def test_retries_until_online():
    f = Fake(offline=3)
    au.check()
    assert not au.pending(), au.pending()
    assert f.passes[0] is None                          # the full pass first
    assert len(f.passes) == 4, f.passes                 # then a retry per wait
    assert f.sleeps == [30, 60, 120], f.sleeps          # backing off
    assert "Waiting for an internet connection" in f.statuses
    assert f.statuses[-1] == ""                         # status cleared at the end
    assert open(au.STATUS_FILE).read() == "\n"


def test_nothing_pending_no_wait():
    f = Fake(offline=0)
    au.check()
    assert f.sleeps == [] and len(f.passes) == 1


def test_removed_apps_stay_removed():
    removed = [a for a in au.APPS if au.APPS[a]["kind"] != "deb"]
    f = Fake(offline=99, removed=removed)
    assert au.pending() == []
    au.check()
    assert f.sleeps == [], f.sleeps


def test_gives_up_after_deadline():
    f = Fake(offline=10 ** 9)
    au.RETRY_FOR = 0
    try:
        au.check()
    finally:
        au.RETRY_FOR = 6 * 3600
    assert len(f.passes) == 1 and au.pending()


def test_pending_skips_heroic():
    Fake(offline=0)
    assert "heroic" not in au.pending()
    assert "claude" in au.pending()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
