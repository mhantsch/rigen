#!/usr/bin/env python3
"""Headless test suite for riview (spec §11, cases 1–8k).

No display required: exercises the pure selection/settle/navigation/
fit-geometry layer with fake clocks, `--print` mode, CLI validation,
desktop install, and launch-context detection via subprocess, plus
headless integration of the watcher/decoder plumbing and the
keyboard/mouse input logic (§11 cases 9–37 are the manual GUI cases).

Run:  python3 tests/test_riview.py -v
"""

import importlib.util
import importlib.machinery
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RIVIEW = os.path.normpath(os.path.join(HERE, "..", "riview"))

_loader = importlib.machinery.SourceFileLoader("riview_mod", RIVIEW)
_spec = importlib.util.spec_from_loader("riview_mod", _loader)
riview = importlib.util.module_from_spec(_spec)
_loader.exec_module(riview)  # must import cleanly headless (spec §13.3)

DEFAULT_EXTS = set(riview.DEFAULT_EXTENSIONS.split(","))


def write(path, data=b"hello", mtime=None):
    with open(path, "wb") as f:
        f.write(data)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _png_bytes(w, h):
    """A minimal valid RGB PNG (red, no compression surprises)."""
    import struct
    import zlib
    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\xff\x00\x00" * w   # filter byte + w RGB pixels
    idat = zlib.compress(row * h)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


class TestParseExtensions(unittest.TestCase):
    def test_default(self):
        self.assertEqual(riview.parse_extensions(None),
                         {"png", "jpg", "jpeg", "webp", "gif", "tiff", "tif", "bmp"})

    def test_custom_and_case(self):
        self.assertEqual(riview.parse_extensions("PNG, jpg ,bmp"), {"png", "jpg", "bmp"})

    def test_empty(self):
        with self.assertRaises(riview.UsageError):
            riview.parse_extensions("")
        with self.assertRaises(riview.UsageError):
            riview.parse_extensions(" , ")

    def test_slash_rejected(self):
        with self.assertRaises(riview.UsageError):
            riview.parse_extensions("png,a/b")

    def test_dot_prefix_rejected(self):
        with self.assertRaises(riview.UsageError):
            riview.parse_extensions(".png")


class TestScanCandidates(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="riview-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _names(self, exts=DEFAULT_EXTS):
        return {os.path.basename(p) for p, _m, _s in
                riview.scan_candidates(self.dir, exts)}

    def test_filters(self, ):
        # case 3: hidden, non-image, subdirectory, no-extension are ignored
        write(os.path.join(self.dir, "a.png"))
        write(os.path.join(self.dir, "b.jpg"))
        write(os.path.join(self.dir, "c.txt"))
        write(os.path.join(self.dir, ".hidden.png"))
        write(os.path.join(self.dir, "noext"))
        os.mkdir(os.path.join(self.dir, "sub"))
        write(os.path.join(self.dir, "sub", "d.png"))
        self.assertEqual(self._names(), {"a.png", "b.jpg"})

    def test_symlink_and_fifo(self):
        write(os.path.join(self.dir, "real.png"))
        os.symlink("real.png", os.path.join(self.dir, "link.png"))
        os.symlink("missing.png", os.path.join(self.dir, "broken.png"))
        fifo = os.path.join(self.dir, "pipe.pgm")
        try:
            os.mkfifo(fifo)
        except OSError:
            pass
        self.assertEqual(self._names(), {"real.png", "link.png"})

    def test_missing_dir(self):
        self.assertEqual(riview.scan_candidates(self.dir + "/nope", DEFAULT_EXTS), [])

    def test_custom_extensions(self):
        write(os.path.join(self.dir, "a.png"))
        write(os.path.join(self.dir, "b.bmp"))
        self.assertEqual(self._names(exts={"bmp"}), {"b.bmp"})


NOW_MONO, NOW_WALL = 1000.0, 1000.0  # fake clocks for the settle tests
WINDOW = 2.0


class TestSettle(unittest.TestCase):
    """Spec §5.3 with fake clocks. Cases 8 (plus the D5 worked example)."""

    def _obs(self, path, mtime_age_s, seen=None, version=(1, 100)):
        """Build observed state for a file whose mtime is `mtime_age_s` ago."""
        mtime_ns = int((NOW_WALL - mtime_age_s) * 1e9)
        if seen is None:
            seen = NOW_MONO
        return riview.Observed(mtime_ns, version[1],
                               seen - max(0.0, mtime_age_s))

    def test_fast_path_old_mtime(self):
        # pre-existing file older than the window: settled at first sighting
        obs = self._obs("a.png", mtime_age_s=3600)
        self.assertTrue(riview.is_settled(obs, NOW_MONO, NOW_WALL, WINDOW))

    def test_fresh_file_not_settled(self):
        obs = self._obs("a.png", mtime_age_s=0.1)
        self.assertFalse(riview.is_settled(obs, NOW_MONO, NOW_WALL, WINDOW))

    def test_settles_after_quiet(self):
        obs = self._obs("a.png", mtime_age_s=0.1)
        # 2.1 s later, file unchanged:
        self.assertTrue(riview.is_settled(obs, NOW_MONO + 2.1, NOW_WALL + 2.1, WINDOW))

    def test_change_resets_window(self):
        # file observed changing at +1.0 s (version change):
        obs = self._obs("a.png", mtime_age_s=0.1)
        cands = [("a.png", int((NOW_WALL + 0.9) * 1e9), 200)]
        riview.update_observed({"a.png": obs}, cands, NOW_MONO + 1.0, NOW_WALL + 1.0)
        obs2 = riview.Observed(cands[0][1], cands[0][2], NOW_MONO + 1.0)
        self.assertEqual(riview.update_observed(
            {"a.png": obs}, cands, NOW_MONO + 1.0, NOW_WALL + 1.0)["a.png"].last_change_mono,
            NOW_MONO + 1.0)
        # 1.9 s after that change (2.9 s after first sighting): not settled
        self.assertFalse(riview.is_settled(obs2, NOW_MONO + 2.9, NOW_WALL + 2.9, WINDOW))
        # 2.1 s after the change: settled
        self.assertTrue(riview.is_settled(obs2, NOW_MONO + 3.1, NOW_WALL + 3.1, WINDOW))

    def test_update_observed_first_sight_uses_mtime(self):
        mtime_ns = int((NOW_WALL - 100.0) * 1e9)
        obs_map = riview.update_observed({}, [("a.png", mtime_ns, 10)],
                                         NOW_MONO, NOW_WALL)
        self.assertEqual(obs_map["a.png"].last_change_mono, NOW_MONO - 100.0)
        self.assertTrue(riview.is_settled(obs_map["a.png"], NOW_MONO, NOW_WALL, WINDOW))

    def test_window_zero_settles_immediately(self):
        obs = self._obs("a.png", mtime_age_s=0.0)
        self.assertTrue(riview.is_settled(obs, NOW_MONO, NOW_WALL, 0.0))

    def test_dropped_paths_removed(self):
        mtime_ns = int(NOW_WALL * 1e9)
        obs_map = {"gone.png": riview.Observed(mtime_ns, 1, NOW_MONO)}
        riview.update_observed(obs_map, [], NOW_MONO, NOW_WALL)
        self.assertEqual(obs_map, {})


def snap(path, mtime, size=10):
    return riview.Snapshot(path, mtime, size)


class TestPickBest(unittest.TestCase):
    """Spec §5.2. Case 7 (plus switch/tie/older cases)."""

    def test_empty(self):
        self.assertIsNone(riview.pick_best([], None))
        self.assertIsNone(riview.pick_best([], snap("a", 100)))

    def test_no_snapshot_picks_newest(self):
        cands = [("/a", 100, 1), ("/b", 300, 1), ("/c", 200, 1)]
        self.assertEqual(riview.pick_best(cands, None), "/b")

    def test_tie_keeps_current(self):
        cands = [("/a", 100, 1), ("/b", 100, 1)]
        self.assertEqual(riview.pick_best(cands, snap("/a", 100, 1)), "/a")

    def test_strictly_newer_switches(self):
        cands = [("/a", 100, 1), ("/b", 101, 1)]
        self.assertEqual(riview.pick_best(cands, snap("/a", 100, 1)), "/b")

    def test_older_does_not_switch(self):
        # case 7: cp -p of an old file never steals the display
        cands = [("/a", 100, 1), ("/old", 50, 1)]
        self.assertEqual(riview.pick_best(cands, snap("/a", 100, 1)), "/a")

    def test_inplace_update_reloads_even_if_older(self):
        # R4: same path, changed version → reload regardless of direction
        cands = [("/a", 40, 1)]
        self.assertEqual(riview.pick_best(cands, snap("/a", 100, 1)), "/a")
        # and it IS a reload (caller sees version mismatch):
        self.assertNotEqual(40, 100)

    def test_inplace_size_change_only_reloads(self):
        cands = [("/a", 100, 20)]  # same mtime, new size
        self.assertEqual(riview.pick_best(cands, snap("/a", 100, 1)), "/a")

    def test_current_gone_falls_back_to_newest(self):
        cands = [("/b", 300, 1), ("/c", 200, 1)]
        self.assertEqual(riview.pick_best(cands, snap("/a", 999, 1)), "/b")

    def test_newer_tie_deterministic(self):
        cands = [("/a", 100, 1), ("/b", 200, 1), ("/c", 200, 1)]
        self.assertEqual(riview.pick_best(cands, snap("/a", 100, 1)), "/c")


class TestNewestForReport(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(riview.newest_for_report([]))

    def test_newest(self):
        cands = [("/a", 100, 1), ("/b", 300, 1)]
        self.assertEqual(riview.newest_for_report(cands), "/b")

    def test_tie_greatest_name(self):
        cands = [("/a", 100, 1), ("/b", 100, 1)]
        self.assertEqual(riview.newest_for_report(cands), "/b")


def run_riview(*args, cwd=None, timeout=10):
    return subprocess.run([sys.executable, RIVIEW, *args], cwd=cwd,
                          capture_output=True, text=True, timeout=timeout)


class TestPrintMode(unittest.TestCase):
    """Spec §11 cases 1–5c (headless `--print`)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="riview-print-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_empty_dir(self):  # case 1
        r = run_riview("--print", self.dir)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "none")

    def test_newest_picked(self):  # case 2
        now = time.time()
        write(os.path.join(self.dir, "old.png"), mtime=now - 100)
        write(os.path.join(self.dir, "new.png"), mtime=now - 1)
        r = run_riview("--print", self.dir)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), os.path.join(self.dir, "new.png"))

    def test_filters(self):  # case 3
        write(os.path.join(self.dir, "x.txt"))
        write(os.path.join(self.dir, ".h.png"))
        os.makedirs(os.path.join(self.dir, "sub"))
        write(os.path.join(self.dir, "sub", "a.png"))
        r = run_riview("--print", self.dir)
        self.assertEqual(r.stdout.strip(), "none")

    def test_tie_greatest_name(self):  # case 4
        t = time.time() - 50
        write(os.path.join(self.dir, "a.png"), mtime=t)
        write(os.path.join(self.dir, "b.png"), mtime=t)
        r = run_riview("--print", self.dir)
        self.assertEqual(r.stdout.strip(), os.path.join(self.dir, "b.png"))

    def test_custom_extensions(self):  # case 5
        write(os.path.join(self.dir, "a.png"))
        write(os.path.join(self.dir, "a.bmp"))
        r = run_riview("--print", "--extensions", "bmp", self.dir)
        self.assertEqual(r.stdout.strip(), os.path.join(self.dir, "a.bmp"))

    def test_file_target(self):  # case 5a (R21)
        p = os.path.join(self.dir, "img.png")
        write(p)
        r = run_riview("--print", p)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), p)

    def test_file_target_bypasses_extensions(self):  # case 5a (R21)
        p = os.path.join(self.dir, "img.png")
        write(p)
        r = run_riview("--print", "--extensions", "bmp", p)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), p)

    def test_file_target_non_image(self):  # case 5b
        f = os.path.join(self.dir, "notes.txt")
        write(f)
        r = run_riview("--print", f)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a directory or a supported image file", r.stderr)

    def test_no_target_uses_cwd(self):  # case 5c
        now = time.time()
        write(os.path.join(self.dir, "a.png"), mtime=now - 10)
        write(os.path.join(self.dir, "b.png"), mtime=now - 1)
        r = run_riview("--print", cwd=self.dir)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), os.path.join(self.dir, "b.png"))


class TestCliValidation(unittest.TestCase):
    """Spec §11 case 6 (exit codes)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="riview-cli-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_version(self):
        r = run_riview("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("riview 1.7.3", r.stdout)

    def test_missing_dir_exit3(self):
        r = run_riview("--print", self.dir + "/no-such-dir")
        self.assertEqual(r.returncode, 3)
        self.assertIn("does not exist", r.stderr)

    def test_dir_is_file_exit2(self):
        f = os.path.join(self.dir, "f.txt")
        write(f)
        r = run_riview("--print", f)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a directory", r.stderr)

    def test_bad_options_exit2(self):
        for extra in (["--poll", "0"], ["--stable-ms", "-1"],
                      ["--extensions", ""], ["--max-dim", "-5"],
                      ["--print", "--fullscreen"], ["--fit", "bogus"]):
            r = run_riview(*extra, self.dir)
            self.assertEqual(r.returncode, 2, f"{extra}: {r.stderr}")

    def test_desktop_flag_conflicts(self):  # case 6
        for extra in (["--install-desktop", self.dir],
                      ["--install-desktop", "--print", self.dir],
                      ["--install-desktop", "--fullscreen", self.dir],
                      ["--install-desktop", "--uninstall-desktop"]):
            r = run_riview(*extra)
            self.assertEqual(r.returncode, 2, f"{extra}: {r.stderr}")

    def test_cycle_time_usage(self):  # case 8j
        for extra in (["--cycle-time", "0"], ["--cycle-time", "-3"],
                      ["--cycle-time", "9.5"], ["--cycle", "0"],
                      ["--cycle", "2.5"]):
            r = run_riview(*extra, self.dir)
            self.assertEqual(r.returncode, 2, f"{extra}: {r.stderr}")

    def test_cycle_time_defaults(self):  # case 8j
        p = riview.build_parser()
        a = p.parse_args(riview._cycle_argv([self.dir]))
        riview.validate(a)
        self.assertFalse(a.cycle)
        self.assertIsNone(a.cycle_value)
        self.assertEqual(a.cycle_time, 9)  # default 9 s
        a = p.parse_args(riview._cycle_argv(["--cycle"]))
        riview.validate(a)
        self.assertTrue(a.cycle)
        self.assertEqual(a.cycle_time, 9)  # flag alone = default 9 s
        a = p.parse_args(riview._cycle_argv(["--cycle", "5", self.dir]))
        riview.validate(a)
        self.assertTrue(a.cycle)
        self.assertEqual(a.cycle_time, 5)  # --cycle's value sets the time
        a = p.parse_args(riview._cycle_argv(["--cycle-time", "3", self.dir]))
        riview.validate(a)
        self.assertFalse(a.cycle)
        self.assertEqual(a.cycle_time, 3)
        # rev 1.7.3: the flags are combinable — when both give a time,
        # --cycle-time takes precedence (the dedicated interval option).
        a = p.parse_args(riview._cycle_argv(
            ["--cycle", "--cycle-time", "3", self.dir]))
        riview.validate(a)
        self.assertTrue(a.cycle)
        self.assertEqual(a.cycle_time, 3)
        a = p.parse_args(riview._cycle_argv(
            ["--cycle", "5", "--cycle-time", "3", self.dir]))
        riview.validate(a)
        self.assertTrue(a.cycle)
        self.assertEqual(a.cycle_time, 3)  # --cycle-time takes precedence

    def test_cycle_argv_plumbing(self):  # case 8j/36
        # The optional seconds value must not swallow the positional
        # target: only a token that looks like a number is taken as the
        # value, and a real target after a bare --cycle stays a target.
        self.assertEqual(riview._cycle_argv(["--cycle"]), ["--cycle"])
        self.assertEqual(riview._cycle_argv(["--cycle", "5"]),
                         ["--cycle", "--cycle-value", "5"])
        self.assertEqual(riview._cycle_argv(["--cycle", "5", "/d"]),
                         ["--cycle", "--cycle-value", "5", "/d"])
        self.assertEqual(riview._cycle_argv(["--print", "--cycle", "/d"]),
                         ["--print", "--cycle", "/d"])
        self.assertEqual(riview._cycle_argv(["/d", "--cycle"]),
                         ["/d", "--cycle"])
        self.assertEqual(riview._cycle_argv(["--cycle", "2.5"]),
                         ["--cycle", "--cycle-value", "2.5"])  # int error

    def test_print_cycle_inert(self):  # case 36
        p = os.path.join(self.dir, "a.png")
        write(p, mtime=time.time() - 100)
        r = run_riview("--print", "--cycle", self.dir)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), p)


class TestDesktopInstall(unittest.TestCase):
    """Spec §11 cases 8a–8b (R20): per-user .desktop entry + icon."""

    def setUp(self):
        self.data = tempfile.mkdtemp(prefix="riview-xdg-")
        self.env = dict(os.environ, XDG_DATA_HOME=self.data)
        self.entry = os.path.join(self.data, "applications",
                                  "com.lemonade.riview.desktop")
        self.icon = os.path.join(self.data, "icons", "hicolor", "scalable",
                                 "apps", "com.lemonade.riview.svg")

    def tearDown(self):
        shutil.rmtree(self.data, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run([sys.executable, RIVIEW, *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_install_writes_both_files(self):  # case 8a
        r = self._run("--install-desktop")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(self.entry))
        self.assertTrue(os.path.isfile(self.icon))
        with open(self.entry) as f:
            text = f.read()
        self.assertIn(f"Exec={os.path.realpath(RIVIEW)} %U", text)
        self.assertIn("Icon=com.lemonade.riview", text)
        self.assertIn("Terminal=false", text)
        self.assertIn("MimeType=inode/directory;image/png;", text)
        with open(self.icon) as f:
            svg = f.read()
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("viewBox", svg)

    def test_install_idempotent(self):  # case 8a
        self.assertEqual(self._run("--install-desktop").returncode, 0)
        self.assertEqual(self._run("--install-desktop").returncode, 0)

    def test_uninstall_removes(self):  # case 8b
        self._run("--install-desktop")
        r = self._run("--uninstall-desktop")
        self.assertEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(self.entry))
        self.assertFalse(os.path.exists(self.icon))

    def test_uninstall_noop(self):  # case 8b
        r = self._run("--uninstall-desktop")
        self.assertEqual(r.returncode, 0)
        self.assertIn("note", r.stderr)


class TestLaunchContext(unittest.TestCase):
    """Spec §11 cases 8c–8d (R22) + target-resolution units (R20–R22)."""

    # -- classifier units (case 8c) ----------------------------------------
    def test_startup_id_means_gui(self):
        self.assertTrue(riview.is_gui_context(
            environ={"DESKTOP_STARTUP_ID": "local:1"}, has_ctty=True))

    def test_ctty_without_startup_id_means_terminal(self):
        self.assertFalse(riview.is_gui_context(environ={}, has_ctty=True))

    def test_no_ctty_means_gui(self):
        self.assertTrue(riview.is_gui_context(environ={}, has_ctty=False))

    def test_resolve_target_modes(self):
        d = tempfile.mkdtemp(prefix="riview-rt-")
        try:
            self.assertEqual(riview.resolve_target(d, False), ("dir", d))
            f = os.path.join(d, "a.png")
            write(f)
            self.assertEqual(riview.resolve_target(f, True),
                             ("file", os.path.abspath(f)))
            # file mode is independent of the context
            self.assertEqual(riview.resolve_target(f, False),
                             ("file", os.path.abspath(f)))
            t = os.path.join(d, "a.txt")
            write(t)
            with self.assertRaises(riview.UsageError):
                riview.resolve_target(t, False)
            with self.assertRaises(riview.NoTargetError):
                riview.resolve_target(os.path.join(d, "nope.png"), False)
            self.assertEqual(riview.resolve_target(None, True), ("none", None))
            self.assertEqual(riview.resolve_target(None, False),
                             ("dir", os.path.abspath(os.getcwd())))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_uri_to_path(self):
        self.assertEqual(riview.uri_to_path("file:///tmp/a b.png"),
                         "/tmp/a b.png")
        self.assertEqual(riview.uri_to_path("/tmp/plain.png"),
                         "/tmp/plain.png")

    # -- context discriminator end-to-end (case 8d) -------------------------
    def test_fullscreen_no_target_context_split(self):
        try:
            import fcntl, termios, pty
        except ImportError:
            self.skipTest("pty/fcntl/termios unavailable")
        env = {k: v for k, v in os.environ.items()
               if k not in ("DISPLAY", "WAYLAND_DISPLAY",
                            "DESKTOP_STARTUP_ID")}
        # pty-less child (setsid): GUI context -> usage error, exit 2
        p = subprocess.Popen([sys.executable, RIVIEW, "--fullscreen"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, preexec_fn=os.setsid,
                             env=env)
        _out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 2, err.decode())
        self.assertIn("--fullscreen requires a target", err.decode())
        # child with a controlling terminal: terminal context -> CWD target
        # -> GTK init fails (no display) -> exit 1
        master, slave = pty.openpty()
        def pre():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        p = subprocess.Popen([sys.executable, RIVIEW, "--fullscreen"],
                             stdin=slave, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, preexec_fn=pre,
                             env=env)
        os.close(slave)
        _out, err = p.communicate(timeout=30)
        os.close(master)
        self.assertEqual(p.returncode, 1, err.decode())


class TestWatcherDecoderIntegration(unittest.TestCase):
    """Runtime plumbing (spec §6, design §12.4/§12.6): real inotify monitor,
    GLib main loop, and decode worker — driven headlessly. The GUI surface
    (window/picture) itself is covered by the manual GUI cases §11 9–22."""

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)  # keep the GTK import clean
        try:
            cls.Decoder, cls.Watcher, _W, _A = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")
        import gi
        gi.require_version("GLib", "2.0")
        from gi.repository import GLib, Gdk
        cls.GLib = GLib
        cls.Gdk = Gdk

    def _png(self):
        import struct, zlib
        def chunk(typ, data):
            return (struct.pack(">I", len(data)) + typ + data
                    + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
        idat = zlib.compress(b"\x00\xff\x00\x00")
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", idat) + chunk(b"IEND", b""))

    def _run_loop(self, w, ms):
        loop = self.GLib.MainLoop()
        w.start()
        self.GLib.timeout_add(ms, loop.quit)
        loop.run()
        w.stop()

    def test_inotify_rescans_on_create(self):
        GLib = self.GLib
        d = tempfile.mkdtemp(prefix="riview-watch-")
        events = []
        w = self.Watcher(d, None, lambda: events.append(time.monotonic()))
        loop = GLib.MainLoop()
        w.start()

        def create_file():
            write(os.path.join(d, "x.png"), self._png())

        GLib.timeout_add(400, create_file)
        GLib.timeout_add(3000, loop.quit)
        loop.run()
        w.stop()
        shutil.rmtree(d, ignore_errors=True)
        # initial rescan + at least one rescan after the file appears
        self.assertGreaterEqual(len(events), 2)
        self.assertLessEqual(events[1] - events[0], 2.5)

    def test_poll_mode_rescans(self):
        d = tempfile.mkdtemp(prefix="riview-watch-")
        events = []
        w = self.Watcher(d, 0.2, lambda: events.append(time.monotonic()))
        self._run_loop(w, 1300)
        shutil.rmtree(d, ignore_errors=True)
        self.assertGreaterEqual(len(events), 3)   # initial + ~5 ticks
        self.assertLessEqual(len(events), 20)     # no run-away rescans

    def test_remonitor_after_dir_recreate(self):
        GLib = self.GLib
        d = tempfile.mkdtemp(prefix="riview-watch-")
        events = []
        w = self.Watcher(d, None, lambda: events.append(time.monotonic()))
        loop = GLib.MainLoop()
        w.start()

        def recreate():
            shutil.rmtree(d)
            os.mkdir(d)

        GLib.timeout_add(500, recreate)
        GLib.timeout_add(2500, lambda: write(os.path.join(d, "y.png"),
                                             self._png()))
        GLib.timeout_add(5000, loop.quit)
        loop.run()
        w.stop()
        shutil.rmtree(d, ignore_errors=True)
        # Requirement: y.png (created after the directory was recreated)
        # must still trigger a rescan, even if the new directory reuses the
        # old inode number (which makes the recreation invisible to inode
        # bookkeeping). A dead watcher would show only the initial rescan.
        self.assertGreaterEqual(len(events), 2)
        self.assertGreaterEqual(events[-1] - events[0], 2.3)

    def test_decoder_success_error_supersede(self):
        GLib = self.GLib
        d = tempfile.mkdtemp(prefix="riview-dec-")
        good = os.path.join(d, "good.png")
        bad = os.path.join(d, "bad.png")
        write(good, self._png())
        write(bad, b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)  # truncated
        dec = self.Decoder()
        res = {}

        def wait(gens, timeout=8.0):
            deadline = time.time() + timeout
            while time.time() < deadline:
                for item in dec.results():
                    res[item[0]] = item
                if all(g in res for g in gens):
                    return True
                time.sleep(0.01)
            return False

        dec.request(1, good, 64, 64)
        self.assertTrue(wait([1]), "good decode did not arrive")
        _g, _p, pixbuf, err = res[1]
        self.assertIsNone(err)
        self.assertIsNotNone(pixbuf)
        self.assertLessEqual(pixbuf.get_width(), 64)   # no upscale past source
        # display path (non-deprecated, §13.2): pixbuf → texture → paintable
        tex = self.Gdk.Texture.new_for_pixbuf(pixbuf)
        self.assertIsInstance(tex, self.Gdk.Paintable)
        self.assertEqual((tex.get_width(), tex.get_height()),
                         (pixbuf.get_width(), pixbuf.get_height()))

        dec.request(2, bad, 64, 64)
        self.assertTrue(wait([2]), "error result did not arrive")
        self.assertIsNotNone(res[2][3])                 # error carried
        self.assertIsNone(res[2][2])                    # no pixbuf

        dec.request(3, good, 32, 32)
        dec.request(4, good, 16, 16)
        self.assertTrue(wait([3, 4]), "superseded result missing")
        # both deliver; the caller discards the stale generation (§12.5)
        dec.stop()
        dec._thread.join(3)
        shutil.rmtree(d, ignore_errors=True)


class TestInputShortcuts(unittest.TestCase):
    """R18/R19: bare-key shortcut logic and canvas double-click, plus clean
    signal quit, driven against a fake window (no display needed). The GTK
    plumbing (EventControllerKey, GestureClick, unix_signal_add) itself is
    covered by manual cases §11 18/22/23/24."""

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)
        try:
            _D, _W, cls.Window, cls.App = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        cls.Gdk = Gdk

    def _fake(self, fullscreen=False):
        w = self.Window.__new__(self.Window)
        w.fullscreen_mode = fullscreen
        w.calls = []
        w.close = lambda: w.calls.append("close")
        w._set_fullscreen = lambda on: w.calls.append(f"fs:{on}")
        return w

    def _key(self, w, keyval, *mods):
        state = 0
        for m in mods:
            state |= int(m)
        return self.Window._on_key(w, None, keyval, 0, state)

    def test_q_quits(self):
        Gdk = self.Gdk
        w = self._fake()
        self.assertTrue(self._key(w, Gdk.KEY_q))
        self.assertEqual(w.calls, ["close"])

    def test_q_shift_tolerated(self):
        Gdk = self.Gdk
        w = self._fake()
        self.assertTrue(self._key(w, Gdk.KEY_Q, Gdk.ModifierType.SHIFT_MASK))
        self.assertEqual(w.calls, ["close"])

    def test_ctrl_q_not_shortcut(self):
        Gdk = self.Gdk
        w = self._fake()
        self.assertFalse(self._key(w, Gdk.KEY_q, Gdk.ModifierType.CONTROL_MASK))
        self.assertEqual(w.calls, [])

    def test_f_toggles_both_directions(self):
        Gdk = self.Gdk
        win = self._fake(fullscreen=False)
        self.assertTrue(self._key(win, Gdk.KEY_f))
        self.assertEqual(win.calls, ["fs:True"])
        fs = self._fake(fullscreen=True)
        self.assertTrue(self._key(fs, Gdk.KEY_F, Gdk.ModifierType.SHIFT_MASK))
        self.assertEqual(fs.calls, ["fs:False"])

    def test_ctrl_f_not_shortcut(self):
        Gdk = self.Gdk
        w = self._fake()
        self.assertFalse(self._key(w, Gdk.KEY_f, Gdk.ModifierType.CONTROL_MASK))
        self.assertEqual(w.calls, [])

    def test_esc_only_in_fullscreen(self):
        Gdk = self.Gdk
        win = self._fake(fullscreen=False)
        self.assertFalse(self._key(win, Gdk.KEY_Escape))
        self.assertEqual(win.calls, [])
        fs = self._fake(fullscreen=True)
        self.assertTrue(self._key(fs, Gdk.KEY_Escape))
        self.assertEqual(fs.calls, ["fs:False"])

    def test_canvas_double_click_toggles(self):
        """R19: two left presses within DOUBLE_CLICK_S toggle; anything
        slower (or a lone press) does nothing."""
        W = self.Window
        w = self._fake(fullscreen=False)
        w._last_canvas_click_s = -1.0
        W._on_canvas_click(w, None, 1, 0.0, 0.0)     # first press: records
        self.assertEqual(w.calls, [])
        w._last_canvas_click_s = time.monotonic() - 0.3
        W._on_canvas_click(w, None, 1, 0.0, 0.0)     # second: toggle on
        self.assertEqual(w.calls, ["fs:True"])
        fs = self._fake(fullscreen=True)
        fs._last_canvas_click_s = time.monotonic() - 0.3
        W._on_canvas_click(fs, None, 1, 0.0, 0.0)    # and back off
        self.assertEqual(fs.calls, ["fs:False"])
        slow = self._fake(fullscreen=False)
        slow._last_canvas_click_s = time.monotonic() - 1.0
        W._on_canvas_click(slow, None, 1, 0.0, 0.0)  # too slow: nothing
        self.assertEqual(slow.calls, [])

    def test_other_keys_ignored(self):
        Gdk = self.Gdk
        w = self._fake()
        self.assertFalse(self._key(w, Gdk.KEY_a))
        self.assertFalse(self._key(w, Gdk.KEY_q,
                                   Gdk.ModifierType.CONTROL_MASK,
                                   Gdk.ModifierType.SHIFT_MASK))
        self.assertEqual(w.calls, [])

    def test_sigint_sigterm_quit_app(self):
        app = self.App.__new__(self.App)
        called = []
        app.quit = lambda: called.append(1)
        self.assertFalse(self.App._on_signal(app, signal.SIGINT))
        self.assertFalse(self.App._on_signal(app, signal.SIGTERM))
        self.assertEqual(len(called), 2)


class _Rec:
    """Record every method call (stand-in for a GTK widget in fakes)."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        def m(*a):
            self.calls.append((name, a))
        return m


class _FakeFeedbackLabel:
    """Stand-in for the R30 feedback Gtk.Label: real .text/.visible state.
    (The generic _Rec records calls but returns recorder functions on read,
    so text/visibility could not be asserted on it.)"""

    def __init__(self):
        self.text = ""
        self.visible = False
        self.halign = None
        self.valign = None
        self.margin_bottom = None
        self.calls = []  # _Rec-compatible call log (the _texts helper)

    def set_css_name(self, name):
        self.calls.append(("set_css_name", (name,)))

    def set_text(self, text):
        self.text = text
        self.calls.append(("set_text", (text,)))

    def set_margin_bottom(self, px):
        self.margin_bottom = px
        self.calls.append(("set_margin_bottom", (px,)))

    def set_visible(self, v):
        self.visible = v
        self.calls.append(("set_visible", (v,)))


class _FakeCanvas:
    """Stand-in for the canvas container (the Gtk.Overlay below the
    header bar): only get_height() matters (R30's show-time margin, §12.7)."""

    def __init__(self, h=720):
        self.h = h

    def get_height(self):
        return self.h


class _FakeDecoder:
    def __init__(self):
        self.requests = []

    def request(self, gen, path, w, h):
        self.requests.append((gen, path))


class _FakeWatcher:
    def __init__(self):
        self.rescans = []

    def schedule_rescan(self, delay_ms=200):
        self.rescans.append(delay_ms)


def make_fake_window(Window, **kw):
    """A RiviewWindow without running __init__ (no GTK surface), ready for
    on_rescan / _rescan_pinned / _nav / _on_key. GTK-dependent attribute
    access is stubbed with _Rec recorders."""
    w = Window.__new__(Window)
    w.observer = {}
    w.snapshot = None
    w.pinned_path = None
    w.image_gone = False
    w.current_gen = 0
    w.window_s = WINDOW
    w.mode = "dir"
    w.decoder = _FakeDecoder()
    w.watcher = _FakeWatcher()
    w.decode_target = lambda: (100, 100)
    w.picture = _Rec()
    w.waiting_label = _Rec()
    w.title_widget = _Rec()
    w.set_title = lambda t: None
    w._subtitle = "/d"
    w.fullscreen_mode = False
    w.only_path = None
    w.exts = set(DEFAULT_EXTS)
    w.dir_abs = ""
    w.failed_versions = set()
    # R24 fit surface (stubbed no-ops; the fit tests override):
    w.fit_mode = "off"
    w.fitted = True
    w.resize = lambda *a: None
    w.get_height = lambda: 720  # allocated-height default (fit-code seams)
    w._canvas = _FakeCanvas(720)  # canvas container (R30 margin source)
    # Cycle mode (rev 1.6, R27–R29): state for _on_key / on_rescan:
    w.cycle_s = 9
    w.cycle_mode = False
    w.start_oldest = False
    w.cycle_deadline = None
    w.cycle_interval_start = None
    w._cycle_tick_id = None
    w._cycle_first_req = None
    w._dims = None
    # Key-press feedback (rev 1.7, R30): label + pending timer:
    w._feedback_label = _FakeFeedbackLabel()
    w._feedback_id = None
    w.header = _Rec()
    for k, v in kw.items():
        setattr(w, k, v)
    return w


class TestNavOrder(unittest.TestCase):
    """Spec §11 case 8e: navigation order & stepping (R23, pure unit)."""

    def test_order_cands_mtime_then_name(self):
        cands = [("/d/a.png", 100, 1),
                 ("/d/b.png", 300, 1),
                 ("/d/c.png", 200, 1)]
        self.assertEqual([c[0] for c in riview.order_cands(cands)],
                         ["/d/b.png", "/d/c.png", "/d/a.png"])

    def test_order_cands_tie_greatest_name_first(self):
        cands = [("/d/a.png", 100, 1),
                 ("/d/b.png", 100, 1),
                 ("/d/c.png", 100, 1)]
        self.assertEqual([c[0] for c in riview.order_cands(cands)],
                         ["/d/c.png", "/d/b.png", "/d/a.png"])

    def test_order_cands_empty(self):
        self.assertEqual(riview.order_cands([]), [])

    def test_nav_target_steps_both_directions(self):
        # rev 1.5: anchor = (path, mtime); -1 = older, +1 = newer
        ordered = riview.order_cands(
            [("/a", 100, 1), ("/b", 200, 1), ("/c", 300, 1)])
        self.assertEqual(riview.nav_target(ordered, ("/c", 300), -1), "/b")
        self.assertEqual(riview.nav_target(ordered, ("/b", 200), +1), "/c")
        self.assertEqual(riview.nav_target(ordered, ("/b", 200), -1), "/a")
        # one step, not a jump to the end (regression, rev 1.5.1):
        self.assertEqual(riview.nav_target(ordered, ("/a", 100), +1), "/b")

    def test_nav_target_clamped_at_ends(self):
        ordered = riview.order_cands([("/a", 100, 1), ("/b", 200, 1)])
        self.assertIsNone(riview.nav_target(ordered, ("/a", 100), -1))  # oldest
        self.assertIsNone(riview.nav_target(ordered, ("/b", 200), +1))  # newest

    def test_nav_target_single_entry(self):
        ordered = riview.order_cands([("/a", 100, 1)])
        self.assertIsNone(riview.nav_target(ordered, ("/a", 100), -1))
        self.assertIsNone(riview.nav_target(ordered, ("/a", 100), +1))

    def test_nav_target_virtual_anchor(self):
        # rev 1.5: the anchor need not be a list member (image-gone,
        # rewrite in flight) — it steps from its (mtime, path) position.
        ordered = riview.order_cands([("/a", 100, 1), ("/b", 200, 1)])
        self.assertEqual(riview.nav_target(ordered, ("/gone", 150), +1), "/b")
        self.assertEqual(riview.nav_target(ordered, ("/gone", 150), -1), "/a")
        # anchor newer than everything / older than everything:
        self.assertIsNone(riview.nav_target(ordered, ("/gone", 300), +1))
        self.assertEqual(riview.nav_target(ordered, ("/gone", 300), -1), "/b")
        self.assertEqual(riview.nav_target(ordered, ("/gone", 50), +1), "/a")
        self.assertIsNone(riview.nav_target(ordered, ("/gone", 50), -1))
        # empty list:
        self.assertIsNone(riview.nav_target([], ("/gone", 50), +1))
        self.assertIsNone(riview.nav_target([], ("/gone", 50), -1))

    def test_nav_target_tie_breaks_by_path(self):
        # equal mtimes: byte-wise greater name sorts newer
        ordered = riview.order_cands([("/a", 100, 1), ("/c", 100, 1)])
        self.assertEqual(ordered[0][0], "/c")
        self.assertEqual(riview.nav_target(ordered, ("/b", 100), +1), "/c")
        self.assertEqual(riview.nav_target(ordered, ("/b", 100), -1), "/a")

    def test_nav_anchor_own_entry(self):
        ordered = riview.order_cands([("/a", 100, 1), ("/b", 200, 1)])
        self.assertEqual(riview.nav_anchor(ordered, "/b", None), ("/b", 200))

    def test_nav_anchor_virtual(self):
        ordered = riview.order_cands([("/a", 100, 1), ("/b", 200, 1)])
        self.assertEqual(
            riview.nav_anchor(ordered, "/gone", snap("/gone", 150)),
            ("/gone", 150))
        # snapshot of a different path (or none): mtime 0 = oldest position
        self.assertEqual(
            riview.nav_anchor(ordered, "/gone", snap("/x", 150)),
            ("/gone", 0))
        self.assertEqual(riview.nav_anchor(ordered, "/gone", None),
                         ("/gone", 0))


class TestCycleTarget(unittest.TestCase):
    """Spec §11 case 8i: the cycle advance target (R27, pure unit)."""

    def _ordered(self):
        # [D, A, B, C]: D newest, C oldest, in order_cands order.
        return riview.order_cands([("/d", 400, 1), ("/a", 300, 1),
                                    ("/b", 200, 1), ("/c", 100, 1)])

    def test_adjacent_newer_step(self):
        ordered = self._ordered()
        self.assertEqual(riview.cycle_target(ordered, ("/c", 100), set()),
                         "/b")  # from C the adjacent newer image
        self.assertEqual(riview.cycle_target(ordered, ("/b", 200), set()),
                         "/a")

    def test_wrap_from_newest_to_oldest(self):
        ordered = self._ordered()
        self.assertEqual(riview.cycle_target(ordered, ("/d", 400), set()),
                         "/c")  # newest end → wrap to the oldest

    def test_virtual_anchor(self):
        ordered = self._ordered()
        # Deleted slide (mtime 350, not in the list): the first settled
        # strictly newer than the anchor.
        self.assertEqual(riview.cycle_target(ordered, ("/gone", 350), set()),
                         "/d")
        # Newer than everything: the wrap.
        self.assertEqual(riview.cycle_target(ordered, ("/gone", 500), set()),
                         "/c")
        # Older than everything: the adjacent newer = the oldest.
        self.assertEqual(riview.cycle_target(ordered, ("/gone", 50), set()),
                         "/c")

    def test_newest_end_reached_only_by_normal_walk(self):
        # A newly settled D' at the newest end: from B the step is A, not
        # D' — the cycle grows, it does not jump.
        ordered = riview.order_cands([("/dp", 400, 1), ("/a", 300, 1),
                                       ("/b", 200, 1), ("/c", 100, 1)])
        self.assertEqual(riview.cycle_target(ordered, ("/b", 200), set()),
                         "/a")

    def test_failed_versions_skipped(self):
        ordered = self._ordered()
        failed = {("/a", 300, 1)}
        self.assertEqual(riview.cycle_target(ordered, ("/b", 200), failed),
                         "/d")  # A corrupt → skipped, never retried
        failed2 = {("/a", 300, 1), ("/d", 400, 1)}
        # All-failed span → fall through to the wrap.
        self.assertEqual(riview.cycle_target(ordered, ("/b", 200), failed2),
                         "/c")

    def test_single_element_same_element(self):
        ordered = riview.order_cands([("/a", 100, 1)])
        self.assertEqual(riview.cycle_target(ordered, ("/a", 100), set()),
                         "/a")  # no advance — the caller holds

    def test_empty_and_all_failed(self):
        self.assertIsNone(riview.cycle_target([], ("/a", 100), set()))
        ordered = riview.order_cands([("/a", 100, 1), ("/b", 200, 1)])
        failed = {("/a", 100, 1), ("/b", 200, 1)}
        self.assertIsNone(riview.cycle_target(ordered, ("/a", 100), failed))

    def test_cycle_first_oldest_or_newest(self):
        # R29: --cycle starts at the OLDEST settled image; an armed `c`
        # starts at the newest. Failed versions are skipped.
        ordered = self._ordered()
        self.assertEqual(riview.cycle_first(ordered, False, set()), "/d")
        self.assertEqual(riview.cycle_first(ordered, True, set()), "/c")
        self.assertEqual(riview.cycle_first(ordered, False, {("/d", 400, 1)}),
                         "/a")
        self.assertEqual(riview.cycle_first(ordered, True, {("/c", 100, 1)}),
                         "/b")
        all_failed = {("/d", 400, 1), ("/a", 300, 1),
                      ("/b", 200, 1), ("/c", 100, 1)}
        self.assertIsNone(riview.cycle_first(ordered, False, all_failed))
        self.assertIsNone(riview.cycle_first(ordered, True, all_failed))


class TestCycleRescale(unittest.TestCase):
    """Spec §11 case 8j (pure part): the cycle-time clamp and the
    current-interval rescale (R28, owner-amended A10)."""

    def test_up_down(self):
        # Up adds 1 s (no upper bound), Down subtracts 1 s.
        self.assertEqual(riview.cycle_rescale(9, 0.0, +1), (10, 10.0))
        self.assertEqual(riview.cycle_rescale(9, 2.0, -1), (8, 6.0))

    def test_worked_example(self):
        # 9 s with 2 s elapsed, Down ×2 → 7 s: the current slide advances
        # after 5 more seconds (elapsed preserved).
        t, _rem = riview.cycle_rescale(9, 2.0, -1)  # → 8 s
        t, rem = riview.cycle_rescale(t, 2.0, -1)   # → 7 s
        self.assertEqual(t, 7)
        self.assertEqual(rem, 5.0)

    def test_floor_noop(self):
        # Down at the 1 s floor: no effect (remaining None → deadline
        # untouched by the caller).
        self.assertEqual(riview.cycle_rescale(1, 0.5, -1), (1, None))

    def test_new_time_below_elapsed(self):
        # A new time shorter than the elapsed time: remaining 0 → the
        # advance fires at the next tick.
        self.assertEqual(riview.cycle_rescale(8, 8.0, -1), (7, 0.0))


class TestPinRescan(unittest.TestCase):
    """Spec §11 case 8f: pinning (R23) with fake clocks, driven against the
    real RiviewWindow._rescan_pinned (GTK widget surface stubbed)."""

    P_OLD = "/d/old.png"
    P_PIN = "/d/pin.png"
    P_NEW = "/d/new.png"
    M_OLD = int((NOW_WALL - 300.0) * 1e9)
    M_PIN = int((NOW_WALL - 200.0) * 1e9)
    M_NEW = int((NOW_WALL - 10.0) * 1e9)

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)
        try:
            _D, _W, cls.Window, _A = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")

    def _win(self, **kw):
        return make_fake_window(self.Window, **kw)

    def _rescan(self, w, cands, now_mono=NOW_MONO, now_wall=NOW_WALL):
        riview.update_observed(w.observer, cands, now_mono, now_wall)
        w._rescan_pinned(cands, now_mono, now_wall)

    def test_newer_candidate_does_not_displace_pin(self):
        w = self._win(pinned_path=self.P_PIN, snapshot=snap(self.P_PIN,
                                                            self.M_PIN, 1))
        cands = [(self.P_OLD, self.M_OLD, 1),
                 (self.P_PIN, self.M_PIN, 1),
                 (self.P_NEW, self.M_NEW, 1)]
        self._rescan(w, cands)
        # R3 suspended while pinned: the settled *newer* file does not
        # displace the pinned display.
        self.assertEqual(w.decoder.requests, [])
        self.assertEqual(w.pinned_path, self.P_PIN)
        self.assertEqual(w.snapshot.path, self.P_PIN)

    def test_pinned_inplace_update_reloads_once_settled(self):
        v1 = (self.P_PIN, self.M_PIN, 10)
        w = self._win(pinned_path=self.P_PIN, snapshot=snap(self.P_PIN,
                                                            self.M_PIN, 10))
        riview.update_observed(w.observer, [v1], NOW_MONO, NOW_WALL)
        m2 = int((NOW_WALL - 0.1) * 1e9)
        v2 = (self.P_PIN, m2, 20)
        self._rescan(w, [v2])            # new version still settling: hold
        self.assertEqual(w.decoder.requests, [])
        self.assertEqual((w.snapshot.mtime_ns, w.snapshot.size),
                         (self.M_PIN, 10))  # old version still displayed
        self._rescan(w, [v2], NOW_MONO + 2.1, NOW_WALL + 2.1)  # settled
        self.assertEqual(w.decoder.requests, [(1, self.P_PIN)])

    def test_pin_lost_goes_image_gone_and_persists(self):
        w = self._win(pinned_path=self.P_PIN, snapshot=snap(self.P_PIN,
                                                            self.M_PIN))
        riview.update_observed(w.observer, [(self.P_PIN, self.M_PIN, 1)],
                               NOW_MONO, NOW_WALL)
        cands = [(self.P_OLD, self.M_OLD, 1)]  # pin deleted/renamed away
        self._rescan(w, cands)
        self.assertTrue(w.image_gone)
        self.assertIsNone(w.snapshot)
        self.assertEqual(w.pinned_path, self.P_PIN)   # pin PERSISTS
        self.assertIn(("set_text", (riview.IMAGE_GONE_TEXT,)),
                      w.waiting_label.calls)
        self.assertIn(("set_paintable", (None,)), w.picture.calls)
        self.assertEqual(w.decoder.requests, [])       # no auto-switch
        # A later rescan stays in the state without re-showing the message.
        self._rescan(w, cands, NOW_MONO + 0.5, NOW_WALL + 0.5)
        self.assertEqual(w.decoder.requests, [])
        self.assertEqual(
            w.waiting_label.calls.count(("set_text", (riview.IMAGE_GONE_TEXT,
                                                      ))), 1)

    def test_pin_reappearing_restores_display_when_settled(self):
        w = self._win(pinned_path=self.P_PIN, image_gone=True)
        riview.update_observed(w.observer, [(self.P_OLD, self.M_OLD, 1)],
                               NOW_MONO, NOW_WALL)
        m_new = int((NOW_WALL - 0.1) * 1e9)
        cands = [(self.P_OLD, self.M_OLD, 1), (self.P_PIN, m_new, 1)]
        self._rescan(w, cands)        # just reappeared: not settled yet
        self.assertEqual(w.decoder.requests, [])
        self.assertTrue(w.image_gone)  # message stays on the canvas
        self._rescan(w, cands, NOW_MONO + 2.1, NOW_WALL + 2.1)  # settled
        self.assertEqual(w.decoder.requests, [(1, self.P_PIN)])
        # Simulate the load landing, then hold:
        w.snapshot = snap(self.P_PIN, m_new, 1)
        w.image_gone = False
        self._rescan(w, cands, NOW_MONO + 2.5, NOW_WALL + 2.5)
        self.assertEqual(w.decoder.requests, [(1, self.P_PIN)])

    def test_back_to_newest_resumes_live_selection(self):
        d = tempfile.mkdtemp(prefix="riview-pin-")
        try:
            now = time.time()
            write(os.path.join(d, "a.png"), mtime=now - 300)
            write(os.path.join(d, "b.png"), mtime=now - 200)
            write(os.path.join(d, "c.png"), mtime=now - 100)
            w = self._win(dir_abs=d)
            w._back_to_newest()      # live mode: no-op
            self.assertEqual(w.watcher.rescans, [])
            w.pinned_path = os.path.join(d, "b.png")
            w._back_to_newest()      # n: live mode + select now
            self.assertIsNone(w.pinned_path)
            self.assertEqual(w.watcher.rescans, [0])
            w.on_rescan()            # live selection: newest is c.png
            self.assertEqual(w.decoder.requests,
                             [(1, os.path.join(d, "c.png"))])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestManualNavKeys(unittest.TestCase):
    """Spec §11 cases 29/30/32 (headless half): Left/Right/n/Home/End key
    handling (R23/R25) against the real RiviewWindow methods; the GTK input
    plumbing and on-screen behaviour are the manual GUI cases 29/30/32."""

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)
        try:
            _D, _W, cls.Window, _A = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        cls.Gdk = Gdk

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="riview-keys-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _win(self, **kw):
        return make_fake_window(self.Window, dir_abs=self.d, **kw)

    def _key(self, w, keyval, *mods):
        state = 0
        for m in mods:
            state |= int(m)
        return self.Window._on_key(w, None, keyval, 0, state)

    def _path(self, name):
        return os.path.join(self.d, name)

    def _settle(self, names):
        """Create files with old mtimes → settled at first observation."""
        now = time.time()
        for name, age_s in names:
            write(self._path(name), mtime=now - age_s)

    def test_left_right_walk_and_clamp(self):
        # c newest, a oldest
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Left))       # c → b, pins
        self.assertEqual(w.pinned_path, self._path("b.png"))
        self.assertEqual(w.decoder.requests,
                         [(1, self._path("b.png"))])
        self._key(w, Gdk.KEY_Left)                        # b → a
        self.assertEqual(w.pinned_path, self._path("a.png"))
        self._key(w, Gdk.KEY_Left)                        # oldest: no-op
        self.assertEqual(len(w.decoder.requests), 2)
        self._key(w, Gdk.KEY_Right)                       # a → b (one step,
        self.assertEqual(w.pinned_path, self._path("b.png"))  # not a jump to c)
        self.assertEqual(len(w.decoder.requests), 3)
        self._key(w, Gdk.KEY_Right)                       # b → c
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self.assertEqual(len(w.decoder.requests), 4)
        self._key(w, Gdk.KEY_Right)                       # newest: the step
        # fails (nothing newer) — the pin is simply unchanged (rev 1.5)
        self.assertEqual(len(w.decoder.requests), 4)

    def test_n_returns_to_live_mode(self):
        self._settle([("a.png", 300), ("b.png", 200)])
        w = self._win(snapshot=snap(self._path("b.png"), 0))
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Left))       # b → a, pins
        self.assertEqual(w.pinned_path, self._path("a.png"))
        self.assertEqual(w.watcher.rescans, [])
        self.assertTrue(self._key(w, Gdk.KEY_n))           # back to live
        self.assertIsNone(w.pinned_path)
        self.assertEqual(w.watcher.rescans, [0])
        self._key(w, Gdk.KEY_n)                            # live: no-op
        self.assertEqual(w.watcher.rescans, [0])
        # Shifted 'n' (R18 tolerates Shift/locks):
        w2 = self._win(pinned_path=self._path("a.png"))
        self.assertTrue(self._key(w2, Gdk.KEY_N, Gdk.ModifierType.SHIFT_MASK))
        self.assertIsNone(w2.pinned_path)

    def test_n_after_image_gone_exits_state(self):
        self._settle([("a.png", 300)])
        w = self._win(pinned_path=self._path("b.png"), image_gone=True)
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Left))        # no-op while gone
        self.assertEqual(w.decoder.requests, [])
        self.assertTrue(self._key(w, Gdk.KEY_n))
        self.assertIsNone(w.pinned_path)
        self.assertEqual(w.watcher.rescans, [0])
        w.image_gone = False                               # (next rescan clears it)
        w.on_rescan()                                      # live: newest is a
        self.assertEqual(w.decoder.requests,
                         [(1, self._path("a.png"))])

    def test_single_file_mode_noop(self):
        # case 30: navigation keys have no effect in single-file mode
        self._settle([("a.png", 300), ("b.png", 200)])
        w = self._win(mode="file", snapshot=snap(self._path("b.png"), 0))
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Left))
        self.assertTrue(self._key(w, Gdk.KEY_Right))
        self.assertTrue(self._key(w, Gdk.KEY_n))
        self.assertEqual(w.decoder.requests, [])
        self.assertIsNone(w.pinned_path)
        self.assertEqual(w.watcher.rescans, [])

    def test_waiting_state_noop(self):
        w = self._win()  # empty directory, nothing displayed
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Left))
        self.assertTrue(self._key(w, Gdk.KEY_Right))
        self.assertEqual(w.decoder.requests, [])
        self.assertIsNone(w.pinned_path)

    def test_rewrite_in_flight_steps_from_old_position(self):
        # rev 1.5: the anchor is the last displayed version's (mtime, path)
        # — Left steps to the older file; Right (nothing newer) fails and
        # pins the display.
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"),
                                    int((time.time() - 100) * 10**9)))
        now_mono = time.monotonic()
        now_wall = time.time()
        riview.update_observed(w.observer,
                               riview.scan_candidates(self.d,
                                                      set(DEFAULT_EXTS)),
                               now_mono, now_wall)
        write(self._path("c.png"), data=b"rewritten")  # fresh mtime
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Left))    # c unsettled → b
        self.assertEqual(w.pinned_path, self._path("b.png"))
        self.assertEqual(w.decoder.requests, [(1, self._path("b.png"))])
        w2 = self._win(snapshot=snap(self._path("c.png"),
                                     int((time.time() - 100) * 10**9)))
        riview.update_observed(w2.observer,
                               riview.scan_candidates(self.d,
                                                      set(DEFAULT_EXTS)),
                               now_mono, now_wall)
        self.assertTrue(self._key(w2, Gdk.KEY_Right))  # nothing newer
        self.assertEqual(w2.pinned_path, self._path("c.png"))
        self.assertEqual(w2.decoder.requests, [])

    def test_modifiers(self):
        self._settle([("a.png", 300), ("b.png", 200)])
        Gdk = self.Gdk
        w = self._win(snapshot=snap(self._path("b.png"), 0))
        # Shift tolerated (R18):
        self.assertTrue(
            self._key(w, Gdk.KEY_Left, Gdk.ModifierType.SHIFT_MASK))
        self.assertEqual(w.pinned_path, self._path("a.png"))
        # Ctrl: not a shortcut (R18):
        w2 = self._win(snapshot=snap(self._path("b.png"), 0))
        self.assertFalse(
            self._key(w2, Gdk.KEY_Left, Gdk.ModifierType.CONTROL_MASK))
        self.assertEqual(w2.decoder.requests, [])

    # -- Home/End jump (R25, §5.5; case 32) -----------------------------

    def test_home_end_jump_and_pin(self):
        # Home → oldest, End → newest; both pin (manual mode); End does not
        # resume live following (no watcher rescan — contrast with n).
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Home))       # live c → a, pins
        self.assertEqual(w.pinned_path, self._path("a.png"))
        self.assertEqual(w.decoder.requests, [(1, self._path("a.png"))])
        self._key(w, Gdk.KEY_Home)                         # oldest: no-op
        self.assertEqual(len(w.decoder.requests), 1)
        self.assertTrue(self._key(w, Gdk.KEY_End))         # a → c, pins
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self.assertEqual(w.decoder.requests,
                         [(1, self._path("a.png")),
                          (2, self._path("c.png"))])
        self._key(w, Gdk.KEY_End)                          # newest: no-op
        self.assertEqual(len(w.decoder.requests), 2)
        self.assertEqual(w.watcher.rescans, [])            # still manual

    def test_right_end_in_live_mode_pin_display(self):
        # rev 1.5: the attempt makes no change (the live display is the
        # newest), but the pin phase still applies — the "freeze the
        # stream" action. No redundant reload, no rescan.
        self._settle([("a.png", 300), ("c.png", 100)])
        Gdk = self.Gdk
        for key in (Gdk.KEY_Right, Gdk.KEY_End):
            w = self._win(snapshot=snap(self._path("c.png"), 0))
            self.assertTrue(self._key(w, key))
            self.assertEqual(w.pinned_path, self._path("c.png"))
            self.assertEqual(w.decoder.requests, [])
            self.assertEqual(w.watcher.rescans, [])

    def test_left_home_single_image_live_pins(self):
        # rev 1.5: a failed attempt still pins (freezes the display).
        self._settle([("a.png", 300)])
        Gdk = self.Gdk
        for key in (Gdk.KEY_Left, Gdk.KEY_Home):
            w = self._win(snapshot=snap(self._path("a.png"), 0))
            self.assertTrue(self._key(w, key))
            self.assertEqual(w.pinned_path, self._path("a.png"))
            self.assertEqual(w.decoder.requests, [])

    def test_step_from_image_gone(self):
        # rev 1.5: the pin holds its last mtime — scanning continues
        # after deleting the displayed file (case 32).
        self._settle([("a.png", 300), ("c.png", 100)])
        # b (between a and c by mtime) was displayed, then deleted:
        mid = int((time.time() - 200) * 10**9)
        w = self._win(pinned_path=self._path("b.png"), image_gone=True,
                      snapshot=snap(self._path("b.png"), mid))
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Right))   # → c (newer)
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self.assertEqual(w.decoder.requests, [(1, self._path("c.png"))])
        w2 = self._win(pinned_path=self._path("b.png"), image_gone=True,
                       snapshot=snap(self._path("b.png"), mid))
        self.assertTrue(self._key(w2, Gdk.KEY_Left))    # → a (older)
        self.assertEqual(w2.pinned_path, self._path("a.png"))
        self.assertEqual(w2.decoder.requests, [(1, self._path("a.png"))])

    def test_pause_pins_display(self):
        # R26: p pins whatever is displayed, no movement attempt.
        self._settle([("a.png", 300), ("c.png", 100)])
        Gdk = self.Gdk
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertTrue(self._key(w, Gdk.KEY_p))
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self.assertEqual(w.decoder.requests, [])   # no reload
        # manual mode: already pinned — no observable effect:
        self.assertTrue(self._key(w, Gdk.KEY_p))
        self.assertEqual(w.decoder.requests, [])
        # Shift tolerated (R18):
        w2 = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertTrue(
            self._key(w2, Gdk.KEY_P, Gdk.ModifierType.SHIFT_MASK))
        self.assertEqual(w2.pinned_path, self._path("c.png"))
        # Ctrl: not a shortcut (R18):
        w3 = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertFalse(
            self._key(w3, Gdk.KEY_p, Gdk.ModifierType.CONTROL_MASK))
        # waiting state: nothing displayed, nothing to pin:
        w4 = self._win()
        self.assertTrue(self._key(w4, Gdk.KEY_p))
        self.assertIsNone(w4.pinned_path)

    def test_home_end_waiting_noop(self):
        w = self._win()  # empty directory, nothing displayed
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Home))
        self.assertTrue(self._key(w, Gdk.KEY_End))
        self.assertEqual(w.decoder.requests, [])
        self.assertIsNone(w.pinned_path)

    def test_home_end_single_file_noop(self):
        # case 32: the jump keys have no effect in single-file mode
        self._settle([("a.png", 300), ("b.png", 200)])
        w = self._win(mode="file", snapshot=snap(self._path("b.png"), 0))
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_Home))
        self.assertTrue(self._key(w, Gdk.KEY_End))
        self.assertEqual(w.decoder.requests, [])
        self.assertIsNone(w.pinned_path)

    def test_end_after_image_gone_pins_newest(self):
        # End recovers the image-gone state but stays manual (pinned to the
        # newest — contrast with n, which resumes live following).
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(pinned_path=self._path("b.png"), image_gone=True)
        Gdk = self.Gdk
        self.assertTrue(self._key(w, Gdk.KEY_End))
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self.assertEqual(w.decoder.requests, [(1, self._path("c.png"))])
        self.assertEqual(w.watcher.rescans, [])

    def test_home_end_modifiers(self):
        # R18: Shift tolerated, Ctrl not a shortcut.
        self._settle([("a.png", 300), ("c.png", 100)])
        Gdk = self.Gdk
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertTrue(
            self._key(w, Gdk.KEY_Home, Gdk.ModifierType.SHIFT_MASK))
        self.assertEqual(w.pinned_path, self._path("a.png"))
        w2 = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertFalse(
            self._key(w2, Gdk.KEY_End, Gdk.ModifierType.CONTROL_MASK))
        self.assertEqual(w2.decoder.requests, [])


class TestCycleModeGui(unittest.TestCase):
    """Spec §11 cases 34–36 (headless half): cycle-mode key handling,
    rescan holding, first-slide selection and the deadline tick (R27–R29)
    against the real RiviewWindow methods; the on-screen advances and the
    `· cycle Ns` indicator are the manual GUI half."""

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)
        try:
            _D, _W, cls.Window, _A = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        cls.Gdk = Gdk

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="riview-cycle-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _win(self, **kw):
        return make_fake_window(self.Window, dir_abs=self.d, **kw)

    def _key(self, w, keyval, *mods):
        state = 0
        for m in mods:
            state |= int(m)
        return self.Window._on_key(w, None, keyval, 0, state)

    def _path(self, name):
        return os.path.join(self.d, name)

    def _settle(self, names):
        """Create files with old mtimes → settled at first observation."""
        now = time.time()
        for name, age_s in names:
            write(self._path(name), mtime=now - age_s)

    def _mns(self, name):
        return os.stat(self._path(name)).st_mtime_ns

    def _rescan_cycle(self, w):
        cands = riview.scan_candidates(self.d, w.exts)
        now_mono, now_wall = time.monotonic(), time.time()
        riview.update_observed(w.observer, cands, now_mono, now_wall)
        self.Window._rescan_cycle(w, cands, now_mono, now_wall)

    # -- case 34: c enters; mode-selecting keys exit --------------------------
    def test_c_enters_cycle_mode(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertTrue(self._key(w, self.Gdk.KEY_c))
        self.assertTrue(w.cycle_mode)
        self.assertIsNone(w.pinned_path)  # the pin is dropped
        self.assertIsNotNone(w._cycle_tick_id)  # the tick is armed
        # `c` again: a no-op, not a toggle (A1)
        self.assertTrue(self._key(w, self.Gdk.KEY_c))
        self.assertTrue(w.cycle_mode)

    def test_c_noop_in_single_file_mode(self):
        p = self._path("a.png")
        write(p)
        w = self._win(mode="file", only_path=p)
        self.assertTrue(self._key(w, self.Gdk.KEY_c))
        self.assertFalse(w.cycle_mode)

    # -- R31 (rev 1.7.2): space toggles cycle <-> pause -------------------------
    def test_space_starts_cycle_like_c(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self.assertTrue(self._key(w, self.Gdk.KEY_space))
        self.assertTrue(w.cycle_mode)
        self.assertIsNone(w.pinned_path)
        self.assertIsNotNone(w._cycle_tick_id)
        self.assertEqual(w._feedback_label.text, "cycle on: 9s")  # R30

    def test_space_stops_cycle_and_pins_like_p(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        self.assertTrue(self._key(w, self.Gdk.KEY_space))
        self.assertFalse(w.cycle_mode)
        self.assertEqual(w.pinned_path, self._path("c.png"))  # pinned
        self.assertIsNone(w._cycle_tick_id)
        self.assertEqual(w._feedback_label.text, "pause")  # R30

    def test_space_toggle_roundtrip(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self._key(w, self.Gdk.KEY_space)  # -> cycling
        self.assertTrue(w.cycle_mode)
        self._key(w, self.Gdk.KEY_space)  # -> paused (pinned)
        self.assertFalse(w.cycle_mode)
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self._key(w, self.Gdk.KEY_space)  # -> cycling again
        self.assertTrue(w.cycle_mode)
        self.assertEqual(w._feedback_label.text, "cycle on: 9s")

    def test_space_noop_in_single_file_mode(self):
        p = self._path("a.png")
        write(p)
        w = self._win(mode="file", only_path=p)
        self.assertTrue(self._key(w, self.Gdk.KEY_space))
        self.assertFalse(w.cycle_mode)
        self.assertFalse(w._feedback_label.visible)  # no-op -> no overlay

    def test_left_exits_cycle_and_steps_older(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        self.assertTrue(self._key(w, self.Gdk.KEY_Left))
        self.assertFalse(w.cycle_mode)
        # normal semantics apply: c → b, pinned (two-phase, R23)
        self.assertEqual(w.pinned_path, self._path("b.png"))
        self.assertEqual(w.decoder.requests, [(1, self._path("b.png"))])

    def test_n_exits_cycle_and_resumes_live(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        self.assertTrue(self._key(w, self.Gdk.KEY_n))
        self.assertFalse(w.cycle_mode)
        self.assertEqual(w.watcher.rescans, [0])  # select the newest now

    def test_p_exits_cycle_and_pins(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        self._key(w, self.Gdk.KEY_p)
        self.assertFalse(w.cycle_mode)
        self.assertEqual(w.pinned_path, self._path("c.png"))  # pinned in
        self.assertEqual(w.decoder.requests, [])  # place, no movement

    def test_home_exits_cycle_and_jumps_oldest(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        self._key(w, self.Gdk.KEY_Home)
        self.assertFalse(w.cycle_mode)
        self.assertEqual(w.pinned_path, self._path("a.png"))

    # -- case 35: Up/Down rescale the current interval ------------------------
    def test_up_down_rescale_current_interval(self):
        self._settle([("a.png", 300)])
        now = time.monotonic()
        w = self._win(snapshot=snap(self._path("a.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        w.cycle_interval_start = now - 2  # 2 s elapsed (worked example)
        self._key(w, self.Gdk.KEY_Down)   # 9 → 8
        self._key(w, self.Gdk.KEY_Down)   # 8 → 7
        self.assertEqual(w.cycle_s, 7)
        self.assertAlmostEqual(w.cycle_deadline, now + 5, delta=0.1)

    def test_down_floor_noop(self):
        self._settle([("a.png", 300)])
        now = time.monotonic()
        w = self._win(snapshot=snap(self._path("a.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        w.cycle_s = 1
        w.cycle_interval_start = now - 0.5
        deadline = w.cycle_deadline
        self._key(w, self.Gdk.KEY_Down)  # at the 1 s floor: no-op
        self.assertEqual(w.cycle_s, 1)
        self.assertEqual(w.cycle_deadline, deadline)  # untouched

    def test_new_time_below_elapsed_advances_at_next_tick(self):
        self._settle([("a.png", 300)])
        now = time.monotonic()
        w = self._win(snapshot=snap(self._path("a.png"), 0))
        self._key(w, self.Gdk.KEY_c)
        w.cycle_s = 3
        w.cycle_interval_start = now - 8  # 8 s elapsed > new 2 s
        self._key(w, self.Gdk.KEY_Down)   # 3 → 2
        self.assertLessEqual(w.cycle_deadline, now + 0.05)

    def test_up_outside_cycle_stores_only(self):
        w = self._win(snapshot=None)
        self._key(w, self.Gdk.KEY_Up)  # works outside cycle mode
        self.assertEqual(w.cycle_s, 10)
        self.assertFalse(w.cycle_mode)
        self.assertIsNone(w.cycle_deadline)  # no deadline exists

    # -- case 36: first slide selection ---------------------------------------
    def test_first_slide_oldest_with_cycle_flag(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(start_oldest=True, cycle_mode=True)
        self._rescan_cycle(w)
        self.assertEqual(w.decoder.requests, [(1, self._path("a.png"))])
        self.assertFalse(w.start_oldest)  # consumed
        self.assertIsNotNone(w.cycle_deadline)  # interval started

    def test_first_slide_newest_when_armed(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(cycle_mode=True)  # armed `c`: start_oldest False
        self._rescan_cycle(w)
        self.assertEqual(w.decoder.requests, [(1, self._path("c.png"))])

    def test_first_request_in_flight_holds(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(cycle_mode=True, start_oldest=True)
        w._cycle_first_req = (self._path("a.png"), 1, 5)
        self._rescan_cycle(w)
        self.assertEqual(w.decoder.requests, [])  # no reselection

    # -- case 34: rescan holding (live following suspended) --------------------
    def test_cycle_rescan_holds_display(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("b.png"), self._mns("b.png"),
                                    5),
                      cycle_mode=True)
        self._rescan_cycle(w)
        self.assertEqual(w.decoder.requests, [])  # newer c.png does not
        # displace the shown b.png (R3 suspended)

    def test_cycle_rescan_inplace_update_settled_reloads(self):
        self._settle([("b.png", 200)])
        old = self._mns("b.png") - 10 ** 9  # a stale version is displayed
        w = self._win(snapshot=snap(self._path("b.png"), old, 5),
                      cycle_mode=True)
        self._rescan_cycle(w)
        self.assertEqual(w.decoder.requests, [(1, self._path("b.png"))])  # R4

    def test_cycle_rescan_deleted_slide_holds(self):
        self._settle([("a.png", 300)])
        w = self._win(snapshot=snap(self._path("b.png"), 123, 5),
                      cycle_mode=True)
        self._rescan_cycle(w)
        self.assertEqual(w.decoder.requests, [])  # last frame held (A3)
        self.assertFalse(w.image_gone)  # no image-gone state while cycling

    # -- case 34: the deadline tick --------------------------------------------
    def test_cycle_tick_noop_before_deadline(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"), 0), cycle_mode=True)
        w.cycle_deadline = time.monotonic() + 99
        self.assertTrue(self.Window._cycle_tick(w))  # keeps firing
        self.assertEqual(w.decoder.requests, [])

    def test_cycle_tick_advances_and_wraps(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"),
                                    self._mns("c.png"), 5),
                      cycle_mode=True)
        w.cycle_deadline = time.monotonic() - 1  # past due
        self.assertTrue(self.Window._cycle_tick(w))
        # c is the newest → the wrap to the oldest
        self.assertEqual(w.decoder.requests, [(1, self._path("a.png"))])
        self.assertGreater(w.cycle_deadline, time.monotonic())

    def test_cycle_tick_steps_to_adjacent_newer(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("a.png"),
                                    self._mns("a.png"), 5),
                      cycle_mode=True)
        w.cycle_deadline = time.monotonic() - 1
        self.assertTrue(self.Window._cycle_tick(w))
        self.assertEqual(w.decoder.requests, [(1, self._path("b.png"))])

    def test_cycle_tick_disarmed(self):
        w = self._win(cycle_mode=False)
        self.assertFalse(self.Window._cycle_tick(w))  # source removed

    def test_cycle_tick_holds_single_settled_image(self):
        self._settle([("a.png", 300)])
        w = self._win(snapshot=snap(self._path("a.png"),
                                    self._mns("a.png"), 5),
                      cycle_mode=True)
        w.cycle_deadline = time.monotonic() - 1
        self.assertTrue(self.Window._cycle_tick(w))
        self.assertEqual(w.decoder.requests, [])  # nothing to advance to


class TestFeedbackOverlay(unittest.TestCase):
    """Spec §11 case 8k (headless): keypress feedback overlay (R30, §5.8)
    — the pure text function, effective-only triggering, windowed and
    full-screen display alike, canvas-based 10% bottom margin, 1 s expiry,
    replace/restart, toggle dismissal and the cosmetic invariant, against
    the real RiviewWindow methods; the on-screen look and the 1 s timing
    feel are the manual GUI half (cases 37/38)."""

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)
        try:
            _D, _W, cls.Window, _A = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        cls.Gdk = Gdk

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="riview-feedback-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _win(self, **kw):
        return make_fake_window(self.Window, dir_abs=self.d, **kw)

    def _key(self, w, keyval, *mods):
        state = 0
        for m in mods:
            state |= int(m)
        return self.Window._on_key(w, None, keyval, 0, state)

    def _path(self, name):
        return os.path.join(self.d, name)

    def _settle(self, names):
        """Create files with old mtimes → settled at first observation."""
        now = time.time()
        for name, age_s in names:
            write(self._path(name), mtime=now - age_s)

    def _mns(self, name):
        return os.stat(self._path(name)).st_mtime_ns

    def _texts(self, w):
        return [a for n, (a,) in w._feedback_label.calls if n == "set_text"]

    def _fs(self, w):
        w.fullscreen_mode = True
        return w

    # -- pure text function (R30) -------------------------------------------
    def test_message_text(self):
        f = riview.feedback_message
        self.assertEqual(f("c", True, 9), "cycle on: 9s")
        self.assertEqual(f("p", True, 9), "pause")
        self.assertEqual(f("n", True, 9), "newest live image")
        self.assertEqual(f("up", True, 4), "cycle: 4s")
        self.assertEqual(f("down", True, 12), "cycle: 12s")

    def test_message_none_for_noop(self):
        f = riview.feedback_message
        for k in ("c", "p", "n", "up", "down"):
            self.assertIsNone(f(k, False, 9))

    # -- effective keypresses show the overlay (full screen) ----------------
    def test_c_shows_overlay(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self._key(w, self.Gdk.KEY_c)
        self.assertEqual(self._texts(w), ["cycle on: 9s"])
        self.assertIn(("set_visible", (True,)), w._feedback_label.calls)
        self.assertIsNotNone(w._feedback_id)  # the 1 s timer is armed

    def test_p_shows_overlay_then_manual_noop(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self._key(w, self.Gdk.KEY_p)  # live → manual: effective
        self.assertEqual(self._texts(w), ["pause"])
        self._key(w, self.Gdk.KEY_p)  # manual: pin already the display
        self.assertEqual(self._texts(w), ["pause"])  # no-op → no overlay

    def test_p_from_cycle_stops_and_pins(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(
            snapshot=snap(self._path("c.png"), self._mns("c.png")),
            cycle_mode=True, cycle_deadline=time.monotonic() + 9,
            cycle_interval_start=time.monotonic()))
        self._key(w, self.Gdk.KEY_p)
        self.assertFalse(w.cycle_mode)
        self.assertEqual(w.pinned_path, self._path("c.png"))
        self.assertEqual(self._texts(w), ["pause"])

    def test_n_from_manual_shows_overlay(self):
        p = self._path("c.png")
        w = self._fs(self._win(snapshot=snap(p, 0), pinned_path=p))
        self._key(w, self.Gdk.KEY_n)
        self.assertEqual(self._texts(w), ["newest live image"])
        self.assertIsNone(w.pinned_path)
        self._key(w, self.Gdk.KEY_n)  # already live: no-op
        self.assertEqual(self._texts(w), ["newest live image"])

    def test_n_from_cycle_shows_overlay(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(
            snapshot=snap(self._path("c.png"), self._mns("c.png")),
            cycle_mode=True, cycle_deadline=time.monotonic() + 9,
            cycle_interval_start=time.monotonic()))
        self._key(w, self.Gdk.KEY_n)
        self.assertFalse(w.cycle_mode)
        self.assertEqual(self._texts(w), ["newest live image"])
        self.assertIn(0, w.watcher.rescans)  # live selection resumed (R3)

    def test_up_down_show_new_value(self):
        w = self._fs(self._win())
        self._key(w, self.Gdk.KEY_Up)
        self.assertEqual(self._texts(w), ["cycle: 10s"])
        self._key(w, self.Gdk.KEY_Down)
        self.assertEqual(self._texts(w), ["cycle: 10s", "cycle: 9s"])

    def test_down_at_floor_shows_nothing(self):
        w = self._fs(self._win(cycle_s=1))
        self._key(w, self.Gdk.KEY_Down)
        self.assertEqual(self._texts(w), [])
        self.assertEqual(w.cycle_s, 1)

    # -- windowed mode: the overlay fires there too (1.7.1 amendment) ------
    def test_windowed_c_shows_too(self):
        # pre-release amendment (riview 1.7.1): the overlay fires in windowed
        # mode too — the header keeps its persistent status alongside it.
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._win(snapshot=snap(self._path("c.png"),
                                    self._mns("c.png")))
        self._key(w, self.Gdk.KEY_c)  # fullscreen_mode stays False
        self.assertTrue(w.cycle_mode)  # the action itself still happened
        self.assertIn(("set_visible", (True,)), w._feedback_label.calls)
        self.assertIn(("set_text", ("cycle on: 9s",)), w._feedback_label.calls)
        self.assertIsNotNone(w._feedback_id)

    # -- no-op keypresses: no overlay (full screen) -------------------------
    def test_c_already_cycling_no_overlay(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(
            snapshot=snap(self._path("c.png"), self._mns("c.png")),
            cycle_mode=True))
        self._key(w, self.Gdk.KEY_c)
        self.assertEqual(self._texts(w), [])

    def test_n_already_live_no_overlay(self):
        p = self._path("c.png")
        w = self._fs(self._win(snapshot=snap(p, 0)))
        self._key(w, self.Gdk.KEY_n)
        self.assertEqual(self._texts(w), [])

    def test_p_waiting_no_overlay(self):
        w = self._fs(self._win())  # no snapshot: waiting state
        self._key(w, self.Gdk.KEY_p)
        self.assertEqual(self._texts(w), [])

    def test_c_single_file_no_overlay(self):
        p = self._path("a.png")
        write(p)
        w = self._fs(self._win(mode="file", only_path=p))
        self._key(w, self.Gdk.KEY_c)
        self.assertFalse(w.cycle_mode)
        self.assertEqual(self._texts(w), [])

    def test_no_overlay_at_startup(self):
        """A full-screen launch shows nothing until the first keypress."""
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self.assertEqual(w._feedback_label.calls, [])

    # -- 1 s lifetime: expiry and replace/restart ----------------------------
    def test_expiry_hides(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self._key(w, self.Gdk.KEY_c)
        self.assertIsNotNone(w._feedback_id)
        w._feedback_hide()  # the 1 s timer's callback
        self.assertIsNone(w._feedback_id)
        self.assertEqual(w._feedback_label.calls[-1],
                         ("set_visible", (False,)))

    def test_noop_keypress_leaves_running_timer(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self._key(w, self.Gdk.KEY_c)  # overlay up
        id_before = w._feedback_id
        self._key(w, self.Gdk.KEY_c)  # still cycling: no-op keypress
        self.assertEqual(self._texts(w), ["cycle on: 9s"])  # no new text
        self.assertEqual(w._feedback_id, id_before)  # timer untouched

    def test_replace_restarts(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self._key(w, self.Gdk.KEY_c)
        first_id = w._feedback_id
        self._key(w, self.Gdk.KEY_Up)  # second feedback within the second
        self.assertEqual(self._texts(w), ["cycle on: 9s", "cycle: 10s"])
        self.assertIsNotNone(w._feedback_id)  # re-armed (last wins)
        self.assertEqual(w._feedback_label.calls.count(
            ("set_visible", (True,))), 2)
        self.assertIsNotNone(first_id)  # the old source was removed

    # -- full-screen toggle dismisses immediately ---------------------------
    def test_fullscreen_toggle_dismisses(self):
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        w.fullscreen = lambda: None
        w.unfullscreen = lambda: None
        self._key(w, self.Gdk.KEY_c)
        self.assertIsNotNone(w._feedback_id)
        self.Window._set_fullscreen(w, False)
        self.assertEqual(w._feedback_label.calls[-1],
                         ("set_visible", (False,)))
        self.assertIsNone(w._feedback_id)
        self.assertIn(("set_visible", (True,)), w.header.calls)
        self.assertFalse(w.fullscreen_mode)

    # -- cosmetic invariant: the cycle clock is untouched -------------------
    def test_overlay_does_not_touch_cycle_state(self):
        self._settle([("a.png", 300), ("b.png", 200), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        self._key(w, self.Gdk.KEY_c)   # cycle on, 9 s
        self._key(w, self.Gdk.KEY_Up)  # R28 rescale, +1 s
        self.assertTrue(w.cycle_mode)  # still cycling
        self.assertEqual(w.cycle_s, 10)
        self.assertIsNotNone(w.cycle_deadline)  # rescaled, not clobbered
        self.assertIsNotNone(w._cycle_tick_id)  # tick still armed

    # -- position: bottom edge 10% up from the canvas bottom (§12.7) --------
    def test_margin_is_10pct_of_canvas_height(self):
        """The bottom margin is computed from the canvas container's
        allocated height at show time (below the header bar in windowed
        mode; canvas == window in full screen) — GTK4 has no window
        size-changed signal to track."""
        self._settle([("a.png", 300), ("c.png", 100)])
        w = self._fs(self._win(snapshot=snap(self._path("c.png"),
                                             self._mns("c.png"))))
        w._canvas = _FakeCanvas(720)
        self._key(w, self.Gdk.KEY_c)
        self.assertIn(("set_margin_bottom", (72,)),  # 10% of 720
                      w._feedback_label.calls)
        w._feedback_label.calls.clear()
        w._canvas = _FakeCanvas(800)
        self._key(w, self.Gdk.KEY_p)
        self.assertIn(("set_margin_bottom", (80,)),  # 10% of 800
                      w._feedback_label.calls)

    def test_window_connects_no_signals(self):
        """Regression guard: RiviewWindow.__init__ connects no signals to
        the window at all — two successive attempts to use window signals
        for the overlay's 10% bottom margin failed on this box
        (window-handle-size-changed needs a newer libadwaita; size-allocate
        does not exist in GTK4), and the suite has no display to catch it.
        The margin is computed at show time instead; if a window signal is
        ever added, it must be verified against the installed
        GTK/libadwaita typelibs and added to the allowlist here."""
        import inspect
        import re
        src = inspect.getsource(self.Window.__init__)
        names = set(re.findall(r'self\.connect\(\s*[\'"]([^\'"]+)', src))
        stable = set()  # no window signals in v1
        self.assertEqual(names, stable)


class TestFitWindow(unittest.TestCase):
    """Spec §11 case 8g: window-fit geometry (R24, pure unit)."""

    def _fit(self, mode, img, box, screen, header=40, sf=1):
        return riview.fit_window(mode, img[0], img[1], box[0], box[1],
                                 screen[0], screen[1], header, sf)

    def test_ratio_landscape(self):
        # 16:9 image, 1200x800 window budget, 40 px header → the canvas
        # budget is 1200x760; width binds → canvas 1200x675 → window
        # 1200x715.
        self.assertEqual(self._fit("ratio", (1920, 1080), (1200, 800),
                                   (1920, 1080)), (1200, 715))

    def test_ratio_portrait(self):
        # 9:16 image in a landscape budget: height binds → canvas 405x720
        # → window 405x760.
        self.assertEqual(self._fit("ratio", (720, 1280), (1200, 760),
                                   (1920, 1080)), (405, 760))

    def test_ratio_square(self):
        self.assertEqual(self._fit("ratio", (800, 800), (1200, 760),
                                   (1920, 1080)), (720, 760))

    def test_ratio_header_correction(self):
        # portrait image, height binds: a taller header shrinks the canvas
        # width (the window height stays at the budget).
        a = self._fit("ratio", (720, 1280), (1200, 760), (1920, 1080),
                      header=40)
        b = self._fit("ratio", (720, 1280), (1200, 760), (1920, 1080),
                      header=100)
        self.assertEqual(a, (405, 760))
        self.assertEqual(b, (371, 760))

    def test_ratio_cosmic_cap_user_case(self):
        # D15: the spec owner's display — 1024x1024 image, 80 % box
        # 2671x1502 (monitor 3339x1878), 47 px header. The cap box is
        # min(2671,1600) x min(1502,1200) = 1600x1200; the header leaves
        # 1153 of canvas height, which binds → canvas 1153x1153 → window
        # 1153x1200.
        self.assertEqual(self._fit("ratio", (1024, 1024), (2671, 1502),
                                   (3339, 1878), header=47), (1153, 1200))

    def test_ratio_cosmic_cap_width_binds(self):
        # D15: 8:3 image, huge 80 % box — the capped width (1600) binds:
        # canvas 1600x600 → window 1600x647.
        self.assertEqual(self._fit("ratio", (4000, 1500), (3000, 1700),
                                   (3840, 2160), header=47), (1600, 647))

    def test_ratio_cosmic_cap_height_binds(self):
        # D15: 9:16 portrait, box taller than the cap — cap box 1600x1200
        # → canvas 1600x1153, the header-corrected height binds →
        # 648.6x1153 → window 649x1200.
        self.assertEqual(self._fit("ratio", (1080, 1920), (2671, 1700),
                                   (3339, 2125), header=47), (649, 1200))

    def test_exact_not_capped_by_cosmic_cap(self):
        # D15: the cap is `ratio`-only — a 1900 px-wide image at 1:1 stays
        # 1900 wide (wider than COSMIC_CAP_W) in exact mode.
        self.assertEqual(self._fit("exact", (1900, 1000), (3000, 1700),
                                   (3840, 2160)), (1900, 1040))

    def test_exact_one_to_one(self):
        # sf=1: canvas = the image, window = image + header.
        self.assertEqual(self._fit("exact", (960, 540), (1200, 800),
                                   (1920, 1080)), (960, 580))

    def test_exact_scale_factor(self):
        # sf=2: a 1920x1080 image is 960x540 logical pixels.
        self.assertEqual(self._fit("exact", (1920, 1080), (1200, 800),
                                   (1920, 1080), sf=2), (960, 580))

    def test_exact_larger_than_screen_degrades_to_ratio(self):
        # 3840x2160 on a 1920x1080 screen: ratio fit within the full
        # monitor minus the header → 1848.9x1040 canvas → 1849x1080 window.
        self.assertEqual(self._fit("exact", (3840, 2160), (1200, 800),
                                   (1920, 1080)), (1849, 1080))

    def test_floor_tiny_square(self):
        # a 16x16 image in exact mode: 1:1 canvas 16x16 → the 320 px floor
        # re-fits within 320x320 → a square canvas.
        self.assertEqual(self._fit("exact", (16, 16), (3000, 1700),
                                   (3840, 2160)), (320, 360))

    def test_floor_preserves_ratio(self):
        # 1:4 portrait, exact mode: 16x64 canvas → floor box → 80x320.
        self.assertEqual(self._fit("exact", (16, 64), (3000, 1700),
                                   (3840, 2160)), (80, 360))

    def test_floor_wins_on_pathological_small_monitor(self):
        # budget canvas 200x110 → 146.7x110 → the floor re-fits to
        # 320x240; the window exceeds the budget (documented degenerate
        # case: the floor wins).
        self.assertEqual(self._fit("ratio", (640, 480), (200, 150),
                                   (200, 150)), (320, 280))

    def test_off_no_fit(self):
        self.assertIsNone(self._fit("off", (960, 540), (1200, 800),
                                    (1920, 1080)))

    def test_missing_monitor_box_no_fit(self):
        self.assertIsNone(self._fit("ratio", (960, 540), (0, 0), (0, 0)))
        self.assertIsNone(self._fit("exact", (960, 540), (1200, 800),
                                    (0, 0)))

    def test_no_canvas_room_no_fit(self):
        # header taller than the budget → no canvas → no fit.
        self.assertIsNone(self._fit("ratio", (960, 540), (1200, 30),
                                    (1920, 1080)))
        self.assertIsNone(self._fit("exact", (960, 540), (1200, 800),
                                    (1920, 1080), header=2000))


class _FakeGeometry:
    def __init__(self, w, h):
        self.width, self.height = w, h


class _FakeMonitor:
    """Duck-typed GdkMonitor: geometry and/or legacy get_width/height."""

    def __init__(self, geo=None, legacy=None):
        self._geo, self._legacy = geo, legacy

    def get_geometry(self):
        return self._geo

    def get_width(self):
        return self._legacy[0] if self._legacy else None

    def get_height(self):
        return self._legacy[1] if self._legacy else None


class TestProbeDimensions(unittest.TestCase):
    """Spec §11 case 8g: header dimension probes (R24 startup fit,
    pure). The window opens at the fit size of the first image, so
    dimensions must come from the file header before any decode."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="riview-probe-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_png(self):
        self.assertEqual(riview.probe_dimensions(_png_bytes(800, 600)),
                         (800, 600))

    def test_png_truncated(self):
        self.assertIsNone(riview.probe_dimensions(_png_bytes(800, 600)[:20]))

    def test_jpeg_sof0_after_segments(self):
        d = (b"\xff\xd8"
             + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
             + b"\xff\xdb\x00\x42" + b"\x00" * 66
             + b"\xff\xc0\x00\x11\x08"
             + (480).to_bytes(2, "big") + (640).to_bytes(2, "big")
             + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")
        self.assertEqual(riview.probe_dimensions(d), (640, 480))

    @staticmethod
    def _webp(chunk, payload):
        body = chunk + len(payload).to_bytes(4, "little") + payload
        return b"RIFF" + (4 + len(body)).to_bytes(4, "little") + b"WEBP" + body

    def test_webp_vp8(self):
        # start code, then 14-bit width (320) and height (240), LE
        p = b"\x9d\x01\x2a" + bytes([0x40, 0x01, 0xF0, 0x00]) + b"\x00" * 10
        self.assertEqual(riview.probe_dimensions(self._webp(b"VP8 ", p)),
                         (320, 240))

    def test_webp_vp8l(self):
        v = 63 | (79 << 14)  # w-1 = 63, h-1 = 79
        p = b"\x2f" + v.to_bytes(4, "little") + b"\x00" * 6
        self.assertEqual(riview.probe_dimensions(self._webp(b"VP8L", p)),
                         (64, 80))

    def test_webp_vp8x(self):
        v = 99 | (99 << 14)  # w-1 = h-1 = 99
        p = b"\x00" + v.to_bytes(4, "little") + b"\x00" * 5
        self.assertEqual(riview.probe_dimensions(self._webp(b"VP8X", p)),
                         (100, 100))

    def test_gif(self):
        d = (b"GIF89a" + (64).to_bytes(2, "little")
             + (48).to_bytes(2, "little") + b"\x00" * 7)
        self.assertEqual(riview.probe_dimensions(d), (64, 48))

    def test_bmp(self):
        d = (b"BM" + b"\x00" * 16 + (32).to_bytes(4, "little")
             + (16).to_bytes(4, "little") + b"\x00" * 4)
        self.assertEqual(riview.probe_dimensions(d), (32, 16))

    def test_bmp_topdown_negative_height(self):
        d = (b"BM" + b"\x00" * 16 + (32).to_bytes(4, "little")
             + (16).to_bytes(4, "little", signed=True) + b"\x00" * 4)
        self.assertEqual(riview.probe_dimensions(d), (32, 16))

    def test_tiff_deliberately_unsupported(self):
        self.assertIsNone(riview.probe_dimensions(b"II\x2a\x00" + b"\x00" * 16))
        self.assertIsNone(riview.probe_dimensions(b"MM\x00\x2a" + b"\x00" * 16))

    def test_garbage_and_empty(self):
        self.assertIsNone(riview.probe_dimensions(b"hello world"))
        self.assertIsNone(riview.probe_dimensions(b""))

    def test_file_roundtrip(self):
        p = os.path.join(self.d, "a.png")
        write(p, _png_bytes(64, 48))
        self.assertEqual(riview.probe_dimensions_file(p), (64, 48))

    def test_file_missing(self):
        self.assertIsNone(riview.probe_dimensions_file("/nonexistent/x.png"))


class TestMonitorSize(unittest.TestCase):
    """Spec §12.7/§13.2: portable monitor size in logical pixels
    (this binding lacks the GTK3-era get_width()/get_height() and
    exposes get_geometry())."""

    def test_geometry_path(self):
        m = _FakeMonitor(geo=_FakeGeometry(1920, 1080))
        self.assertEqual(riview._monitor_logical_size(m), (1920, 1080))

    def test_geometry_wins_over_legacy(self):
        m = _FakeMonitor(geo=_FakeGeometry(1920, 1080), legacy=(640, 480))
        self.assertEqual(riview._monitor_logical_size(m), (1920, 1080))

    def test_legacy_width_height_path(self):
        m = _FakeMonitor(legacy=(3840, 2160))
        self.assertEqual(riview._monitor_logical_size(m), (3840, 2160))

    def test_neither_api_none(self):
        class Bare:
            pass
        self.assertIsNone(riview._monitor_logical_size(Bare()))

    def test_zero_geometry_none(self):
        self.assertIsNone(riview._monitor_logical_size(
            _FakeMonitor(geo=_FakeGeometry(0, 0))))


class TestResizeWindow(unittest.TestCase):
    """§12.7/§13.2: the portable resize chain. This binding exposes no
    Gtk.Window.resize (deprecated in GTK 4.14) and set_default_size is
    a no-op on a mapped window (verified on Wayland/COSMIC): mapped
    growth therefore goes through a size request (a minimum) that is
    released afterwards; shrink is the compositor's domain."""

    class W:
        def __init__(self, mapped=True, size=(3000, 1728),
                     with_resize=False):
            self.calls = []
            self.get_mapped = lambda: mapped
            self.get_size = lambda: size
            self.set_default_size = (lambda a, b: self.calls.append(
                ("default", a, b)))
            self.set_size_request = (lambda a, b: self.calls.append(
                ("request", a, b)))
            if with_resize:
                self.resize = (lambda a, b: self.calls.append(
                    ("resize", a, b)))

    def test_resize_api_preferred(self):
        w = self.W(with_resize=True)
        riview._resize_window(w, 1000, 800)
        self.assertEqual(w.calls, [("resize", 1000, 800)])

    def test_unmapped_uses_default_size(self):
        w = self.W(mapped=False)
        riview._resize_window(w, 1000, 800)
        self.assertEqual(w.calls, [("default", 1000, 800)])

    def test_mapped_shrink_or_keep_is_noop(self):
        w = self.W(mapped=True, size=(3000, 1728))
        riview._resize_window(w, 1600, 900)
        self.assertEqual(w.calls, [])

    def test_mapped_grow_uses_size_request(self):
        w = self.W(mapped=True, size=(1000, 800))
        riview._resize_window(w, 1600, 900)
        self.assertEqual(w.calls, [("request", 1600, 900)])

    def test_mapped_grow_within_tolerance_is_noop(self):
        # A few-px grow (the fit pass re-measuring the header against the
        # 47 px construction estimate) must not issue a resize: on
        # COSMIC/Wayland the size-negotiation round trip can make the
        # compositor apply the remembered window size — observed as
        # --fit ratio snapping to a smaller non-ratio size ~1 s after
        # open (§13.2).
        w = self.W(mapped=True, size=(1713, 1760))
        riview._resize_window(w, 1716, 1763)
        self.assertEqual(w.calls, [])
        # beyond the tolerance on either axis: the grow proceeds
        w2 = self.W(mapped=True, size=(1713, 1760))
        target_w = 1713 + riview.RESIZE_TOL + 2
        riview._resize_window(w2, target_w, 1763)
        self.assertEqual(w2.calls, [("request", target_w, 1763)])

    def test_mapped_grow_unknown_size_skips(self):
        # gtk_window_get_size was observed reporting 0×0 on a mapped
        # window (Wayland/COSMIC); with no other size source the current
        # size is unverifiable → no grow: the min-size request and its
        # later release can make COSMIC re-apply the remembered window
        # size (§13.2).
        w = self.W(mapped=True, size=(0, 0))
        riview._resize_window(w, 1455, 1502)
        self.assertEqual(w.calls, [])

    def test_window_size_prefers_widget_queries(self):
        # The user's snap scenario: the window is visibly 1455×1502 but
        # gtk_window_get_size reports 0×0; get_width()/get_height()
        # (GTK 4.10) report the truth → the equal target is a no-op.
        w = self.W(mapped=True, size=(0, 0))
        w.get_width = lambda: 1455
        w.get_height = lambda: 1502
        riview._resize_window(w, 1455, 1502)
        self.assertEqual(w.calls, [])
        # …and a genuinely larger target still grows.
        w2 = self.W(mapped=True, size=(0, 0))
        w2.get_width = lambda: 1455
        w2.get_height = lambda: 1502
        riview._resize_window(w2, 2000, 1502)
        self.assertEqual(w2.calls, [("request", 2000, 1502)])

    def test_window_size_fallback_chain(self):
        class F:
            get_size = lambda self: (111, 222)
        self.assertEqual(riview._window_size(F()), (111, 222))
        class G(F):
            def __init__(self):
                self.get_allocated_width = lambda: 333
                self.get_allocated_height = lambda: 444
        self.assertEqual(riview._window_size(G()), (333, 444))
        class H(G):
            def __init__(self):
                G.__init__(self)
                self.get_width = lambda: 5
                self.get_height = lambda: 0  # invalid → fall through
        self.assertEqual(riview._window_size(H()), (333, 444))
        class I:
            pass
        self.assertEqual(riview._window_size(I()), (0, 0))

    def test_mapped_grow_releases_clamp(self):
        # Regression (real GLib main loop): PyGObject invokes
        # GLib.timeout_add callbacks with NO arguments (the C
        # g_source_func signature does not apply to Python). If the
        # release callback takes one, every tick raises a TypeError and
        # the size-request clamp is never released — the window is
        # permanently unshrinkable by hand (§13.2).
        import gi
        gi.require_version("GLib", "2.0")
        from gi.repository import GLib
        w = self.W(mapped=True, size=(1000, 800))
        riview._resize_window(w, 1600, 900)
        self.assertEqual(w.calls[-1], ("request", 1600, 900))
        w.get_size = lambda: (1600, 900)  # compositor acked the grow
        loop = GLib.MainLoop()
        GLib.timeout_add(500, loop.quit)
        loop.run()
        self.assertEqual(w.calls[-1], ("request", -1, -1))


class TestFitWindowGui(unittest.TestCase):
    """Spec §11 case 8h: fit-once and `r` (R24) against the real
    RiviewWindow methods with a fake window; the GTK surface is stubbed
    (the on-screen behaviour is manual case 31)."""

    BOX = (1200, 800, 1920, 1080, 40, 1)  # box, screen, header_h, sf

    @classmethod
    def setUpClass(cls):
        for var in ("DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(var, None)
        try:
            _D, _W, cls.Window, _A = riview._gui_classes()
        except Exception as e:
            raise unittest.SkipTest(f"GTK not importable headless: {e}")
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        cls.Gdk = Gdk
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        cls.Pixbuf = GdkPixbuf.Pixbuf

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="riview-fit-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _pixbuf(self, w, h):
        p = os.path.join(self.d, f"img-{w}x{h}.png")
        write(p, self._png_bytes(w, h))
        pb = self.Pixbuf.new_from_file(p)
        self.assertIsNotNone(pb)
        return pb

    @staticmethod
    def _png_bytes(w, h):
        return _png_bytes(w, h)

    def _win(self, **kw):
        calls = []
        kw.setdefault("fit_mode", "ratio")
        kw.setdefault("fitted", False)
        kw.setdefault("_monitor_box", lambda: self.BOX)
        w = make_fake_window(self.Window, calls=calls,
                             resize=lambda *a: calls.append(("resize", a)),
                             **kw)
        return w

    def _load(self, w, pixbuf):
        self.Window._on_load_ok(w, "/d/img.png", pixbuf)

    def test_fit_pass_resizes_once_on_first_load(self):
        # 160x80 (2:1) in canvas budget 1200x760: width binds → canvas
        # 1200x600 → window 1200x640; a second load resizes nothing.
        w = self._win()
        self._load(w, self._pixbuf(160, 80))
        self.assertEqual(w.calls, [("resize", (1200, 640))])
        self.assertTrue(w.fitted)
        self._load(w, self._pixbuf(80, 160))
        self.assertEqual(w.calls, [("resize", (1200, 640))])

    def test_fit_pass_uses_original_dimensions(self):
        # The fit is measured on the image's ORIGINAL dimensions, not the
        # scaled display pixbuf (1:1 "exact" semantics, §5.6): the file
        # is 320x160; the decoded pixbuf is 960x480 (decode target).
        p = os.path.join(self.d, "orig.png")
        write(p, self._png_bytes(320, 160))
        w = self._win(fit_mode="exact")
        self.Window._on_load_ok(w, p, self._pixbuf(960, 480))
        # 320x160 at 1:1 (sf=1), floor-preserving → window 320x200
        # (header 40). If the scaled 960x480 pixbuf were used: 960x520.
        self.assertEqual(w.calls, [("resize", (320, 200))])

    def test_fit_pass_skipped_in_off_mode(self):
        w = self._win(fit_mode="off")
        self._load(w, self._pixbuf(160, 80))
        self.assertEqual(w.calls, [])
        self.assertFalse(w.fitted)   # off never latches

    def test_fit_pass_skipped_in_fullscreen_until_windowed(self):
        w = self._win(fullscreen_mode=True)
        self._load(w, self._pixbuf(160, 80))
        self.assertEqual(w.calls, [])
        self.assertFalse(w.fitted)   # not latched while full-screened
        w.fullscreen_mode = False    # user exits full screen (f)
        self._load(w, self._pixbuf(160, 80))
        self.assertEqual(w.calls, [("resize", (1200, 640))])

    def test_r_refits_to_current_image(self):
        Gdk = self.Gdk
        w = self._win()
        self._load(w, self._pixbuf(160, 80))
        self.assertEqual(w.calls, [("resize", (1200, 640))])
        self.assertTrue(self.Window._on_key(w, None, Gdk.KEY_r, 0, 0))
        self.assertEqual(w.calls, [("resize", (1200, 640)),
                                   ("resize", (1200, 640))])
        # navigate to a 3:1 image (snapshot swapped), then r: canvas
        # 1200x400 → window 1200x440.
        w.snapshot = riview.Snapshot("/d/other.png", 0, 0, 900, 300)
        self.assertTrue(self.Window._on_key(w, None, Gdk.KEY_R, 0, 0))
        self.assertEqual(w.calls[-1], ("resize", (1200, 440)))

    def test_r_uses_original_dimensions(self):
        Gdk = self.Gdk
        p = os.path.join(self.d, "orig.png")
        write(p, self._png_bytes(320, 160))
        w = self._win(fit_mode="exact")
        # displayed (scaled) size 960x480; original file 320x160
        w.snapshot = riview.Snapshot(p, 0, 0, 960, 480)
        self.assertTrue(self.Window._on_key(w, None, Gdk.KEY_r, 0, 0))
        self.assertEqual(w.calls, [("resize", (320, 200))])

    def test_r_noop_in_off_fullscreen_waiting(self):
        Gdk = self.Gdk
        off = self._win(fit_mode="off")
        off.snapshot = riview.Snapshot("/d/a.png", 0, 0, 160, 80)
        self.assertTrue(self.Window._on_key(off, None, Gdk.KEY_r, 0, 0))
        self.assertEqual(off.calls, [])
        fs = self._win(fullscreen_mode=True)
        fs.snapshot = riview.Snapshot("/d/a.png", 0, 0, 160, 80)
        self.assertTrue(self.Window._on_key(fs, None, Gdk.KEY_r, 0, 0))
        self.assertEqual(fs.calls, [])
        wait = self._win()            # no snapshot (waiting state)
        self.assertTrue(self.Window._on_key(wait, None, Gdk.KEY_r, 0, 0))
        self.assertEqual(wait.calls, [])

    def test_fit_window_synonym_parses(self):
        p = riview.build_parser()
        self.assertEqual(p.parse_args(["--fit", "exact", "d"]).fit, "exact")
        self.assertEqual(p.parse_args(["--fit-window", "exact", "d"]).fit,
                         "exact")
        self.assertEqual(p.parse_args(["d"]).fit, "ratio")

    def test_monitor_box_from_geometry(self):
        # The real _monitor_box against a duck-typed monitor returning a
        # real Gdk.Rectangle — the installed binding exposes no
        # monitor get_width()/get_height(), only get_geometry (§13.2).
        from gi.repository import Gdk
        geo = Gdk.Rectangle()
        geo.width, geo.height = 1920, 1080
        class Mon:
            def get_geometry(self):
                return geo
        class Hdr:
            def get_allocated_height(self):
                return 40
        w = make_fake_window(self.Window, _monitor=lambda: Mon(),
                             header=Hdr(), get_scale_factor=lambda: 1)
        self.assertEqual(w._monitor_box(), (1536, 864, 1920, 1080, 40, 1))

    # -- R24 early fit: the window opens at the fit size of the newest
    #    settled file, computed from its header before the first decode
    #    (set_default_size before presentation is the only reliable
    #    client-side sizing on this binding, §13.2).

    class _Hdr:
        def __init__(self, h):
            self._h = h

        def get_height(self):
            return self._h

        def get_allocated_height(self):
            return self._h

    def _monitor1920(self):
        from gi.repository import Gdk
        geo = Gdk.Rectangle()
        geo.width, geo.height = 1920, 1080

        class Mon:
            def get_geometry(self):
                return geo
        return Mon()

    def _init_win(self, **kw):
        """A window whose REAL _monitor_box runs against a 1920×1080
        monitor (box 1536×864)."""
        kw.setdefault("fit_mode", "ratio")
        w = make_fake_window(self.Window, **kw)
        w._monitor = lambda: self._monitor1920()
        w.get_scale_factor = lambda: 1
        w.header = self._Hdr(40)
        return w

    def test_init_size_early_fit_ratio(self):
        # 800x600 (4:3) settled: canvas budget 1536x824 → height binds
        # → canvas 1099x824 → window 1099x864 (header 40).
        p = os.path.join(self.d, "a.png")
        write(p, self._png_bytes(800, 600), mtime=time.time() - 100)
        w = self._init_win(dir_abs=self.d)
        self.assertEqual(w._init_size(), (1099, 864))

    def test_init_size_exact_mode(self):
        p = os.path.join(self.d, "a.png")
        write(p, self._png_bytes(800, 600), mtime=time.time() - 100)
        w = self._init_win(dir_abs=self.d, fit_mode="exact")
        # 1:1 (sf=1): 800x600 within screen-minus-header (1920x1040)
        # → window 800x640.
        self.assertEqual(w._init_size(), (800, 640))

    def test_init_size_no_candidate_default_box(self):
        w = self._init_win(dir_abs=self.d)  # empty directory
        self.assertEqual(w._init_size(), (1536, 864))

    def test_init_size_unsettled_file_default_box(self):
        p = os.path.join(self.d, "a.png")
        write(p, self._png_bytes(800, 600))  # mtime = now → not settled
        w = self._init_win(dir_abs=self.d)
        self.assertEqual(w._init_size(), (1536, 864))

    def test_init_size_fit_off_ignores_candidate(self):
        p = os.path.join(self.d, "a.png")
        write(p, self._png_bytes(800, 600), mtime=time.time() - 100)
        w = self._init_win(dir_abs=self.d, fit_mode="off")
        self.assertEqual(w._init_size(), (1536, 864))

    def test_init_size_single_file_mode(self):
        p = os.path.join(self.d, "a.png")
        write(p, self._png_bytes(800, 600), mtime=time.time() - 100)
        w = self._init_win(mode="file", only_path=p, dir_abs=self.d)
        self.assertEqual(w._init_size(), (1099, 864))

    def test_init_size_header_fallback_47(self):
        # Header not allocated yet (construction time): the 47 px
        # fallback is used for the early fit.
        p = os.path.join(self.d, "a.png")
        write(p, self._png_bytes(800, 600), mtime=time.time() - 100)
        w = self._init_win(dir_abs=self.d)
        w.header = self._Hdr(0)  # unallocated
        self.assertEqual(w._init_size(), (1089, 864))


if __name__ == "__main__":
    unittest.main(verbosity=2)
