# riview — Reloading Image Viewer — Software Specification & Design

**Status:** Implemented — `./riview` + `tests/test_riview.py` (65 tests) built against this
revision. All headless cases pass; manual GUI cases §11 9–28 verified on COSMIC (rev 0.8).
**Released as riview 1.0.0 (spec rev 1.0).**

**Workspace:** `/home/max/src/sdcpp-setup-lemonade/`
**Target system:** Pop!_OS 24.04 LTS with COSMIC desktop (this machine — verified facts in §13)
**Convention:** follows the structure of `RIGEN-SW-SPECIFICATION.md` / `RIGEN-SW-DESIGN.md`; this
document combines specification (§1–§11) and design (§12–§13) in one file.

## Revision history

**Version agreement (from rev 1.0):** the spec and the software share a version scale —
spec rev 1.0 ↔ `riview` 1.0.0, and from here on 1.1 ↔ 1.1.0, 2.0 ↔ 2.0.0. Every behavior
change bumps both together; the major numbers always agree. Prose-only document edits do
not force a rev bump — they append to the current rev's history entry. `riview --version`
prints the `VERSION` constant (§12.3).

| Rev | Change |
|-----|--------|
| 0.1 | Initial draft. Spec (§1–§11) + design (§12–§13). Decisions D1–D11 confirmed by spec owner (D1–D5 answer open questions Q1–Q5; D6–D11 are design defaults). |
| 0.2 | Implementation corrections found by headless integration testing: `GInotifyFileMonitor` has no `cancelled` signal and a deleted+recreated directory can reuse its inode number, so R14 recovery now uses a 1 s recheck timer that re-creates the monitor unconditionally (§6.1, §12.6, §13.2). GUI-layer classes moved into `_gui_classes()` (lazy GTK import; test seam, §12.3). |
| 0.3 | Display: black letterbox background (new R17); `--fullscreen` is image-only — header bar and waiting text hidden (R16 amended). Touches §3, §4.1, §5.4, §7.1, §11 (cases 9/10/18), §12.5, §12.7. |
| 0.4 | Keyboard shortcuts (new R18 + §4.4 + §12.9): `q`/`Ctrl+C` quit, `f` toggles full screen both ways, `Esc` leaves it; clean SIGINT/SIGTERM handling (`GLib.unix_signal_add`). §11 case 23; §13.2 notes the missing `is_fullscreened`/`IS_*` masks. |
| 0.5 | Non-deprecated display path: `set_pixbuf`/`set_keep_aspect_ratio` (deprecated in GTK ≥ 4.10, warned at runtime) replaced by `set_paintable(Gdk.Texture.new_for_pixbuf(…))` + `content-fit=CONTAIN` (§7.1, §12.5, §12.7, §13.2). |
| 0.6 | Canvas double-click toggles full screen (new R19 + §4.5 + §12.9 + §11 case 24): a left double-click anywhere on the canvas (image or letterbox) takes the same path as `f`. Manual detection via `Gtk.GestureClick` — the installed typelib lacks `Gtk.GestureMultiPress`/`GtkEventControllerPointer` (§13.2). Also fixed an orphaned sentence left in §4.3 by the rev 0.4 edit. |
| 0.7 | Header timestamp now includes the date: mtime formatted as local `YYYY-MM-DD HH:MM:SS` instead of `HH:MM:SS` (R10, §12.7). |
| 0.8 | Desktop integration & targets (new R20–R22): the target may be a directory *or* an image file (single-file watch mode, R21); `--install-desktop`/`--uninstall-desktop` write/remove a per-user `.desktop` entry + embedded SVG icon (`Exec %U`, `MimeType` for folders and images, R20); no target → CWD when launched from a terminal, else the **idle state** (message + `no file` subtitle) based on the launch-context heuristic (`DESKTOP_STARTUP_ID` / controlling tty, R22, new §4.6–§4.7); `--newest` renamed `--print` and extended to file targets (R12, §4.3, D10 reworked, D2 replaced, new D12); no in-session re-targeting and no drag-and-drop (non-goals, §10 — the binding lacks `Gtk.GestureDrop`, §13.2). Header note added stating the spec-revision vs. software-version distinction. |
| 1.0 | **First release.** Spec ratified at 1.0 with software version `riview` 1.0.0; the version-agreement policy above adopted. No behaviour changes in this rev. |

---

# Part I — Specification

## 1. Purpose

`riview` is a small GUI utility that **watches a directory** and **always displays the newest
image file in it**. When a newer image file appears — or the currently displayed file is updated
in place — the display **updates automatically**, with no user interaction.

Primary use case: live preview of a running generation pipeline. While `lemond`/`rigen` writes
images into an output directory, `riview` shows each finished image as soon as the file is
complete:

```
cd sdcpp-setup-lemonade && riview out
```

Since rev 0.8 the target can also be a **single image file** (single-file watch
mode, R21), and `riview --install-desktop` adds a per-user desktop entry and
icon so the app can be launched from the app menu or via the file manager's
"Open with" on a folder or an image (R20).

Design goals, in order:

1. **Reactive** — the newest settled image is shown within one settle window of the file
   becoming complete.
2. **Safe** — never display a half-written file; never blank or corrupt the visible image on a
   failed load (dual buffer).
3. **Simple** — a single executable file; no pip packages; no config files; no persistent state.

`riview` never modifies the watched directory. It is a read-only observer and renderer.

---

## 2. Glossary

| Term | Definition |
|------|------------|
| **target** | The `TARGET` argument: a directory (directory mode) or an image file (single-file mode, R21). May arrive as a `file://` URI from the desktop entry's `%U` (R20). |
| **target directory** | The directory being watched — the target itself in directory mode, or the containing directory in single-file mode (R21). With no target and a terminal launch, the current working directory (R22). |
| **single-file mode** | Target is one image file: only that file is ever displayed (R21). |
| **idle state** | No target resolved in a GUI context: black canvas + explanatory message, header subtitle `no file` (R22). |
| **launch context** | Terminal vs. GUI context classification used for the no-target fallback (R22, §4.6). |
| **candidate** | A regular, non-hidden file in the target directory whose extension is in the supported set (§5.1). |
| **hidden file** | A file whose name begins with `.`. |
| **settled** | A candidate that has been quiet long enough to be safe to display (§5.3). |
| **settle window** | The quiet period required before display; `--stable-ms`, default **2000** ms. |
| **snapshot** | The identity of the currently displayed image: `(path, mtime_ns, size)`. |
| **newer-only rule** | The display never switches to a *different* file whose mtime is not strictly newer than the current snapshot's (§5.2). |
| **rescan** | One full enumeration of the target directory plus candidate selection (§6). |
| **generation** | A monotonically increasing id attached to each decode request; used to discard stale results (§12.5). |
| **dual buffer** | The visible image is replaced only *after* the replacement has been fully and successfully decoded (§5.4). |
| **file version** | The triple `(path, mtime_ns, size)` — identifies one specific content of a file. |

---

## 3. Functional requirements

| ID | Requirement |
|----|-------------|
| R1 | At startup, `riview` displays the newest **settled** candidate of the target directory. If none exists, it shows a *waiting* state and continues watching. |
| R2 | The target directory is watched continuously. Created, modified, deleted, or renamed files are picked up without polling delays greater than the coalesce interval (§6.1). Inotify is the default mechanism; polling is an option and an automatic fallback. |
| R3 | When a candidate appears whose mtime is **strictly newer** than the current snapshot's, the display switches to it automatically, once it is settled (newer-only rule, §5.2). |
| R4 | When the **currently displayed file is updated in place** (its mtime or size changes), the display reloads it automatically, once settled — regardless of mtime direction for the same path. |
| R5 | Only **candidates** (§5.1) are ever considered. Hidden files, non-regular files, files with other extensions, and subdirectories are always ignored. |
| R6 | A candidate is displayable only once **settled** (§5.3): quiet for the settle window both by observed-change age and by mtime age. |
| R7 | **Dual buffer:** the visible image is replaced only after the replacement image has been fully decoded. A decode failure never blanks the display; the previous image stays. |
| R8 | When there is no settled candidate (empty directory, all files removed), the view shows a *waiting* placeholder. The placeholder returns automatically if the displayed file is deleted or candidates disappear. |
| R9 | The image always **fits the window** with preserved aspect ratio and no cropping. No zoom, pan, or scroll in v1. |
| R10 | The window header shows: the displayed file's base name, the decoded pixel dimensions, and the file's mtime formatted as local `YYYY-MM-DD HH:MM:SS`. Not shown in `--fullscreen` mode (R16). |
| R11 | All behaviour is controlled by the command line (§4). No config files, no state, no environment variables. |
| R12 | `--print` runs headless (no GTK import, no display): prints the path of the image `riview` would display — the newest candidate in a directory, or the file itself when a file is given — as one **absolute path** to stdout (`none` when a directory has no candidates) and exits. The settle window is not applied: it is a point-in-time answer, not a delayed one. |
| R13 | Exit codes per §8. All diagnostics go to **stderr**; stdout is reserved for `--print` output and nothing else. One target per process. |
| R14 | **Watcher resilience:** if inotify monitoring cannot be established, `riview` falls back to polling and warns on stderr. If the target directory is deleted and recreated (new inode), monitoring is re-established on the new directory. |
| R15 | A **decode failure** of a settled file (corrupt/truncated content) is reported once per file version on stderr; the viewer keeps the previous image (or the waiting state) and retries only if the file's version changes. No retry storms. |
| R16 | `--fullscreen` starts the window in full-screen mode, **image only**: no header bar and no waiting-state text — just the black canvas and the image. |
| R17 | The area of the window not covered by the image (letterbox) is **black**, in windowed and full-screen modes alike; the waiting-state text is white on it. |
| R18 | **Keyboard shortcuts** (window focused; work in windowed *and* full-screen mode alike; bare keys — Shift tolerated, any other modifier leaves the key unhandled): `q` quits (exit 0); `f` toggles full screen ↔ windowed, both directions (header bar reappears on exit); `Esc` leaves full screen (no-op in windowed mode). `Ctrl+C` and `SIGTERM` also quit cleanly (exit 0, no traceback). |
| R19 | A **left double-click** (two presses within 400 ms) **anywhere on the canvas** — on the image or on the black letterbox; the header bar is excluded — toggles full screen ↔ windowed, both directions, with the same effect as `f` (R18). |
| R20 | **Desktop integration:** `--install-desktop` writes, per user (no root), a `.desktop` entry to `$XDG_DATA_HOME/applications/com.lemonade.riview.desktop` (default `$XDG_DATA_HOME` = `~/.local/share`) and the app's SVG icon to `$XDG_DATA_HOME/icons/hicolor/scalable/apps/com.lemonade.riview.svg`; the icon is **embedded in the script** (single-file property preserved). Both operations are idempotent. The entry uses `Exec=<absolute path to the riview script> %U` and registers `MimeType=inode/directory;` plus the default image MIME types, so the file manager's "Open with" can launch `riview` on a folder or an image; `%U`-supplied targets arrive as `file://` URIs and are accepted. `--uninstall-desktop` removes both files (a note on stderr, exit 0, if neither is present). |
| R21 | **Single-file watch mode:** the target may be an image file instead of a directory. Then **only that file is ever displayed**: it reloads when its file version changes (R4/R6 settle logic over a one-element candidate set), and a newer *other* file in the same directory never displaces it. The containing directory is watched, so deleting the file returns the waiting state and recreating it restores the display. An explicit file target **bypasses `--extensions`** (the flag filters selection *inside* directories only); the file's extension must be in the *default* extension set, else usage error (exit 2). |
| R22 | **Launch context & idle state:** with no target argument: launched from a **terminal** → watches the current working directory; launched in a **GUI context** (⇔ `DESKTOP_STARTUP_ID` is set, or the process has no controlling terminal — a documented convenience heuristic, §4.6) → **idle state**: the black canvas with the wrapped, centered, white message *"No target given. Right-click a folder or an image and choose \"Open with riview\", or pass a directory or file on the command line."* and header subtitle `no file`; `q`/`f`/`Esc` remain active. `--fullscreen` with no resolved target → usage error, exit 2. `--print` does not use context detection (always CWD). |

### 3.1 Non-functional

- **Language:** Python 3.10+, single executable file `./riview`, `argparse` + PyGObject only.
  **No pip packages** — GTK 4, libadwaita, and GdkPixbuf come from system packages
  (all present on the target system; §13.1).
- **Responsiveness:** directory scans and the UI run on the GTK main thread; image decoding
  runs on a dedicated worker thread so the window never freezes on large files (§12.5).
- **Read-only:** `riview` never writes, renames, or deletes anything in the target directory.
  (`--install-desktop` writes per-user files under `XDG_DATA_HOME` — that is installation,
  not state; `--uninstall-desktop` removes them. The app itself keeps no state, rev 0.8.)
- **Deterministic selection:** §5.2/§5.3 are pure functions of (file stat data, wall/monotonic
  time) — unit-testable without a display (see `tests/test_riview.py`, §12.2).

---

## 4. Command-line interface

```
riview [TARGET] [options]
```

`TARGET` is a directory (directory mode) or an image file (single-file mode, R21);
it may be a `file://` URI (the desktop entry's `%U`, R20).

### 4.1 Arguments

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `TARGET` (positional) | path | none (see R22) | Directory or image file to watch (R21). No target: CWD when launched from a terminal, idle state in a GUI context (R22). |
| `--extensions` | comma list | `png,jpg,jpeg,webp,gif,tiff,tif,bmp` | Candidate extensions, lowercase, without dots. Case-insensitive on input. The empty list is a usage error. (`avif` and `svg` loaders exist on the target system and may be added here; they are not in the default set by design decision D4.) Filters selection *inside directories* only — an explicit file target bypasses it (R21). |
| `--stable-ms` | int ≥ 0 | `2000` | Settle window in milliseconds (§5.3). `0` disables the window (file displayable as soon as first observed — for testing). |
| `--poll` | float seconds, > 0 | off | Force polling mode with the given interval (R2). Also serves as the fallback interval when inotify is unavailable and this flag was given. |
| `--max-dim` | int px ≥ 0 | `0` | Absolute cap on the **longer side** of the decoded image, in pixels. `0` (default) means no cap beyond window-fit scaling (§7.1). |
| `--fullscreen` | flag | off | Start full-screen, image only: no header bar, no waiting-state text (R16). Usage error (exit 2) when no target resolves (R22). |
| `--print` | flag | off | Headless query mode (R12): print the absolute path of the image `riview` would display (`none` if a directory has no candidates) and exit. No GUI, no settle wait. |
| `--install-desktop` | flag | off | Install the per-user `.desktop` entry + icon (R20), then exit 0. Headless. |
| `--uninstall-desktop` | flag | off | Remove the per-user `.desktop` entry + icon (R20), then exit 0. Headless. |
| `--version` | flag | off | Print version and exit. |
| `--help` | flag | off | Usage help. |

### 4.2 Validation (before any window or watcher is created)

- `--stable-ms` must be an integer ≥ 0; `--poll` a number > 0; `--max-dim` an integer ≥ 0.
- `--extensions` must parse to a non-empty set of non-empty tokens; tokens containing `/` or
  starting with `.` are rejected.
- If `TARGET` exists but is **neither a directory nor an image file** (extension not in the
  default set, R21) → exit **2**.
- If `TARGET` **does not exist** → exit **3** (fail fast; `riview` does not wait for a
  target to appear).
- `--print` is incompatible with `--fullscreen` (exit 2).
- `--install-desktop` / `--uninstall-desktop` are mutually exclusive, and each is
  incompatible with `TARGET`, `--print`, or `--fullscreen` (exit 2).
- `--fullscreen` with no resolved target (no argument in a GUI context, R22) → exit **2**.
- All validation failures exit **2** with a one-line message on stderr, before any GUI work.

### 4.3 `--print` mode (R12)

- Prints exactly one line to stdout: the **absolute path** of the image `riview` would
  display — the newest candidate of a directory target, or the file itself for a file
  target — or `none` (directory target, no candidates).
- Applies the candidate rules of §5.1 (extensions, hidden, regular file) but **not** the
  settle window: a point-in-time answer. Scripts must not expect any deliberate delay,
  and a file that is still being written is reported as-is.
- Newest = greatest `st_mtime_ns`; ties broken by **byte-wise lexicographically greatest**
  file name (deterministic, locale-independent).
- Exit code `0` in all cases (an empty directory is not an error here; a missing target is
  exit 3, a non-image file target is exit 2).
- No target: the current working directory — **always**, regardless of launch context
  (CLI semantics; R22's context detection applies to the GUI only).
- `--print` is incompatible with `--fullscreen` (usage error, exit 2); other display options
  are simply ignored by it. It imports no GTK and needs no display (§13.3).

### 4.4 Keyboard shortcuts (R18)

With the window focused, in windowed and full-screen mode alike (bare keys; Shift is
tolerated, so `Q`/`F` work too; any other modifier leaves the key unhandled):

| Key | Action |
|-----|--------|
| `q` | Quit (exit 0). |
| `Ctrl+C` / `SIGTERM` | Quit cleanly (exit 0, no traceback — §11 case 22). |
| `f` | Toggle full screen ↔ windowed, both directions. |
| `Esc` | Leave full screen. No-op in windowed mode. |

### 4.5 Mouse (R19)

| Gesture | Area | Action |
|---------|------|--------|
| Left double-click (two presses within 400 ms) | The canvas — the image and/or the black letterbox (the header bar is excluded) | Toggle full screen ↔ windowed, both directions (same as `f`). |

### 4.6 Launch context & idle state (R22)

With no `TARGET` argument the GUI falls back on the **launch context**:

| Context | Behaviour |
|---------|-----------|
| Terminal | Watch the current working directory (the historical default, D2 rev 1). |
| GUI (app menu, panel, …) | **Idle state**: black canvas, wrapped centered white message (R22 text), header subtitle `no file`. No watcher, no decoder. `q`/`f`/`Esc` remain active. |

- **GUI context ⇔ `DESKTOP_STARTUP_ID` is set, or the process has no controlling terminal**
  (opening `/dev/tty` fails). Presence of `DESKTOP_STARTUP_ID` is a *sufficient* condition
  (startup-notification launchers set it per launch); a missing controlling terminal is the
  general case for session-spawned processes. This is a documented **convenience heuristic**,
  not a contract, with two known misclassifications: a terminal launch under a pty-less
  sandbox sees the idle message (it says how to pass a directory), and a pty-allocating
  launcher watches its own CWD — usually `$HOME`, where the non-recursive scan typically
  finds no images, so the failure is soft.
- `--print` never consults the context (§4.3); `--install-desktop`/`--uninstall-desktop`
  never consult the context either.
- `--fullscreen` with no resolved target is a usage error (exit 2): a full-screen idle state
  would be a pure black screen, since R16 hides the waiting text.

### 4.7 Desktop entry (R20)

- `--install-desktop` (headless, exit 0) writes, per user, no root:
  - `$XDG_DATA_HOME/applications/com.lemonade.riview.desktop` (default `$XDG_DATA_HOME` is
    `~/.local/share`), and
  - `$XDG_DATA_HOME/icons/hicolor/scalable/apps/com.lemonade.riview.svg` — the icon is
    embedded in the script as a string constant and written out here (single-file property
    preserved, D6).
  Both are idempotent overwrites. No `update-desktop-database` call is needed: file
  managers and the app grid watch these directories.
- The entry: `Type=Application`, `Name=riview`, `Comment=Reloading image viewer`,
  `Exec=<absolute path of the riview script> %U`, `Icon=com.lemonade.riview`,
  `Terminal=false`, `Categories=Utility;Viewer;Graphics;`,
  `MimeType=inode/directory;image/png;image/jpeg;image/webp;image/gif;image/tiff;image/bmp;`.
- `%U` delivers `file://` URIs; `riview` accepts URIs as `TARGET` (directory → directory
  mode, image file → single-file mode, R21). If several URIs are ever passed, the first
  wins (file managers pass one in practice).
- `--uninstall-desktop` removes both files; if neither exists, a note goes to stderr and the
  exit code is still 0 (idempotent).
- The window's own icon is `com.lemonade.riview` when the icon is installed (so the
  decoration matches the menu), falling back to `image-x-generic` otherwise.

---

## 5. Selection & display semantics

### 5.1 Candidates (R5)

A path in the target directory is a candidate iff all hold:

1. `stat(path)` (following symlinks) is a **regular file** (symlinks to regular files count;
   broken symlinks are skipped and may become candidates later — rescans self-heal).
2. The file name is **not hidden** (does not start with `.`).
3. The file's extension (text after the final `.`, lowercased) is in the `--extensions` set.
   Files without an extension are not candidates.
4. The path is in the target directory itself — **no recursion** into subdirectories.

In single-file mode (R21) the scan is over the *containing* directory, but the candidate set
is restricted to the single target path (all other entries are ignored); the file's own
extension is not filtered against `--extensions`.

### 5.2 Ordering, the newer-only rule, and in-place updates (R3, R4)

- **Newest** = greatest `st_mtime_ns` (nanosecond resolution).
- **Switching files:** the display switches to a *different* path only if its `mtime_ns` is
  **strictly greater** than the current snapshot's. Equal mtimes (ties) **keep the current**
  image. The display therefore never moves backward in time — an old file copied in with
  `cp -p` never steals the display.
- **Same path:** if the displayed path's `(mtime_ns, size)` differs from the snapshot (an
  in-place update), it reloads — regardless of whether the new mtime is older or newer
  (R4). A rewrite that changes neither mtime nor size is undetectable and not required to
  update (out of scope).
- **Current path gone** (deleted or renamed away): the display has no snapshot; the newest
  settled candidate becomes the display (or the waiting state if none).
- The tie-break rule of §4.3 (greatest name) is used **only** by `--print`, which has no
  "current" to keep.

### 5.3 Settled (R6)

Per-path observed state is kept in memory: `(mtime_ns, size, last_change_mono)`, where
`last_change_mono` is the monotonic timestamp at which this viewer last observed a change of
`(mtime_ns, size)` for that path (including first sighting).

On each rescan, for every candidate:

- if its `(mtime_ns, size)` differs from the observed state → update the observed state and set
  `last_change_mono = now` (monotonic clock);
- otherwise → keep `last_change_mono`.

A candidate is **settled** iff **both** hold:

```
(now_mono  − last_change_mono) ≥ settle window      (observed quiet)
(now_wall  − mtime_wall)     ≥ settle window        (self-reported quiet)
```

- The **observed quiet** condition guards against writers that emit inotify events in bursts
  during a multi-part write (the file keeps changing across rescans, so it never settles early).
- The **mtime age** condition gives a fast path at startup (a file whose mtime is already older
  than the window is settled immediately on first sighting) and guards against a writer that
  updates content without mtime movement being observable between two rescans.
- `--stable-ms 0` makes both conditions vacuously true: display on first observation.
- The two conditions use **different clocks on purpose**: wall time compares against the file's
  own mtime; monotonic time measures *our* observation. Neither is trusted alone.

**Worked example (default window 2000 ms):** a 2 MB PNG is written over ~300 ms in a burst of
inotify events. First sighting at t=0 (mtime ≈ t=0.3 s). Rescans at t≈0.2, 0.4, … observe the
size growing → `last_change_mono` keeps resetting. Write finishes; from t≈0.5 s the file is
static. At the first rescan with `now_mono − last_change_mono ≥ 2 s` **and**
`now_wall − mtime ≥ 2 s` (t ≈ 2.5 s) it settles and is displayed. Total latency after the
writer's last byte: ≈ 2 s + one coalesce interval (200 ms) + decode time.

### 5.4 Load & swap — the dual buffer (R7, R15)

- If the best settled candidate's file version differs from the current snapshot → a decode
  request is issued (§12.5).
- **Success:** the picture, header info (windowed mode only, R16), and snapshot are
  swapped in one main-thread step.
- **Failure:** the visible image is **untouched**. The failed file version
  `(path, mtime_ns, size)` is recorded; stderr receives one line naming the file and the error.
  That version is never retried; if the file changes again (new version) it is eligible again.
  If no image was on display yet, the waiting state's text becomes
  `Could not load <name> — see stderr` (the text is not shown in `--fullscreen`
  mode, R16).
- Only **one** decode request is in flight at a time; a newer request supersedes a pending one
  (its result is discarded via the generation counter, §12.5).

---

## 6. Directory watching

### 6.1 Mechanisms (R2)

- **inotify (default):** a `Gio.File` monitor on the target directory. *Any* event (created,
  changed, changed-attributes, deleted, moved in/out, owner change) marks the directory dirty.
  Events are **coalesced**: at most one rescan is scheduled per 200 ms (internal constant),
  each rescan being a full enumeration anyway.
- **Polling:** `riview --poll S` replaces the monitor with a timer that rescans every S
  seconds. Used for filesystems without inotify support and as the automatic fallback.
- **Fallback (R14):** if monitor creation fails (GError, e.g. unsupported filesystem),
  `riview` prints a warning to stderr and switches to polling at 1.0 s (or the `--poll`
  value, if given).
- **Re-monitoring (R14):** inotify watches are per directory *instance*: if the directory
  is deleted and recreated — even under a reused inode number — the old monitor is
  silently dead and no further events ever arrive. `riview` therefore keeps a 1 s
  recheck timer in inotify mode that stats the path and recreates the monitor. A
  missing path clears the display to the waiting state (once); a path that exists as
  a directory gets a fresh monitor, and a rescan is issued whenever the recheck
  detects a gap, an inode-number change, or every 5th tick as a safety net (so state
  always converges to disk truth within a few seconds, whatever happened).

### 6.2 Rescan

A rescan (always on the main thread) is: enumerate the directory (`os.scandir`) → stat each
entry → update observed state (§5.3) → pick the best settled candidate (§5.2) → issue a decode
request if the display should change (§5.4). For the expected workload (a few thousand files at
most) this is a sub-millisecond operation and costs nothing on the main thread.

The first rescan happens at startup, so pre-existing files are displayed without waiting for an
event (subject to the settle window, §5.3).

---

## 7. Rendering

### 7.1 Decode & scaling (R9)

- Images are decoded with `GdkPixbuf.Pixbuf.new_from_file_at_scale(path, W, H,
  preserve_aspect_ratio=True)` on the worker thread, where the target box is
  `W = 2 × scale_factor × window_width`, `H = 2 × scale_factor × window_height` (the 2×
  oversample keeps the image sharp through moderate window resizes and HiDPI), further capped
  by `--max-dim` on the longer side when given, and never enlarged beyond the source's native
  dimensions.
- The pixbuf is handed to a `Gtk.Picture` via `Gdk.Texture.new_for_pixbuf` +
  `set_paintable` (the non-deprecated display API, §13.2), configured
  `content-fit=CONTAIN`: the image always fits the window, is never cropped, and is
  letterboxed with a black background (R17) when aspect ratios differ. (CONTAIN
  preserves the aspect ratio; the deprecated `keep-aspect-ratio` property is not used.)
- Window resize in v1 does **not** re-decode; the 2× oversample absorbs reasonable resizes
  (non-goal: adaptive re-decode).
- Initial window size: 80 % of the primary monitor's work area, minimum 900×675 logical
  pixels; `--fullscreen` overrides to full screen after showing, with the chrome
  hidden (R16).

### 7.2 Formats (R5)

- Decoding capability = the system's GdkPixbuf loaders; on the target system: png, jpeg,
  webp, gif, tiff, bmp (all in the default set), plus avif, svg, ico, pnm, tga, xbm, xpm
  (opt-in via `--extensions`).
- **Animated GIF: first frame only** (GdkPixbuf's loader decodes the first frame; animation is
  a non-goal, §10).
- EXIF orientation is **not** applied (GdkPixbuf default behaviour). Generation pipelines do
  not emit EXIF; this is documented behaviour, not a bug.
- A file whose bytes do not decode to a supported image is a decode failure (§5.4), never a
  crash.

---

## 8. Exit codes

| Code | Meaning |
|------|---------|
| `0` | Normal: window closed, `--print` completed (including printing `none`), or a desktop install/uninstall completed. |
| `2` | Usage / argument validation error (§4.2), or incompatible flags. |
| `3` | Target (directory or file) does not exist at startup. |
| `1` | Any other unexpected internal error (e.g. display unavailable while creating the window). |

`--help` / `--version` exit `0`.

---

## 9. Examples

```bash
# Watch the pipeline output directory (typical use), from the workspace root.
cd /home/max/src/sdcpp-setup-lemonade && riview out

# Watch the current working directory (terminal context, R22).
cd out && riview

# Watch a single image file in place (single-file mode, R21).
riview out/frame_012.png

# Full-screen preview while a long batch runs.
riview out --fullscreen

# Network filesystem or inotify-quota problems: poll every half second.
riview /mnt/renders --poll 0.5

# Fast pipeline, small files: shorter settle window.
riview out --stable-ms 500

# Low-power machine, huge images: cap the decode at 1024 px on the longer side.
riview out --max-dim 1024

# Headless: which file would riview show right now? (scripts, tests)
riview --print out
riview --print out/frame_012.png

# Accept AVIF too.
riview out --extensions png,jpg,webp,avif

# Install the app into the desktop: app menu entry + icon + "Open with" on
# folders and images (per user, idempotent; --uninstall-desktop removes it).
riview --install-desktop
```

---

## 10. Non-goals (v1)

- No zoom, pan, rotate, crop, or full-size inspection (fit-to-window only, R9).
- No navigation *between* files (previous/next, keyboard or mouse) — riview is a reload
  viewer, not a browser.
- No animation of multi-frame images (GIF first frame only).
- No config files, no persistent state, no "remember last directory".
- No recursive watching; subdirectories are never scanned.
- No multi-directory watching in one process (run two `riview` processes if needed).
- No adaptive re-decode on window resize (§7.1).
- No EXIF orientation handling, no colour-management, no ICC profiles.
- No drag-and-drop of folders or images onto the window — the installed `Gtk` typelib lacks
  `Gtk.GestureDrop` (§13.2). The launch paths are the `.desktop` entry's `Exec %U` (R20)
  and the command line.
- No re-targeting in a running session — no in-app folder picker, no key for it: to watch
  something else, quit and relaunch (rev 0.8 design decision; the `.desktop` entry makes
  relaunches cheap).
- No notifications, tray icon, or D-Bus interface.
- No Windows/macOS port (Linux; inotify with a polling fallback).

---

## 11. Verification plan

Headless cases (runnable in a plain shell, no display needed — `tests/test_riview.py`):

1. **`--print`, empty dir** → prints `none`, exit 0.
2. **`--print`, two PNGs, staggered mtimes** (`touch -d`) → prints the newer one (absolute
   path), exit 0.
3. **`--print` filtering** → a `.txt`, a hidden `x.png`, and a subdirectory `sub/a.png` are
   all ignored.
4. **`--print` tie** → equal mtimes → byte-wise greatest name is printed.
5. **`--print` custom extensions** → `--extensions bmp` ignores a PNG, picks a BMP.
5a. **`--print` file target** → `--print DIR/img.png` prints that file's absolute path;
   `--extensions bmp` does not change the result (R21).
5b. **`--print` non-image file target** → exit 2, message on stderr.
5c. **`--print` no target** → the CWD is used regardless of launch context (§4.3).
6. **Startup errors** → non-existent dir → exit 3 + stderr message; dir that is a regular
   file → exit 2; non-image file target → exit 2; `--poll 0` / `--stable-ms -1` /
   `--extensions ''` → exit 2; `--print --fullscreen` → exit 2; `--install-desktop DIR` /
   `--install-desktop --print` / `--install-desktop --uninstall-desktop` → exit 2.
7. **Selection logic (unit)** → newer-only: old `cp -p` copy-in does not displace current;
   tie keeps current; in-place mtime change reloads; deleted current falls back to newest.
8. **Settle logic (unit, fake clocks)** → a file observed changing across two scans does not
   settle; a file static for the window settles; mtime-older-than-window fast path settles at
   first sighting; `--stable-ms 0` settles immediately.
8a. **Desktop install (R20)** → `--install-desktop` with `XDG_DATA_HOME` pointed at an empty
   tree → `applications/com.lemonade.riview.desktop` and
   `icons/hicolor/scalable/apps/com.lemonade.riview.svg` are written; the entry contains
   `Exec=<abs path of the riview script> %U`, `Icon=com.lemonade.riview`,
   `MimeType=inode/directory;…`, `Terminal=false`; a repeat run stays green (idempotent).
8b. **Desktop uninstall (R20)** → `--uninstall-desktop` removes both files; with nothing
   installed → note on stderr, exit 0.
8c. **Launch-context classifier (R22, unit)** → `DESKTOP_STARTUP_ID` set → GUI; controlling
   tty present, no env var → terminal; no controlling tty → GUI.
8d. **`--fullscreen` no target, no display** → a child with a controlling terminal (pty)
   classifies as terminal → CWD → GTK init fails → exit 1; a pty-less child (`setsid`) classifies
   as GUI → usage error → exit 2.

GUI cases (require a graphical session — run inside COSMIC; this workspace's shell has no X
authority, so these are manual/semi-automated):

9. **Waiting state** → `riview` on an empty dir shows the placeholder (white text on a
   black canvas); no crash.
10. **First image** → copy a finished PNG in → it is displayed within ≈ settle window + decode;
    header shows base name, dimensions, mtime; the letterbox around the image is black (R17).
11. **Newer file switches** → copy a second PNG with a newer mtime → display switches
    automatically.
12. **In-place update** → overwrite the displayed PNG (different content, new mtime) → display
    reloads automatically.
13. **Half-written file** → write 10 % of a large PNG's bytes, wait > settle window, then
    finish the write → the viewer must **never** show the partial image; it shows the final one.
    (With `--stable-ms 0` the partial may be attempted; a failed decode must then keep the
    previous image intact — R7.)
14. **No backward switch** → `cp -p` an older-mtime file in → display unchanged (newer-only).
15. **Deletion** → remove all images → waiting state returns; add one → displayed.
16. **Corrupt file** → write settled invalid bytes as `z.png` (guaranteed-newest mtime) → one
    stderr warning, previous image retained, no repeated warnings while the file is unchanged.
17. **Polling mode** → `--poll 0.5` repeats cases 10–12 with equivalent behaviour.
18. **Fullscreen** → `--fullscreen` starts full-screen, image only (no header bar, no
    waiting text — just the black canvas and the image); window close exits 0.
19. **`--max-dim`** → a 4096 px source with `--max-dim 512` shows a ≤512 px decode (header
    dimensions confirm).
20. **Directory delete + recreate** (inotify mode) → `rm -r out && mkdir out` and drop a new
    PNG → monitoring re-establishes and the new image appears (R14).
21. **GIF** → a multi-frame GIF shows its first frame, stably.
22. **SIGINT/SIGTERM** → clean exit, code 0, no traceback.
23. **Keyboard shortcuts (R18)** → with the window focused: `q` quits (rc 0); `Ctrl+C`
    quits cleanly (rc 0, no traceback); `f` toggles full screen both ways (header bar
    hidden in full screen, back on exit); `Esc` leaves full screen and does nothing in
    windowed mode; `Ctrl+q` / `Ctrl+f` are **not** shortcuts (leave the keys unhandled).
24. **Canvas double-click (R19)** → a left double-click on the image *and* on the black
    letterbox both toggle full screen ↔ windowed (header bar hidden in full screen, back on
    exit); a double-click on the header bar does nothing; single clicks do nothing.
25. **Idle state (R22)** → launched from the app menu / panel (no target, GUI context) →
    black canvas with the wrapped message, header subtitle `no file`, `q` quits cleanly.
26. **Desktop entry (R20)** → after `--install-desktop`: the entry and icon appear in the
    app grid and in Files; right-click a folder → "Open with riview" → directory mode;
    right-click a PNG → single-file mode; `--uninstall-desktop` removes the entry and icon.
27. **Single-file mode (R21)** → `riview out/x.png` shows x.png only; overwriting x.png in
    place reloads it; a newer *other* image in `out/` does **not** displace it; deleting
    x.png → "Waiting for x.png to settle…"; recreating it → displayed again.
28. **Terminal CWD (R22)** → `cd out && riview` (no argument) watches the CWD — no idle
    message appears.

---

# Part II — Design

## 12. Design

### 12.1 Confirmed decisions

D1–D5 answer the open questions (Q1–Q5) raised before drafting; D6–D11 are design defaults
flagged for review.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Newest = `st_mtime_ns`; newer-only switching** (strictly greater mtime to switch files; ties keep current; same-path changes always reload). §5.2, R3/R4. | Confirmed (Q1). mtime is the only order that is both general and update-sensitive; strict-newer prevents flapping when old files are copied in; same-path reload gives "file updated → display updates". |
| D2 | **Target resolution & launch context (rev 0.8):** an explicit target may be a directory or an image file (single-file mode, R21). No target: watch the CWD when launched from a terminal, else the idle state (R22) — GUI context ⇔ `DESKTOP_STARTUP_ID` set or no controlling tty (§4.6, a documented heuristic). | Replaces rev-1 "default target = CWD". A menu-launched app must not silently watch `$HOME`; a terminal launch keeps the historical zero-surprise CWD default. |
| D3 | **Fit-to-window only; `--fullscreen` flag; no zoom/pan.** | Confirmed (Q3). Keeps the tool a *reload* viewer; sharp through resize via 2× oversample (§7.1). |
| D4 | **Default extensions `png,jpg,jpeg,webp,gif,tiff,tif,bmp`; GIF = first frame; `avif`/`svg` opt-in via `--extensions`.** | Confirmed (Q4). Covers all lemond output formats plus common extras; SVG excluded from defaults because vector files are misleading as "generated image" previews. |
| D5 | **Settle window default 2000 ms (`--stable-ms`), dual conditions (§5.3); dual buffer — display swap only after successful decode (§5.4).** | Confirmed (Q5). 2 s of quiet is safe for bursty 1–10 MB writes; the mtime-age condition gives a startup fast path; the dual buffer makes decode failures invisible to the user except on stderr. |
| D6 | **Single-file Python 3 + PyGObject (GTK 4 + libadwaita); no pip packages.** | Matches the workspace convention (`rigen`, `vary`) and the target system's installed stack (§13.1). GTK 4 + libadwaita is the first-class toolkit for the COSMIC desktop. |
| D7 | **Inotify via `Gio.File` monitor, 200 ms event coalescing; `--poll S` forces polling; inotify failure auto-falls back to 1.0 s polling with a warning.** | Full-rescan-on-event is simplest and correct (a rescan re-derives everything from disk truth); coalescing bounds event storms from bursty writers. |
| D8 | **Decode on a single worker thread; `threading` + `queue` bridge to the main loop; one decode in flight; generation counter supersedes stale results.** | Verified on this system that PyGObject 3.48.2 exposes neither `GLib.spawn_threaded` nor `MainContext.invoke` (§13.2), so the plain, guaranteed-correct bridge is a worker thread + `queue.Queue` drained by a 16 ms `GLib.timeout_add` pump. |
| D9 | **`Gio.ApplicationFlags.NON_UNIQUE`** — every `riview` process is independent; two windows can watch two directories. | An app-ID singleton would make a second (different-directory) instance steal the first window; independence is the useful behaviour for a utility. |
| D10 | **`--print` headless query mode** (replaces `--newest`; no settle window; point-in-time; file target prints itself; no target → CWD always; tie → byte-wise greatest name). | Mirrors `rigen --list`/`--dry-run`: a small, scriptable, headlessly-testable surface for the selection logic (§11 cases 1–5c). The rename reflects that it now answers "what would riview display", not just "what is newest". |
| D11 | **Initial window = 80 % of primary monitor work area (min 900×675); decode target = min(source, 2×scale_factor×window, `--max-dim` on longer side).** | A window sized to the image would make 4K sources produce unusable windows; 2× oversample covers HiDPI and moderate resizes without re-decode. |
| D12 | **Desktop integration via `--install-desktop`/`--uninstall-desktop` (R20):** per-user `.desktop` + embedded SVG icon under `XDG_DATA_HOME`; `Exec %U`; `MimeType` for `inode/directory` + default image types; idempotent; uninstall is a no-op-OK. The icon lives in the script as a string constant (D6 preserved). | The file manager and the app grid watch these directories (no `update-desktop-database` needed); `Exec %U` is the standard, dependency-free way to get "right-click → Open with riview"; per-user scope avoids root and package management. |

### 12.2 Deliverables

```
sdcpp-setup-lemonade/
├── riview                    # the viewer (single file, executable, Python 3.10+)
├── RIVIEW-SW-SPEC-AND-DESIGN.md   # this document
└── tests/
    └── test_riview.py        # headless suite: selection + settle logic (fake clocks),
                              # --print mode, CLI validation, desktop install, launch
                              # context (no display required)
```

No `.desktop` file is *shipped* in the repository: the entry is generated at runtime by
`--install-desktop` (R20, D12) into the user's own `XDG_DATA_HOME`.

### 12.3 Program structure

Single file `./riview`, top to bottom: (the GUI-layer classes are defined inside
`_gui_classes()` so that `--print` and the desktop flags never import GTK, and so the
headless test suite can drive `Watcher`/`Decoder` without a display — `run_gui` calls it
and runs the app).

1. **Constants** — `VERSION = "1.0.0"`; exit codes (`OK=0, USAGE=2, NO_TARGET=3, INTERNAL=1`);
   defaults (`DEFAULT_EXTENSIONS`, `DEFAULT_STABLE_MS=2000`,
   `COALESCE_MS=200`, `FALLBACK_POLL_S=1.0`, `RECHECK_MS=1000`, `PUMP_MS=16`,
   `OVERSAMPLE=2`, `DOUBLE_CLICK_S=0.4`); desktop strings (`APP_ID`, `ICON_SVG`,
   `DESKTOP_MIMETYPES`, `IDLE_TEXT`, `WAITING_TEXT`).
2. **Data** — `Observed` (per-path: `mtime_ns, size, last_change_mono`); `Snapshot`
   (displayed: `path, mtime_ns, size, width, height, label`).
3. **Selection layer (pure, unit-tested)** —
   `scan_candidates(dir, exts) -> [(path, mtime_ns, size)]` (applies §5.1, follows symlinks,
   skips broken links);
   `update_observed(obs_map, cands, now_mono) -> obs_map`;
   `is_settled(obs, now_mono, now_wall, window) -> bool` (§5.3);
   `pick_best(settled_cands, snapshot) -> path|None` (§5.2 switch/tie/reload rules);
   `newest_for_report(cands) -> path|None` (§4.3 tie-break).
4. **Launch context & target resolution (rev 0.8, pure, unit-tested)** —
   `has_controlling_tty()`, `is_gui_context(environ, has_ctty)` (§4.6),
   `uri_to_path(target)` (`file://` URIs from `%U`),
   `resolve_target(raw, gui_ctx) -> ("dir"|"file"|"none", abs_path|None)` (raises
   `UsageError` / `NoTargetError`).
5. **Watcher** — `class Watcher`: owns inotify monitor *or* poll timer (R14 recovery via
   periodic re-monitoring)
   logic, §6); exposes `start(on_rescan)` / `stop()`; stats the target on each rescan for the
   `(dev, ino)` check.
6. **Decoder** — worker thread + `queue.Queue`; `request_load(generation, path, W, H)`;
   results delivered as `(generation, path, pixbuf|Error)` (§12.5).
7. **UI** — `RiviewApp(Adw.Application)` (`NON_UNIQUE`, app id `com.lemonade.riview`) and
   `RiviewWindow(Adw.ApplicationWindow)`: header bar, picture, status label, rescan pump,
   load orchestration (§5.4 swap), initial-size/fullscreen policy (§7.1, D11), idle state
   (R22), single-file mode (R21), window icon (R20).
   **The GTK/GdkPixbuf `gi` imports happen only in this section and are imported lazily**
   (inside the GUI code path), so `--print` never imports them (§13.3).
8. **CLI** — `build_parser()`, `validate(args)` (raises `UsageError`; maps to exit 2;
   missing target → exit 3); `run_print(mode, path, args)`; `run_desktop_install(args)`
   (`_desktop_paths()`, `DESKTOP_ENTRY` template).
9. **`main()`** — dispatch (`--version`; desktop flags → `run_desktop_install`; validate →
   `resolve_target` → `--print` headless path; else GUI).

### 12.4 Threading model

```
┌────────────────────────────── main thread ──────────────────────────────┐
│ GTK main loop (Adw.Application.run)                                     │
│  • Watcher callbacks (inotify "changed", poll timer, recheck timer)      │
│  • coalesce timer (200 ms) → rescan (scandir + stat + selection)        │
│  • pump timer (16 ms) → drain result queue → swap display + snapshot    │
└──────────────▲───────────────────────────────────────────┬──────────────┘
               │ result (generation, path, pixbuf|Error)   │ request (generation, path, W, H)
               │            queue.Queue (thread-safe)      │
┌──────────────┴───────────────────────────────────────────▼──────────────┐
│ decoder worker thread (single, persistent)                              │
│  GdkPixbuf.Pixbuf.new_from_file_at_scale(path, W, H, True)              │
└─────────────────────────────────────────────────────────────────────────┘
```

- The scan is deliberately small (stat-based, sub-ms) — it stays on the main thread; only
  decoding (10 ms–500 ms) leaves it.
- **Verified API note (D8):** this system's PyGObject 3.48.2 does **not** expose
  `GLib.spawn_threaded` or `MainContext.invoke` (checked: §13.2), so the bridge is
  `threading.Thread` + `queue.Queue` + a 16 ms `GLib.timeout_add` pump. This pattern is
  trivially correct and has no binding-surface risk.
- `new_from_file_at_scale` touches no GTK main-context state and is safe to call from the
  worker thread.

### 12.5 Decode pipeline

```
on_rescan():
    cands   = scan_candidates(dir, exts)              # §5.1
    if single-file mode (R21):
        cands   = [c for c in cands if c[0] == only_path]   # restrict to the target file
    obs     = update_observed(obs_map, cands, mono_now)
    settled = [c for c in cands if is_settled(obs[c.path], mono_now, wall_now, window)]
    best    = pick_best(settled, snapshot)            # §5.2  → path | None
    if best is None:
        show_waiting()                                # R8 (text hidden in --fullscreen, R16;
                                                      #   "Waiting for {name} to settle…" in R21)
    elif best != snapshot.path or version(best) != snapshot.version:
        gen = next_generation()
        W, H = decode_target()                        # §7.1 (window × scale_factor × 2, capped)
        decoder.request_load(gen, best, W, H)
        # NOTE: display is NOT touched here — the swap happens only in on_result on success.

on_result(gen, path, pixbuf|error):                   # main thread, via pump
    if gen != current_generation: discard             # superseded
    if error:
        failed_versions.add(version(path))            # R15: no retry of same version
        warn(stderr, path, error)
        if no image on display: show_waiting(error_note)
        # else: keep current image (dual buffer, R7)
    else:
        picture.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))   # §13.2 (non-deprecated)
        snapshot = Snapshot(path, mtime_ns, size, pixbuf.width, pixbuf.height)
        if not fullscreen:                            # R16: image only, no header
            header.update(basename, f"{w}×{h}", mtime_local)
        hide_waiting()
```

`pick_best` returns the same path+version as the snapshot → nothing happens (no decode).

### 12.6 Watcher

- **inotify mode:** `Gio.File.new_for_path(dir).monitor(Gio.FileMonitorFlags.NONE, None)`;
  connect `"changed"` (all event types funnel into the same dirty flag). Plus a 1 s
  recheck timer (below). Dirty → `GLib.timeout_add(200, do_rescan)` if none pending.
- **Poll mode:** `GLib.timeout_add(poll_ms, do_rescan)`; no monitor, no recheck.
- **Recheck timer (inotify mode, R14):** every second: stat the path; if missing →
  mark gone and rescan once (clears the display to the waiting state); if a directory →
  recreate the monitor (watch is per-instance; a deleted+recreated directory kills the
  old one, even under a reused inode number) and rescan when a gap was observed, the
  inode number changed, or every 5th tick (safety net). One or two syscalls per second.
- **Fallback:** monitor creation raising `GLib.Error` → stderr warning → poll mode at
  `--poll` value or 1.0 s (the recheck timer then disarms itself).

### 12.7 UI layout

```
Adw.ApplicationWindow  (icon: com.lemonade.riview if installed, else image-x-generic,
                        title "riview")
└── Gtk.Box (vertical)
    ├── Adw.HeaderBar            (hidden in --fullscreen, R16)
    │   └── Adw.WindowTitle
    │         title    = basename of displayed file   (or "riview")
    │         subtitle = "{w}×{h}  ·  {YYYY-MM-DD HH:MM:SS}" (decoded size · file mtime, local)
    │                    or "no file" in the idle state (R22)
    └── Gtk.Overlay          (left double-click → toggle full screen, R19)
        ├── Gtk.Picture        (hexpand/vexpand, content_fit=CONTAIN, can_shrink=True;
        └── Gtk.Box (center)
            └── Gtk.Label      (waiting/idle state, wrapped, max 60 chars, class
                                riview-waiting; never shown in --fullscreen:
                                "Waiting for images…" /
                                "Waiting for {name} to settle…" (R21) /
                                IDLE_TEXT (R22) /
                                "Could not load … — see stderr")
```

- Window class: `Adw.ApplicationWindow` (not plain `Gtk.Window`) for COSMIC/GNOME-standard
  chrome; libadwaita 1.5 styling is inherited from the desktop theme automatically.
- No actions in the header bar in v1 (close button only).
- **Black canvas (R17):** a `Gtk.CssProvider` at `STYLE_PROVIDER_PRIORITY_USER` (added
  once, display-wide, during window construction) sets `window { background-color:
  #000000; }` — the `Gtk.Picture` letterbox is transparent, so black shows around the
  image; the waiting label carries the CSS class `riview-waiting` (`color: #ffffff`)
  so it stays legible under light themes.
- **Full screen (R16):** the header bar is hidden at construction and the waiting label
  is never shown, so the window contains only the black canvas and the image.
- **Idle state (R22):** with mode `none` the window creates no watcher, decoder, or pump;
  the label shows `IDLE_TEXT` (wrapped) and the subtitle reads `no file`.

### 12.8 COSMIC integration notes

- `cosmic-comp` provides a Wayland session; GTK 4 clients run on its Wayland backend or, via
  XWayland, on X11 (this workspace's X session is `:1`). GTK 4 handles backend selection
  itself; no `GDK_BACKEND` pinning is needed, and riview sets none.
- No portals, no autostart. **Desktop entry (rev 0.8, R20/D12):** `--install-desktop`
  generates the per-user `com.lemonade.riview.desktop` + icon (§4.7); until then the app
  appears to COSMIC as a standard GTK client with the `image-x-generic` icon (and is
  launched from the terminal).

### 12.9 Keyboard shortcuts & signal handling (R18)

- **Keys:** a `Gtk.EventControllerKey` on the window handles `key-pressed`: `q` →
  `window.close()` (last-window close quits the `Gio.Application`, exit 0); `f` → toggle
  per the window's own `fullscreen_mode` flag (the only code that changes it —
  deterministic, no compositor round-trip); `Esc` → un-fullscreen, only when currently
  full-screened. A key is acted on only when `state` carries no modifier beyond
  `SHIFT_MASK`/`LOCK_MASK` (the binding exposes no `IS_*` masks, §13.2), so `Ctrl+q` etc.
  are not consumed. The handler returns `True` to consume the event.
- **Full-screen toggle:** `gtk_window_fullscreen()` / `unfullscreen()` plus
  `header.set_visible(not on)`, so the windowed-mode chrome (R10 header) returns when
  leaving full screen.
- **Canvas double-click (R19):** a `Gtk.GestureClick` (button 1) attached to the overlay
  (picture + letterbox + waiting label; the header bar is outside it) fires `pressed` per
  click; two presses within `DOUBLE_CLICK_S` (0.4 s) take the same
  `_set_fullscreen(not …)` path as `f`. Detected manually because this binding lacks
  `Gtk.GestureMultiPress` and `Gtk.EventControllerPointer` (§13.2); the press window is a
  constant (GDK's own double-click time is environment-dependent). The picture widget
  allocates the letterbox as transparent space inside itself, so image and black area both
  hit the same gesture.
- **Ctrl+C / SIGTERM:** `GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, cb)` installs
  C-level handlers (replacing Python's `KeyboardInterrupt` path) that call
  `Gio.Application.quit()` → clean shutdown, exit 0 (§11 case 22). The callback returns
  `False` (one-shot).

### 12.10 Target resolution, launch context, desktop install (rev 0.8; §4.6–§4.7, R20–R22)

```
resolve_target(raw, gui_ctx):
    if raw is not None:
        p = abspath(uri_to_path(raw))            # %U arrives as file:// URIs
        if not exists(p): raise NoTargetError    # exit 3
        if isdir(p):            return ("dir",  p)
        if image_file(p, DEFAULT_EXTS): return ("file", p)     # R21; default set only
        raise UsageError                           # exit 2
    if gui_ctx: return ("none", None)             # R22 idle state
    return ("dir", abspath("."))                   # terminal fallback (D2 rev 1)

is_gui_context(): DESKTOP_STARTUP_ID set  OR  /dev/tty not openable
```

- **Mode propagation:** `main` stores `args.mode` and `args.target_abs`; the window
  interprets them:
  - `dir` — as before (watcher on the target directory, exts from `--extensions`).
  - `file` (R21) — watcher on the *containing* directory; candidate set restricted to the
    single target path in `on_rescan` (§12.5); `--extensions` bypassed. The existing R14
    recheck machinery is reused as-is: deletion of the file (or of its directory) lands in
    the waiting state; recreation restores the display.
  - `none` (R22) — no watcher, no decoder, no pump; label = `IDLE_TEXT` (wrapped, max
    60 chars), subtitle `no file`.
- **Single-file settle:** unchanged R6 logic over a one-element candidate set — the file
  must be static for the window (or already older than the window at first sighting).
- **`--print` (R12):** `dir` → `newest_for_report(scan_candidates(...))` (absolute path or
  `none`); `file` → the file's absolute path. Point-in-time; no settle; no GTK.
- **Desktop install (R20):** `_desktop_paths()` resolves
  `XDG_DATA_HOME/applications/com.lemonade.riview.desktop` and
  `XDG_DATA_HOME/icons/hicolor/scalable/apps/com.lemonade.riview.svg` (default
  `XDG_DATA_HOME` = `~/.local/share`, `os.path.expanduser`); install `makedirs(exist_ok=True)`
  + writes the `DESKTOP_ENTRY` template (`Exec=os.path.realpath(__file__) + " %U"`,
  `Icon=com.lemonade.riview`, `MimeType=inode/directory;image/png;image/jpeg;image/webp;
  image/gif;image/tiff;image/bmp;`, `Terminal=false`, `Categories=Utility;Viewer;Graphics;`)
  + `ICON_SVG`; both idempotent overwrites. Uninstall removes both (`FileNotFoundError`
  tolerated; a note on stderr when nothing was removed); exit 0 either way.
- **Window icon (R20):** `set_icon_name("com.lemonade.riview")` when the icon file exists
  at the installed path, else `image-x-generic`.

## 13. Environment (verified on this machine, 2026-02)

### 13.1 Facts

| Item | Value |
|------|-------|
| OS | Pop!_OS 24.04 LTS (`PRETTY_NAME="Pop!_OS 24.04 LTS"`) |
| Desktop | COSMIC (`cosmic-comp`, `cosmic-panel`, … running); X session at `DISPLAY=:1` |
| Python | 3.12.3 |
| PyGObject | 3.48.2 (`python3-gi`, `python3-gi-cairo`) |
| GTK | 4.14.5 (`gir1.2-gtk-4.0`, `libgtk-4-1`) |
| libadwaita | 1.5.0 (`gir1.2-adw-1`, `libadwaita-1-0`) |
| GLib | 2.80.0 |
| GdkPixbuf | 2.42.10; loaders present: png, jpeg, webp, gif, tiff, bmp, avif, ico, pnm, qtif, svg (rsvg), tga, xbm, xpm, ani, icns |
| librsvg | 2.58.0 (SVG loader backend) |
| Name collision | none — no `riview` binary in `$PATH`, no dpkg package named `riview` |

### 13.2 API quirks verified during planning

- `Gio.File` monitor API is `monitor()` / `monitor_directory()` (there is no
  `create_monitor` in the Python binding).
- The content-fit enum is `Gtk.ContentFit` (not `Gtk.Picture.ContentFit`);
  `Gtk.Picture.set_content_fit` exists.
- **`Gtk.Picture.set_pixbuf` and `set_keep_aspect_ratio` are deprecated** (GTK ≥ 4.10;
  PyGObject emits `DeprecationWarning` at the call site). Use `set_paintable` instead:
  `GdkPixbuf.Pixbuf` itself is **not** a `Gdk.Paintable` (verified), so wrap it with
  `Gdk.Texture.new_for_pixbuf(pixbuf)` — `Gdk.Texture` implements `Gdk.Paintable`
  (verified; works headless too).
- `GLib.spawn_threaded`, `GLib.spawn_main_context`, `MainContext.invoke`,
  `Gio.Application.idle_add` are **not** exposed by PyGObject 3.48.2 → D8's
  `threading` + `queue` + pump bridge.
- `GdkPixbuf.Pixbuf.new_from_file_at_scale`, `Gio.FileMonitorFlags`,
  `Adw.Application(ApplicationWindow, HeaderBar, WindowTitle)`,
  `Gtk.Widget.get_scale_factor`, `Gtk.Window.fullscreen` all verified present.
- **`GInotifyFileMonitor` exposes no `"cancelled"` signal** (verified: connecting to it
  raises `TypeError: unknown signal name`) — directory-removal recovery therefore uses the
  periodic recheck timer instead (§12.6).
- inotify watches are per directory instance; a deleted+recreated directory can carry a
  *reused* inode number, so inode-number comparison alone cannot detect the recreation —
  the recheck timer re-creates the monitor unconditionally (§12.6).
- PyGObject 3.48.2 exposes **no** `Gtk.Window.is_fullscreened()` / `get_fullscreened()`
  (the `fullscreened` *property* exists) and **no** `Gdk.ModifierType.IS_*` masks —
  full-screen state is tracked in a window flag, and shortcut modifier checks use the
  plain masks (§12.9).
- The installed `Gtk` typelib is **missing `Gtk.GestureMultiPress` and
  `Gtk.EventControllerPointer`** (verified by symbol scan) even though both exist in GTK 4 —
  double-click is therefore detected manually via `Gtk.GestureClick` + a 0.4 s press
  window (§12.9). `Gtk.GestureDrop` is also missing — drag-and-drop is a non-goal (§10).
- **Launch-context probe (R22):** `os.open("/dev/tty")` succeeds iff the process has a
  controlling terminal (verified headless and in terminals). `DESKTOP_STARTUP_ID` is the
  startup-notification launch-id set per launch by conforming launchers (GNOME/COSMIC shell
  integrations); its presence is sufficient for GUI context but its absence is *not* proof
  of a terminal.

### 13.3 Runtime requirements

- GUI mode: a graphical session (COSMIC, or any X11/Wayland session with GTK 4 available).
- `--print` mode (formerly `--newest`, rev 0.8) and the desktop flags
  (`--install-desktop`/`--uninstall-desktop`): no display needed. `--print` must not call
  `Gtk.init` at all, and must not even import the `Gtk`/`GdkPixbuf` typelibs (lazy import,
  §12.3) — verified on this
  machine that merely importing `Gtk` (without `Gtk.init`) still prints
  `Authorization required, but no authorization protocol specified` to stderr in a session
  without X authority, which would pollute `--print`'s one-line stdout contract. Importing
  `GdkPixbuf` without a display is clean.
- The implementation must not require network access, root, or any package not listed in §13.1.
