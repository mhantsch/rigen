# rigen — Software Design (v1)

**Status:** Implemented — first release (software `rigen` 1.0.0)
**Spec:** `RIGEN-SW-SPECIFICATION.md` (RIGEN-SW-SPEC, rev 1.0)
**Rev:** 1.0 (first release; version-agreement policy per the spec's revision-history note)
**Companion:** single-file implementation `./rigen` (Python 3.10+, stdlib only), tests in `tests/`

---

## 1. Scope & confirmed decisions

`rigen` is a thin, robust HTTP client over a running `lemond` (Lemonade) service. It never
loads models, keeps no state, and has no dependencies beyond the Python standard library.

Decisions confirmed with the spec owner (deltas vs. the draft spec, all applied):

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | No `@file` syntax for `--prompt`; prompt files are used via stdin (`cat f \| rigen …`). | Simpler; stdin mode already covers it. |
| D2 | Unicode dashes in model display names map to ASCII `-` in filenames; every other character outside `[A-Za-z0-9._-]` maps to `_`. | Both spec examples show `AmazingRender‑XL‑v14 → AmazingRender-XL-v14` (bytes verified: U+2011 in name, ASCII `-` in expected file). |
| D3 | `{timestamp}` is captured **once at run start** (UTC) and shared by all files of that run. | One run → one consistent, predictable file set. |
| D4 | `--size` validated as `^(\d+)x(\d+)$`, both dimensions ≥ 1. (Spec's `^\d+\d+$` was a typo missing the `x`.) | §4.1 defines size as `WIDTHxHEIGHT`. |
| D5 | `--json` emits an **NDJSON** stream: one compact JSON object per line (per-image records, then a final summary record). | "One record per image plus a final summary record" = a line stream; each line is individually valid JSON. |
| D6 | A `--fmt` pattern that lacks `{ext}` gets `.{ext}` appended automatically, unless the user passes an explicit `--ext ''`. | Common `--fmt` use cases then always produce suffixed files; `''` is the opt-out. |
| D7 | Default `--base-url` is `http://127.0.0.1:13305`. | The local `lemond` listens on 13305 (spec draft said 8001). |
| D8 | `--start` is **0-based** and all indices keep **full-list positions**: the run window is `prompts[start:]`, but `prompt_idx`/`{prompt}` continue from S and the `image_idx` sequence starts at `S × #models × count` (skipped prompts reserve their slots). | Filenames of a resumed run are identical to an uninterrupted run's — no collisions, no clobbering of already-written files — and the next resume index reads straight off the `--json` records (last fully completed `prompt_idx` + 1) with no off-by-one translation. |
| D9 | No persistent resume state: `--start` is always supplied explicitly by the user or a wrapper script; the NDJSON summary record gains a `start` field so scripts can log the run window. | Keeps the "no state/config files" goal (spec §3.1/§10); the JSON stream is already the natural, auditable progress source. |
| D10 | `--quiet --verbose` still prints the prompt text: `say_wrapped` deliberately does **not** check `quiet`, so `--quiet` hides the progress lines while `--verbose` prompts remain visible. | Intended use: keep the console free of progress chatter, but still see which prompt is being generated. |

---

## 2. Deliverables

```
sdcpp-setup-lemonade/
├── rigen                  # the image-generation client (single file, executable)
├── vary                   # prompt-spec expander: {a|b|c} → one prompt per combination
├── README.md              # usage summary, examples, exit codes
├── RIGEN-SW-SPECIFICATION.md
├── RIGEN-SW-DESIGN.md     # this document
└── tests/
    ├── mock_lemond.py     # fake lemond HTTP server (for tests + manual smoke tests)
    ├── fake_lemonade      # fake `lemonade` CLI printing a canned `list` table
    └── test_rigen.py      # unittest suite mirroring spec §11
```

---

## 3. Program structure

Single file, top to bottom:

1. **Constants** — `VERSION = "1.0.0"`, exit codes (`OK=0, USAGE=2, NO_WORK=3,
   BACKEND_ERR=4, UNREACHABLE=5, INTERNAL=1`), defaults (base URL, fmt pattern, ext).
2. **`UsageError(Exception)`** — raised for every exit-2 condition; caught once in `main`.
3. **CLI layer** — `build_parser()`, `parse_and_validate(args)`.
4. **Prompt collection** — `collect_prompts(args, stdin_isatty)` (D1 semantics, §5 here);
   `apply_start(prompts, start)` slices the run window and carries the `--start` offset
   (exit 3 if `start ≥ len(prompts)`, §5.1).
5. **Model enumeration** — `run_lemonade_list(cmd)`, `parse_lemonade_list(text)`,
   `cmd_list(args)`.
6. **Filename layer** — `parse_fmt(pattern)`, `sanitize_component(s)`,
   `make_renderer(segs)`, `render_filename(render, ctx)`.
7. **HTTP layer** — `check_connectivity(base, timeout)`, `post_generation(base, body, timeout)`,
   exception types `BackendUnreachable`, `BackendError`.
8. **Execution** — `progress_label(done, total, eta)`, `format_hms(seconds)`, `run_generation(...)` (orchestration, §9), `cmd_dry_run(...)`.
9. **`main()`** — dispatch (`--version`/`--help` handled by argparse; then `--list`,
   validation, `--dry-run`, generation), top-level exception → exit-code mapping.

---

## 4. CLI & validation

### 4.1 argparse setup

| Option | dest/type | default |
|--------|-----------|---------|
| `-p, --prompt` | str | `None` |
| `--start` | int | `0` |
| `-m, --model` | str, `append` → list | `[]` (required in gen/dry-run modes) |
| `--fmt` | str | `{model}_{prompt}_{batch_idx}.{ext}` |
| `-n, --count` | int | `1` |
| `-o, --out` | path | `.` |
| `-s, --size` | str | `None` |
| `--steps` | int | `None` |
| `--cfg` | float | `None` |
| `--seed` | int (negative allowed) | `None` |
| `--ext` | str | `png` (empty allowed ⇒ disables the suffix) |
| `--base-url` | str | `http://127.0.0.1:13305` |
| `--timeout` | float | `0.0` (0 ⇒ no timeout) |
| `--list` | flag | off |
| `--recipe` | str | `None` |
| `--lemonade-cmd` | str | `lemonade` |
| `--json` | flag | off |
| `--quiet` | flag | off |
| `--verbose` | flag | off |
| `--dry-run` | flag | off |
| `--version` | flag (argparse `version` action, prints `rigen 1.0.0`) | — |
| `--help` | flag (argparse) | — |

`--model` is **not** argparse-`required`: `--list`, `--version`, `--help` must work without it.
Requirement is enforced in validation for generation/dry-run modes (exit 2).

### 4.2 Validation order (before any network activity)

1. `--count` ≥ 1.
2. `--size` (if given) matches `^(\d+)x(\d+)$` and both dimensions ≥ 1 (D4).
3. `--steps` (if given) ≥ 1; `--cfg` (if given) finite.
4. `--ext` non-empty and matches `[A-Za-z0-9._-]+` (it becomes part of filenames).
5. `--fmt` placeholders & format specs (see §6.1).
6. `--timeout` ≥ 0; `--base-url` non-empty, trailing `/` stripped.
7. `--recipe` only allowed together with `--list` (else usage error).
8. In generation/dry-run mode: ≥ 1 `--model`.
9. `--start` is an integer ≥ 0 (argparse enforces the int type; a negative value → exit 2).
10. Prompt availability (see §5): missing prompt on a TTY stdin, or an empty `--prompt`
    value after trimming → exit 2.
11. `--start` ≥ (number of collected prompts) → exit 3 (no work), checked after prompt
    collection (§5.1).

### 4.3 Exit codes

| Code | Trigger |
|------|---------|
| 0 | all images written (also `--help`/`--version`/`--list`/`--dry-run`) |
| 2 | any validation failure above (argparse itself also exits 2 on bad flags/types) |
| 3 | no work planned: stdin mode with zero non-blank prompts, or `--start` ≥ number of prompts |
| 4 | ≥ 1 model request failed (partial or total); other models were still attempted |
| 5 | backend unreachable (startup connectivity check **or** a connection-level failure during a run — aborts immediately, per spec §7.3) |
| 1 | anything unexpected (uncaught exception, `lemonade list` failing, unwritable out dir) |

Error messages always go to **stderr** and are concise and actionable; `--quiet` suppresses
progress only, never errors.

---

## 5. Prompt collection

- `--prompt` given → exactly one prompt = its value (trimmed); stdin is **never read**.
  Trimmed value empty → exit 2 (`--prompt must not be empty`).
- No `--prompt`, stdin is a TTY → exit 2 with the spec's exact message:
  `No --prompt supplied and stdin is interactive; pipe prompts via stdin or pass --prompt.`
- No `--prompt`, stdin not a TTY → read **all** of stdin up front (per spec §4.3),
  decode UTF-8 (invalid UTF-8 → exit 2), split on `\n`, strip a trailing `\r` and surrounding
  whitespace per line, **skip blank lines**. Zero resulting prompts → exit 3 (`no prompts
  read from stdin`).

Prompts keep their original order; that order defines `prompt_idx` (0-based).

### 5.1 Applying `--start`

After the full list is collected (order preserved, blank lines skipped):

- `--start < 0` → exit 2 (caught in validation, §4.2).
- `start ≥ len(prompts)` → exit 3, the same `NoWorkError` path as empty stdin, before any
  network activity: `no prompts at or after index {start} ({n} prompt(s) read)`.
- The **run window** is `prompts[start:]`; the offset `start` is passed to execution
  (`run_generation`) and to the dry run (`cmd_dry_run`).
- All indices keep full-list positions (D8): in the loop, `prompt_idx`/`{prompt}` =
  `start + local_idx` and the global image counter starts at `start × #models × count`.
  Skipped prompts produce no requests, no records, no progress lines — but they reserve
  their index slots, so filenames are identical to an uninterrupted run (spec §4.4/§5.2).

---

## 6. Filenames

### 6.1 `--fmt` parsing & validation

First the *effective* pattern is computed (D6): if `--ext` is non-empty and the
pattern contains no `{ext}`, `.{ext}` is appended. Validation and rendering use
the effective pattern. The pattern is then scanned with `\{([^{}]*)\}`. Rules:

- Every brace group is a placeholder `name` or `name:spec`.
- Recognized names: `model`, `prompt`, `model_idx`, `prompt_idx`, `batch_idx`,
  `image_idx`, `timestamp`, `ext`. Anything else → exit 2.
- Unbalanced `{` or `}` (a brace not part of a valid group) → exit 2.
- `timestamp:spec` — `spec` is a `strftime` format; validated by formatting a sample
  UTC datetime (ValueError → exit 2) and by requiring the formatted sample to contain no
  `/` (e.g. `{timestamp:%Y/%m/%d}` is rejected, exit 2).
- Numeric indices (`prompt`, `model_idx`, `prompt_idx`, `batch_idx`, `image_idx`) accept an
  optional spec matching `\d*d` (e.g. `04d`) — validated via `format(0, spec)`.
- Literal text (outside braces) must not contain `/` → exit 2 (covers the "final filename
  must not contain `/`" rule up front; sanitized values can never introduce one).

Parsing yields a list of segments: `("lit", text)` / `("ph", name, spec)`.

### 6.2 Placeholder values

| Placeholder | Value |
|-------------|-------|
| `{model}` | `sanitize_component(display_name)` (D2) |
| `{prompt}` | 0-based ordinal of the prompt in the run (a *number*, not the text) |
| `{model_idx}` | model position within the current prompt (resets per prompt) |
| `{prompt_idx}` | prompt position within the current model (resets per model) |
| `{batch_idx}` | image position within its batch (0 … count−1) |
| `{image_idx}` | global position in the whole run (never resets) |
| `{timestamp}` | run-start UTC time: default `%Y%m%dT%H%M%SZ`, or the given `strftime` (D3) |
| `{ext}` | `--ext` value |

Numeric placeholders render as `format(value, spec)` (default `"d"`).

With `--start S` the ctx values already carry full-list positions (D8: `prompt`/
`prompt_idx` from S, `image_idx` from `S × #models × count`) — the renderer is unchanged.

### 6.3 Sanitization (D2)

`sanitize_component(s)`: for each character —

- ASCII letter/digit/`_`/`.`/`-` → kept;
- Unicode dash set `U+2010, U+2011, U+2012, U+2013, U+2014, U+2015, U+2212` → ASCII `-`;
- anything else → `_`.

Applied to the `{model}` and `{prompt}` substituted values (per spec §5.3; the prompt
value is numeric so this is a no-op in practice). The model name is passed to the backend
**verbatim** — sanitization is filename-only.

### 6.4 Final checks

The assembled filename must be non-empty and not `.`/`..`; it must contain no `/`
(guaranteed by 6.1/6.3, re-checked defensively). Path is `out_dir / filename`.

---

## 7. Backend integration

### 7.1 Connectivity check

In generation mode (not `--list`, not `--dry-run`), before the first request:
`GET {base}/v1/models`.

- Any HTTP response (even 4xx/5xx) ⇒ service reachable; response body ignored.
- Connection-level failure (`URLError`/`OSError`) ⇒ exit 5:
  `cannot reach Lemonade backend at {base} — is lemond running? Check --base-url.`
- Uses the same `--timeout` (0 ⇒ no timeout).

### 7.2 Generation request

`POST {base}/api/v1/images/generations`, `Content-Type: application/json`.

Body keys, in this order (only non-`None` optional keys are included):

```json
{"model": …, "prompt": …, "size": …?, "n": count, "response_format": "b64_json",
 "steps": …?, "cfg_scale": …?, "seed": …?}
```

`seed` is passed verbatim (negative ⇒ backend picks randomly). One request per
(prompt, model) pair with `n = --count` (spec R6).

### 7.3 Response handling

- **200 + `data` list**: process entries in order. Each entry: `b64_json` (required —
  missing/undecodable ⇒ that image is failed, others continue), optional `index`,
  optional `generation_info` (surfaced in progress off, included in JSON records).
  If the backend returns **fewer than n** images, exactly the returned count is written
  (global `image_idx` advances only for processed images); this is noted in the summary
  (`succeeded` reflects actual files).
- **Non-200**: parse `error.message` (fall back to raw body / status text) → the whole
  batch for that (prompt, model) pair fails; remaining models continue (spec §7.3).
- **Connection-level failure mid-run** (e.g. lemond dies between batches): exit 5
  immediately (spec §7.3 treats "connection cannot be established" as fatal).

### 7.4 File writing

`base64.b64decode` → bytes written atomically-enough via `open(path, "wb")` (v1: plain
write, no temp+rename — single process, no concurrent writers per spec §3.1). The out dir
is created (`mkdir -p` semantics) before any write. Write failure ⇒ that image failed
(OSError), run continues, exit 4 overall.

---

## 8. Model enumeration (`--list`)

- Executes `[lemonade-cmd, "list"]` via subprocess, captures stdout (UTF-8), does **not**
  touch the HTTP backend (spec §7.2 note: `/v1/models` only lists LLM models).
- Binary missing ⇒ exit 2 with a clear message; non-zero exit ⇒ exit 1, message includes
  lemonade's stderr tail.
- Parser (verified against live output, incl. a live bug found in smoke testing): finds the
  `Local` section (a line whose stripped content is exactly `Local`), skips to the first
  all-dash underline, then reads table rows until the next all-dash line / end of input.
  Each row is split on whitespace into `<name> <Yes|No> <size> <recipe>`; a row is accepted
  only if field 2 is `Yes`/`No`. Name = field 1, recipe = last field. Fixed column slicing
  is deliberately avoided: lemonade pads the name column by *display* width (unicode dashes
  count double), so the character offset of the following columns varies per row.
- `--recipe` filters rows to an exact recipe match. No matches ⇒ empty list (text: no
  lines; JSON: `{"models": []}`), exit 0.
- Text output, one line per model: `<display-name>  (<recipe>)` (two spaces, per spec).
- `--list --json` output (single JSON object on stdout):
  `{"models": [{"name": "…", "recipe": "…"}, …]}`.

---

## 9. Execution orchestration

```
prompts = collect_prompts(...)             # full list, in order
if start >= len(prompts): exit 3           # NoWorkError, §5.1
timestamp = now(UTC)                       # once, D3
planned = (len(prompts) - start) * len(models) * count
succeeded = failed = 0
global_idx = start * len(models) * count   # skipped prompts reserve slots (D8)
for prompt_idx, prompt in enumerate(prompts):
    if prompt_idx < start: continue        # ignored: no request/record/progress
    for model_idx, model in enumerate(models):
        try: data = post_generation(model, prompt, n=count, …)
        except BackendUnreachable: log; exit 5            # fatal, spec §7.3
        except BackendError as e:
            failed += count                               # whole batch lost
            record(status=error, batch_idx=null, image_idx=null, error=e)
            continue
        for batch_idx, entry in enumerate(data):
            name = render_filename(model_idx, prompt_idx, batch_idx, global_idx)
            try: write file; succeeded += 1; status ok
            except (decode/write) as e: failed += 1; status error
            global_idx += 1
exit = OK if failed == 0 else BACKEND_ERR
```

- Outer loop = prompt, inner loop = model ⇒ spec §5.1 ("one request per model", models in
  the order given) and §4.3 ("for each prompt … one request per model") coincide.
- `model_idx`/`prompt_idx` are the 0-based list positions; because the inner/outer loops
  always restart at 0, their "resets" are structural.
- Total images in a run = `#prompts × #models × count`; `image_idx` runs 0 … total−1.
  With `--start S`, `planned` counts only the remaining images and `image_idx` starts at
  `S × #models × count` (D8).

### 9.1 Stderr progress (suppressed by `--quiet` except the `--verbose` prompt text, D10; errors always printed)

```
rigen: [1/12 (8%)] SD-1.5 prompt 0/1: requesting 2 image(s)
rigen: [1/12 (8%) 00:00:44 remaining] wrote SD-1.5_0_0.png
rigen: [2/12 (16%) 00:00:42 remaining] wrote SD-1.5_0_1.png
rigen: [3/12 (25%) 00:00:42 remaining] AmazingRender-XL-v14 prompt 0/1: requesting 2 image(s)
…
rigen: done: 12/12 images written to /abs/out          # exit 0
# on partial failure:
rigen: [SD-1.5] prompt 0: FAILED: unknown model 'SD-1.5'
rigen: done: 10/12 images written to /abs/out (2 failed)   # exit 4
```

Prefix `[k/total (p%)]` counts images written so far + current image (best-effort
ordering); `p = 100 * k // total` — integer percent, floored, so the last progress line
reads exactly `100%`.

ETA: with `c` images accounted for since run start (written or failed) and elapsed wall
time `e`, the estimate is `(e / c) × (total − c)` — average wall time per image times
the images left, rounded to the nearest second, formatted `HH:MM:SS` (hours unbounded).
Wall time includes request, decode, and write, not only backend generation. The ETA is
omitted until `c ≥ 1`; on a `wrote` line the just-written image counts as accounted for.
With `--start S`, `total` is the remaining image count and the prompt counter is shown in
full-list coordinates (e.g. `prompt 2/3` when resuming at 2 of 4 prompts).

`--verbose`: before each model's request, the current prompt text is additionally printed
via `Progress.say_wrapped` — wrapped at 120 columns (word boundary preferred, hard break
otherwise), every physical line prefixed ` > `. Deliberately **not** suppressed by
`--quiet` (D10): `--quiet --verbose` hides the progress lines while the prompts remain
visible. Errors are never suppressed.

### 9.2 Stdout JSON stream (`--json`, D5) — NDJSON

Per image (planned-image granularity; `batch_idx`/`image_idx` null on whole-batch failure):

```json
{"type":"image","model":"SD-1.5","model_idx":0,"prompt":"…","prompt_idx":0,"batch_idx":0,"image_idx":0,"file":"/abs/out/SD-1.5_0_0.png","status":"ok","error":null,"generation_info":{"seed":42}}
```

`file` is the absolute path; `generation_info` is `null` when absent. Final summary:

```json
{"type":"summary","planned":12,"succeeded":12,"failed":0,"start":0,"out_dir":"/abs/out","exit_code":0}
```

`start` is the applied `--start` value (0 when not given); with `--start S`, `planned`
counts only the run window. The next resume index is derived from the per-image records
(one more than the `prompt_idx` of the last fully completed prompt), not from
`planned`/`succeeded`.

`--json` changes only stdout; progress remains on stderr (see `--quiet`).

---

## 10. Dry run (`--dry-run`)

After validation & prompt collection, before any network activity, print to stdout:

```
# dry-run: 2 request(s), 4 image(s) planned (base http://127.0.0.1:13305)
## POST http://127.0.0.1:13305/api/v1/images/generations
{
  "model": "SD-1.5",
  "prompt": "A fox …",
  "size": "1024x1024",
  "n": 2,
  "response_format": "b64_json",
  "seed": 42
}
…
```

One block per (prompt, model) request in execution order, skipping prompts with index <
`--start` (spec §4.4). No files, no sockets, exit 0. With `--start S > 0` the header
carries the run window instead of a bare base URL:

```
# dry-run: 2 request(s), 4 image(s) planned (base http://127.0.0.1:13305, start 2 of 6 prompts)
```

(`--json` does not alter dry-run output in v1.)

---

## 11. Testing strategy (mirrors spec §11)

`tests/mock_lemond.py` — stdlib `http.server` fake backend on a test-chosen port:

- `GET /v1/models` → 200 (reachable).
- `POST /api/v1/images/generations` → validates the body:
  - unknown `model` → 400 `{"error":{"message":"unknown model: …",…}}`
  - empty `prompt` → 400
  - otherwise → 200 with `n` entries, each `b64_json` = a real 1×1 PNG whose pixel is a
    deterministic function of (model, prompt, index) — so tests can assert *distinct*
    decoded content; `generation_info` echoes the request.
  - env knobs: `RIGEN_MOCK_SHORT=1` (return 1 image even if n>1), `RIGEN_MOCK_FAIL=1`
    (500 every request).
  - appends each request body (one JSON line) to a log file so tests can assert request
    counts and that dry-run made none.

`tests/fake_lemonade` — executable Python script printing a canned `lemonade list`
table (Local section incl. `SD-1.5`, `AmazingRender‑XL‑v14` with U+2011, a `llamacpp` model, and
an "Available for Download" section that must be ignored).

`tests/test_rigen.py` — `unittest`, invokes `./rigen` as a subprocess against the mock:

1. happy path: 1 model, count 2 → 2 valid PNGs (signature + size), exit 0
2. multi-model: 2 models, count 1 → 2 files, correct default names
3. batch: count 3 → exactly 3 files/model, distinct pixel content (no dupes/gaps)
4. unknown model (alone and mixed) → exit 4, stderr message, partial success kept
5. dead `--base-url` port → exit 5, message
6. `--list` via fake lemonade (names+recipes, `--recipe` filter, `--json` shape)
7. `--dry-run` → stdout contains request, no files, mock log empty, exit 0
8. `--json` → every stdout line valid JSON; image records have `file`+`status`; summary last
9. filename safety: U+2011 model → `AmazingRender-XL-v14_…png`; `bad/name` model → `bad_name_…`
10. stdin: 3 prompts w/ blanks + trailing newline → exact file count; empty stdin → exit 3;
    TTY stdin (via `pty`) without `--prompt` → exit 2
11. `--fmt` indices: 2 prompts × 2 models × 2 count with all four reset scopes → exact
    expected filenames; unknown `{foo}` → exit 2; `{image_idx:04d}` padding;
    literal `/` in fmt → exit 2
12. validation: `--count 0`, `--size 1024x0`/`1024`, missing `--model`, empty `--prompt` → exit 2
13. `--start`: 4 stdin prompts, `--start 2`, 1 model, `--count 1` → exactly 2 files with
    full-list names (`SD-1.5_2_0.png`, `SD-1.5_3_0.png`), exit 0, and the mock request log
    holds only prompts 2 and 3. `--start 4` / `--start 5` → exit 3, no files. `--start -1`
    → exit 2. `--prompt` + `--start 1` → exit 3; `--prompt` + `--start 0` → normal run.
    `--start 2 --dry-run` → header shows the run window, only 2 request blocks, no files,
    mock log empty. `--start 2 --json` → `prompt_idx`/`image_idx` are 2, 3 and the summary
    carries `"start": 2`.
14. `--verbose`: stderr contains the wrapped prompt text (` > ` prefix) before each
    request; absent without the flag; `--quiet --verbose` → progress lines hidden,
    prompt text still printed (D10).
15. Progress percent: a 3-image run's stderr shows `[1/3 (33%)]` on the first requesting
    and wrote lines up to `[3/3 (100%)]` on the last; with `--start 2` of 4 prompts the
    percent is over the remaining window (`[1/2 (50%)]` to `[2/2 (100%)]`).
16. ETA: on a 3-image run the first line carries no `remaining` token; every later line
    does (`HH:MM:SS`, tiny values under the mock); with `--start` the ETA is over the
    remaining window.

Plus a live smoke test (manual): `./rigen --list` and one real 1-image generation against
the running local `lemond` into a scratch dir.

---

## 12. Out of scope (v1)

Per spec §10: no img2img/inpaint, no cross-model concurrency, no model management, no
GUI/config, no streaming. A `--end` stop index and automatic resume (progress file) are
likewise out of scope — `--start` is always explicit (D9). Temp-file+rename atomicity and
a cross-model `--concurrency` flag are natural v2 follow-ups.
