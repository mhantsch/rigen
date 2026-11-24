#!/usr/bin/env python3
"""rigen test suite — mirrors RIGEN-SW-SPECIFICATION.md §11.

Run:  python3 tests/test_rigen.py [-v]
"""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIGEN = ROOT / "rigen"
MOCK = Path(__file__).resolve().parent / "mock_lemond.py"
FAKE_LEMONADE = Path(__file__).resolve().parent / "fake_lemonade"

PNG_SIG = b"\x89PNG\r\n\x1a\n"
AMAZING_RENDER = "AmazingRender\u2011XL\u2011v14"  # display name with U+2011


def pixel_of(png: bytes) -> tuple:
    """Decode the pixel of the mock's 1x1 RGB PNGs."""
    idx = png.find(b"IDAT")
    assert idx > 0, "not a mock PNG"
    length = struct.unpack(">I", png[idx - 4:idx])[0]
    raw = zlib.decompress(png[idx + 4:idx + 4 + length])
    return tuple(raw[1:4])


def dead_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class RigTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rigen-test-"))
        self.outdir = self.tmp / "out"
        self.logfile = self.tmp / "requests.log"
        self.control = self.tmp / "mock-control"
        self.srv = subprocess.Popen(
            [sys.executable, str(MOCK), "0", str(self.logfile), str(self.control)],
            stdout=subprocess.PIPE, text=True)
        self.port = int(self.srv.stdout.readline().strip())
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.srv.terminate()
        try:
            self.srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.srv.kill()
        if self.srv.stdout:
            self.srv.stdout.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_rigen(self, *args, stdin=None, env=None, expect_exit=0):
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        p = subprocess.run([sys.executable, str(RIGEN), *args], input=stdin,
                           capture_output=True, text=True, cwd=self.tmp,
                           env=full_env, timeout=60)
        if expect_exit is not None:
            self.assertEqual(p.returncode, expect_exit,
                             f"exit={p.returncode}\nstdout: {p.stdout}\nstderr: {p.stderr}")
        return p

    def files_in(self, d=None):
        d = d or self.outdir
        return sorted(x.name for x in d.iterdir() if x.is_file())

    # -- 1. happy path ------------------------------------------------------

    def test_happy_path(self):
        self.run_rigen("-p", "A cyberpunk city", "-m", "SD-1.5", "-n", "2",
                       "-o", "out", "--base-url", self.base)
        self.assertEqual(self.files_in(), ["SD-1.5_0_0.png", "SD-1.5_0_1.png"])
        p0 = (self.outdir / "SD-1.5_0_0.png").read_bytes()
        p1 = (self.outdir / "SD-1.5_0_1.png").read_bytes()
        self.assertTrue(p0.startswith(PNG_SIG))
        self.assertTrue(p1.startswith(PNG_SIG))
        self.assertNotEqual(pixel_of(p0), pixel_of(p1), "images must be distinct")

    # -- 2. multi-model ------------------------------------------------------

    def test_multi_model(self):
        self.run_rigen("-p", "A", "-m", "SD-1.5", "-m", AMAZING_RENDER,
                       "-o", "out", "--base-url", self.base)
        self.assertEqual(self.files_in(),
                         ["AmazingRender-XL-v14_0_0.png", "SD-1.5_0_0.png"])

    # -- 3. batch -------------------------------------------------------------

    def test_batch_count(self):
        self.run_rigen("-p", "A", "-m", "SD-1.5", "-n", "3",
                       "-o", "out", "--base-url", self.base)
        names = self.files_in()
        self.assertEqual(len(names), 3)
        pixels = {pixel_of((self.outdir / n).read_bytes()) for n in names}
        self.assertEqual(len(pixels), 3, "no duplicates/gaps in a batch")

    # -- 4. backend errors -----------------------------------------------------

    def test_unknown_model_total_failure(self):
        p = self.run_rigen("-p", "A", "-m", "No-Such-Model",
                           "-o", "out", "--base-url", self.base, expect_exit=4)
        self.assertIn("unknown model", p.stderr)
        self.assertEqual(self.files_in(), [])

    def test_unknown_model_partial_failure(self):
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-m", "No-Such-Model",
                           "-o", "out", "--base-url", self.base, expect_exit=4)
        self.assertEqual(self.files_in(), ["SD-1.5_0_0.png"])
        self.assertIn("FAILED", p.stderr)
        self.assertIn("unknown model", p.stderr)

    def test_backend_500(self):
        self.control.write_text("FAIL")
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out",
                           "--base-url", self.base, expect_exit=4)
        self.assertIn("mock backend failure", p.stderr)

    # -- 5. connectivity --------------------------------------------------------

    def test_connectivity_unreachable(self):
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out",
                           "--base-url", f"http://127.0.0.1:{dead_port()}",
                           expect_exit=5)
        self.assertIn("cannot reach Lemonade backend", p.stderr)
        self.assertEqual(self.files_in([]) if self.outdir.exists() else [], [])

    # -- 6. --list ---------------------------------------------------------------

    def test_list_text(self):
        p = self.run_rigen("--list", "--lemonade-cmd", str(FAKE_LEMONADE))
        self.assertIn("SD-1.5  (sd-cpp)", p.stdout)
        self.assertIn(f"{AMAZING_RENDER}  (sd-cpp)", p.stdout)  # verbatim name
        self.assertNotIn("Anima-Turbo", p.stdout)        # remote section ignored

    def test_list_recipe_filter(self):
        p = self.run_rigen("--list", "--lemonade-cmd", str(FAKE_LEMONADE),
                           "--recipe", "sd-cpp")
        self.assertIn("SD-1.5  (sd-cpp)", p.stdout)
        self.assertNotIn("Flint-GGUF", p.stdout)

    def test_list_json(self):
        p = self.run_rigen("--list", "--lemonade-cmd", str(FAKE_LEMONADE),
                           "--json", "--recipe", "sd-cpp")
        doc = json.loads(p.stdout)
        names = {m["name"] for m in doc["models"]}
        self.assertEqual(names, {"SD-1.5", "SD-Turbo", AMAZING_RENDER,
                                 "Qwen-Image-2.1-Turbo"})
        self.assertTrue(all(set(m) == {"name", "recipe"} for m in doc["models"]))

    # -- 7. --dry-run --------------------------------------------------------------

    def test_dry_run(self):
        p = self.run_rigen("-p", "hello world", "-m", "SD-1.5", "-n", "2",
                           "--dry-run", "--base-url", self.base)
        self.assertIn("1 request(s), 2 image(s) planned", p.stdout)
        self.assertIn(f"POST {self.base}/api/v1/images/generations", p.stdout)
        self.assertIn('"model": "SD-1.5"', p.stdout)
        self.assertFalse(self.outdir.exists(), "dry-run must not create out dir")
        self.assertFalse(self.logfile.exists(), "dry-run must not hit the backend")

    # -- 8. --json ---------------------------------------------------------------------

    def test_json_stream(self):
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-n", "2", "-o", "out",
                           "--base-url", self.base, "--json")
        lines = [json.loads(line) for line in p.stdout.strip().splitlines()]
        self.assertEqual(len(lines), 3)
        imgs, summary = lines[:2], lines[2]
        for rec in imgs:
            self.assertEqual(rec["type"], "image")
            self.assertEqual(rec["status"], "ok")
            self.assertTrue(Path(rec["file"]).is_file())
            self.assertIn("generation_info", rec)
        self.assertEqual([r["image_idx"] for r in imgs], [0, 1])
        self.assertEqual([r["batch_idx"] for r in imgs], [0, 1])
        self.assertEqual(summary, {"type": "summary", "planned": 2, "succeeded": 2,
                                   "failed": 0, "start": 0,
                                   "out_dir": str(self.outdir.resolve()),
                                   "exit_code": 0})

    # -- 9. filename safety --------------------------------------------------------------

    def test_filename_safety_unicode_dash(self):
        self.run_rigen("-p", "A", "-m", AMAZING_RENDER, "-o", "out", "--base-url", self.base)
        names = self.files_in()
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].startswith("AmazingRender-XL-v14_"), names)
        self.assertNotIn("\u2011", names[0])

    def test_filename_safety_slash(self):
        self.run_rigen("-p", "A", "-m", "bad/name", "-o", "out", "--base-url", self.base)
        self.assertEqual(self.files_in(), ["bad_name_0_0.png"])
        self.assertTrue((self.outdir / "bad_name_0_0.png").is_file())

    # -- 10. stdin mode ---------------------------------------------------------------------

    def test_stdin_three_prompts(self):
        self.run_rigen("-m", "SD-1.5", "-n", "1", "-o", "out",
                       "--base-url", self.base, stdin="A\nB\nC\n")
        self.assertEqual(self.files_in(),
                         ["SD-1.5_0_0.png", "SD-1.5_1_0.png", "SD-1.5_2_0.png"])

    def test_stdin_blank_lines_and_trailing_newline(self):
        self.run_rigen("-m", "SD-1.5", "-n", "1", "-o", "out",
                       "--base-url", self.base, stdin="\nA\n\n\nB\n\n")
        self.assertEqual(self.files_in(), ["SD-1.5_0_0.png", "SD-1.5_1_0.png"])

    def test_stdin_crlf(self):
        self.run_rigen("-m", "SD-1.5", "-n", "1", "-o", "out",
                       "--base-url", self.base, stdin="A\r\nB\r\n")
        self.assertEqual(self.files_in(), ["SD-1.5_0_0.png", "SD-1.5_1_0.png"])

    def test_stdin_empty(self):
        p = self.run_rigen("-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                           stdin="", expect_exit=3)
        self.assertIn("no prompts", p.stderr)

    def test_stdin_interactive(self):
        import pty
        master, slave = pty.openpty()
        try:
            p = subprocess.run([sys.executable, str(RIGEN), "-m", "SD-1.5"],
                               stdin=slave, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, timeout=30)
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(p.returncode, 2)
        self.assertIn("No --prompt supplied and stdin is interactive; "
                      "pipe prompts via stdin or pass --prompt.", p.stderr)

    # -- 11. filename pattern ------------------------------------------------------------------

    def test_fmt_reset_scope_indices(self):
        self.run_rigen("--fmt", "{model_idx}{prompt_idx}{batch_idx}{image_idx}",
                       "-m", "SD-1.5", "-m", "SD-Turbo", "-n", "2", "-o", "out",
                       "--base-url", self.base, stdin="A\nB\n")
        self.assertEqual(self.files_in(), sorted([
            "0000.png", "0011.png", "1002.png", "1013.png",
            "0104.png", "0115.png", "1106.png", "1117.png",
        ]))

    def test_fmt_zero_pad(self):
        self.run_rigen("--fmt", "{image_idx:04d}", "-m", "SD-1.5", "-n", "1",
                       "-o", "out", "--base-url", self.base, stdin="A\n")
        self.assertEqual(self.files_in(), ["0000.png"])

    def test_fmt_ext_autosuffix_disabled(self):
        self.run_rigen("--fmt", "{model}", "--ext", "", "-m", "SD-1.5",
                       "-o", "out", "--base-url", self.base, stdin="A\n")
        self.assertEqual(self.files_in(), ["SD-1.5"])

    def test_fmt_ext_placeholder_no_double_suffix(self):
        self.run_rigen("--fmt", "x.{ext}", "-m", "SD-1.5", "-n", "1",
                       "-o", "out", "--base-url", self.base, stdin="A\n")
        self.assertEqual(self.files_in(), ["x.png"])

    def test_fmt_custom_ext_autosuffix(self):
        self.run_rigen("--fmt", "{model}", "--ext", "jpg", "-m", "SD-1.5",
                       "-o", "out", "--base-url", self.base, stdin="A\n")
        self.assertEqual(self.files_in(), ["SD-1.5.jpg"])

    def test_fmt_timestamp(self):
        import re as _re
        self.run_rigen("--fmt", "{timestamp:%Y%m%d}", "-m", "SD-1.5",
                       "-o", "out", "--base-url", self.base, stdin="A\n")
        names = self.files_in()
        self.assertEqual(len(names), 1)
        self.assertTrue(_re.fullmatch(r"\d{8}\.png", names[0]), names)

    def test_fmt_unknown_placeholder(self):
        p = self.run_rigen("--fmt", "{foo}", "-p", "A", "-m", "SD-1.5",
                           "--base-url", self.base, expect_exit=2)
        self.assertIn("unknown placeholder", p.stderr)

    def test_fmt_slash_rejected(self):
        p = self.run_rigen("--fmt", "a/b", "-p", "A", "-m", "SD-1.5",
                           "--base-url", self.base, expect_exit=2)
        self.assertIn("'/'", p.stderr)

    def test_fmt_unbalanced_braces(self):
        p = self.run_rigen("--fmt", "{model", "-p", "A", "-m", "SD-1.5",
                           "--base-url", self.base, expect_exit=2)
        self.assertIn("unbalanced", p.stderr)

    # -- 12. validation ---------------------------------------------------------------------

    def test_validation_errors(self):
        for args, needle in [
            (["-p", "A", "-m", "SD-1.5", "--count", "0"], "--count"),
            (["-p", "A", "-m", "SD-1.5", "--size", "1024x0"], "--size"),
            (["-p", "A", "-m", "SD-1.5", "--size", "1024"], "--size"),
            (["-p", "A", "--size", "1024x1024"], "--model"),
            (["-p", "", "-m", "SD-1.5"], "--prompt"),
            (["-p", "   ", "-m", "SD-1.5"], "--prompt"),
        ]:
            p = self.run_rigen(*args, "--base-url", self.base, expect_exit=2)
            self.assertIn(needle, p.stderr, args)
        self.assertFalse(self.logfile.exists(), "validation must not hit the backend")

    # -- extras: request body, short batch, version ---------------------------------------------

    def test_request_body_fields(self):
        self.run_rigen("-p", "A fox", "-m", "SD-1.5", "-n", "2", "-o", "out",
                       "--base-url", self.base, "--size", "512x512", "--steps", "4",
                       "--cfg", "3.5", "--seed", "7")
        with open(self.logfile, encoding="utf-8") as f:
            body = json.loads(f.readline())
        self.assertEqual(body, {"model": "SD-1.5", "prompt": "A fox", "size": "512x512",
                                "n": 2, "response_format": "b64_json", "steps": 4,
                                "cfg_scale": 3.5, "seed": 7})

    def test_negative_seed_passthrough(self):
        self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                       "--seed", "-1")
        body = json.loads(self.logfile.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(body["seed"], -1)

    def test_short_batch(self):
        self.control.write_text("SHORT")
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-n", "3", "-o", "out",
                           "--base-url", self.base, "--json")
        self.assertEqual(len(self.files_in()), 1)
        summary = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual((summary["planned"], summary["succeeded"],
                          summary["failed"], summary["exit_code"]), (3, 1, 0, 0))

    def test_version(self):
        p = self.run_rigen("--version")
        self.assertIn("rigen 1.0.0", p.stdout)

    def test_quiet(self):
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out",
                           "--base-url", self.base, "--quiet")
        self.assertEqual(p.stderr.strip(), "")

    # -- 13. --start (resume) ----------------------------------------------------------------

    def test_start_resumes_with_full_list_names(self):
        self.run_rigen("-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                       "--start", "2", stdin="A\nB\nC\nD\n")
        self.assertEqual(self.files_in(), ["SD-1.5_2_0.png", "SD-1.5_3_0.png"])
        with open(self.logfile, encoding="utf-8") as f:
            sent = [json.loads(line)["prompt"] for line in f]
        self.assertEqual(sent, ["C", "D"], "skipped prompts must not be requested")

    def test_start_multi_model_image_idx(self):
        # full-list image_idx with 2 models: prompt1 -> 2,3 ; prompt2 -> 4,5
        self.run_rigen("--fmt", "{model_idx}{prompt_idx}{image_idx}",
                       "-m", "SD-1.5", "-m", "SD-Turbo", "-o", "out",
                       "--base-url", self.base, "--start", "1", stdin="A\nB\nC\n")
        self.assertEqual(self.files_in(), sorted(["012.png", "113.png",
                                                  "024.png", "125.png"]))

    def test_start_out_of_range(self):
        for s in ("4", "5"):
            p = self.run_rigen("-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                               "--start", s, stdin="A\nB\nC\nD\n", expect_exit=3)
            self.assertIn("no prompts at or after index", p.stderr, s)
            self.assertFalse(self.outdir.exists())
        self.assertFalse(self.logfile.exists(), "no-work check must not hit the backend")

    def test_start_negative(self):
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out",
                           "--base-url", self.base, "--start", "-1", expect_exit=2)
        self.assertIn("--start", p.stderr)
        self.assertFalse(self.logfile.exists(), "validation must not hit the backend")

    def test_start_with_single_prompt(self):
        p = self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out",
                           "--base-url", self.base, "--start", "1", expect_exit=3)
        self.assertIn("no prompts at or after index 1", p.stderr)
        self.run_rigen("-p", "A", "-m", "SD-1.5", "-o", "out",
                       "--base-url", self.base, "--start", "0")
        self.assertEqual(self.files_in(), ["SD-1.5_0_0.png"])

    def test_start_dry_run(self):
        p = self.run_rigen("-m", "SD-1.5", "-n", "2", "--dry-run",
                           "--base-url", self.base, "--start", "2", stdin="A\nB\nC\nD\n")
        self.assertIn("2 request(s), 4 image(s) planned", p.stdout)
        self.assertIn(f"(base {self.base}, start 2 of 4 prompts)", p.stdout)
        self.assertEqual(p.stdout.count("POST "), 2)
        self.assertIn('"prompt": "C"', p.stdout)
        self.assertIn('"prompt": "D"', p.stdout)
        self.assertNotIn('"prompt": "A"', p.stdout)
        self.assertFalse(self.outdir.exists())
        self.assertFalse(self.logfile.exists(), "dry-run must not hit the backend")

    def test_start_json_global_indices(self):
        p = self.run_rigen("-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                           "--start", "2", "--json", stdin="A\nB\nC\nD\n")
        lines = [json.loads(line) for line in p.stdout.strip().splitlines()]
        imgs, summary = lines[:2], lines[2]
        self.assertEqual([r["prompt_idx"] for r in imgs], [2, 3])
        self.assertEqual([r["image_idx"] for r in imgs], [2, 3])
        self.assertEqual(summary, {"type": "summary", "planned": 2, "succeeded": 2,
                                   "failed": 0, "start": 2,
                                   "out_dir": str(self.outdir.resolve()),
                                   "exit_code": 0})

    # -- 14. --verbose -----------------------------------------------------------------------

    def test_verbose_prints_wrapped_prompt(self):
        prompt = "A" * 130  # longer than the 120-column wrap width
        p = self.run_rigen("-p", prompt, "-m", "SD-1.5", "-o", "out",
                           "--base-url", self.base, "--verbose")
        self.assertGreaterEqual(p.stderr.count(" > "), 2, "long prompt wraps")
        self.assertIn("requesting 1 image(s)", p.stderr)

    def test_verbose_off_by_default(self):
        p = self.run_rigen("-p", "a distinctive prompt phrase", "-m", "SD-1.5",
                           "-o", "out", "--base-url", self.base)
        self.assertNotIn("a distinctive prompt phrase", p.stderr)
        self.assertIn("requesting 1 image(s)", p.stderr)

    def test_quiet_verbose_shows_only_prompts(self):
        p = self.run_rigen("-p", "a distinctive prompt phrase", "-m", "SD-1.5",
                           "-o", "out", "--base-url", self.base,
                           "--quiet", "--verbose")
        self.assertIn(" > a distinctive prompt phrase", p.stderr)
        self.assertNotIn("requesting 1 image(s)", p.stderr)
        self.assertNotIn("wrote ", p.stderr)

    # -- 15. progress percentage + ETA -------------------------------------------------------

    def _progress_tokens(self, stderr):
        import re as _re
        return [m.groups() for m in _re.finditer(
            r"\[(\d+/\d+ \(\d+%\))(?: (\d{2}:\d{2}:\d{2}) remaining)?\]", stderr)]

    def test_progress_percentage_eta(self):
        p = self.run_rigen("-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                           stdin="A\nB\nC\n")  # 3 images
        toks = self._progress_tokens(p.stderr)
        self.assertEqual([t[0] for t in toks],
                         ["1/3 (33%)", "1/3 (33%)", "2/3 (66%)", "2/3 (66%)",
                          "3/3 (100%)", "3/3 (100%)"])
        self.assertIsNone(toks[0][1], "no ETA before the first generated image")
        for base, eta in toks[1:]:
            self.assertIsNotNone(eta, base)
            h, m, s = (int(x) for x in eta.split(":"))
            self.assertEqual(h, 0)
            self.assertLess(m, 5)  # mock backend is fast

    def test_progress_percentage_eta_with_start(self):
        p = self.run_rigen("-m", "SD-1.5", "-o", "out", "--base-url", self.base,
                           "--start", "2", stdin="A\nB\nC\nD\n")  # 2 remaining
        toks = self._progress_tokens(p.stderr)
        self.assertEqual([t[0] for t in toks],
                         ["1/2 (50%)", "1/2 (50%)", "2/2 (100%)", "2/2 (100%)"])
        self.assertIsNone(toks[0][1])
        self.assertTrue(all(t[1] is not None for t in toks[1:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
