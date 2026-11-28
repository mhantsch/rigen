# rigen — Rapid/Repeated Image GENeration

`rigen` is a small, scriptable CLI that generates raster images through the local
[Lemonade](https://lemonade-server.ai) backend (`lemond`). It is a thin, dependency-free
Python 3.10+ client: pass prompts + model names + a count, get deterministic files.

See `RIGEN-SW-SPECIFICATION.md` (requirements) and `RIGEN-SW-DESIGN.md` (design).

## Usage

```bash
# One image with one model in the current directory.
./rigen --prompt "A cyberpunk city at night, rain, neon" --model SD-1.5

# 3 images each with two models, into ./out, fixed size/seed.
./rigen -p "A fox reading a book by candlelight" \
        -m "AmazingRender‑XL‑v14" -m "SDXL-Base-1.0" \
        --count 3 --out ./out --size 1024x1024 --seed 42

# Stdin mode: one prompt per line (prompt files work too: cat prompts.txt | rigen …).
printf 'A\nB\nC\n' | ./rigen -m SD-1.5 --count 2 --out ./out

# Timestamped filenames, one group per model.
./rigen --fmt '{timestamp:%Y%m%d}-{model}-{batch_idx}' -m SD-1.5 < prompts.txt

# Machine-readable NDJSON on stdout (progress stays on stderr).
./rigen -m SD-1.5 --count 3 < prompts.txt --json > run.json

# Discover models (via `lemonade list`).
./rigen --list
./rigen --list --recipe sd-cpp --json

# Preview the requests without touching the backend.
./rigen -p "hello world" -m SD-1.5 --count 2 --dry-run
```

### Filename patterns (`--fmt`)

Default: `{model}_{prompt}_{batch_idx}.{ext}`.

| Placeholder | Meaning |
|---|---|
| `{model}` | sanitized model display name |
| `{prompt}` | 0-based ordinal of the prompt in the run |
| `{model_idx}` | model position within the current prompt (resets per prompt) |
| `{prompt_idx}` | prompt position within the current model (resets per model) |
| `{batch_idx}` | image position within its batch (0 … count−1) |
| `{image_idx}` | global position in the whole run (never resets) |
| `{timestamp[:STRFTIME]}` | run-start UTC time (default `%Y%m%dT%H%M%SZ`) |
| `{ext}` | the `--ext` value |

Numeric indices accept zero-padding: `{image_idx:04d}` → `0007`. If your pattern
contains no `{ext}` and `--ext` is not empty, `.{ext}` is appended automatically
(`--ext ''` disables this).

## vary — prompt variation

`vary` expands `{a|b|c}` groups in a prompt spec into multiple prompts (one per
line); multiple groups produce the cartesian product, `-r` picks random options
(`-n N` repeats it N times).

```bash
./vary "a {tall|short|slender} man"          # 3 prompts
./vary -r -n 5 "pick {one|two|three}"        # 5 random prompts
printf 'a {red|blue} sky\n' | ./vary | ./rigen -m SD-1.5 --count 2 --out ./out
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | all images generated |
| 2 | usage / validation error |
| 3 | no work planned (e.g. empty stdin) |
| 4 | backend error for one or more models (partial or total failure) |
| 5 | backend unreachable |
| 1 | unexpected internal error |

## riview — Reloading Image Viewer

`riview` is a small GTK 4 / libadwaita viewer that watches a directory (or a
single image file — in which case it watches the file's directory and starts
pinned to that file in manual mode) and displays the newest image in it, reloading the display
as files change. It is meant to sit open while `rigen` (or anything else)
writes into the watched directory. In directory mode you can step back through
the settled images with `Left`/`Right`, jump to either end with `Home`/`End`, and
return to live following with `n` (see the keyboard section below). With `c`
(or `--cycle` at startup) the directory can also run as a **slide show**: the
settled images advance toward the newer end every *cycle time*, wrapping from
the newest to the oldest image (rev 1.6). Like
`rigen`, it is a single-file, dependency-free Python 3.10+ client — the GUI is
provided by the system PyGObject (GTK 4 + libadwaita), no pip packages.

See `RIVIEW-SW-SPEC-AND-DESIGN.md` (specification §1–§11 and design §12–§13).

```bash
# Watch a directory, showing the newest image.
./riview out

# No argument: watches the current working directory (terminal launch).
# Launched from the app menu with no target, it shows a short explanation
# on the black canvas (idle state) instead of guessing a directory.
cd out && ./riview

# File target: watch the containing directory, starting pinned to one image
# file (manual mode) — it reloads as it is overwritten (a newer *other* file in
# the same directory never takes over); Left/Right navigate the directory, n
# goes live, c cycles starting at this file (rev 1.7.4).
./riview out/frame_012.png

# Watch a specific directory, full screen (image only, no header bar).
./riview out --fullscreen

# Slower settle window (busy writes), custom extensions.
./riview out --stable-ms 5000 --extensions png,jpg,webp

# Force polling every 2 s (e.g. NFS / 9p shares without inotify).
./riview out --poll 2

# Slide show (cycle mode): the settled images advance toward the newer end
# every cycle time (default 9 s), wrapping from the newest to the oldest;
# `--cycle` starts at the OLDEST image. `--cycle N` sets the cycle time to
# N s; `--cycle-time N` only sets it (start the cycle with `c`). The two
# flags are combinable; when both give a time, `--cycle-time` takes
# precedence (1.7.3).
./riview out --cycle
./riview out --cycle 5
./riview out --cycle --cycle-time 3

# Window fit: size the window to the first displayed image (ratio is the
# default); exact = 1:1 logical pixels, capped at the screen; off = never
# resize (the 80% default window stays). `--fit-window` is a synonym.
# (ratio fits within the smaller of the 80% budget and a 1600x1200 cap —
# a workaround for an upstream COSMIC window-clamping bug; see the spec D15.)
./riview out --fit exact
./riview out --fit off

# Headless: print the path of the image riview would display (or "none"),
# no GUI, no settle wait — for scripts.
./riview --print out
./riview --print out/frame_012.png

# Install the app into the desktop (per user, idempotent): app menu entry +
# icon + "Open with riview" on folders and images in the file manager.
./riview --install-desktop
./riview --uninstall-desktop   # removes the entry and icon again
```

Images are shown fit-to-window on a black background (no zoom/pan in v1).
The window opens at the size of the newest already-settled image
(`--fit ratio`, the default: the image's aspect ratio within the smaller of
an 80% monitor budget and a 1600×1200 px cap (width × height) — a temporary workaround for an
upstream COSMIC window-clamping bug, spec D15; `exact`: 1:1 logical pixels,
capped at the screen minus the header bar; `off`: the 80% window) — read
from the file header, no decode — and
`r` re-fits it to the currently displayed image on demand (post-startup
resizes can only grow the window: on Wayland, shrinking is the
compositor's job). After the fit the window is yours. A file only becomes
*the newest* after it has been quiet for the settle window (default 2 s,
`--stable-ms`); the visible image is only replaced once the new one has
decoded (dual buffer, so a corrupt/in-progress file is never shown).
GIFs show their first frame. To watch something else, quit and relaunch (no
in-app re-targeting, no drag-and-drop in v1).

Keyboard (window focused): `q` or `Ctrl+C` quit; `f` — or a left double-click
anywhere on the canvas (image or black letterbox) — toggles full screen both
ways; `Esc` leaves full screen. In directory mode, `Left`/`Right` step
backward/forward through the settled images (one step per press) and
`Home`/`End` jump to the oldest/newest — **every movement key ends by pinning
the display**, so files settling in the background don't replace it; in live
mode `Right`/`End` (and `Left`/`Home` with a single image) pin the current
display in place, freezing the stream; `p` pauses — pins the display without
moving. `n` is the only key that jumps back to the newest and resumes live
following. `c` starts **cycle mode** (the slide show, rev 1.6): the settled
images advance one at a time toward the newer end, wrapping from the newest
to the oldest, every *cycle time* (default 9 s; `--cycle-time N` or
`--cycle N`); while cycling the header shows `· cycle Ns`, and `Up`/`Down`
shorten/lengthen the cycle time by 1 s (floor 1 s) — while cycling the
in-progress interval is rescaled (its elapsed time is preserved), so every
following interval is the new full time. `space` toggles between cycle and
pause — as `c` when not cycling, as `p` (stop and pin) while cycling (1.7.2).
Any mode-selecting key
(`Left`/`Right`/`Home`/`End`/`p`/`n`/`space`) stops the cycle first, then
behaves as usual; `f`/`Esc`/`r`/double-click leave it running. In windowed or
full-screen mode, an effective `c`/`p`/`n`/`Up`/`Down`/`space` keypress also
shows a brief 1 s
on-canvas overlay — pale-yellow text on a semi-transparent gray shade,
bottom center, its bottom edge about 10% up from the canvas bottom; in
windowed mode the header keeps its status alongside it (rev 1.7, window
mode added in 1.7.1). `h` (or `?`) shows a short keyboard help overlay,
centered on the canvas at a normal font size; it stays on screen until the
next keypress, which dismisses it and — if the key is bound — executes it
as usual, so the help overlay and the feedback overlay never appear at the
same time (1.7.5). If the
pinned file is deleted or renamed away the canvas goes black with a message;
`Left`/`Right` keep scanning from where the image was (the pin remembers its
mtime), and the display restores itself if the file reappears. `r` re-fits the
window to the currently displayed image (any mode except `--fit off`). A
file target starts pinned to that file (manual mode) — the movement keys
navigate the containing directory's images from there (1.7.4).

### Exit codes

| Code | Meaning |
|---|---|
| 0 | normal exit (window closed, `--print` completed, desktop install/uninstall) |
| 1 | internal error (display unavailable, fatal failure) |
| 2 | usage / validation error |
| 3 | target (directory or file) does not exist |

## Tests

```bash
python3 tests/test_rigen.py -v      # rigen + vary
python3 tests/test_riview.py -v     # riview (selection/settle logic + headless watcher/decode integration)
```

The suites run against `tests/mock_lemond.py` (a fake `lemond`), `tests/fake_lemonade`
(a fake `lemonade` CLI), and (for riview) a real GLib main loop in headless mode;
no GPU is required. The riview GUI surface itself is covered by the manual cases in
`RIVIEW-SW-SPEC-AND-DESIGN.md` §11 (9–37).
