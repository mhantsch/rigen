# rigen — Rapid Image GENeration — Software Specification

**Status:** Implemented — first release (software `rigen` 1.0.0)
**Workspace:** `/home/max/src/sdcpp-setup-lemonade/`
**Target backend:** local [Lemonade](https://lemonade-server.ai) service (`lemond`)

## Revision history

**Version agreement (from rev 1.0):** the spec and the software share a version scale —
spec rev 1.0 ↔ `rigen` 1.0.0, and from here on 1.1 ↔ 1.1.0, 2.0 ↔ 2.0.0. Every behavior
change bumps both together; the major numbers always agree. Prose-only document edits
do not force a rev bump — they append to the current rev's history entry.

| Rev | Change |
|-----|--------|
| 0.1 | Initial draft. |
| 0.2 | Added `--start S` — resume an interrupted stdin run from prompt index S: new requirement R12, CLI argument (§4.1), validation rules (§4.2), behaviour in §4.4, index semantics with skipped prompts (§5.2), exit-code note (§8), examples (§9), non-goals (§10), verification case 12 (§11). |
| 0.3 | Documented the `--verbose` flag (present in the implementation but previously undocumented): §4.1, §11. |
| 0.4 | Progress lines now carry an integer percentage — `[x/y (z%)]` — in addition to the image counters: R9, §11. |
| 0.5 | Progress lines also carry a remaining-time estimate — `[x/y (z%) HH:MM:SS remaining]` — once at least one image has been generated; omitted before that: R9, §11. |
| 1.0 | **First release.** Spec ratified at 1.0 with software version `rigen` 1.0.0; the version-agreement policy above adopted. No behaviour changes in this rev. |

---

## 1. Purpose

`rigen` is a small, scriptable command‑line tool that generates raster images through the
local Lemonade image‑generation backend (`lemond`). It takes **one or more prompts** (a single
`--prompt`, or several newline‑separated prompts from stdin), **one or more model names**, and
**a count**, then produces `count` images for **each** requested model **and prompt**.

Its design goals, in order:

1. **Reliable** — correct integration with the Lemonade backend; clear, actionable failures.
2. **Scriptable** — every parameter is passed on the command line; output is predictable and
   machine‑readable.
3. **Simple** — a single dependency‑free program; no GUI, no config files.

`rigen` never loads a model itself. It is a thin, robust client over the Lemonade HTTP API.

A stdin-driven batch run can be long and may be interrupted at any point (program stopped,
machine rebooted, ...). Such a run can be **resumed**: `--start S` skips the first S prompts
of the list and processes the rest, with filenames identical to those of an uninterrupted run
(§4.4).

---

## 2. Glossary

| Term | Definition |
|------|------------|
| `lemond` | The Lemonade local inference HTTP service (systemd unit `lemond`). |
| **model** | A registered image‑generation model, referenced by its **display name** (e.g. `SD-1.5`, `AmazingRender‑XL‑v14`, `Qwen-Image-2.1-Turbo`). Display names come from `lemonade list`. |
| **count** | The number of images generated **per model**. |
| **backend** | The HTTP endpoint that performs generation (the running `lemond`). |
| **start index** (`--start`) | 0-based index of the first prompt to process; prompts with a lower index are read but ignored (§4.4). |

---

## 3. Functional requirements

| ID | Requirement |
|----|-------------|
| R1 | Given a prompt, a list of ≥1 models, and a count *N*, generate *N* images with **each** model. |
| R2 | Deliver images to the backend over HTTP using the Lemonade image‑generation API. |
| R3 | Decode each base64 image returned by the backend and write a PNG file to the output directory. |
| R4 | Default output directory is the current working directory; `--out` overrides it. |
| R5 | Filenames are deterministic and safe (no shell‑injection, no path traversal) so scripts can reference them. |
| R6 | A single request may request *N* images as a batch (one HTTP call per model). |
| R7 | `--list` enumerates the available image models and exits. |
| R8 | `--dry-run` prints the planned requests and exits without contacting the backend. |
| R9 | Progress is reported to stderr, each line prefixed `[x/y (z%) HH:MM:SS remaining]` — x = current image, y = images in this run, z = integer percent (floored) — with the remaining-time estimate shown once at least one image has been generated and omitted before that; an optional machine‑readable JSON stream goes to stdout (`--json`). |
| R10 | Errors are reported with distinct exit codes and concise messages. |
| R11 | If the backend is unreachable, the program fails fast with a clear message and a non‑zero exit code. |
| R12 | An interrupted run can be resumed: `--start S` (S ≥ 0, default 0) ignores prompts with index < S and processes the rest; all indices keep their full-list positions so filenames are unchanged (§4.4, §5.2). |

### 3.1 Non‑functional

- **No third‑party dependencies** — standard library only (see §9).
- **Language:** Python 3.10+ (stdlib: `argparse`, `urllib.request`, `base64`, `json`, `pathlib`, `shutil`).
- **Sequential** execution by default (models generated one after another) to keep peak GPU
  memory predictable. Concurrency is explicitly out of scope for v1.
- Deterministic and portable; no reliance on locale or terminal width.

---

## 4. Command‑line interface

All parameters are passed on the command line. `rigen` uses `argparse` (long options with a
single‑letter alias where natural).

### 4.1 Arguments

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--prompt`, `-p` | string | see §4.3 | Text prompt. Optional when stdin mode is active (§4.3). (Prompt files are read via stdin, e.g. `cat prompt.txt \| rigen …`.) |
| `--start` | int | `0` | 0-based index of the first prompt to process; prompts with a lower index are ignored (§4.4). Applies to both `--prompt` and stdin mode; ignored by `--list`. |
| `--model`, `-m` | string (repeatable) | **(required, ≥1)** | Image-model display name(s). May be given multiple times. |
| `--fmt` | string | `{model}_{prompt}_{batch_idx}.{ext}` | Output filename pattern. Placeholders (see §5.2), incl. the reset‑scope indices `{model_idx}`, `{prompt_idx}`, `{batch_idx}`, `{image_idx}`; `{timestamp}` may take an optional `strftime` format (`{timestamp:%Y%m%d}`). If the pattern contains no `{ext}` and `--ext` is not empty, `.{ext}` is appended automatically. |
| `--count`, `-n` | int | `1` | Number of images generated **per model**. Must be ≥1. |
| `--out`, `-o` | path/dir | current dir (`.`) | Output directory. Created if it does not exist. |
| `--size`, `-s` | string | model default | Image size as `WIDTHxHEIGHT` (e.g. `1024x1024`). Omit to let the backend use the model's native size. |
| `--steps` | int | model default | Sampling steps. |
| `--cfg` | float | model default | Classifier‑free guidance scale (aka `cfg_scale`). |
| `--seed` | int | backend default | Fixed RNG seed for reproducible output. A **negative** value requests a random seed. |
| `--ext` | string | `png` | Output image extension (used only for the file suffix; the bytes are whatever the backend returns). An explicit empty value (`--ext ''`) disables the suffix. |
| `--base-url` | url | `http://127.0.0.1:13305` | Base URL of the running `lemond`. |
| `--timeout` | float seconds | `0` (no limit) | Per‑request HTTP timeout in seconds. `0` disables the timeout (used because CPU generation can take minutes). |
| `--list` | flag | off | List available image models, then exit. |
| `--recipe` | string | all | With `--list`, restrict to a single recipe (e.g. `sd-cpp`, `thenoise`, `llamacpp`). |
| `--lemonade-cmd` | path | `lemonade` | The `lemonade` binary to invoke when resolving `--list`. |
| `--json` | flag | off | Emit a machine‑readable JSON stream to **stdout**: one record per image plus a final summary record. Progress goes to stderr only. |
| `--quiet` | flag | off | Suppress the human progress report on stderr. The `--verbose` prompt text is **not** suppressed; errors are never suppressed. |
| `--verbose` | flag | off | In addition to the progress report, print the full text of the current prompt to stderr before each model's request (wrapped; by default only the prompt index is shown). Unlike the progress report, the prompt text is **not** suppressed by `--quiet` — so `--quiet --verbose` shows only the prompts. |
| `--dry-run` | flag | off | Print the planned requests (one per model) and exit without calling the backend. |
| `--version` | flag | off | Print version and exit. |
| `--help` | flag | off | Usage help. |

### 4.2 Constraints & validation (before any HTTP call)

- `--count` must be an integer ≥ 1.
- `--size`, if given, must match `^\d+\d+$` (width×height); both dimensions must be positive.
- `--fmt`, if given, must use only recognized placeholders (see §5.2); the optional `{timestamp:…}`
  format must be a valid `strftime` format.
- At least one `--model` is required.
- `--seed` must be an integer (may be negative).
- `--model` names are treated **literally** as model ids; they are sanitized only for use in
  **filenames** (see R5 / §5.3), never interpreted as paths.
- `--start` must be an integer ≥ 0 (a negative value is a usage error, exit **2**).
  `--start` ≥ (number of prompts) is **not** a usage error but a no-work condition (exit
  **3**), determined after the prompts are read (§4.4).

Validation failures abort before any network activity and exit with code **2**.

### 4.3 stdin mode

When `--prompt` is **not** given, prompts are read from **stdin** instead of the command line:

1. If `--prompt` is present, it is used and stdin is ignored.
2. If `--prompt` is absent **and stdin is not a TTY** (piped or redirected), stdin mode is active.
3. If `--prompt` is absent **and stdin is a TTY**, the program aborts with exit code **2**:
   `No --prompt supplied and stdin is interactive; pipe prompts via stdin or pass --prompt.`
   This rule (2) avoids a silent, infinite wait for input the user never sees.

Behavior of stdin mode:

- Prompts are separated by **newlines**. Each line is decoded as UTF‑8, a trailing `\r` (CRLF) is
  stripped, and leading/trailing whitespace is trimmed.
- **Blank lines** are treated as separators and skipped — they never generate empty‑prompt errors
  and a trailing newline at EOF does not produce a phantom prompt.
- **Each line is one prompt.** A line beginning with `@` is just a literal prompt
  character, not a file reference (file-based prompts use stdin, e.g. `cat prompt.txt | rigen …`).
- For **each** prompt the program generates `count × (#models)` images (one request per model),
  then reads the next prompt. The run ends at **EOF**. To make `--fmt` indices such as `{image_idx}` correct, stdin
  is fully read up front and the prompts are then processed in order, starting at index 0
  unless `--start` (§4.4) skips leading prompts.
- `--model` remains required. If stdin mode is active but no `--model` was given, that is a usage
  error (exit **2**).

### 4.4 Resuming an interrupted run (`--start`)

A long stdin-driven run can be interrupted at any point (program stopped, machine rebooted,
...). To continue, invoke `rigen` again with the **same prompt list** and the same options,
plus `--start S`, where S is the 0-based index of the first prompt that still needs images.

- S counts **prompts** (non-blank lines after the §4.3 processing), not raw input lines, and
  is 0-based, consistent with `{prompt_idx}`. Example: if the run stopped after prompt 39
  completed, resume with `--start 40`.
- Prompts with index < S are **ignored**: no request is sent and no file is written for them
  (stdin is still read in full up front, per §4.3).
- All indices refer to the **full input list**, not the resumed sub-run (§5.2 note): the first
  processed prompt has `{prompt}`/`{prompt_idx}` = S, and the first image of the resumed run
  has `{image_idx}` = S × (#models) × `count` — the skipped prompts reserve their slots. This
  is what makes the filenames of a resumed run identical to those of an uninterrupted run, so
  files produced by the interrupted part are never overwritten.
- `--start 0` (the default) changes nothing; behaviour is exactly as without the option.
- `--start` applies to both prompt sources. With a single `--prompt`, `--start 0` is a no-op
  and `--start ≥ 1` means no work (exit **3**). `--list` ignores `--start`.
- `--start < 0` is a usage error (exit **2**, before any network activity). `--start` ≥
  (number of prompts) is a no-work error (exit **3**), checked after the prompts are read —
  the same path as empty stdin.
- `--dry-run` honours `--start`: it lists only the requests that would actually be sent
  (prompts S … end of list).
- Per-prompt behaviour is unchanged: each processed prompt still issues one request per model
  with `n = --count` (R6, §5.1).
- `rigen` keeps **no state across runs**: it does not record which prompts completed. Choosing
  S is the responsibility of the operator or a wrapper script — e.g. from the stderr progress,
  or from the `--json` records (resume at one more than the `prompt_idx` of the last fully
  completed prompt; per-image records carry the global indices).

## 5. Output

### 5.1 Delivery

For each model in order, `rigen` sends **one** batched request with `n = --count`, receives the
images, decodes each, and writes the files in order. Generation across models is sequential.

### 5.2 Filename

The output filename is built from the `--fmt` pattern (default `{model}_{prompt}_{batch_idx}.{ext}`).
Placeholders are substituted, the result is sanitized (see §5.3), and the image is written to
`--out`/`<filename>`.

| Placeholder | Value |
|-------------|-------|
| `{model}` | Sanitized display name (see §5.3). |
| `{prompt}` | 0‑based ordinal of the current prompt in the run (distinct from `{prompt_idx}` — see below). |
| `{model_idx}` | Position of the current model **within the current prompt**. Resets per prompt — 0, 1, …, (#models−1). |
| `{prompt_idx}` | Position of the current prompt **within the current model**. Resets per model — 0, 1, …, (#prompts−1). |
| `{batch_idx}` | Position of the image **within its batch** (the current prompt+model pair). Resets per batch — 0, 1, …, count−1. |
| `{image_idx}` | Position of the image **within the whole run**. Never resets — 0, 1, 2, 3, … (global counter). |
| `{timestamp}` | Prompt timestamp. An optional `strftime` format may follow, as
  `{timestamp:%Y%m%d}`; the default when no format is given is `%Y%m%dT%H%M%SZ`. |
| `{ext}` | Value of `--ext` (default `png`). |

Notes:

- `batch_idx` or `image_idx` (or another varying field such as `{timestamp}`) should be present, otherwise repeated
  generations with the same prompt/model would collide.
- With `--start S` (§4.4) the indices keep counting from the start of the **full** input list:
  `{prompt}`/`{prompt_idx}` take the values S, S+1, ..., (#prompts−1) and the `{image_idx}`
  sequence starts at S × (#models) × count — the skipped prompts reserve their slots. A
  resumed run therefore writes exactly the filenames an uninterrupted run would have.
- `{timestamp:FORMAT}` uses Python `strftime` directives — the same core directives as the unix
  `date` command (`%Y`, `%m`, `%d`, `%H`, `%M`, `%S`, …).
- Only the placeholders above are recognized; any other `{...}` is a validation error (exit **2**).
- The assembled filename is sanitized (§5.3) and must not contain `/`; such a pattern is rejected.
- The four reset‑scope indices (`{model_idx}`, `{prompt_idx}`, `{batch_idx}`, `{image_idx}`) differ only in *when* they reset (see the table). Numeric indices accept an optional zero‑pad/width format as `{...:fmt}` (e.g. `{image_idx:04d}` → `0007`, `{batch_idx:02d}` → `00`).

Example — `--fmt '{timestamp:%Y%m%d}-{model}-{batch_idx}'`, model `AmazingRender‑XL‑v14`, `--count 3`:

```
20260115-AmazingRender-XL-v14-0.png  20260115-AmazingRender-XL-v14-1.png  20260115-AmazingRender-XL-v14-2.png
```

### 5.3 Filename sanitization

The substituted `{model}` and `{prompt}` values are made filesystem‑safe by replacing any character
outside `[A-Za-z0-9._-]` with `_`, except for em-dash, en-dash, non-breaking-dash (and similar
dash-looking characters) which will be replaced with regular dash `-`.
This prevents injection/path‑traversal while keeping the name recognizable.
(`AmazingRender‑XL‑v14` → `AmazingRender-XL-v14`; an em‑dash becomes `-` and any `/` become `_`.)
The final assembled filename must not contain `/`; such a pattern is a validation error (exit **2**).

---

## 6. Backend contract (Lemonade HTTP API)

`rigen` talks to the running `lemond` over HTTP. This is the **only** integration point.

### 6.1 Endpoint

```
POST {base-url}/api/v1/images/generations
Content-Type: application/json
```

### 6.2 Request body (JSON)

```json
{
  "model": "SD-Turbo",
  "prompt": "A serene mountain landscape at sunset",
  "size": "1024x1024",
  "n": 3,
  "response_format": "b64_json",
  "steps": 25,
  "cfg_scale": 6.5,
  "seed": 12345
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `model` | yes | Model display id (see §2 / §7). |
| `prompt` | yes | Plain string; must be non‑empty. If empty the backend returns an error. |
| `size` | no | `WIDTHxHEIGHT`. Omit to use the model's native size. Separate `width`/`height` fields are **dropped** by the backend — use `size` only. |
| `n` | no | Number of images to generate in this batch (set to `--count`; default `1`). |
| `response_format` | no | Must be `"b64_json"` (the only supported value). |
| `steps` | no | Falls back to the model's configured steps. |
| `cfg_scale` | no | Falls back to the model's configured cfg. |
| `seed` | no | Integer; negative ⇒ random. Falls back to the backend default. |

### 6.3 Success response (HTTP 200)

OpenAI‑compatible shape:

```json
{
  "object": "list",
  "data": [
    { "index": 0, "b64_json": "<base64-encoded PNG>", "generation_info": { ... } },
    { "index": 1, "b64_json": "<base64-encoded PNG>", "generation_info": { ... } }
  ]
}
```

`rigen` decodes each `b64_json` and writes the file named in §5.2. The optional `generation_info`
object is reported (and, in `--json` mode, included in the per‑image record) but is **not**
required to write the file.

### 6.4 Error response (HTTP 5xx / non‑200)

```json
{ "error": { "message": "…", "type": "…", "code": "…" } }
```

`rigen` surfaces `error.message` as the failure reason, marks that model failed, and continues
with the remaining models (see §7.3), unless the **connection itself** is unreachable (§7.1).

### 6.5 Prerequisite & connectivity

- `lemond` must be running. At startup `rigen` performs a lightweight connectivity check against
  `{base-url}/v1/models`; if it cannot reach the service it exits **5** with a message telling the
  user to start `lemond` and/or check `--base-url`.

---

## 7. Model selection & enumeration

### 7.1 Selecting a model

A model is selected by its **display name** as shown by `lemonade list`
(e.g. `SD-1.5`, `SD-Turbo`, `AmazingRender‑XL‑v14`, `Qwen-Image-2.1-Turbo`).
The id is passed verbatim as the `model` field in the request.

### 7.2 Enumerating models (`--list`)

`rigen --list` invokes `lemonade list` (via `--lemonade-cmd`) and parses the **Local** section,
returning each model's display name and recipe. Optional `--recipe <name>` filters the output.

- Text mode: one line per model — `<display-name>  (<recipe>)`.
- `--list --json`: `{"models": [{"name": "…", "recipe": "…"}, …]}`.

**Important implementation note (verified):** the live HTTP route
`GET {base-url}/v1/models` currently returns only the LLM (llama‑cpp) models, **not** the
sd‑cpp/thenoise image models. Therefore model discovery uses `lemonade list`, not the HTTP
`/v1/models` route. `rigen` should prefer explicit `--model` selection in scripts (more robust)
and use `--list` for human discovery.

### 7.3 Partial failure semantics

- If the **connection** cannot be established → exit **5** immediately (no images produced).
- If a **single model's request** fails (backend error / invalid model / decode error) → that
  model is reported as failed, the remaining models are attempted, and the process exits **4**
  if **any** model failed but at least one succeeded; exit **0** only if all requested images
  succeeded. If **all** models fail, exit **4**.

---

## 8. Exit codes

| Code | Meaning |
|------|---------|
| `0` | All requested images generated successfully. |
| `2` | Usage / argument validation error (e.g. missing `--prompt`, `--count < 1`, bad `--size`). |
| `3` | No work planned (e.g. no valid models after filtering, empty stdin, `--start` ≥ number of prompts) — typically overlaps with R2 validation. |
| `4` | Backend responded with an error for one or more models (partial or total failure). |
| `5` | Backend unreachable / connectivity error. |
| `1` | Any other unexpected internal error. |

Usage/help (`--help`, `--version`) exit `0`.

---

## 9. Examples

```bash
# Generate 1 image with one model in the current directory.
rigen --prompt "A cyberpunk city at night, rain, neon" --model SD-1.5

# 3 images each with two models, into ./out, fixed size/seed.
rigen -p "A fox reading a book by candlelight" \
      -m "AmazingRender‑XL‑v14" -m "SDXL-Base-1.0" \
      --count 3 --out ./out --size 1024x1024 --seed 42

# Stdin mode: one prompt per line, 2 images each, into ./out.
printf 'A\nB\nC\n' | rigen -m SD-1.5 --count 2 --out ./out

# Resume an interrupted run: skip the first 2 of 4 prompts, process prompts 2 and 3.
# Filenames keep their full-list position (default pattern): SD-1.5_2_0.png, SD-1.5_3_0.png.
printf 'A\nB\nC\nD\n' | rigen -m SD-1.5 --out ./out --start 2

# Same, as a preview: lists only the requests for prompts 2 and 3, no backend, no files.
printf 'A\nB\nC\nD\n' | rigen -m SD-1.5 --start 2 --dry-run

# Stdin + timestamped filenames, one group per model.
rigen --fmt '{timestamp:%Y%m%d}-{model}-{batch_idx}' -m SD-1.5 -m "AmazingRender‑XL‑v14" < prompts.txt

# Count placeholders across a whole run.
rigen --fmt '{image_idx:03d}-{model}-{batch_idx}' -m SD-1.5 --count 3 < prompts.txt > run.json

# See what image models exist.
rigen --list
rigen --list --recipe sd-cpp --json

# Preview the requests without touching the backend.
rigen -p "hello world" -m SD-1.5 --count 2 --dry-run
```

---

## 10. Non‑goals (for v1)

- No image‑to‑image, in‑painting, edits, variations, or upscaling (different route).
- No concurrency/batching across models (keep VRAM predictable; easy to add later).
- No model pulling/management — a model must already be present (run `lemonade pull …` first).
- No GUI, no persistent state/config files.
- No `--end` / run-length limit — a resumed run always processes to the end of the input list.
- No automatic resume/checkpointing — `rigen` does not record progress across runs; the
  starting index is supplied by the user or a wrapper script (§4.4).
- No streaming or partial output (each model completes before the next begins).

---

## 11. Verification plan (for the implementation phase)

1. **Happy path:** one model, count 2 → 2 correctly‑decoded PNGs in `--out`.
2. **Multi‑model:** two models, count 1 each → 2 files, correct names.
3. **Batch vs correctness:** `--count N` → exactly `N` files per model, no duplicates/gaps.
4. **Error handling:** request an unknown `--model`; expect a partial/total failure path with
   exit code 4 and a message.
5. **Connectivity:** stop `lemond` (or point `--base-url` at a dead port); expect exit 5.
6. **`--list`:** output contains the known image models (`SD-1.5`, `AmazingRender‑XL‑v14`, …).
7. **`--dry-run`:** prints requests; no files written; no backend hit.
8. **`--json`:** stdout is valid JSON; each per‑image record includes the file path and status.
9. **Filename safety:** model name with an em‑dash or slash produces a clean, in‑directory file.
10. **Stdin mode:** three newline‑separated prompts yield three groups of images; blank lines and
    a trailing newline produce no extra work; interactive‑terminal use without `--prompt` exits 2.
11. **Filename pattern:** a custom `--fmt` with the reset‑scope indices `{model_idx}` (resets per prompt), `{prompt_idx}` (resets per model), `{batch_idx}` (per batch), and `{image_idx}` (the whole run, never resets); substitution is verified, an unknown `{...}` is rejected (exit **2**), and numeric indices honour `{...:0Nd}` zero‑padding.
12. **`--start` (resume):** 4 stdin prompts, `--start 2`, one model, `--count 1` → exactly
    2 files, named as an uninterrupted run would name prompts 2 and 3 (default pattern:
    `SD-1.5_2_0.png`, `SD-1.5_3_0.png`), exit 0. `--start 4` (= #prompts) and `--start 5`
    (> #prompts) → exit 3, no files. `--start -1` → exit 2. `--prompt` + `--start 1` → exit
    3; `--prompt` + `--start 0` → normal single-prompt run. `--start 2` + `--dry-run` → only
    the requests for prompts 2 and 3 are listed. `--start 2` + `--json` → records carry the
    global positions (`prompt_idx` 2, 3 and `image_idx` 2, 3 with one model, `--count 1`).
13. **`--verbose`:** stderr contains the full prompt text (wrapped, ` > ` prefix) before
    each model's request; without the flag, only the prompt index. `--quiet --verbose`
    hides the progress lines but still shows the prompt text (intentional, see the
    `--quiet`/`--verbose` rows in §4.1).
14. **Progress percentage:** every progress line begins with `[x/y (z%)]` — x the
    current image, y the images in this run, z the integer percent (floored; the final
    progress line reads 100%).
15. **ETA:** once at least one image has been generated, each progress line carries
    `HH:MM:SS remaining` after the percent (average wall time per image × images left,
    rounded to the nearest second); the lines before the first generated image carry no
    ETA.