#!/usr/bin/env python3
"""Headless test suite for riview (spec §11, cases 1–8d).

No display required: exercises the pure selection/settle layer with fake
clocks, `--print` mode, CLI validation, desktop install, and launch-context
detection via subprocess, plus headless integration of the watcher/decoder
plumbing and the keyboard/mouse input logic (§11 cases 9–28 are the manual
GUI cases).

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
        self.assertIn("riview 1.0.0", r.stdout)

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
                      ["--print", "--fullscreen"]):
            r = run_riview(*extra, self.dir)
            self.assertEqual(r.returncode, 2, f"{extra}: {r.stderr}")

    def test_desktop_flag_conflicts(self):  # case 6
        for extra in (["--install-desktop", self.dir],
                      ["--install-desktop", "--print", self.dir],
                      ["--install-desktop", "--fullscreen", self.dir],
                      ["--install-desktop", "--uninstall-desktop"]):
            r = run_riview(*extra)
            self.assertEqual(r.returncode, 2, f"{extra}: {r.stderr}")


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
