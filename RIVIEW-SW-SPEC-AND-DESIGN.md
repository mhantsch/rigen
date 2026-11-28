# riview — Reloading Image Viewer — Software Specification & Design

**Status:** rev 1.8 — prompt information overlay: `i` (R18 conventions)
toggles a **persistent** on-canvas overlay showing the generation prompt
embedded in the **currently displayed** image — or `no information` — which
updates on every display change (new R33 + §5.10; the §5.9 help list gains
its line; `riview` 1.8.0), plus **`Ctrl+C` copies the displayed image's prompt to the clipboard** — a hidden feature (not in the §5.9 help list) with the R30 overlay `prompt copied` on an effective copy (new R34; `riview` 1.8.1). Rev 1.7: keypress feedback: a 1 s on-canvas
overlay for the effective `c`/`p`/`n`/`Up`/`Down` keypresses in windowed
and `--fullscreen` modes alike (new R30, §5.8; implemented as `riview` 1.7.2 — pale-yellow 2.5×
text on a semi-transparent gray shade, bottom center with its bottom edge
about 10% up from the canvas bottom; §11 cases 8k + 37/38), plus the `space`
cycle/pause toggle (new R31; §11 cases 8l + 39); `--cycle` is **combinable** with `--cycle-time` (when both give a time, `--cycle-time` takes precedence — riview 1.7.3 fix, R29); a **file target** (R21) now starts in manual mode **pinned to that file** — the retired single-file mode (riview 1.7.4 amendment, §11 cases 27/30/40); a **keyboard help overlay** on `h`/`?` (new R32 + §5.9 — stays on screen until the next keypress, which dismisses it and executes it if bound — riview 1.7.5 amendment, §11 case 41). Rev 1.6: cycle mode (slide show) +
`--cycle-time`, `Up`/`Down`
cycle-time adjustment, `--cycle` startup flag (new R27–R29, §5.7, D18/D19;
all detail assumptions confirmed by the spec owner, including the rev-1.6
amendment to A10: an adjustment rescales the *current* interval — elapsed
time preserved), implemented as `riview` 1.6.0. Rev 1.5: movement
keys always pin; `p` pause; position-preserving
image-gone (R23/R25 revised, new R26, D17); implemented as `riview` 1.5.1.
Rev 1.4 is implemented as `riview` 1.4.0 (Home/End jump, R25; D16 superseded
by D17).
Rev 1.1 is implemented as `riview` 1.1.0 (manual navigation,
R23; `tests/test_riview.py` at 84 tests, all headless cases passing; manual GUI
cases 29/30 pending on a real display). Rev 1.0 is released as `riview` 1.0.0
(65 tests); manual GUI cases §11 9–28 verified on COSMIC.

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
| 1.1 | **Manual navigation (new R23 + §5.5 + §4.4 + §12.5 + §12.9):** in directory mode, `Left`/`Right` walk one image at a time through the *settled* candidates toward the older/newer end (order as §4.3), clamped at both ends (further keypresses ignored); `n` returns to the newest image and resumes live following. A manual selection **pins** the display — newer files settling while the user browses do not displace it (R3 suspended for a pinned display); an in-place update of the pinned file still reloads once settled (R4); the pinned file disappearing shows the **image-gone** state (black canvas + message; the pin persists — the file reappearing restores the display; `n` exits). All three keys are no-ops in single-file mode (R21). The "no navigation between files" non-goal (§10) is retired. `--print` unaffected. |
| 1.2 | **Window fit (new R24 + §5.6 + `--fit`/`--fit-window` in §4.1 + `r` in §4.4 + §3.1 + §7.1 + §10 + §11 + §12.3/§12.5/§12.7/§12.9):** the window opens at the D11 default (now the *pre-image* size) and resizes **once** on the first successful decode so that the *canvas* (window minus header bar) matches the displayed image — `ratio` (default): the largest rectangle of the image's aspect ratio within the 80 % budget box, header-corrected (the first image has no letterbox); `exact`: image size in logical pixels (÷ scale factor), capped at the full monitor minus the header; 320 px-per-side floor. No automatic resize on later loads (after the fit pass the window belongs to the user); `r` re-fits on demand to the currently displayed image (no-op in `off` mode, waiting/idle/image-gone states, `--fullscreen`). Fit and `r` are measured on the window's current monitor (drag to another screen + `r` re-fits to that screen); the pre-image default uses the primary/first monitor (window not placed yet). D11 amended; D14 added. Implementation fixes against the installed binding (GTK 4.14.5, PyGObject 3.48.2): monitor size via `get_geometry()` (the GTK3-era `Gdk.Monitor.get_width` was never in the GTK 4 gir — pre-1.2 `_init_size` silently fell back to 1280×960 on every GTK 4 machine); header height via `get_height()` (`get_allocated_height` is deprecated and warns); window resize via `resize()` → pre-presentation `set_default_size()` → post-map size-request grow (verified: `resize` is hidden — deprecated in 4.14 — and `set_default_size` is a no-op on a mapped window here; shrink is compositor-mediated on Wayland). Because post-map resize cannot shrink, the window now opens at the fit size of an already-settled newest file (early fit, `probe_dimensions` header probe — §5.6/§12.3); the post-map fit pass remains the safety net. Post-release fix: the clamp-release timer callback must be **no-argument** (PyGObject's timeout contract — a `TypeError` there left the size-request minimum in place, making the window permanently unshrinkable by hand; regression-tested with a real `GLib.MainLoop` spin), and the deprecated `get_allocated_height` fallback is only called when `get_height` is absent (calling it at construction emitted a `DeprecationWarning`); the fit pass and `r` now measure the **original** file dimensions (header probe; displayed-dimension fallback) as R24/§5.6 requires (they had used the scaled display pixbuf — wrong for `exact`'s 1:1 semantics); and a post-map grow within the 8 px `RESIZE_TOL` is skipped, because on COSMIC the size-negotiation round trip triggered the compositor's window-size memory — `--fit ratio` snapped to a smaller non-ratio size ≈1 s after open (§5.6/§13.2). `RIVIEW_DEBUG=1` now traces all fit/resize decisions. Post-release fix 3: the post-map grow now requires a **verified** current size (`get_width`/`get_height` → `get_allocated_*` → `get_size`; the last was observed reporting 0×0 on a mapped Wayland window, which caused a blind `set_size_request` even when the window was already at the fitted size — and it was the later clamp **release** that made COSMIC re-apply the remembered window size: the snap coincided with the `clamp released` trace line); an unverifiable (0×0) size skips the grow (§13.2). Post-release fix 4: the size watch and a late check after a reached grow identified the remaining ratio-mode snap as an **upstream COSMIC compositor bug** that reconfigures mapped windows larger than a certain size — the spec owner's research found matching bug reports, and the behavior was confirmed **not** to be related to the window's position on screen (the earlier work-area/placement theory was wrong; corrected in rev 1.3, where D15 caps the `ratio` fit box); riview logs the re-clamp and does not fight it (§13.2). §12.3/§12.7/§13.2. |
| 1.3 | **`--fit ratio` COSMIC cap (new D15):** the spec owner's research found upstream bug reports: the COSMIC compositor reconfigures mapped windows larger than a certain size (the rev 1.2 diagnostic instrumentation — `SIZE` size watch + late check after a reached grow — established the behavior is **not** related to the window's position on screen; the earlier work-area/placement theory was wrong). Decision (spec owner): for now, cap the `ratio` fit box at **1600×1200 logical pixels (width × height)** — the image is ratio-fitted inside the smaller of the 80 % budget box and this fixed cap (`COSMIC_CAP_W`/`COSMIC_CAP_H`, §5.6/§12.3); `exact` and `off` are unchanged; the 320 px floor still applies to the capped fit. Revisit (raise or delete the cap) after a COSMIC update fixes the clamping. The debug note now cites the COSMIC bug instead of a placement limit. Behavior change: rev 1.3 ↔ `riview` 1.3.0 (4 new unit tests — cap width-bind, height-bind, the spec owner's 1024² case, and `exact`-not-capped). §5.6/§12.3/§13.2. |
| 1.4 | **Home/End jump (new R25 + §4.4 + §5.5 + §12.9):** in directory mode, `Home` jumps the display to the **oldest** settled image and `End` to the **newest** — both **pin** the display (manual mode, R23 pinning semantics); `End` deliberately does **not** resume live following (that remains `n`). No-ops: single-file mode (R21), the idle state (R22), the waiting state (no settled candidates), and when the target is already the displayed/pinned file — so `End` in live mode is a no-op (the live display is the newest) and repeated presses at an end are no-ops. Unlike `Left`/`Right`, both work **from the image-gone state** (the jump target does not depend on the pin): the display recovers and stays manual. Key conventions as R18 (bare key, Shift tolerated; windowed and full-screen alike). Jumps never resize the window (R24); `--print` unaffected. Decision D16 (spec owner). §11 case 32; 6 new headless tests. |
| 1.5 | **Movement keys always pin; `p` pause; position-preserving image-gone (R23/R25 revised, new R26, D17):** every movement key (`Left`/`Right`/`Home`/`End`) is **two-phase** — *attempt a movement* over the settled candidate list (loading the target only when it differs from the display), then **pin whatever is displayed**; a failed attempt still pins. Consequences: in live mode every movement key **exits live mode** — `Right`/`End` (and `Left`/`Home` with a single settled image) pin the current display in place, the "freeze the stream" action; manual movement is otherwise unchanged (step/jump, load on change). The `Left`/`Right` anchor is the position where the displayed version sorts in the list by `(mtime, path)` — its own entry when settled, else the virtual position of its last known `(mtime, path)` — so **`Left`/`Right` work from the image-gone state** (the pin holds its last mtime; scanning continues after deleting the displayed file) and from a rewrite in flight. New key **`p`** (R26): pins the displayed image with no movement attempt. `n` remains the only key that resumes live mode. The image-gone message now also offers scanning. The "no-op / clamped-ignored" wording for movement keys is replaced throughout by the two-phase rule (R23/R25, §4.4, §5.5, §11, §12.9). Decision D17 (spec owner); D16 is superseded. Behavior change: rev 1.5 ↔ `riview` 1.5.1 (anchor-based `nav_target`, new `nav_anchor`; new freeze/pause/gone-stepping tests). *Patch 1.5.1:* implementation bug fix, no behavior change — the "newer" branch of `nav_target` iterated the list newest-first, so `Right` jumped to the **newest** candidate instead of stepping to the adjacent newer one (the "older" branch was correct); the walk test's missing intermediate assertions let it through. |
| 1.6 | **Cycle mode / slide show (new R27–R29, new §5.7, §4.4, §12.9, D18/D19):** `c` enters **cycle mode**: starting at the currently displayed image, the display advances one *settled* image at a time toward the **newer** end of the navigation list (§5.5) every **cycle time**, wrapping from the newest to the **oldest** image and continuing. Live following (R3) is suspended while cycling: newly settled images do **not** interrupt the display — they join the list at the newest end and are shown when the cycle reaches them (the cycle grows as images are added; deleted files drop out). Any mode-selecting keypress exits cycle mode first, then applies its normal semantics (`Left`/`Right`/`Home`/`End`/`p` two-phase → manual, R23/R25/R26; `n` → live). Cycle time: `--cycle-time` (integer seconds, min 1, default **9**), dynamically adjustable with `Up`/`Down` (±1 s, floor 1 s), during *or* outside cycle mode — an adjustment rescales the current interval (elapsed time preserved, see the amendment below). Cycle position is re-derived from an anchor each tick (the §5.5 `nav_anchor` philosophy, so the list may grow/shrink underneath the cycle); failed decodes (R15) are skipped, never retried. Behaviour change: rev 1.6 ↔ `riview` 1.6.0. **Detail assumptions, confirmed by the spec owner (rev-1.6 review):** [A1] `c` while already cycling is a no-op (not a toggle); [A2] `p` is treated as a navigation key — it stops cycling and pins (manual); [A3] a deleted currently-shown slide is held on the canvas (no image-gone state) until the next advance, which continues from where the image was; [A4] cycling survives the list going empty (waiting state, R8) and resumes on the first settled candidate; [A5] `c` in the waiting state enters cycle mode armed — the first settled candidate becomes the first slide at the next advance; [A6] `--cycle-time` is integer seconds ≥ 1 — no fractions (0/negative → exit 2); [A7] the first advance is a full cycle time after `c`; the clock is not reset by new-image arrivals; a decode failure holds the previous slide and the next advance skips the failed file; [A8] `f`/`Esc`/`r`/canvas double-click leave cycle mode running; [A9] the header subtitle shows `· cycle Ns` while cycling (visible `Up`/`Down` feedback; hidden in `--fullscreen` per R16); [A10] *amended* — `Up`/`Down` rescale the **current** interval: the elapsed time of the in-progress slide is preserved (remaining = new time − elapsed; if the new time is shorter than the elapsed time the advance fires at the next tick), and every following interval uses the new full cycle time — worked example: cycle time 9 s with 2 s elapsed, `Down`×2 → 7 s, so this slide advances after 5 s and the next image gets a full 7 s; outside cycle mode the keys adjust the stored value only. Also confirmed (rev-1.6 review): a new time **shorter** than the elapsed time advances the slide pretty much immediately (next tick); an in-place rewrite of the currently shown slide reloads (R4) with the cycle clock **kept advancing** (defined edge case, confirmed). **Final amendment (spec owner):** a `--cycle` flag automatically enters cycle mode at startup; the first slide is the **oldest** settled image (R29, D19 — the spec owner's stated preference; starting at the newest and wrapping on the first advance was the acceptable fallback). Amended again by the spec owner: `--cycle` takes an **optional value in seconds** — the initial cycle time (flag alone = the 9 s default); originally also made **mutually exclusive** with `--cycle-time` (exit 2) — **retracted by the spec owner as a confirmation mistake (riview 1.7.3 fix)**: `--cycle` carries no interval of its own, so the combination is unambiguous — the flags are **combinable**: `--cycle --cycle-time 3` starts the cycle at 3 s, and when both give a time `--cycle-time` takes precedence. |
| 1.7 | **Full-screen keypress feedback (new R30 + §5.8, §4.4, §12.7/§12.9):** in `--fullscreen` mode (R16) the header — the feedback channel for cycle mode and keypresses in windowed mode (R10/R28) — is hidden, so the spec owner asked for short, on-canvas feedback of mode-changing keypresses. The **effective** keypresses `c`, `p`, `n`, `Up`/`Down` now show an overlay — pale-yellow text (2.5× the normal size) on a semi-transparent gray shade, centered horizontally with its bottom edge about 10% up from the bottom of the canvas — for **1 second**: `c` → `cycle on: {N}s`, `p` → `pause`, `n` → `newest live image`, `Up`/`Down` → `cycle: {N}s` (N = the current cycle time). No-op keypresses show nothing — the overlay fires only when the keypress effects its named change, mirroring the §4.4/§5.5/§5.7 no-op rules (e.g. `c` while cycling / idle / single-file, `n` in live mode, `p` in manual / image-gone / waiting, `Down` at the 1 s floor). The overlay is shown in **windowed and full-screen modes alike** (pre-release amendment — originally full-screen-only, the windowed header keeps its persistent status instead of acting as the sole feedback channel); a further feedback keypress within the 1 s replaces the text and restarts the timer (last wins); a full-screen toggle (`f`/`Esc`/double-click) dismisses an active overlay immediately; nothing is shown at startup (e.g. `--cycle --fullscreen` opens without one). Purely cosmetic: the cycle clock (R28), selection (R3), decode (R7), and window size (R24) are unaffected; `f`/`Esc`/`r`/double-click/`q` show no overlay; `--print` unaffected (no window). R16 amended with the transient exception. Behaviour change: rev 1.7 ↔ `riview` 1.7.0. §11 cases 8k + 37. **Pre-release amendment (spec owner, before any 1.7 release):** the overlay is **not** full-screen-only — it shows in **windowed mode too** (the header keeps its persistent status, R10 — the overlay is the transient confirmation in both modes; the no-doubling rationale is retired), and its bottom edge is 10% up from the **canvas** bottom (the image area below the header bar — full-screen appearance is unchanged, there canvas == window), measured from the canvas container's allocated height at show time. Tracked as `riview` 1.7.1. §11 case 38. **Pre-release amendment 2 (spec owner, `riview` 1.7.2):** `space` **toggles between cycle and pause** — while not cycling it acts exactly as `c` (starts the cycle, overlay `cycle on: {N}s`), while cycling it acts exactly as `p` (stops the cycle and pins the current slide, overlay `pause`); no new mode, state, or message — an alias chosen by the current mode, inheriting all `c`/`p` no-op rules (R31, §4.4, §5.7, §11 cases 8l + 39). **Pre-release amendment 3 (spec owner, `riview` 1.7.4):** the **file target** (R21) is no longer a single-file watch mode — `riview IMG` now watches the **containing directory in full** and **starts in manual mode, pinned to that file**: the file displays **immediately** at process start (no initial settle wait), in-place updates reload once settled (R4), and every directory-mode key works from there (`Left`/`Right`/`Home`/`End`/`p`/`n`/`c`/`space` — all former "no observable effect in single-file mode" clauses are retired); the target file stays in the navigation list even when its extension is not in the `--extensions` set (the target file's own extension bypasses the filter; the default-set gate, exit 2, is unchanged); `--cycle` and `c` start the cycle **at the file** (R29's oldest-start rule does not apply — the explicit file is the start anchor); deleting the file at runtime lands in the **image-gone** state (R23; pin persists, reappearing restores). The term "single-file mode" is retired (now "file target"). §11 cases 27/30 rewritten, case 40 new. **Pre-release amendment 4 (spec owner, `riview` 1.7.5):** **keyboard help overlay** — `h` or `?` shows a list of all function keys with a short description for each (normative text, §5.9), in **all windowed states** (live, manual, cycle, waiting, idle, image-gone) and in both windowed and full-screen modes, **centered** on the canvas (same visual family as R30, normal font size). It **stays on screen until the next keypress**: that keypress **always** dismisses the overlay — if it is a bound function key it is **executed as usual** (a no-op dispatch also dismisses; the dismissing keypress's R30 feedback shows as usual, so the two overlays never coexist), any other key simply dismisses and keeps the current image or message screen; `h`/`?` themselves only dismiss (no re-show). Purely cosmetic (R28 clock / R3 selection / R7 decode / R24 sizing unaffected — cycle slides continue under the overlay). Nothing shown at startup; `--print` unaffected. New R32 + §5.9 + §4.4 row; §11 case 41. |
| 1.8 | **Prompt information overlay (new R33 + §5.10, §4.4, §5.9, §12.7/§12.9/§12.11):** the spec owner asked for the generation prompt embedded in `rigen` images to be visible while viewing. `i` (R18 conventions) **toggles** a **persistent** on-canvas overlay showing the prompt extracted from the **currently displayed** image file — or **`no information`** when none is found, which includes every state with no displayed image (waiting (R8), idle (R22), image-gone (R23)). Display: word-wrapped at **80 % of the canvas width**, pale-yellow text at **1.5×** on the R30 gray shade, bottom-center column with its bottom edge **22 %** up from the canvas bottom — **above** the R30 feedback zone (bottom edge 10 %), so a 1 s R30 feedback can appear below it without overlap and expire as usual; content beyond **50 % of the canvas height** is elided (`…` on the last visible line). **Persistence:** no timer — stays until `i` again; every **display change** (movement keys, `p`, `n`, cycle advances, live arrivals, in-place updates) re-extracts the prompt from the newly displayed file and **updates the text in place**. **Exclusivity (spec owner):** the info overlay and the keyboard help (R32) **never coexist** — `i` dismisses the help (the R32 dismiss-then-dispatch rule) and shows the info overlay; `h`/`?` dismiss the info overlay and show the help; **no state is remembered** (dismissing one does not re-show the other). `i` shows **no** R30 feedback (the overlay is its own feedback); `f`/`Esc`/double-click do **not** dismiss the info overlay — a full-screen toggle keeps it, repositioned from the new canvas dimensions. **Sources (initial set — revisitable):** PNG `tEXt`/`zTXt`/`iTXt` chunks with keys `parameters`/`prompt`/`Prompt`/`Comment` — the prompt is the text before the first `Steps:`/`CFG scale:`/`Sampler:`/`Seed:`/`Size:` line (the stable-diffusion.cpp convention); JPEG/WebP EXIF `UserComment`; the read is bounded to the **first 8 MiB** (nothing within the bound → `no information`). The §5.9 help list gains the line `i   show prompt information` (13 lines). R16 amended (the info overlay is the second full-screen exception). Purely cosmetic: R28 clock, R3 selection, R7 decode, R24 sizing unaffected — in cycle mode the timer ticks under the overlay and slide changes update its text. Nothing shown at startup; `--print` unaffected. Behaviour change: rev 1.8 ↔ `riview` 1.8.0. §11 case 42 + 8m; case 41 extended. **Pre-release amendment 5 (spec owner, `riview` 1.8.1):** **prompt copy** — with the window focused, `Ctrl+C` (Shift tolerated) **copies the generation prompt of the currently displayed image to the system clipboard** — the **same text the R33 overlay shows** (the §5.10/§12.11 extraction). An **effective** copy shows the R30 overlay `prompt copied` (1 s); when nothing can be copied — no displayed image (waiting (R8), idle (R22), image-gone (R23)) or a file without a prompt — the keypress is a no-op: **no clipboard write and no overlay** (R30 effective-only). It is a **hidden feature**: the §5.9 help list is unchanged (13 lines). With the help (R32) displayed it **dismisses it first** (the R32 dismiss-then-dispatch rule — a bound key), and the `prompt copied` overlay then appears (R30 and R32 never coexist); with the info overlay (R33) displayed it **leaves it in place** and copies the same text it shows. The **terminal** `Ctrl+C` (SIGINT) and `SIGTERM` still quit (R18 clarified — the window-focused *keypress* is the copy, not a quit). Purely cosmetic beyond the clipboard write: R28 clock, R3 selection, R7 decode, R24 sizing unaffected — cycle mode keeps ticking. `--print` unaffected (no window). New R34 + §4.4 row + §5.10 bullet; §11 case 43 + 8n; case 23 clarified. Spec stays rev 1.8; tracked as `riview` 1.8.1. **Pre-release fix (latent R18 defect, found while verifying case 43):** this GLib/PyGObject invokes the `unix_signal_add` closure with **no arguments** — the old `signum`-required signature raised a `TypeError` on the first terminal `Ctrl+C` (and, the source being one-shot, consumed the handler, so the second press had to reach Python's default path); the closure signature now accepts both calling conventions (§13.2). **Pre-release patch (spec owner, `riview` 1.8.2):** **letterboxed prompt overlay** — the R33 wrap width now follows the **rendered** image width (80 % of it, the letterbox extent under the current R24 layout), **capped at 80 % of the canvas width** (an image wider than the window: unchanged) and **floored at 50 % of the canvas width** (a letterboxed image narrower than 62.5 % of the canvas keeps a usable column); update-on-swap now re-applies the wrap width (it can change between slides) and `r` repositions the overlay while visible (a re-fit can change the rendered image width). Everything else about the overlay is unchanged. §5.10/§12.7; §11 case 8o new, case 42 extended. Spec stays rev 1.8; tracked as `riview` 1.8.2. **Pre-release patch (spec owner, `riview` 1.8.3):** **reflow on window resize** — a windowed-mode window resize (drag) now reflows the R33 overlay live: while visible, a **50 ms GLib timeout** (no resize signal, the R30 constraint) reads the canvas's allocated size and, on change, re-applies wrap / elision / bottom margin from the **cached full extracted text** (no re-extraction — a resize changes no file; unelided so a grow de-elides); installed on show, removed on hide/shutdown (zero cost when hidden). R30's 1 s feedback and the R32 help remain show-time-only (transient text). During verification the original frame-clock tick mechanism was replaced by this timeout: this PyGObject invokes tick callbacks with a non-standard argument count (a TypeError on the first frame — the §13.2 convention family); the zero-argument timeout convention is the one proven throughout the program. §5.10/§12.7; §11 case 8p new, case 42 extended. Spec stays rev 1.8; tracked as `riview` 1.8.3. |

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

Since rev 0.8 the target can also be a **single image file** (file target,
R21: the containing directory is watched in full and the view starts in
manual mode pinned to that file), and `riview --install-desktop` adds a per-user desktop entry and
icon so the app can be launched from the app menu or via the file manager's
"Open with" on a folder or an image (R20).

Since rev 1.1 the user can also **walk through the directory's images**: `Left`/`Right`
step one image toward the older/newer end and `n` jumps back to the newest (manual
navigation, R23); the default display remains the newest settled image.

Since rev 1.2 the initial window **fits the image**: on the first displayed
load the window is resized once so the canvas matches the image's aspect ratio
(`--fit ratio`, the default) or exact size (`--fit exact`), and `r` re-fits on
demand (R24, §5.6).

Since rev 1.6 `riview` can also run as a **slide show**: `c` starts **cycle
mode**, which presents the directory's settled images one after another toward
the newer end every *cycle time* (default 9 s, `--cycle-time`; `Up`/`Down`
adjust it live), wrapping around at the newest image (R27/R28). `--cycle`
starts in cycle mode at launch, beginning at the **oldest** image (R29).

Since rev 1.7, the mode-changing keypresses give brief on-canvas feedback —
a 1 s pale-yellow overlay on a semi-transparent gray shade, centered
horizontally about 10% up from the bottom of the canvas (`cycle on: {N}s` /
`pause` / `newest live image` / `cycle: {N}s`) — in windowed and full-screen
modes alike: in full screen the header is hidden (R16), and in windowed mode
the header keeps its persistent status while the overlay is the transient
confirmation (`space` shows the text of its dispatched action, R31; R30,
§5.8).

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
| **target** | The `TARGET` argument: a directory (directory mode) or an image file (file target, R21). May arrive as a `file://` URI from the desktop entry's `%U` (R20). |
| **target directory** | The directory being watched — the target itself in directory mode, or the containing directory for a file target (R21). With no target and a terminal launch, the current working directory (R22). |
| **file target** | Target is one image file: the containing directory is watched in full and the view starts in manual mode, pinned to the file (R21). |
| **idle state** | No target resolved in a GUI context: black canvas + explanatory message, header subtitle `no file` (R22). |
| **launch context** | Terminal vs. GUI context classification used for the no-target fallback (R22, §4.6). |
| **candidate** | A regular, non-hidden file in the target directory whose extension is in the supported set (§5.1). |
| **hidden file** | A file whose name begins with `.`. |
| **settled** | A candidate that has been quiet long enough to be safe to display (§5.3). |
| **settle window** | The quiet period required before display; `--stable-ms`, default **2000** ms. |
| **snapshot** | The identity of the currently displayed image: `(path, mtime_ns, size)`. |
| **newer-only rule** | The display never switches to a *different* file whose mtime is not strictly newer than the current snapshot's (§5.2). Governs live mode only; suspended for a pinned display (R23). |
| **live mode** | The default display mode: the display follows the newest settled candidate (R1/R3/R4). |
| **manual mode** | The display is pinned to a user-selected candidate (`Left`/`Right`, R23); live following is suspended until `n` (pin loss leads to the image-gone state, §5.5). |
| **image-gone state** | The manual-mode display state when the pinned file ceases to be a candidate: black canvas + message; the pin persists, `n` exits (R23, §5.5). |
| **navigation list** | The target directory's settled candidates in navigation order — greatest `st_mtime_ns`, ties → byte-wise greatest name (the §4.3 order) — index 0 = newest (R23, §5.5). |
| **cycle mode** | The slide-show display mode: the display advances automatically through the settled images toward the newer end, wrapping from the newest to the oldest (R27, §5.7). Live following is suspended while cycling. |
| **cycle time** | The interval between cycle advances; `--cycle-time`, integer seconds, minimum 1, default **9**; dynamically adjustable with `Up`/`Down` (R28). |
| **cycle advance** | One step of the cycle: the display moves to the next settled image toward the newer end, or wraps to the oldest (R27, §5.7). |
| **canvas** | The part of the window covered by the picture widget — the window minus the header bar; the black letterbox (R17) is inside it. |
| **fit mode** | The `--fit`/`--fit-window` value: `ratio` (default), `exact`, or `off` (R24, §5.6). |
| **fit pass** | The one-time window resize on the first displayed load that matches the canvas to the image's geometry (R24); re-runnable on demand via `r`. |
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
| R16 | `--fullscreen` starts the window in full-screen mode, **image only**: no header bar and no waiting-state text — just the black canvas and the image; the single transient exception is the 1 s keypress-feedback overlay (R30); the second exception is the prompt information overlay (R33 — persistent until `i`, positioned above the R30 zone, §5.10). |
| R17 | The area of the window not covered by the image (letterbox) is **black**, in windowed and full-screen modes alike; the waiting-state text is white on it. |
| R18 | **Keyboard shortcuts** (window focused; work in windowed *and* full-screen mode alike; bare keys — Shift tolerated, any other modifier leaves the key unhandled, **with one exception: `Ctrl+C` is the prompt-copy key (R34)**): `q` quits (exit 0); `f` toggles full screen ↔ windowed, both directions (header bar reappears on exit); `Esc` leaves full screen (no-op in windowed mode). `Ctrl+C` **in the terminal** (SIGINT) and `SIGTERM` quit cleanly (exit 0, no traceback) — a `Ctrl+C` **keypress with the window focused** copies the prompt instead (R34); it does not quit. |
| R19 | A **left double-click** (two presses within 400 ms) **anywhere on the canvas** — on the image or on the black letterbox; the header bar is excluded — toggles full screen ↔ windowed, both directions, with the same effect as `f` (R18). |
| R20 | **Desktop integration:** `--install-desktop` writes, per user (no root), a `.desktop` entry to `$XDG_DATA_HOME/applications/com.lemonade.riview.desktop` (default `$XDG_DATA_HOME` = `~/.local/share`) and the app's SVG icon to `$XDG_DATA_HOME/icons/hicolor/scalable/apps/com.lemonade.riview.svg`; the icon is **embedded in the script** (single-file property preserved). Both operations are idempotent. The entry uses `Exec=<absolute path to the riview script> %U` and registers `MimeType=inode/directory;` plus the default image MIME types, so the file manager's "Open with" can launch `riview` on a folder or an image; `%U`-supplied targets arrive as `file://` URIs and are accepted. `--uninstall-desktop` removes both files (a note on stderr, exit 0, if neither is present). |
| R21 | **File target:** the target may be an image file instead of a directory. Then the file's **containing directory is watched in full** (a normal directory-mode scan, §5.1) and the view **starts in manual mode, pinned to the target file** (R23/R26 pin semantics): the file displays **immediately at process start** (no initial settle wait), and an in-place update of it reloads once settled (R4) — with no keypresses the view behaves exactly like a pinned manual selection: the file refreshes on change, while newer *other* files never displace it. Every directory-mode behaviour applies from there: `Left`/`Right`/`Home`/`End` navigate the containing directory's settled candidates (R23/R25), `p` is a no-op (already pinned, R26), `n` returns to the newest and resumes live following (R23), and `c`/`space` start the cycle **from the file** (R27/R31; `--cycle` likewise, R29). The target file is a member of the navigation list **even when its extension is not in the `--extensions` set** (the target file's own extension bypasses the filter, §5.1); its extension must be in the *default* extension set, else usage error (exit 2, §4.2). If the file ceases to be a candidate at runtime (deleted, renamed away), the display enters the **image-gone state** (R23): the pin persists with its last mtime, the file reappearing and settling restores the display, and `n` exits to the newest. `--print` (R12) still prints the file itself. *(Pre-release amendment, riview 1.7.4: the original "single-file watch mode" — only that file is ever displayed, keys inert — is retired; the term "single-file mode" no longer exists.)* |
| R22 | **Launch context & idle state:** with no target argument: launched from a **terminal** → watches the current working directory; launched in a **GUI context** (⇔ `DESKTOP_STARTUP_ID` is set, or the process has no controlling terminal — a documented convenience heuristic, §4.6) → **idle state**: the black canvas with the wrapped, centered, white message *"No target given. Right-click a folder or an image and choose \"Open with riview\", or pass a directory or file on the command line."* and header subtitle `no file`; `q`/`f`/`Esc` remain active. `--fullscreen` with no resolved target → usage error, exit 2. `--print` does not use context detection (always CWD). |
| R23 | **Manual navigation (directory mode):** with the window focused, every **movement key** is **two-phase (rev 1.5)**: *attempt a movement* over the navigation list (settled candidates, §5.5) — the display loads the target only when the attempt resolves to a candidate different from the current display — and then **pin whatever is displayed**. `Left`/`Right` attempt a step one image toward the older / newer end, from the position where the displayed version sorts in the list by `(mtime, path)` (§4.3 order); when the displayed file is not a settled candidate — the **image-gone** state (the pin holds the file's last mtime) or a **rewrite in flight** (the last displayed version's mtime) — the position is that last known `(mtime, path)`, so scanning continues from where the image was. A failed attempt (nothing on that side, no settled candidates) leaves the display unchanged; the pin phase still applies. In **live mode** every movement key therefore **exits live mode** (pins the display, or the stepped-to image); in manual mode the pin phase is unobservable (already pinned). `n` returns to the **newest** image and resumes **live mode** (R1/R3) — the only key that does. While a manual selection is active the display is **pinned** to the chosen file: files that settle *newer* while the user is browsing do **not** displace it (the newer-only rule, R3, is suspended for the pinned display), and an in-place update of the pinned file reloads once settled (R4) — pinning never blocks an in-place update of the pinned file itself. If the pinned file ceases to be a *candidate* (deleted, renamed away), the display enters the **image-gone state**: the canvas goes black with the white message *"Current image gone — 'n' jumps to the newest, ←/→ keep scanning."* (hidden in `--fullscreen` like all waiting texts, R16); the pin **persists with its last mtime** — `Left`/`Right` step from that position, the file reappearing and settling restores the display, and `n` exits the state by jumping to the newest and resuming live mode. In the idle state (R22) there is no directory. A file target (R21) starts in manual mode pinned to the target file — the movement keys work over the containing directory's candidates from there. Key conventions as R18: bare keys (Shift tolerated), windowed and full-screen mode alike. |
| R24 | **Window fit:** the window opens at the D11 **pre-image default** (80 % of the primary monitor, min 900×675 — the waiting size; the window is not placed yet, so its own monitor is not addressable) and, on the **first successful decode that reaches the display**, is resized **once** so that the *canvas* (window minus the header bar) matches the displayed image per the **fit mode** (`--fit`, synonym `--fit-window`): `ratio` (default) — the largest rectangle of the image's aspect ratio that fits the 80 % budget box — itself capped at the fixed D15 COSMIC box (1600×1200 logical px, width × height) until the upstream COSMIC clamping bug is fixed — with the header height subtracted from the available height, so the first displayed image has **no letterbox**; `exact` — the image's dimensions in logical pixels (physical ÷ window scale factor), capped at the **full monitor minus the header** (degrading to a ratio fit within that cap when the image is larger than the screen; the window then fills the screen but keeps its header bar — deliberately not `--fullscreen`); `off` — no resize (pre-image size only). A fit result below **320 logical pixels** on either side is recomputed as the largest ratio-preserving rectangle within a 320×320 box. After the fit pass the window is **never auto-resized again**: new loads, in-place updates, and manual navigation (R23) all leave it alone (letterbox as usual, R9/R17). The fit budget and the `exact` cap are measured on the **monitor the window is currently on** (queried at fit time; the primary monitor — or the first monitor — when undetermined, e.g. before window-manager placement), so dragging the window to another screen and pressing `r` re-fits to *that* screen. `r` (R18 key conventions) re-fits on demand to the *currently displayed* image using the same computation — in directory mode and for a file target (R21) alike; a no-op in `off` mode, the waiting/idle/image-gone states, and `--fullscreen`. The option is inert in `--print` and `--fullscreen`. |
| R25 | **Home/End jump (directory mode):** `Home`/`End` are two-phase movement keys (R23, rev 1.5): the attempt jumps to the **oldest** / **newest** settled candidate — absolute list ends, no position anchor needed; the display loads it when it differs from the current display; then whatever is displayed is pinned. In live mode they therefore always exit live mode — at the matching end (or with a single settled image) the attempt makes no change and the current display is **pinned in place** (freeze). In the image-gone state they recover the display on the oldest/newest settled candidate (staying manual). In the waiting state (nothing displayed) there is nothing to pin; for a file target (R21) they behave as in ordinary directory mode (the view simply starts pinned to the target file). Key conventions as R18 (bare key, Shift tolerated; windowed and full-screen alike). A jump never resizes the window (R24). |
| R26 | **Pause key (directory mode):** `p` pins whatever image is currently displayed, with **no movement attempt** — the pure "stay on this image" key: in live mode it freezes the stream (newer files no longer displace the display; an in-place update of the pinned file still reloads once settled, R4). In manual mode, the image-gone state, and the waiting state it has no observable effect (the pin already is the display / nothing is displayed). It is the only key that pins without moving — in the brief rewrite-in-flight window, where `Home`/`End` jump to a settled end, `p` keeps the displayed image. `n` resumes live mode (R23). `space` while cycling dispatches here (R31). Key conventions as R18 (bare key, Shift tolerated; windowed and full-screen alike). No window resize (R24); `--print` unaffected. |
| R27 | **Cycle mode — slide show (directory mode):** with the window focused, `c` (or `space` when not cycling, R31 — R18 key conventions) enters **cycle mode**: starting at the currently displayed image, the display **advances** one settled image at a time toward the **newer** end of the navigation list (§5.5) every **cycle time** (R28); when the newest settled image is reached, the cycle **wraps to the oldest** settled image and continues. Only **settled** candidates are ever shown — a file still inside its settle window is never a slide (§5.5 rationale). While cycling, live following is **suspended** (R3): newly settled images do **not** interrupt the display; they join the cycle list at the newest end and are shown when the cycle reaches them — the cycle **grows** as new images settle, and files deleted from the directory drop out of the list. Each advance is a normal decode request (dual-buffered, R7); a slide whose version fails to decode (R15) is skipped by subsequent advances, never retried. The cycle position is **re-derived from an anchor on every advance** (the displayed version's entry in the list, or its virtual `(mtime, path)` position when the displayed file is not a settled candidate — §5.5 anchor rules), never stored as an index, so the list may grow and shrink underneath the cycle. Any keypress that selects a display mode **exits cycle mode first**, then applies its normal semantics: `Left`/`Right`/`Home`/`End`/`p` are two-phase as usual (R23/R25/R26) — the attempt resolves against the currently displayed image and then pins it (→ manual mode); `n` exits to **live** mode (newest, R3 resumed). Keys that do not select a display mode — `f`, `Esc`, `r`, the canvas double-click — leave cycle mode running. `c` while already in cycle mode is a no-op. If the currently shown slide ceases to be a candidate (deleted, renamed away), the canvas **holds the last decoded slide** (no image-gone state while cycling); the next advance continues from where that image was (virtual anchor). If no settled candidate exists (nothing on the list), the display shows the waiting state (R8) and cycle mode **stays active** — the first settling candidate becomes a slide at the next advance. `c` in the waiting state enters cycle mode immediately (armed): no advance occurs until the first candidate settles. An in-place update of the displayed slide reloads once settled (R4), as with pinning; the next advance anchors on the new version. In the idle state (R22) there is no directory. For a file target (R21) the cycle starts from the target file, which is a member of the navigation list (§5.1). Advances never resize the window (R24); `--print` unaffected. |
| R28 | **Cycle time:** the cycle time is set by `--cycle-time` — **integer seconds, minimum 1, default 9** (`0` or negative → usage error, exit 2). `Up`/`Down` (R18 key conventions) **increase / decrease the cycle time by 1 second** at any time — during *or* outside cycle mode — without changing the mode or the display; `Down` at the minimum (1 s) has no effect. An adjustment **rescales the current interval immediately**: the elapsed time of the in-progress slide is preserved — its deadline becomes `now + (new time − elapsed)`; if the new time is **shorter** than the elapsed time (the slide has already outlived its new allotment) the advance fires at the next tick; every following interval is the new full cycle time (worked example: 9 s with 2 s elapsed, `Down`×2 → 7 s → this slide advances after 5 s, the next image gets a full 7 s). The first advance occurs a full cycle time after `c` (the starting image is shown for one full interval), and the cycle clock is not reset by new-image arrivals or by decode failures. While cycling, the header subtitle shows the current value — the R10 subtitle plus ` · cycle {N}s` — so `Up`/`Down` adjustments are visible; the header is hidden in `--fullscreen` (R16), where the R30 overlay (`cycle: {N}s`, `cycle on: {N}s`) is the visible feedback instead. |
| R29 | **Cycle mode at startup (`--cycle`):** with the flag `--cycle`, `riview` enters **cycle mode automatically at process start** — before any display — instead of starting in live mode: the **first displayed image is the oldest settled candidate** (the last entry of the cycle list, §5.7), not the newest that R3 would show at startup; from there the cycle advances toward the newer end every cycle time and wraps from the newest to the oldest exactly as usual (R27). If no candidate is settled at startup, the waiting state (R8) is shown with cycle mode armed (as for `c` in the waiting state, R27) and the first displayed image is the **oldest** candidate of the first non-empty settled list. No live-mode window ever opens: the first display already belongs to the cycle. All other `--cycle`/cycle-mode semantics are R27/R28 (keys, rescale, wrap, failed-skip, image-gone hold). `--cycle` takes an **optional value — the initial cycle time in seconds** (the flag alone = the R28 default of 9 s; a value must be an integer ≥ 1, §4.2) and is **combinable with `--cycle-time`** — when both give a time, **`--cycle-time` takes precedence** (the dedicated interval option; the flag's value is then ignored — rev 1.7.3 fix). For a **file target** (R21) the first slide is **the target file** — the oldest-start rule does not apply, the explicit file is the start anchor (rev 1.7.4); in `--print` mode (R12) the flag is inert (no window, no cycle state). |
| R30 | **Keypress feedback (overlay):** an **effective** keypress of `c`, `p`, `n`, `Up`, `Down`, `space`, or `Ctrl+C` (R34) shows a **brief text overlay** on the canvas for **1 second**, in **windowed and `--fullscreen` (R16) modes alike**, then it disappears: `c` → `cycle on: {N}s`, `p` → `pause`, `n` → `newest live image`, `Up`/`Down` → `cycle: {N}s`, `space` → the text of the action it dispatches (R31), `Ctrl+C` → `prompt copied` (R34) (N = the current cycle time). An overlay appears **only when the keypress effects its named change** — no-op keypresses show nothing (`c` while already cycling / in the idle state; `p` in manual mode, the image-gone state, or the waiting state (R26); `n` when already in live mode (R23); `Down` at the 1 s floor (R28); `space` when its dispatch is a no-op (R31); `Ctrl+C` when nothing can be copied (R34)). The overlay appears **in both modes** (pre-release amendment, tracked as `riview` 1.7.1): in windowed mode the header (R10 subtitle, `· cycle {N}s` indicator, R28) keeps its **persistent** status — the overlay is the **transient** confirmation (the original no-doubling rationale is retired). Position: bottom center of the canvas, its bottom edge **10% up from the canvas bottom** (below the header bar in windowed mode; canvas == window in full screen), computed from the canvas container's allocated height at show time. A further feedback keypress within the 1 s **replaces the text and restarts the 1 s timer** (last wins). A full-screen toggle (`f`/`Esc`/canvas double-click) **dismisses an active overlay immediately**. The overlay is purely cosmetic: it does not affect the cycle clock or deadlines (R28), selection (R3/R5), decode (R7), or window size (R24); nothing is shown at startup (e.g. `--cycle --fullscreen` opens without one); `f`/`Esc`/`r`/`h`/`?`/`i`/double-click/`q` show no overlay (`h`/`?` have their own overlay, R32; `i` likewise, R33); `--print` mode is unaffected (no window, R12). |
| R31 | **`space` — the cycle/pause toggle (directory mode, rev 1.7.2):** `space` toggles between **cycle mode** (R27) and **pause** (R26), the action being chosen by the current mode: while **not** cycling it acts *exactly* as `c` — it starts cycle mode from the currently displayed image (all R27 semantics, including the no-op in the idle state); while **cycling** it acts *exactly* as `p` — it stops the cycle and pins the current slide (manual mode, the R26 stop-and-pin). Pressing it again reverses: from the pause it restarts the cycle at the currently displayed image (as `c`). It shows the R30 overlay of the action it dispatches (`cycle on: {N}s` / `pause`) exactly when that action is effective; a no-op dispatch shows nothing. No new mode, state, or message — `space` is an alias, and every existing `c`/`p` rule applies to it unchanged. |
| R32 | **Keyboard help overlay:** with the window focused, `h` or `?` (R18 key conventions — bare key, Shift tolerated) shows a **keyboard help overlay** on the canvas, in **all windowed states** (live, manual, cycle, waiting (R8), idle (R22), image-gone (R23)) and in **windowed and `--fullscreen` (R16) modes alike**: the list of all function keys with a short description for each (normative text in §5.9), **centered** on the canvas (both axes), the same visual family as R30 (pale-yellow text on a semi-transparent gray shade) but at **normal** font size (not 2.5× — the list must be readable at the default window size, 900×675, R24). The overlay **stays on screen until the next keypress**: that keypress **always** dismisses the overlay; if the key is a **bound function key** (the §4.4 table) it is then **executed as usual** (a no-op dispatch also dismisses — the overlay disappears either way); any other key simply dismisses it and the current image or message screen keeps showing. While the help is displayed, `h`/`?` themselves **only dismiss** (no re-show — the overlay can always be closed with `h`). The **dismissing keypress's R30 feedback shows as usual** (e.g. `n` with the help displayed → the help closes and then the `newest live image` overlay appears for 1 s) — the two overlays **never coexist** (the keypress closes the help first); `h`/`?` themselves show no R30 overlay (joining `f`/`Esc`/`r`/`q` on the no-overlay list). **Nothing is shown at startup**; `--print` (R12) unaffected (no window). **Purely cosmetic:** the help overlay does not affect the cycle clock (R28), selection (R3), decode (R7), or window size (R24) — in cycle mode the timer **keeps ticking under the overlay** and slides may change while it is displayed; a later keypress acts on the *current* slide. **Exclusivity with the prompt information overlay (R33, rev 1.8):** showing the help dismisses an active info overlay, and `i` (a bound key — the dismiss-then-dispatch rule above) dismisses the help and then shows the info overlay — the two **never coexist**, and **no state is remembered** (dismissing the help later does not re-show the info overlay). *(Rev 1.7, pre-release amendment 4 — riview 1.7.5.)* |
| R33 | **Prompt information overlay:** with the window focused, `i` (R18 key conventions — bare key, Shift tolerated) **toggles** a **prompt information overlay** on the canvas, in **all windowed states** (live, manual, cycle, waiting (R8), idle (R22), image-gone (R23)) and in **windowed and `--fullscreen` (R16) modes alike**: the **generation prompt** extracted from the **currently displayed** image file (sources and the 8 MiB read bound in §5.10) — or **`no information`** when no prompt is found, which includes every state with no displayed image. Display: word-wrapped at **80 % of the rendered image width** — the width the image actually occupies on the canvas under the current R24 layout — **capped at 80 % of the canvas width** (an image wider than the window: unchanged) and **floored at 50 % of the canvas width** (a letterboxed image narrower than 62.5 % of the canvas keeps a usable column) (1.8.2 patch), pale-yellow text at **1.5×** the normal font size on a semi-transparent gray shade (the R30 visual family), in the bottom-center column with its bottom edge **22 % up from the canvas bottom** — above the R30 feedback zone (bottom edge 10 %), so a 1 s R30 feedback can appear below it without overlap and expire as usual while the overlay stays; content taller than **50 % of the canvas height** is elided, the last visible line ending in `…`. **Persistence:** the overlay has **no timer** — it stays on screen until `i` is pressed again; every **display change** (movement keys, `p`, `n`, cycle advances (R27), live arrivals (R1/R3), in-place updates (R4) — any new displayed image version, §5.4) re-extracts the prompt from the newly displayed file and **updates the text in place** (to another prompt, or to `no information`). **Exclusivity with the help overlay (R32):** the two **never coexist**, and **no state is remembered** — `i` with the help displayed dismisses the help (the R32 dismiss-then-dispatch rule) and then shows the info overlay; `h`/`?` with the info overlay displayed dismiss the info overlay and then show the help; dismissing the help later does not re-show the info overlay (`i` again does). **No R30 feedback for `i`** (the overlay is its own feedback — `i` joins `f`/`Esc`/`r`/`h`/`?`/`q` on the no-overlay list); a concurrent R30 feedback (e.g. `c` while the overlay is displayed) appears **below** it as usual and expires after 1 s. `f`/`Esc`/canvas double-click **do not dismiss** the overlay — a full-screen toggle keeps it, **repositioned** from the new canvas dimensions; `r` re-fits and **repositions** the overlay while visible (a re-fit can change the rendered image width — 1.8.2); a **windowed-mode window resize (drag) reflows the overlay live** — while visible, a **50 ms size poll** (a GLib timeout; GTK4 has no resize signal — the R30 constraint) reads the canvas's allocated size and, when it changes, re-applies the wrap, elision, and bottom margin from the **cached extracted text** (no re-extraction — the text did not change) — the reflow follows the drag within one poll period; the poll is installed on show and removed on hide/shutdown (zero cost when hidden) (1.8.3). **Purely cosmetic:** the overlay does not affect the cycle clock or deadlines (R28), selection (R3/R5), decode (R7), or window size (R24) — in cycle mode the timer **keeps ticking under the overlay** and each advance updates its text. Nothing is shown at startup; `--print` (R12) unaffected (no window). *(Rev 1.8 — `riview` 1.8.0.)* |
| R34 | **Prompt copy (hidden feature, rev 1.8 amendment 5):** with the window focused, `Ctrl+C` (and `Ctrl+Shift+C` — Shift tolerated, R18 convention) **copies the generation prompt of the currently displayed image to the system clipboard** — the **same text the prompt information overlay (R33) displays**: the §5.10/§12.11 extraction (PNG text chunks / JPEG–WebP EXIF `UserComment`, 8 MiB read bound) — in **all windowed states** (live, manual, cycle, waiting (R8), idle (R22), image-gone (R23)) and in **windowed and `--fullscreen` (R16) modes alike**. **Effective-only (R30):** a copy actually performed shows the R30 overlay `prompt copied` for 1 s; when there is **nothing to copy** — no displayed image (waiting / idle / image-gone) or the displayed file carries no prompt — the keypress is a **no-op: no clipboard write and no overlay**. **Exclusivity:** with the keyboard help (R32) displayed, `Ctrl+C` **dismisses it first** (the R32 dismiss-then-dispatch rule — it is a bound key) and, when a copy is performed, the `prompt copied` overlay then appears (R30 and R32 never coexist); with the prompt information overlay (R33) displayed it **leaves it in place** (no toggle, no dismissal) and the copied text is the same as the text it shows. **Hidden feature:** it is **not** in the §5.9 help list (the 13 lines are unchanged) — documented here, in the README, and in §11 only. **Purely cosmetic beyond the clipboard write:** no effect on the cycle clock or deadlines (R28), selection (R3/R5), decode (R7), or window size (R24) — in cycle mode the timer keeps ticking under it and the copy takes the *current* slide's prompt. `--print` (R12) unaffected (no window); `Ctrl+C` **in the terminal** (SIGINT) and `SIGTERM` still quit cleanly (R18). *(Rev 1.8, pre-release amendment 5 — `riview` 1.8.1.)* |

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
  time) — unit-testable without a display (see `tests/test_riview.py`, §12.2). The
  window-fit geometry (§5.6) is likewise a pure function of (fit mode, image
  dimensions, monitor box, header height, scale factor), and the cycle target
  (§5.7) a pure function of (settled list, anchor, failed versions).

---

## 4. Command-line interface

```
riview [TARGET] [options]
```

`TARGET` is a directory (directory mode) or an image file (file target, R21);
it may be a `file://` URI (the desktop entry's `%U`, R20).

### 4.1 Arguments

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `TARGET` (positional) | path | none (see R22) | Directory to watch, or an image file (file target: the containing directory is watched and the view starts in manual mode pinned to the file, R21). No target: CWD when launched from a terminal, idle state in a GUI context (R22). |
| `--extensions` | comma list | `png,jpg,jpeg,webp,gif,tiff,tif,bmp` | Candidate extensions, lowercase, without dots. Case-insensitive on input. The empty list is a usage error. (`avif` and `svg` loaders exist on the target system and may be added here; they are not in the default set by design decision D4.) Filters selection *inside directories*; the target file of a file target stays a candidate even when its extension is not in the set (R21, §5.1). |
| `--stable-ms` | int ≥ 0 | `2000` | Settle window in milliseconds (§5.3). `0` disables the window (file displayable as soon as first observed — for testing). |
| `--cycle-time` | int seconds ≥ 1 | `9` | Cycle time for cycle mode (R27/R28, §5.7): seconds between cycle advances. Minimum 1 (`0` or negative → exit 2). `Up`/`Down` adjust the value at runtime (±1 s, floor 1 s), during or outside cycle mode — while cycling an adjustment rescales the current interval (R28). Combinable with `--cycle`; when both give a time, `--cycle-time` takes precedence (rev 1.7.3 fix). |
| `--cycle [SECONDS]` | optional int seconds ≥ 1 (flag = default 9) | off | Enter cycle mode automatically at startup; the first slide is the **oldest** settled image (R29, §5.7). The optional value sets the **initial cycle time** (R28); **combinable with `--cycle-time`** — when both give a time, `--cycle-time` takes precedence (rev 1.7.3 fix). For a file target (R21) the first slide is the target file (the oldest-start rule does not apply, rev 1.7.4); inert in `--print` mode (R12). |
| `--poll` | float seconds, > 0 | off | Force polling mode with the given interval (R2). Also serves as the fallback interval when inotify is unavailable and this flag was given. |
| `--max-dim` | int px ≥ 0 | `0` | Absolute cap on the **longer side** of the decoded image, in pixels. `0` (default) means no cap beyond the decode-target scaling (§7.1). |
| `--fit` (synonym `--fit-window`) | `ratio` / `exact` / `off` | `ratio` | Window fit mode (R24, §5.6): how the window is sized to the first displayed image — `ratio`: the image's aspect ratio within the 80 % budget box (itself capped at the D15 COSMIC box, 1600×1200 logical px, until the upstream COSMIC clamping bug is fixed); `exact`: 1:1 logical pixels, capped at the screen minus the header; `off`: the D11 pre-image size only. Inert in `--print`/`--fullscreen`. |
| `--fullscreen` | flag | off | Start full-screen, image only: no header bar, no waiting-state text (R16) — the 1 s keypress-feedback overlay may still appear (R30), and the prompt information overlay may be shown (R33). Usage error (exit 2) when no target resolves (R22). |
| `--print` | flag | off | Headless query mode (R12): print the absolute path of the image `riview` would display (`none` if a directory has no candidates) and exit. No GUI, no settle wait. |
| `--install-desktop` | flag | off | Install the per-user `.desktop` entry + icon (R20), then exit 0. Headless. |
| `--uninstall-desktop` | flag | off | Remove the per-user `.desktop` entry + icon (R20), then exit 0. Headless. |
| `--version` | flag | off | Print version and exit. |
| `--help` | flag | off | Usage help. |

### 4.2 Validation (before any window or watcher is created)

- `--stable-ms` must be an integer ≥ 0; `--poll` a number > 0; `--max-dim` an
  integer ≥ 0; `--cycle-time` an integer ≥ 1 (R28); `--cycle` (with a value)
  an integer ≥ 1 (either → exit 2); when **both** `--cycle [SECONDS]` and
  `--cycle-time` give a time, `--cycle-time` takes precedence — no error (rev 1.7.3
  fix); `--fit` one of
  `ratio`/`exact`/`off` (any other value → exit 2).
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
- Manual navigation (R23) does not affect `--print`: there is no viewer state in a separate
  process — it always answers the newest (point-in-time).

### 4.4 Keyboard shortcuts (R18)

With the window focused, in windowed and full-screen mode alike (bare keys; Shift is
tolerated, so `Q`/`F` work too; any other modifier leaves the key unhandled; a
file target (R21) starts in manual mode pinned to the target file — this full
table applies from there):

In **cycle mode** (R27), every mode-selecting key — `Left`/`Right`/`Home`/`End`/`p`/`n`/`space` —
**exits cycle mode first**, then applies the semantics below; `f`/`Esc`/`r`/
double-click do not affect it; `Up`/`Down` adjust the cycle time (R28).

| Key | Action |
|-----|--------|
| `q` | Quit (exit 0). |
| `h` or `?` | **R32:** show the keyboard help overlay (§5.9) — all windowed states, windowed and full-screen alike. Stays until the next keypress; that keypress always dismisses it and, if it is a bound function key, executes it as usual (any other key simply dismisses). `h`/`?` only dismiss (no re-show). Dismisses an active prompt information overlay (R33 — the two never coexist). |
| `i` | **R33:** toggle the **prompt information overlay** (§5.10) — the generation prompt of the currently displayed image, or `no information`, all windowed states, windowed and full-screen alike. **Stays until `i` again**; every display change updates its text. No R30 feedback (the overlay is its feedback). Dismisses an active keyboard help overlay (R32 — the two never coexist). |
| `Ctrl+C` (window focused) | **R34 (hidden — not in the §5.9 help):** copy the **currently displayed image's prompt** — the same text the R33 overlay shows — to the **system clipboard** (Shift tolerated: `Ctrl+Shift+C` alike). R30 overlay `prompt copied` when a copy is actually performed; nothing to copy (no prompt / no displayed image) → no-op, no overlay, clipboard unchanged. Dismisses an active keyboard help overlay (R32) first. |
| `Ctrl+C` (terminal) / `SIGTERM` | Quit cleanly (exit 0, no traceback — the signal path; §11 case 22). |
| `f` | Toggle full screen ↔ windowed, both directions. |
| `Esc` | Leave full screen. No-op in windowed mode. |
| `Left` | Step one image **older**, then **pin the result** (R23, §5.5). In live mode this exits live mode — a step that can't resolve (single image, or nothing older) still pins the display. Works from the image-gone state: it steps from where the image was (the pin remembers its mtime). |
| `Right` | Step one image **newer**, then pin (R23, §5.5). In live mode the step never changes the display (you are at the newest end) — the key **pins the current display**: the "freeze the stream" action. As `Left` from the image-gone state and mid-rewrite. |
| `Home` | Jump to the **oldest** image, then pin the result (R25, §5.5) — absolute, no position needed. Exits live mode even when the oldest is already displayed (pins in place). Recovers the image-gone state on the oldest (stays manual). |
| `End` | Jump to the **newest** image, then pin (R25, §5.5) — unlike `n`, does **not** resume live following. In live mode it pins the current display (freeze). Recovers the image-gone state on the newest. |
| `p` | **Pause:** pin whatever image is displayed, no movement attempt (R26, §5.5) — the pure freeze; the only key that pins without moving. No observable effect in manual mode, the image-gone state, or the waiting state. |
| `n` | Return to the **newest** image and resume live following (R23, §5.5) — including out of the image-gone state. No-op when already in live mode. The **only** key that leaves manual mode. Exits cycle mode (R27). |
| `c` | **Start cycle mode** — the slide show (R27, §5.7): from the currently displayed image, advance to the next newer settled image every cycle time, wrapping from the newest to the oldest. No-op in the idle state and while already cycling. |
| `space` | **Toggle cycle ↔ pause** (R31, §5.7): while not cycling it acts as `c` (start the slide show — overlay `cycle on: {N}s`); while cycling it acts as `p` (stop the cycle and pin the current slide — overlay `pause`). No-op in the idle state (its dispatch is a no-op — no overlay). |
| `Up` | **Increase the cycle time by 1 s** (R28, §5.7) — during or outside cycle mode; while cycling it **rescales the current interval** (elapsed time preserved, R28); no other effect. |
| `Down` | **Decrease the cycle time by 1 s** (R28), minimum 1 s (no effect at the minimum); while cycling it rescales the current interval (R28). |
| `r` | Re-fit the window to the **currently displayed** image per the `--fit` mode (R24, §5.6). No-op in `off` mode, in the waiting/idle/image-gone states, and in `--fullscreen`. |

The **effective** keypresses `c`/`p`/`n`/`Up`/`Down`/`space` show a brief (1 s)
on-canvas overlay message — `cycle on: {N}s` / `pause` / `newest live image` /
`cycle: {N}s` — in windowed and full-screen modes alike (in full screen the
header is hidden, R16; in windowed mode the header keeps its persistent
status alongside the transient overlay, R30, §5.8).

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
  mode, image file → file target, R21). If several URIs are ever passed, the first
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

For a **file target** (R21) the scan is over the *containing* directory and covers
**all** of its candidate entries, with the target file included as a candidate **even
when its extension is not in the `--extensions` set** (the target file's own extension
bypasses the filter; its extension must be in the *default* set — §4.2).

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
- **Manual navigation (R23, §5.5):** the newer-only rule governs *live* following only.
  For a display pinned by the user it is suspended — a newer file settling does not
  displace the pinned image until `n` (or until the pinned file ceases to be a candidate).

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

### 5.5 Manual navigation (R23, R25, R26)

The **navigation list** is the target directory's **settled** candidates (§5.3) in
navigation order (the §4.3 order: greatest `st_mtime_ns`, ties → byte-wise greatest
name), index 0 = newest. **Settled-only, by design:** an image still inside its settle
window can never be landed on, so navigation can never put a half-written file on the
display (design goal 2, §1). In practice this is rarely felt: files still being written
are the *newest* ones, i.e. the end you walk *toward*, not from.

**Two-phase keys (rev 1.5):** every movement keypress (*`Left`*, *`Right`*,
*`Home`*, *`End`*) **attempts a movement** over the navigation list — the display
loads the target only when the attempt resolves to a candidate **different** from
the current display — and then **pins whatever is displayed**. A failed attempt
(nothing on the relevant side of the anchor, or no settled candidates) leaves the
display unchanged, and the pin phase still applies. Consequences:

- **Live mode:** every movement key **exits live mode**. `Right`/`End` can never
  change the display there (the live display is the newest) — they are the
  **"freeze the stream"** action; `Left`/`Home` step/jump and pin the landed
  image (with a single settled image they pin the display in place).
- **Manual mode:** the pin phase is unobservable (the display already is the
  pin); the keys step or jump as below.
- **`p` (pause, R26):** pins whatever is displayed with **no movement attempt** —
  the only key that pins without moving. It matters in the rewrite-in-flight
  window, where `Home`/`End` jump to a settled end.
- **`n`:** the **only** key that leaves manual mode — return to **live mode**: the
  display is the newest settled candidate (or the waiting state if there is none,
  R8) and R1/R3 following resumes; it also exits the image-gone state. No-op when
  already in live mode.

**The anchor.** `Left`/`Right` step from the position where the *displayed
version* sorts in the current navigation list by `(mtime, path)` (§4.3 order) —
`Right` to the first candidate strictly **newer** than the anchor, `Left` to the
first strictly **older**, none → the attempt fails. When the displayed file is a
settled candidate the anchor is its own entry (plain index stepping). When it is
not — the **image-gone** state (the pin holds the file's last mtime) or a
**rewrite in flight** (the anchor is the last displayed version's mtime) — the
anchor is the **virtual position** of that last known `(mtime, path)`, so
`Left`/`Right` continue scanning from where the image was. `Home`/`End` are
absolute (list endpoints) and need no anchor.

- **Pinning:** every keypress ends in manual mode with the display pinned to the
  shown file. While pinned, rescan selection bypasses §5.2 (no automatic
  switching): newer files settling in the background leave the display untouched;
  an in-place update of the pinned file reloads once settled (R4/R6) with the
  previous version kept on the canvas until the decode succeeds (dual buffer,
  R7) — pinning never blocks an in-place update of the pinned file itself; a
  decode failure of the pinned version is handled as R15.
- **Image-gone state:** the pinned file ceases to be a *candidate* (deleted,
  renamed away, extension changed) → the canvas goes **black** with the white,
  wrapped, centered message *"Current image gone — 'n' jumps to the newest, ←/→
  keep scanning."* (hidden in `--fullscreen` like all waiting texts, R16; header
  as in the waiting state). The **pin persists with the file's last mtime** (the
  anchor, above): `Left`/`Right` step to the neighbors on each side — scanning
  continues after deleting the displayed file. On a later rescan the file
  reappearing (and settling) restores the display — the same delete/recreate
  semantics as the manual pin (R23), without a keypress. `n` exits the state: jump to the newest
  (or the waiting state if none, R8) and resume live mode.
- **Rewrite in flight:** while the displayed file has a *new, still-unsettled*
  version the display holds the previous version; `Left`/`Right` anchor on that
  version's `(mtime, path)` (they may step away), `p` pins the display (stays
  put), `Home`/`End` jump to a settled end; once the rewrite settles, the
  pinned/live display reloads it (R4/R7). `n` still works.
- **Moving list:** the anchor is re-derived from the displayed path (and its
  last known mtime) on each keypress, so files settling or leaving in the
  background never shift the display by a step — the display changes only
  through the user's keypresses, the image-gone event (pin ceases to be a
  candidate), and its restoration (pin reappears and settles).
- **No observable effect:** the idle state (R22 — no directory) and the waiting
  state (nothing displayed to pin). A file target (R21) is ordinary directory
  mode from startup (the view starts pinned to the target file), so no movement
  key is inert there.
- Each successful move is a **normal decode request** through the existing
  pipeline (§12.5): dual-buffered, superseded by the next move if keys are
  pressed quickly.
- **Window:** movement and pinning never resize the window (R24) — the window is
  fit only on the first displayed load and by `r`.

### 5.6 Window fit (R24)

The window opens at the **early-fit size** — or the **pre-image default**
when no early fit applies (D11: 80 % of the primary monitor, min 900×675
logical pixels) — so the waiting state has a sensible size and the window
appears immediately (the window is not placed at construction, so only the
primary monitor is addressable before the first frame). **Early fit
(startup):** if the fit mode is not `off` and a candidate is *already
settled* at construction (the common case — a directory the pipeline has
filled), the window is sized to that file's dimensions *before
presentation* — read from the file header alone, no decode (§12.3
`probe_dimensions`) — so the window simply **opens** at the fit size. The
header height is the 47 px fallback (the header is not allocated yet). On
the **first successful decode that reaches the display**, if the fit mode is
`ratio` or `exact`, the **fit pass** runs once — the safety net for files
still settling at construction and for the 47 px header estimate — sizing
the *canvas* — the window minus the header bar — to the image's geometry:

- **`ratio` (default):** canvas = the largest rectangle of the image's aspect
  ratio that fits the 80 % budget box — itself capped at the fixed **D15
  COSMIC box, 1600×1200 logical pixels (width × height)** (`COSMIC_CAP_W`/`COSMIC_CAP_H`;
  the upstream COSMIC clamping bug reconfigures larger windows — revisit
  after a COSMIC update fixes it), with the header height subtracted from
  the available height. The first displayed image has **no letterbox**.
  On the spec owner's display (3339×1878 @ 2×, 80 % box 2671×1502) a
  1024×1024 image now opens at 1153×1200 (the header-corrected cap
  height, 1153, binds).
- **`exact`:** canvas = the image's dimensions in logical pixels (physical
  pixels ÷ the window's scale factor) — 1:1 with the screen at scale factor 1.
  If the image is larger than the screen, the canvas is instead the largest
  ratio-preserving rectangle within the **full monitor minus the header**: the
  window then occupies the whole screen but keeps its header bar
  (deliberately *not* `--fullscreen`, which also hides the header).
- A fit result below **320 logical pixels** on either side is recomputed as
  the largest ratio-preserving rectangle within a 320×320 box (degenerate-case
  guard; on real displays the budgets bind first, and the floor may exceed the
  budget only on pathologically small monitors).
- **Which monitor:** the fit budget and the `exact` cap are measured on the
  **monitor the window is currently on**, queried at fit time; the primary
  monitor (or the first monitor) when undetermined — e.g. before the window
  manager has placed the window. The scale factor used for `exact` is the
  window's own (`get_scale_factor()`), so mixed-DPI setups are handled. Dragging
  the window to another screen and pressing `r` therefore re-fits to *that*
  screen.

After the fit pass the window is **stable**: no new load, in-place update,
manual navigation (R23), or pinning resizes it — an image whose ratio differs
from the canvas is letterboxed (R9/R17) as usual. The fit — early fit, fit
pass, and `r` alike — is measured on the image's **original** pixel
dimensions (the file header, `probe_dimensions` — §12.3); where the probe
cannot resolve (e.g. TIFF, unrecognized), the displayed (scaled) dimensions
are used. `r` re-runs the same
computation against the *currently displayed* image, on demand (directory mode
and file targets (R21) alike). The fit pass is skipped — and `r` is a no-op — in the
waiting/idle/image-gone states (no image to fit to), in `--fullscreen`, and in
`off` mode. `--print` is unaffected.

**Resize mechanics / Wayland caveat (§13.2):** GTK 4.14 deprecated the
client-side window resize (`gtk_window_resize`). On this binding the post-map
resize is therefore a *size request* — a minimum — so the fit pass and `r`
**grow** the window to the fit size but cannot shrink it below the size the
user or window manager already set; shrinking is compositor-mediated on
Wayland. The early fit exists precisely because it sizes the window *before*
presentation, where both grow and shrink work.

**Sharpness:** the fit pass never makes the canvas larger than the first
decode's target box (2× oversample × the pre-image window, §7.1), so the
existing texture is always at least 1.6× the canvas: the fit resizes the
*window*, never the decode (non-goal: adaptive re-decode, §10).

### 5.7 Cycle mode (R27, R28)

The **cycle list** is the navigation list (§5.5) — the settled candidates in
`order_cands` order (newest first). Cycle direction is *toward the newer end*,
i.e. decreasing index; an advance moves to the adjacent newer settled image,
and from index 0 (newest) it **wraps** to the last entry (oldest).

**The toggle (R31, rev 1.7.2).** `space` toggles between cycle and pause:
while not cycling it enters cycle mode exactly as `c` (from the currently
displayed image); while cycling it stops the cycle and pins the current
slide exactly as `p` (manual mode). Pressing it again reverses — the cycle
restarts at the currently displayed image. No new state: `space` is an alias
for `c` or `p` chosen by the current mode, and it shows the R30 overlay of
the dispatched action.

**The anchor.** On every advance the target is computed from the **current**
list and the **current** displayed version — the same re-derivation as
`Right` in manual mode (§5.5): the anchor is the displayed version's own
entry when it is a settled candidate, else its virtual `(mtime, path)`
position (a rewrite in flight, or a deleted slide). Because position is
never stored, the list may grow or shrink between advances without desyncing
the cycle:

- a newly settled image joins at the newest end (index 0) and is shown when
  the cycle reaches the newest end and continues into it — i.e. on the next
  loop around (it does **not** interrupt the current slide); files removed
  from the directory simply drop out of the list;
- a deleted currently-shown slide: the canvas holds the last decoded
  slide (no image-gone state while cycling); the next advance uses the
  virtual anchor and moves to the first settled image newer than where the
  image was, or wraps to the oldest if there is none.

**The advance (tick).** Every cycle time, on the main thread:

- list empty → the display is the waiting state (R8); cycle mode stays
  active; the timer keeps running;
- no display (snapshot `None` — e.g. resuming after the list was empty, or
  an armed `c` pressed in the waiting state) → the target is the **newest**
  settled candidate (index 0) — or the **oldest** (last entry) on the **first
  display when started with `--cycle`** (R29);
- otherwise → the target is the first settled candidate **strictly newer**
  than the anchor (scanning the list from the newest end, so the adjacent
  newer image), **skipping candidates whose version is in the R15
  failed-version set** (a corrupt file is never retried — the advance moves
  past it); if no such candidate exists (the anchor is at the newest end, or
  only failed versions lie between it and the newest), the target is the
  **oldest** non-failed settled candidate (the wrap).

The target's version differing from the displayed version → one ordinary
decode request (§5.4/§12.5): dual-buffered (R7), a failed decode keeps the
previous slide and records the version (R15). Target equal to the displayed
version → no request (e.g. the single-settled-image case: the cycle holds on
the same image).

**The clock.** The first advance is a full cycle time after entering cycle
mode; each advance schedules the next at `now + cycle time` (a fixed-period
deadline on the monotonic clock; no catch-up after stalls). Arrivals of new
images and decode failures do not reset or shift the clock. An `Up`/`Down`
adjustment (R28) **rescales the current interval immediately**: the deadline
of the in-progress slide becomes `now + (new time − elapsed)` (elapsed = time
since the last advance or the entry into cycle mode), so a shorter new time
pulls the advance forward — if the new time is already below the elapsed
time the advance fires at the next tick — and a longer new time pushes it
back; every following interval is the new full cycle time. The indicator
shows the current value.

**Display-holding between advances.** While cycling, rescan selection holds
the display like a pin on the displayed path (§12.5): no live switching (R3
suspended), an in-place update of the displayed slide reloads once settled
(R4, dual-buffered), a decode failure of the slide is handled as R15. This is
why a new image never jumps the display mid-slide.

**Entering / leaving.**

- **Enter (`c`):** from live or manual mode — the currently displayed image
  is the first slide; any active pin is dropped (`pinned_path = None`; the
cycle is not a pin — it advances). From the waiting state: enters
  armed; the first settling candidate becomes the first slide at the next
  advance. No-op in the idle state (no directory) and while already cycling.
  For a file target (R21) the cycle starts from the target file.
- **Start (`--cycle`, R29):** from process start, before any display, cycle
  mode is armed — `cycle_mode = True`, `start_oldest = True`,
  `pinned_path = None`. At the first display the target is the **oldest**
  settled candidate (last entry of the list) instead of the newest; `start_oldest`
  is cleared and every subsequent tick is exactly as above (first advance a
  full cycle time after the display). For a **file target** (R21) the first
  slide is the **target file** — the oldest-start rule does not apply (the
  explicit file is the start anchor, rev 1.7.4); `--print` ignores it.
- **Leave:** `Left`/`Right`/`Home`/`End`/`p` — the cycle stops, then the key's
  two-phase semantics apply against the currently displayed slide (attempt,
  then pin → manual mode; the `Left`/`Right` anchor is the slide's own entry
  since it is a settled candidate). `n` — the cycle stops and live mode
  resumes (newest, R3). `q`/`Ctrl+C`/`SIGTERM` quit (R18). Display keys —
  `f`, `Esc`, `r`, canvas double-click — do not leave cycle mode.

**Window:** advances never resize the window (R24 — the fit pass, early fit,
and `r` are unaffected); `--print` is unaffected (it has no cycle state).

**Headless-testable core:** the advance target is a pure function
`cycle_target(ordered, anchor_key, failed_versions) -> path|None` (§12.3):
`None` when the list is empty or every candidate is a failed version.

### 5.8 Keypress feedback overlay (R30)

The feedback keypresses show a brief message on the canvas, visible for
**1 second**, in **windowed and full-screen modes alike**: pale-yellow text at
about 2.5× the normal font size, centered horizontally with its bottom edge
about **10% up from the bottom of the canvas** (below the header bar in
windowed mode; in full screen the canvas is the whole window), on a
**semi-transparent gray shade**
that locally tones down the image brightness behind and around the text so
the message stays readable over any image (appearance per §12.7):

| Effective keypress | Overlay text |
|--------------------|--------------|
| `c` (cycle mode starts) | `cycle on: {N}s` |
| `p` (the pin engages) | `pause` |
| `n` (back to live following on the newest) | `newest live image` |
| `Up` / `Down` (the cycle time changes) | `cycle: {N}s` |
| `Ctrl+C` (R34 — a copy actually performed) | `prompt copied` |

("{N}" is the current cycle time in seconds.) `space` (R31) shows the text
of the action it dispatches — `cycle on: {N}s` (as `c`) or `pause` (as `p`);
a no-op dispatch shows nothing. `Ctrl+C` (R34) shows `prompt copied` when a
copy is actually performed; a no-op copy (nothing to copy — R34) shows
nothing.

- **Effective** = the keypress effects the named change; the no-op rules of
  §4.4/§5.5/§5.7 decide — `c` while already cycling, in the idle state;
  `p` in manual mode, the image-gone state, or the waiting
  state; `n` when already in live mode; `Down` at the 1 s floor; `Ctrl+C`
  with nothing to copy (R34) — show
  **nothing** (a feedback message for a no-op would be false feedback).
- **Both modes (pre-release amendment; `riview` 1.7.1):** in windowed mode
  the header (R10 subtitle, the `· cycle {N}s` indicator of R28) keeps its
  **persistent** status — the overlay is the **transient** confirmation, shown
  in windowed and full-screen modes alike (the original no-doubling rationale
  is retired by the spec owner).
- **Timer:** one-shot, exactly 1 s (a named constant, main thread). A further
  feedback keypress within the 1 s replaces the text and restarts the timer
  (last wins); the previous timer is cancelled.
- **Mode switch:** `f`/`Esc`/double-click dismiss an active overlay
  immediately — the feedback channel switches with the mode.
- **Cosmetic invariant:** the overlay does not touch the cycle clock or
  deadlines (R28 — an overlay neither delays nor advances a slide), selection
  (R3), the decode pipeline (R7), or the window size (R24); nothing is shown
  at startup (the overlay is keypress feedback, not a state indicator —
  `--cycle --fullscreen` opens without one); `f`/`Esc`/`r`/`i`/double-click/
  `q` show no overlay (`i` has its own overlay, R33). `--print` mode has no
  window and is unaffected (R12).
- Headless-testable: which text (or none) a keypress shows is a pure
  function of the keypress and the pre-press state (case 8k); the on-screen
  surface (show, 1 s expiry, replace, dismiss-on-toggle) is manual cases 37
  (full screen) and 38 (windowed).

---

### 5.9 Keyboard help overlay (R32; rev 1.7 amendment 4)

- **Trigger:** `h` or `?` (R18 conventions: bare key, Shift tolerated — `?` already requires Shift), window focused, in **every** windowed state (live / manual / cycle / waiting / idle (R22) / image-gone (R23)), windowed and `--fullscreen` alike.
- **Display:** the list below, **centered** on the canvas (both axes), pale-yellow text on a semi-transparent gray shade (the R30 visual family), at **normal** font size (≈1×, not R30's 2.5×) — readable at the default window size (900×675, R24). Column alignment and padding are presentation details; the **strings** are normative.
- **Persistence & dismissal:** the overlay stays on screen until the **next keypress**. That keypress **always** dismisses it; if the key is a bound function key (§4.4) it is then **executed as usual** (a no-op dispatch also dismisses); any other key simply dismisses it and the current image or message screen keeps showing. While the help is displayed, `h`/`?` only dismiss (no re-show). Showing the help immediately hides an active R30 feedback overlay (the two never coexist); the R30 feedback of the **dismissing** keypress is shown as usual after the dismissal (the normal dispatch path). The same exclusivity applies to the prompt information overlay (R33): showing the help dismisses an active info overlay, and `i` (a bound key) dismisses the help and then shows the info overlay — the two **never coexist**, and **no state is remembered** (dismissing the help later does not re-show the info overlay; `i` again re-shows it).
- **Cosmetic invariant:** no effect on the R28 clock/deadline, R3 selection, R7 decode, or R24 sizing — in cycle mode the timer ticks under the overlay, slides may change while it is displayed, and a later keypress acts on the *current* slide. Nothing is shown at startup; `--print` unaffected.

**Help text (normative — shown with the `Keys` header line):**

```
Keys
  Left / Right     display older / newer image
  Home / End       display oldest / newest image
  n                display newest image and follow live
  c                cycle (slide show)
  p                pause cycling
  space            toggle cycle / pause
  Up / Down        adjust cycle time ±1s (min 1s)
  r                re-fit window to image
  f / Esc          toggle full screen
  h / ?            show this help
  i                show prompt information
  q                quit
```

### 5.10 Prompt information overlay (R33; rev 1.8)

- **Trigger:** `i` (R18 conventions: bare key, Shift tolerated), window
  focused, in **every** windowed state (live / manual / cycle / waiting (R8) /
  idle (R22) / image-gone (R23)), windowed and `--fullscreen` (R16) alike.
  `i` **toggles**: it shows the overlay when hidden and hides it when shown.
  It is always effective (show or hide) and shows **no R30 feedback** — the
  overlay is its own feedback.
- **Content:** the **generation prompt** of the **currently displayed**
  image file, extracted from the file's embedded metadata. **Sources (initial
  set — revisitable as generation tools evolve):**

  | Format | Where | The prompt is |
  |--------|-------|---------------|
  | PNG | `tEXt` / `zTXt` / `iTXt` chunks, key `parameters`, `prompt`, `Prompt`, or `Comment` (first match wins) | the text **before the first line that begins** (after leading whitespace) with `Steps:` / `CFG scale:` / `Sampler:` / `Seed:` / `Size:` — the stable-diffusion.cpp metadata convention (that line and everything after it is generator metadata, not displayed); with no such line, the whole value |
  | JPEG / WebP | EXIF `UserComment` (CIPA ASCII or Unicode) | the comment text |

  The read is **bounded to the first 8 MiB** of the file (embedded metadata
  sits at the file head; the bound keeps large files from stalling the main
  thread). A prompt not found within the bound counts as **not found**.
- **`no information`:** shown instead of a prompt whenever none is found —
  the displayed file carries no embedded prompt, the file cannot be read, or
  **no image is displayed at all** (waiting (R8), idle (R22), image-gone
  (R23)).
- **Display:** word-wrapped at **80 % of the rendered on-canvas image width** — the width the image actually occupies under the current R24 layout (the letterbox extent), **not the file's natural size** — **capped at 80 % of the canvas width** (an image wider than the window, or oversized in `off` mode, reduces to exactly the pre-patch rule) and **floored at 50 % of the canvas width** (a letterboxed image narrower than **62.5 % of the canvas width** keeps a usable column instead of one that hugs it; spec owner, 1.8.2). The wrap width is `min(0.8·canvas_w, max(0.8·image_w, 0.5·canvas_w))` — in the no-letterbox case (window fitted to the image) and whenever the rendered image is at least 62.5 % of the canvas width, the column hugs the image at 80 % of its rendered width. Pale-yellow text at **1.5×** the normal font size on
  the R30 gray shade (`#ffffb5` on `rgba(70,70,70,.65)`), in the
  **bottom-center column** with its bottom edge **22 % up from the canvas
  bottom** — above the R30 feedback zone (bottom edge 10 %), so a 1 s R30
  feedback can appear below the info overlay without overlap and expire as
  usual while the info overlay stays. The prompt's own line breaks are
  preserved. Content taller than **50 % of the canvas height** is **elided**:
  the text is truncated to the lines that fit, the last visible line ending
  in `…`.
- **Persistence & updates:** the overlay has **no timer** — it stays on
  screen until `i` is pressed again. Every **display change** — a movement
  key, `p`, `n`, a cycle advance (R27), a live arrival (R1/R3), an in-place
  update (R4): any new displayed image version (§5.4) — **re-extracts** the
  prompt from the newly displayed file and **updates the text in place**
  (to another prompt, or to `no information`). Position, margins, and wrap
  are computed at **show time**, at each **full-screen toggle** (new canvas
  dimensions), at each **display change** (the rendered image width can
  change between slides — 1.8.2), and at each **`r` re-fit while visible**
  (1.8.2), and **live during a windowed-mode window resize** (1.8.3 — GTK4
  has no resize signal, the R30 constraint, so the observation is a
  **50 ms GLib timeout** — the zero-argument timeout convention proven
  throughout this program; the frame-clock tick was the original
  mechanism, but this PyGObject invokes tick callbacks with a
  non-standard argument count, a TypeError on the first frame (§13.2):
  installed while the overlay is visible, removed on hide/shutdown via
  `GLib.source_remove`, a cheap size comparison each poll and the Pango
  re-wrap/re-elide only when the size actually changes — the reflow
  follows the drag within one poll period (imperceptible); the
  extraction is **not** re-run on a resize — the reflow uses the cached
  extracted text, kept unelided so a grow de-elides).
- **Exclusivity with the help overlay (R32):** the two **never coexist**, and
  **no state is remembered**: `i` with the help displayed dismisses the help
  (the R32 dismiss-then-dispatch rule — `i` is a bound key) and then shows
  the info overlay; `h`/`?` with the info overlay displayed dismiss the info
  overlay and then show the help; dismissing the help later does **not**
  re-show the info overlay (`i` again does).
- **Cosmetic invariant:** no effect on the cycle clock or deadlines (R28),
  selection (R3/R5), decode (R7), or window size (R24) — in cycle mode the
  timer **keeps ticking under the overlay** and each advance updates its
  text. `f`/`Esc`/canvas double-click **do not dismiss** the overlay — a
  full-screen toggle keeps it, repositioned from the new canvas dimensions;
  `q`/shutdown hides it. Nothing is shown at startup; `--print` (R12)
  unaffected (no window).
- **Prompt copy (`Ctrl+C`, R34, rev 1.8 amendment 5):** with the window
  focused, `Ctrl+C` (Shift tolerated: `Ctrl+Shift+C` alike) copies **the
  same text this overlay would display** — the displayed file's prompt, or
  nothing — to the **system clipboard**: an effective copy shows the R30
  overlay `prompt copied` (1 s); when there is nothing to copy (no displayed
  image, or the file carries no prompt) there is **no clipboard write and no
  overlay**. The overlay itself is **left in place** (the copy neither
  toggles nor dismisses it); with the keyboard help (R32) displayed, the
  help is dismissed first (the R32 dismiss-then-dispatch rule). It is a
  **hidden feature** — not in the §5.9 help list. Purely cosmetic beyond the
  clipboard write (the cosmetic invariant above). The terminal `Ctrl+C`
  (SIGINT) and `SIGTERM` still quit (R18).
- Headless-testable: the extracted prompt (or `no information`) for a file is
  a **pure function of the file's bytes** — the extraction algorithm
  (§12.11) is unit-testable with fixture images, no display required (case
  8m); the copy seam (R34) — which text `Ctrl+C` hands to the clipboard,
  or none — is likewise a pure function of the pre-press state (case 8n);
  the overlay surface (toggle, update-on-swap, exclusivity, position) is
  manual case 42, and the copy's on-screen surface (the `prompt copied`
  overlay, the clipboard contents) is manual case 43.

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
- Initial window size (the **pre-image default**): 80 % of the primary
  monitor, minimum 900×675 logical pixels; on the first displayed load the
  window is fit to the image per R24/§5.6 (`--fit`, default `ratio`);
  `--fullscreen` overrides to full screen after showing, with the chrome
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

# Watch the containing directory, starting pinned to one image file (file target, R21).
riview out/frame_012.png

# Full-screen preview while a long batch runs.
riview out --fullscreen

# Network filesystem or inotify-quota problems: poll every half second.
riview /mnt/renders --poll 0.5

# Fast pipeline, small files: shorter settle window.
riview out --stable-ms 500

# Low-power machine, huge images: cap the decode at 1024 px on the longer side.
riview out --max-dim 1024

# Window fit (R24): the default fits the window to the image's aspect ratio;
# `exact` sizes the canvas 1:1 to the image (capped at the screen); `off` keeps
# the classic 80 % window. `r` re-fits on demand in any of the three.
riview out                 # --fit ratio (default)
riview out --fit exact     # --fit-window exact is the same (synonym)
riview out --fit off       # pre-image 80 % window, no resize on load

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
- No manual navigation beyond `Left`/`Right`/`Home`/`End`/`p`/`n` (R23/R25/R26) and
  the automatic slide show (R27): no jump to an arbitrary position, no reverse
  (older-end) cycling, no cycle-speed presets beyond ±1 s (R28), no mouse-based
  navigation — riview is a reload viewer with a step-back and a slide show,
  not a browser.
- No animation of multi-frame images (GIF first frame only).
- No config files, no persistent state, no "remember last directory".
- No recursive watching; subdirectories are never scanned.
- No multi-directory watching in one process (run two `riview` processes if needed).
- No adaptive re-decode on window resize (§7.1).
- No automatic window resize on new loads: the window is sized once on the
  first displayed load (R24 fit pass) and then belongs to the user; re-fitting
  is on demand via `r` only.
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
8e. **Navigation order & stepping (R23, unit)** → the navigation list orders settled
   candidates by (mtime_ns desc, name desc); `Left`/`Right` move one index from the
   current position and clamp at both ends (no-op); `n` → index 0 (live mode).
8f. **Pinning (R23, unit, fake clocks)** → with a pinned path: a *newer* candidate
   settling does not displace the pinned path (R3 suspended); an in-place update of the
   pinned file reloads only once settled (display holds the old version meanwhile); the
   pinned file removed from the candidates → image-gone state (display cleared, pin
   kept, no auto-switch); the file reappearing and settling → display restored to it;
   `n` → live mode (newest settled, or `None`).
8g. **Fit geometry & header probe (R24, unit)** → the pure `fit_window`
   computation: `ratio` fits the image's aspect ratio inside the budget box
   (landscape, portrait, square) with canvas + header = window (header
   correction); `exact` is image ÷ scale factor at 1:1; `exact` larger than
   the screen → ratio fit within the full-monitor-minus-header cap; a tiny
   image → 320 px floor with the ratio preserved; `off` → no fit. The pure
   `probe_dimensions` header probe: PNG / JPEG / WebP (VP8, VP8L, VP8X) /
   GIF / BMP → (w, h); TIFF, unrecognized, and truncated input → None.
8h. **Fit-once, `r` & startup size (R24, unit, fake window)** → the fit pass
   resizes the window exactly once, on the first displayed load, and never
   again (a second load or a navigation request resizes nothing); `r`
   re-fits to the currently displayed image; `r` is a no-op in `off` mode, in
   `--fullscreen`, and with no image on display; the `--fit-window` synonym
   parses to the same mode; the window opens at the fit size of an already-
   settled newest file (early fit; header 47 px fallback; `exact` and file
   targets (R21) alike) and at the 80 % default box when there is no
   settled candidate or the fit mode is `off`; the portable resize chain
   (`resize` → pre-presentation `set_default_size` → post-map size-request
   grow; shrink is a no-op); the post-map clamp release is regression-tested
   with a **real `GLib.MainLoop` spin** proving the no-argument timeout
   callback fires and releases the `set_size_request` minimum (§13.2).
8i. **Cycle target (R27, unit)** → the pure `cycle_target(ordered,
   anchor, failed)`: adjacent newer step (list `[D,A,B,C]`, anchor `C` → `B`);
   at the newest end → wrap to the oldest (anchor `D` → `C`); a deleted slide
   (virtual anchor not in the list) → first settled strictly newer than the
   anchor, else the wrap; a newly settled image at the newest end is only
   reached by the normal walk (anchor `B` → `A`, not `D'`); a failed version
   between the anchor and the newest is skipped, and an all-failed span falls
   through to the wrap; single-element list → the same element (no advance);
   empty list → `None`; every candidate failed → `None`.
8j. **Cycle time (R28)** → `--cycle-time 0` / `--cycle-time -3` → exit 2;
   `--cycle-time 9.5` → exit 2 (integer-only); default is 9 s; `--cycle
   --cycle-time 3` → starts in cycle mode at 3 s (combinable — rev 1.7.3
   fix); `--cycle 5 --cycle-time 3` → 3 s (`--cycle-time` takes precedence); `--cycle 0`
   / `--cycle 2.5` → exit 2; the clamp
   logic: `Up` adds 1 s (no upper bound), `Down` subtracts 1 s, floor 1 s
   (no effect at the floor); the rescale logic: 9 s with 2 s elapsed, `Down`
   ×2 → 7 s → the current slide's deadline moves to now+5 s (elapsed
   preserved) and the following interval is 7 s; a new time shorter than the
   elapsed time (e.g. 8 s elapsed, `Down` to 2 s) moves the deadline to the
   past → advance at the next tick; outside cycle mode the keys change the
   stored value only (no deadline exists).
8k. **Keypress feedback overlay (R30, unit + fake window)** → the effective
   keypresses map to the overlay text with the current cycle time (`c` →
   `cycle on: {N}s`, `p` → `pause`, `n` → `newest live image`, `Up`/`Down` →
   `cycle: {N}s`); no-op keypresses show nothing (`c` while cycling, `n` in
   live mode, `p` in manual mode, `Down` at the 1 s floor); windowed mode shows
   the same overlays (pre-release amendment — the 10% margin is canvas-based
   in both modes); the overlay is armed for 1 s and then
   hidden (fake timers); a second feedback keypress within the 1 s replaces
   the text and restarts the timer; a full-screen toggle dismisses an active
   overlay; the overlay does not touch the cycle deadline (the R28 clock
   invariant) and is not shown at startup.

8l. **`space` cycle/pause toggle (R31, unit + fake window)** → `space` while
   not cycling starts the cycle exactly as `c` (overlay `cycle on: {N}s`);
   `space` while cycling stops the cycle and pins exactly as `p` (overlay
   `pause`); a no-op dispatch (idle state) shows nothing;
   the overlay text is the dispatched action's (R30).
8m. **Prompt extraction (R33, rev 1.8, unit — no display)** → `extract_prompt`
   is a pure function of the file's bytes: fixture PNGs with a `parameters`
   chunk (single-line prompt; multi-line prompt with the `Steps:` metadata
   line split off; `zTXt` compressed variant; key not in the set → ignored),
   a JPEG / WebP EXIF `UserComment`, a file with no prompt text, an unknown
   format, and a prompt beyond the 8 MiB read bound (→ not found) — each
   asserts the extracted text or "not found" (the waiting / idle /
   image-gone states likewise yield `no information` — no displayed file).
8n. **Prompt copy seam (R34, rev 1.8 amendment 5, unit — no display)** → the
   text `Ctrl+C` hands to the clipboard is a pure function of the pre-press
   state: a displayed image with an embedded prompt → **exactly that prompt**
   (the R33/§12.11 extraction — the same string the overlay shows, multi-line
   prompts included); a displayed image without a prompt → **nothing** (no
   clipboard write); no displayed image (waiting / idle / image-gone) →
   nothing. The R30 feedback decision follows the effective-only rule: an
   effective copy → `prompt copied`; a no-op copy → no overlay.
8o. **Prompt overlay wrap width (R33, rev 1.8 patch, unit — no display)** →
   the wrap width is a pure function of the canvas width and the rendered
   image width: `min(0.8·canvas_w, max(0.8·image_w, 0.5·canvas_w))` —
   image wider than the canvas (or oversized in `off` mode) → 0.8·canvas_w
   (the pre-patch rule, unchanged); rendered image ≥ 62.5 % of the canvas →
   0.8·image_w (the column hugs the letterboxed image); rendered image
   < 62.5 % of the canvas → 0.5·canvas_w (the floor). Recomputed at show
   time, at every display change (update-on-swap re-applies it), at a
   full-screen toggle, and at an `r` re-fit while visible; windowed and
   `--fullscreen` alike.
8p. **Info overlay reflow seam (R33, rev 1.8.3, unit — no display)** →
   the **50 ms poll** (a zero-argument GLib timeout; a `True` return
   keeps the source; removed via `GLib.source_remove`) is a pure
   function of the canvas size and the cached full extracted text: size unchanged → **no label writes** (the
   two integer reads are the whole cost); size changed → wrap / elision /
   margin re-applied **from the cache** — the extraction is **not**
   called (a resize changes no file), and a grow de-elides (the cache is
   the unelided text). The callback is installed on show and removed on
   hide / `h`-dismiss / shutdown — nothing runs while the overlay is
   hidden. (Manual side: case 42's drag-resize check.)

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
    (Keypress feedback: cases 37/38, R30.)
19. **`--max-dim`** → a 4096 px source with `--max-dim 512` shows a ≤512 px decode (header
    dimensions confirm).
20. **Directory delete + recreate** (inotify mode) → `rm -r out && mkdir out` and drop a new
    PNG → monitoring re-establishes and the new image appears (R14).
21. **GIF** → a multi-frame GIF shows its first frame, stably.
22. **SIGINT/SIGTERM** → clean exit, code 0, no traceback.
23. **Keyboard shortcuts (R18)** → with the window focused: `q` quits (rc 0); a `Ctrl+C`
    **keypress with the window focused** copies the prompt (R34 — it is *not* a quit;
    cases 8n/43); a `Ctrl+C` **in the terminal** (SIGINT) quits cleanly (rc 0, no
    traceback); `f` toggles full screen both ways (header bar
    hidden in full screen, back on exit); `Esc` leaves full screen and does nothing in
    windowed mode; `Ctrl+q` / `Ctrl+f` are **not** shortcuts (leave the keys unhandled).
24. **Canvas double-click (R19)** → a left double-click on the image *and* on the black
    letterbox both toggle full screen ↔ windowed (header bar hidden in full screen, back on
    exit); a double-click on the header bar does nothing; single clicks do nothing.
25. **Idle state (R22)** → launched from the app menu / panel (no target, GUI context) →
    black canvas with the wrapped message, header subtitle `no file`, `q` quits cleanly.
26. **Desktop entry (R20)** → after `--install-desktop`: the entry and icon appear in the
    app grid and in Files; right-click a folder → "Open with riview" → directory mode;
    right-click a PNG → file target (starts pinned to it, R21); `--uninstall-desktop` removes the entry and icon.
27. **File target (R21, rev 1.7.4)** → `riview out/x.png` with `out/` holding ≥3
    settled images: the window opens showing **x.png immediately** (no waiting
    state; header shows its name/dimensions/mtime; mode is manual, pinned);
    overwriting x.png in place reloads it once settled (R4); a newer *other*
    image in `out/` does **not** displace it (the pin, R23); `Left`/`Right`
    step through `out/`'s settled candidates from x.png's position, `Home`/`End`
    jump to the oldest/newest; `n` → newest + live following; `c` → the cycle
    starts **at x.png**; deleting x.png → the **image-gone** state (black canvas
    + message, pin persists); recreating it (after it settles) restores the
    display without a keypress.
28. **Terminal CWD (R22)** → `cd out && riview` (no argument) watches the CWD — no idle
    message appears.
29. **Manual navigation (R23, rev 1.5)** → `riview out` with ≥3 settled images:
   `Left` steps one image older per press, `Right` back toward the newer end;
   every keypress pins the display after the step, so while browsing manually a
   newly settled image does **not** displace it. In live mode `Right`/`End` (and
   `Left`/`Home` with a single image) leave the display unchanged but **pin it**
   — the stream is frozen; `n` resumes live following (a newly settled image
   then displaces the display, R3). Delete the pinned image → black canvas with
   the image-gone message; `Left`/`Right` **keep scanning from where the image
   was** (the pin remembers its mtime); `n` → newest + live following; recreating
   the file (after it settles) restores the display without a keypress. The keys
   behave identically in full screen (`f`); there the image-gone state is a bare
   black canvas (R16).
30. **Movement keys from a file target (R23/R25/R26/R21, rev 1.7.4)** → `riview
    out/x.png` with ≥3 settled images: `Left`/`Right` step one image older/newer
    through `out/`'s settled candidates (starting from x.png's position) and pin
    the result; `Home`/`End` jump to the oldest/newest and pin; `p` is a no-op
    (already pinned — no overlay); `n` → the newest image + live following
    (overlay `newest live image`); in a directory holding **only** x.png the
    movement keys have no observable effect (single-candidate clamping, R23).
31. **Window fit (R24)** → default (`ratio`): a square image opens in a near-square
   window with no visible letterbox after the first load; a portrait image in a
   portrait window (header-corrected). `--fit exact` at scale factor 1: canvas =
   image pixels (± window-manager constraints); an image larger than the screen →
   window = full screen minus the header bar. `--fit off` → the classic 80 % window,
   no resize on load. A new load of a different size → the window does **not**
   resize (letterbox as needed); `Left` to another image → no resize; `r` → the
   window re-fits to the currently displayed image. In `--fullscreen`: no fit pass,
   `r` has no effect. Multi-monitor: drag the window to a second (differently
   sized) monitor → `r` re-fits to *that* monitor (ratio budget / exact cap).
32. **Home/End jump (R25, rev 1.5)** → `riview out` with ≥3 settled images: `Home`
   jumps to the oldest image and pins it (a newly settled image does **not**
   displace it); `End` jumps to the newest and pins it — a newly settled image
   still does **not** displace it (`n` is needed to resume live following). `End`
   in live mode → display unchanged, **now pinned** (frozen); `Home` with a single
   settled image → pinned in place; at an end the matching key pins in place.
   Delete the pinned image → image-gone state: `End` → the newest, **still
   manual**; `n` → the newest, live. Single-file mode: no observable effect. A
   jump never resizes the window (R24).
33. **Pause (R26)** → in live mode: `p` freezes the display — a newly settled
   image does **not** displace it; `n` resumes following. In the
   rewrite-in-flight window `p` keeps the displayed image (whereas `End` jumps
   to the newest settled). Manual mode, image-gone, waiting: no observable
   effect.
34. **Cycle mode (R27, rev 1.6)** → `riview out` with ≥3 settled images:
   `c` → the header indicator appears; after ≈ one cycle time the display
   advances to the next newer image, again after the next interval, and after
   the newest image it **wraps to the oldest** and keeps cycling. A newly
   settled image during the cycle does **not** interrupt the current slide; it
   appears once the cycle reaches the newest end and continues into it. `Left`/
   `Right`/`Home`/`End`/`p` mid-cycle **stop the cycle** and pin per the R23
   two-phase rule (display now manual — a newly settled image does not
   displace it); `n` mid-cycle stops the cycle and resumes live following (a
   newly settled image then displaces the display, R3). `f`/`r`/double-click
   mid-cycle: the cycle continues. Delete the currently shown slide → the
   canvas holds the image (no image-gone text) until the next advance, which
   continues from where the image was. Delete **all** images → waiting
   state, cycle still active; add an image → it becomes a slide at the next
   advance. `c` in the waiting state → armed cycle; first settling image
   becomes the first slide. A corrupt newest image (guaranteed-newest
   mtime, settled, invalid bytes) → one stderr warning, the advance skips it
   to the next image (or wraps), no retry storm (R15). File target (R21): `c`
   starts the cycle at the target file. Advances never resize the window (R24).
35. **Cycle time (R28)** → `riview out --cycle-time 3` → advances every ≈ 3 s.
   `Up` during the cycle → the *current* slide's remaining time grows by 1 s
   (elapsed preserved) and every following interval is 1 s longer; `Down`
   shrinks the current remaining time accordingly — an image already shown
   for longer than its new cycle time advances at once. `Down` to 1 s → the
   floor; further `Down` has no effect. `Up`/`Down` **outside** cycle mode
   change the stored time only (visible in the indicator once `c` is
   pressed). `--cycle-time 0` → exit 2. In-place rewrite of the currently
   shown slide (new version of the displayed file) → reloads once settled
   (R4) with the cycle clock **not** reset — the next advance is on schedule
   (confirmed edge case).
36. **Cycle at startup (R29, rev 1.6)** → `riview out --cycle` with ≥3 settled
   images: the window opens showing the **oldest** image (not the newest — the
   R3 startup display is bypassed), indicator shown; advances toward the newer
   end every cycle time; wrap newest→oldest as usual. `--cycle 5` → the cycle
   starts at 5 s (every ≈ 5 s). Empty directory at
   startup → waiting state; the first settling image becomes the first slide;
   a second image settling afterwards is the next advance (strictly newer
   than the anchor). `Left`/`n` exit the cycle as usual. File target (R21):
   `riview out/x.png --cycle` starts the cycle **at x.png** (the oldest-start
   rule does not apply — rev 1.7.4); `--print --cycle` prints per R12 and exits
   (inert).
37. **Full-screen keypress feedback (R30, rev 1.7)** → `riview out
   --fullscreen --cycle-time 3` with ≥3 settled images: `c` → a pale-yellow
   `cycle on: 3s` on a semi-transparent gray shade, centered horizontally about
   10% up from the bottom of the canvas, gone within ≈ 1 s; `Up`
   → `cycle: 4s`; `Down` → `cycle: 3s`; `Down`×2 → `cycle: 1s`, then `Down` →
   **no** overlay (the 1 s floor, R28); `p` → `pause`; `n` → `newest live
   image`; `n` again (now live) → no overlay. `c` followed by `Up` within the
   1 s → the text is replaced and the visible lifetime restarts at ≈ 1 s
   (last wins). The cycle keeps advancing on schedule throughout — the
   overlay neither resets nor shifts the clock (R28). `f` → windowed: an
   active overlay is dismissed immediately, and the overlays continue on the
   canvas below the header (case 38). `--cycle --fullscreen` at startup
   → no overlay at open. Single-file mode: `c`/`n`/`p` are no-ops → no
   overlay; `Up`/`Down` still show `cycle: {N}s` (the stored value changes,
   R28).

38. **Windowed keypress feedback (R30, rev 1.7 pre-release amendment)** →
   `riview out --cycle-time 3` (windowed) with ≥3 settled images: the same
   four overlays (`c` → `cycle on: 3s`, `p` → `pause`, `n` → `newest live
   image`, `Up`/`Down` → `cycle: {N}s`) on the canvas **below the header bar**
   — pale-yellow on a semi-transparent gray shade, bottom center, its bottom
   edge about 10% up from the canvas bottom — gone within ≈ 1 s; the header
   keeps its persistent status (`· cycle Ns` marker, R10/R28) alongside the
   transient overlay; same no-op rules (no overlay for no-ops); same
   replace/restart within the 1 s; `f` (to full screen) dismisses an active
   overlay immediately and the overlays continue on the now header-less
   canvas. Nothing at startup (`--cycle` windowed opens without one).

39. **`space` cycle/pause toggle (R31, rev 1.7.2)** → `riview out
   --cycle-time 3` (windowed) with ≥3 settled images: `space` → `cycle on:
   3s`, the slides advance every ≈ 3 s; `space` again → `pause`, the cycle
   stops and the current slide is pinned (manual mode — `Left`/`Right` step
   from it); `space` again → `cycle on: 3s`, the cycle restarts at the
   currently shown image; `space` in the idle state does nothing (no
   overlay); for a file target (R21) it starts the cycle at the target file (as `c`).

40. **File target — extension bypass and cycle start (R21/R29, rev 1.7.4)** →
   `riview out/x.bmp --extensions png` (x.bmp settled, plus settled PNGs in
   `out/`): x.bmp displays **immediately** at process start, pinned (manual
   mode); `Left`/`Right` navigate **through** x.bmp (the target file bypasses
   `--extensions`, §5.1); `--cycle` / `c` start the cycle **at x.bmp**
   (advancing toward the newer end and wrapping as usual — x.bmp included among
   the slides); `riview out/x.tga` (extension not in the default set) → exit 2
   (the default-set gate, §4.2 — `--extensions` does not lift it).
41. **Keyboard help (R32, rev 1.7 amendment 4)** → live directory with 3 settled
   images: `h` → the centered 13-line list (`Keys` header + 12 key lines, the exact
   §5.9 text) appears on the canvas over the current image; header/status unchanged.
   `h` again → closes (no re-show). An unbound key (`a`) → closes, display
   unchanged. `n` with the help displayed → closes **and** switches to the newest
   image, then the R30 `newest live image` overlay shows for 1 s (the two never
   coexist). Cycle mode: the timer keeps ticking under the overlay — the slide may
   change while the help is displayed — and `space` with the help displayed →
   closes and stops the cycle, pinning the *current* slide (R30 `pause` overlay).
   In the idle state (R22) `?` shows the same list. With the prompt
   information overlay (R33) displayed, `h` → the info overlay is dismissed
   and the list appears; dismissing the help does **not** re-show the info
   overlay (no state remembered); `i` again re-shows it. Nothing is shown at
   startup (including with `--cycle`); `--print` unaffected.
42. **Prompt information overlay (R33, rev 1.8)** → a directory with settled
   `rigen` images (embedded `parameters` chunk) and one image without
   metadata: `i` → the displayed image's prompt appears bottom-center, above
   the R30 feedback zone, word-wrapped at 80 % of the rendered image width
   (window fitted to the image: 80 % of the canvas, as before), and stays
   on screen (no timer); `i` again → it disappears. Step to the
   metadata-free image (`Left`/`Right`) → the overlay's text switches to
   `no information` (still displayed); step back → its prompt returns.
   Cycle mode with the overlay displayed: every advance updates the text to
   the new slide's prompt (the timer ticks underneath); `c` itself shows the
   R30 `cycle on: {N}s` **below** the overlay, expiring after 1 s while the
   overlay stays. Waiting state (empty directory), idle (R22), and
   image-gone: `i` → `no information`. **Letterboxed window (1.8.2):** with
   the window wider than the image (`--fit off` with a small image, or
   full-screen on a small image) the prompt column hugs the **image** —
   word-wrapped at 80 % of the image's rendered width, not the window's, so
   the text no longer runs across the letterbox; a very narrow image (less
   than 62.5 % of the canvas width) keeps the column at least 50 % of the
   canvas width. `r` with the overlay displayed re-fits and repositions it
   (the wrap follows the new rendered width). **Drag-resize (1.8.3):**
   with the overlay displayed, drag the window smaller → the text
   re-wraps and, once the height budget is exceeded, re-elides **live
   during the drag** (no `i` toggle needed); drag it back larger → the
   elision lifts from the cached full text; the bottom edge tracks 22 %
   of the new canvas height. Hidden: a drag resizes nothing else (the
   observation is not installed). `h` with the overlay displayed → the
   overlay is dismissed and the help list appears; dismissing the help does
   **not** re-show it; `i` again re-shows it (and vice versa). `f` keeps the
   overlay through the full-screen toggle, repositioned. `i` shows no R30
   feedback. Nothing is shown at startup; `--print` unaffected.
43. **Prompt copy (R34, rev 1.8 amendment 5)** → a directory with settled
   `rigen` images (embedded `parameters` chunks) and one image without
   metadata: `Ctrl+C` on a prompted image → the R30 overlay `prompt copied`
   shows for 1 s and the prompt pastes into another app (verified with
   `wl-paste` / `xclip -o`) **character-for-character** identical to what the
   `i` overlay displays (multi-line prompts preserved). `Ctrl+Shift+C` →
   identical. On the metadata-free image — and in the waiting / idle /
   image-gone states — nothing happens: no overlay, the clipboard
   **unchanged** (a sentinel paste before the press still reads the
   sentinel). With the prompt information overlay (R33) displayed: it stays
   in place and the copied text equals its text. With the keyboard help
   (R32) displayed: the help is dismissed and, when a copy is performed,
   `prompt copied` shows (the two never coexist). Cycle mode: the timer
   keeps ticking; the copy takes the *current* slide's prompt. Windowed and
   `--fullscreen` alike. `Ctrl+C` in the **terminal** (SIGINT) still quits
   (case 22). `--print` unaffected.

---

# Part II — Design

## 12. Design

### 12.1 Confirmed decisions

D1–D5 answer the open questions (Q1–Q5) raised before drafting; D6–D18 are design
defaults and owner-confirmed additions (D13–D17 confirmed by the spec owner; D18
per the spec owner's rev-1.6 request, its detail assumptions confirmed by the
spec owner — A10 amended: current-interval rescale; D19 per the spec owner's
final rev-1.6 amendment).

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Newest = `st_mtime_ns`; newer-only switching** (strictly greater mtime to switch files; ties keep current; same-path changes always reload). §5.2, R3/R4. | Confirmed (Q1). mtime is the only order that is both general and update-sensitive; strict-newer prevents flapping when old files are copied in; same-path reload gives "file updated → display updates". |
| D2 | **Target resolution & launch context (rev 0.8):** an explicit target may be a directory or an image file (file target, R21). No target: watch the CWD when launched from a terminal, else the idle state (R22) — GUI context ⇔ `DESKTOP_STARTUP_ID` set or no controlling tty (§4.6, a documented heuristic). | Replaces rev-1 "default target = CWD". A menu-launched app must not silently watch `$HOME`; a terminal launch keeps the historical zero-surprise CWD default. |
| D3 | **Fit-to-window only; `--fullscreen` flag; no zoom/pan.** | Confirmed (Q3). Keeps the tool a *reload* viewer; sharp through resize via 2× oversample (§7.1). |
| D4 | **Default extensions `png,jpg,jpeg,webp,gif,tiff,tif,bmp`; GIF = first frame; `avif`/`svg` opt-in via `--extensions`.** | Confirmed (Q4). Covers all lemond output formats plus common extras; SVG excluded from defaults because vector files are misleading as "generated image" previews. |
| D5 | **Settle window default 2000 ms (`--stable-ms`), dual conditions (§5.3); dual buffer — display swap only after successful decode (§5.4).** | Confirmed (Q5). 2 s of quiet is safe for bursty 1–10 MB writes; the mtime-age condition gives a startup fast path; the dual buffer makes decode failures invisible to the user except on stderr. |
| D6 | **Single-file Python 3 + PyGObject (GTK 4 + libadwaita); no pip packages.** | Matches the workspace convention (`rigen`, `vary`) and the target system's installed stack (§13.1). GTK 4 + libadwaita is the first-class toolkit for the COSMIC desktop. |
| D7 | **Inotify via `Gio.File` monitor, 200 ms event coalescing; `--poll S` forces polling; inotify failure auto-falls back to 1.0 s polling with a warning.** | Full-rescan-on-event is simplest and correct (a rescan re-derives everything from disk truth); coalescing bounds event storms from bursty writers. |
| D8 | **Decode on a single worker thread; `threading` + `queue` bridge to the main loop; one decode in flight; generation counter supersedes stale results.** | Verified on this system that PyGObject 3.48.2 exposes neither `GLib.spawn_threaded` nor `MainContext.invoke` (§13.2), so the plain, guaranteed-correct bridge is a worker thread + `queue.Queue` drained by a 16 ms `GLib.timeout_add` pump. |
| D9 | **`Gio.ApplicationFlags.NON_UNIQUE`** — every `riview` process is independent; two windows can watch two directories. | An app-ID singleton would make a second (different-directory) instance steal the first window; independence is the useful behaviour for a utility. |
| D10 | **`--print` headless query mode** (replaces `--newest`; no settle window; point-in-time; file target prints itself; no target → CWD always; tie → byte-wise greatest name). | Mirrors `rigen --list`/`--dry-run`: a small, scriptable, headlessly-testable surface for the selection logic (§11 cases 1–5c). The rename reflects that it now answers "what would riview display", not just "what is newest". |
| D11 | **Initial window = 80 % of primary monitor work area (min 900×675); decode target = min(source, 2×scale_factor×window, `--max-dim` on longer side).** (Rev 1.2: the 80 % box is the *pre-image* default and the `ratio` fit budget; the post-image window is set by R24/D14. Large-screen note, spec owner's call: **no maximum cap** — the 80 % rule is tried as-is on UHD/4K, where it produces a large but usable window; the percentage is a single constant, adjustable later if needed.) | A window sized to the image would make 4K sources produce unusable windows; 2× oversample covers HiDPI and moderate resizes without re-decode. |
| D12 | **Desktop integration via `--install-desktop`/`--uninstall-desktop` (R20):** per-user `.desktop` + embedded SVG icon under `XDG_DATA_HOME`; `Exec %U`; `MimeType` for `inode/directory` + default image types; idempotent; uninstall is a no-op-OK. The icon lives in the script as a string constant (D6 preserved). | The file manager and the app grid watch these directories (no `update-desktop-database` needed); `Exec %U` is the standard, dependency-free way to get "right-click → Open with riview"; per-user scope avoids root and package management. |
| D13 | **Manual navigation (rev 1.1, R23):** `Left`/`Right` step through the *settled* candidates in §4.3 order, clamped at both ends; a selection **pins** the display (live following suspended) until `n`; the pinned file disappearing shows the image-gone state (black canvas + message; the pin persists, the file reappearing restores the display); `n` = newest + live mode. | Confirmed by the spec owner (rev 1.1 request). The use case is scrubbing back through pipeline output *while the pipeline keeps writing*: pinning (not auto-jump) keeps the view stable; settled-only navigation preserves "never display a half-written file"; clamping keeps the key surface minimal; a disappeared image gets an explicit, self-explaining escape (the image-gone message) rather than a silent mid-browse switch, and recreation restores it without a keypress (R23 pin semantics); `n` is the one-keystroke return to the tool's primary (live) behaviour. |
| D14 | **Window fit (rev 1.2, R24):** `--fit {ratio,exact,off}` (synonym `--fit-window`), default `ratio`. The window opens at the D11 pre-image default; the first displayed load resizes the window once so the *canvas* (window minus header) matches the image — `ratio`: the largest image-ratio rectangle within the 80 % budget box (header-corrected); `exact`: 1:1 logical pixels, capped at the full monitor minus the header (ratio-fit fallback); 320 px-per-side floor. **No automatic resize on later loads** — after the fit pass the window belongs to the user; `r` re-fits on demand to the currently displayed image. Fit and `r` are measured on the **monitor the window is currently on** (drag to another screen + `r` re-fits to that screen); the pre-image default uses the primary/first monitor (the window is not placed yet). | Confirmed by the spec owner (rev 1.2 request, five answers): default `ratio`; `ratio` keeps the 80 % budget; `exact` capped at the maximum screen size minus the header ("still a window, not `--fullscreen`"); the `r` re-fit key; `--fit`/`--fit-window` synonyms. The image-driven sizing stays bounded (D11 compatibility — no unusable windows from 4K sources); skipping per-load resizes keeps the window stable in the primary use case (a pipeline keeps writing frames of varying sizes) and through R23 navigation (each step would otherwise resize the window). |
| D15 | **`--fit ratio` COSMIC cap (rev 1.3):** the `ratio` fit box is the smaller of the D11 80 % budget box and a fixed **1600×1200 logical-pixel (width × height)** box (`COSMIC_CAP_W`/`COSMIC_CAP_H`, §12.3); the image is ratio-fitted inside it (header-corrected as usual; the 320 px floor still applies). `exact` and `off` are unchanged. **Temporary**: the COSMIC compositor has an upstream bug that reconfigures mapped windows larger than a certain size (not position-related — the spec owner's research found matching bug reports); the cap keeps fitted windows below the clamping threshold. **Revisit after a COSMIC update fixes the bug: raise or delete the cap.** | Confirmed by the spec owner (rev 1.3): "for now we just scale to a maximum … and fit the image inside this box (ratio-scaled) for the `--fit ratio` option" — "maximum size would be 1200 height and 1600 width"; "maybe re-address it after a future update of COSMIC." Chosen over fighting the compositor from the client (no Wayland API to prevent or correct the reconfigure) and over detecting-then-adapting (the client cannot know the threshold). |
| D16 | **Home/End jump (rev 1.4, R25):** `Home` → the oldest settled image, `End` → the newest settled image, both **pinning** the display (manual mode); `End` does **not** resume live following (`n` remains the live key); no-op when the target is already the displayed/pinned file (hence `End` in live mode is a no-op), in the waiting state, and in the idle state; both work from the image-gone state (recover the display, stay manual). | Confirmed by the spec owner (rev 1.4 request): "the additional keys `home` and `end` should move to the oldest and to the newest image (when in directory mode). `end` does not start the automatic mode, it just pins to the currently newest image." The already-displayed no-op — and hence the `End`-in-live-mode no-op — is the implementer's reading of "just pins to the currently newest image", chosen for consistency with R23's clamped-end no-op philosophy (no invisible live→manual mode change). **Superseded by D17 (rev 1.5):** the "already-displayed no-op" reading was replaced by the two-phase rule — a movement keypress always pins, including when the attempt makes no change. |
| D17 | **Movement keys always pin; position-preserving image-gone; `p` pause (rev 1.5, R23/R25/R26):** every movement key is two-phase — attempt a movement over the settled list, then pin whatever is displayed (a failed attempt still pins; in live mode every movement key therefore exits live mode). The `Left`/`Right` anchor is where the displayed version sorts by `(mtime, path)` — virtual (last known mtime) in the image-gone state and mid-rewrite, so scanning continues after deleting the displayed file. `p` pins the display without moving. `n` is the only key that resumes live mode. | Confirmed by the spec owner: "movement key = try the movement (maybe it changes the image, or maybe it doesn't), and then pin whatever is displayed"; "if an image hasn't settled, it's not yet a candidate to be displayed, so the movement keys can't select it; no special clauses for this"; "we can also add a 'p' key (pause), that will simply pin whatever image is being displayed"; "with Image-gone, we still hold that path pinned together with its previous mtime … I can still right or left to the next image and keep scanning." Supersedes D16's "already-displayed no-op" reading. |
| D18 | **Cycle mode / slide show (rev 1.6, R27/R28):** `c` enters a third display mode — the slide show: every **cycle time** (`--cycle-time`, integer seconds, min 1, default 9; `Up`/`Down` ±1 s at runtime, floor 1 s, rescaling the current interval — elapsed preserved) the display advances one *settled* image toward the newer end of the navigation list, wrapping newest→oldest. Live following (R3) is suspended while cycling; newly settled images join the list at the newest end and are picked up when the cycle reaches them (the cycle grows), deleted files drop out. The advance target is re-derived from the §5.5 anchor each tick (no stored index), so the list may grow/shrink underneath the cycle; failed decodes (R15) are skipped, never retried. Every mode-selecting key exits cycling first, then applies its normal semantics (two-phase → manual; `n` → live); display keys (`f`/`Esc`/`r`/double-click) do not affect it. | Per the spec owner's rev-1.6 request (slide show over the settled images, `c` to start, any navigation key to stop and fall into manual/live, `--cycle-time` default 9 s with `Up`/`Down` ±1 s down to 1 s). The re-derived-anchor choice follows the rev-1.5 philosophy (D17: "the anchor is re-derived … so files settling or leaving in the background never shift the display"). Detail assumptions A1–A9 confirmed as drafted in the rev-1.6 review; A10 **amended by the spec owner**: an `Up`/`Down` adjustment rescales the **current** interval — elapsed time preserved (remaining = new time − elapsed; a new time below the elapsed time advances at the next tick) — and every following interval uses the new full cycle time (worked example: 9 s with 2 s elapsed, `Down`×2 → remaining 5 s, next image a full 7 s). |
| D19 | **`--cycle` at startup (rev 1.6, R29):** the flag `--cycle` arms cycle mode from process start (before any display) and selects the **oldest** settled candidate for the first display instead of the newest R3 would show; from there the cycle runs exactly as R27 (advance toward the newer end, wrap newest→oldest). `--cycle` takes an optional value — the initial cycle time in seconds — and is combinable with `--cycle-time` (when both give a time, `--cycle-time` takes precedence — rev 1.7.3 fix). | Per the spec owner's final rev-1.6 amendment ("a `--cycle` option that will automatically start cycle mode when the software starts. Preferably, it would start at the oldest image"), amended by the spec owner: "--cycle and --cycle-time should be mutually exclusive… --cycle should have an option value, in seconds, for the initial cycle time" — the mutual-exclusion amendment **retracted by the spec owner** (a confirmation mistake, rev 1.7.3): `--cycle` carries no interval of its own, so the combination is unambiguous; the rule is now that `--cycle-time` takes precedence when both give a time. Oldest-start is specified (the acceptable fallback — newest start, wrap on the first advance — was not needed: with the re-derived anchor the oldest is just a different first target). For a file target (R21) the cycle starts at the target file (rev 1.7.4 — the explicit file is the start anchor); inert in `--print` (R12). |

### 12.2 Deliverables

```
sdcpp-setup-lemonade/
├── riview                    # the viewer (single file, executable, Python 3.10+)
├── RIVIEW-SW-SPEC-AND-DESIGN.md   # this document
└── tests/
    └── test_riview.py        # headless suite: selection + settle + navigation +
                              # fit geometry (fake clocks), --print mode, CLI
                              # validation, desktop install, launch context (no
                              # display required)
```

No `.desktop` file is *shipped* in the repository: the entry is generated at runtime by
`--install-desktop` (R20, D12) into the user's own `XDG_DATA_HOME`.

### 12.3 Program structure

Single file `./riview`, top to bottom: (the GUI-layer classes are defined inside
`_gui_classes()` so that `--print` and the desktop flags never import GTK, and so the
headless test suite can drive `Watcher`/`Decoder` without a display — `run_gui` calls it
and runs the app).

1. **Constants** — `VERSION = "1.2.0"`; exit codes (`OK=0, USAGE=2, NO_TARGET=3, INTERNAL=1`);
   defaults (`DEFAULT_EXTENSIONS`, `DEFAULT_STABLE_MS=2000`,
   `COALESCE_MS=200`, `FALLBACK_POLL_S=1.0`, `RECHECK_MS=1000`, `PUMP_MS=16`,
   `OVERSAMPLE=2`, `DOUBLE_CLICK_S=0.4`, `FIT_FLOOR=320`,
   `DEFAULT_CYCLE_S=9`, `MIN_CYCLE_S=1`, `CYCLE_CHECK_MS=250` (the short
   main-thread timeout that fires cycle advances when the deadline is due,
   §5.7/§12.9)); desktop strings
   (`APP_ID`, `ICON_SVG`, `DESKTOP_MIMETYPES`, `IDLE_TEXT`, `WAITING_TEXT`,
   `IMAGE_GONE_TEXT`).
2. **Data** — `Observed` (per-path: `mtime_ns, size, last_change_mono`); `Snapshot`
   (displayed: `path, mtime_ns, size, width, height, label`).
3. **Selection layer (pure, unit-tested)** —
   `scan_candidates(dir, exts) -> [(path, mtime_ns, size)]` (applies §5.1, follows symlinks,
   skips broken links);
   `update_observed(obs_map, cands, now_mono) -> obs_map`;
   `is_settled(obs, now_mono, now_wall, window) -> bool` (§5.3);
   `pick_best(settled_cands, snapshot) -> path|None` (§5.2 switch/tie/reload rules;
   live mode);
   `order_cands(cands) -> [(path, mtime_ns, size)]` (navigation list, §5.5:
   (mtime_ns, name) descending);
   `nav_target(list, cur, direction) -> path|None` (§5.5 one step older/newer, clamped;
   `None` = keypress is a no-op);
   `cycle_target(ordered, anchor_key, failed_versions) -> path|None` (§5.7 cycle
   advance: first settled candidate strictly newer than the anchor `(mtime_ns,
   path)` not in `failed_versions`, scanning newest-first; else the oldest
   non-failed candidate (wrap); `None` when the list is empty or every
   candidate is a failed version);
   `fit_window(mode, img_w, img_h, box_w, box_h, screen_w, screen_h, header_h, sf)
   -> (win_w, win_h)|None` (§5.6/R24 window-fit geometry; `None` = no fit — `off`
   mode or missing monitor box);
   `probe_dimensions(data) -> (w, h)|None` (§5.6 R24 early fit: intrinsic pixel
   dimensions from an image header — PNG, JPEG, WebP VP8/VP8L/VP8X, GIF, BMP;
   TIFF, unrecognized, or truncated input → `None`);
   `newest_for_report(cands) -> path|None` (§4.3 tie-break; unaffected by R23).
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
   (R22), file target (R21), manual navigation `pinned_path` + `Left`/`Right`/`n`
   (R23, §12.9), window fit `fit_mode`/`fitted` + `r` + `_monitor_box()` (R24, §5.6/§12.7), window icon (R20).
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
    cands   = scan_candidates(dir, exts, target_file)
        # §5.1 — file target (R21, rev 1.7.4): the directory's candidates plus
        # the target file itself (its extension bypasses exts, §5.1/§4.2)
    obs     = update_observed(obs_map, cands, mono_now)
    settled = [c for c in cands if is_settled(obs[c.path], mono_now, wall_now, window)]
    # file target (R21, rev 1.7.4): its FIRST display is an immediate load at
    # process start (as a manual selection); this settle-gated branch re-displays
    # the pin only after it has settled (reappearance restoration, R23).
    if pinned_path is not None:                       # manual mode (R23, §5.5)
        if pinned_path not in cands:
            show_image_gone()                         # black canvas + message (R16);
            return                                    # pin PERSISTS — restore on reappear
        if snapshot is None or snapshot.path != pinned_path:
            if is_settled(obs[pinned_path], mono_now, wall_now, window):
                request_load(pinned_path)             # (re)display the pin (dual buffer)
            return                                    # unsettled → stay on the message
        if version(pinned_path) == snapshot.version:
            return                                    # hold (displayed version unchanged)
        if is_settled(obs[pinned_path], mono_now, wall_now, window):
            request_load(pinned_path)                 # R4 in-place reload (§12.5 machinery)
            return
        return                                        # rewrite in flight — hold display;
                                                      # Left/Right are no-ops (§5.5)
    elif cycle_mode:                                  # cycle mode (R27, §5.7)
        # display-holding = the pinned branch with pin = the displayed path:
        # no live switching (R3 suspended); an in-place update of the shown
        # slide reloads once settled (R4); a deleted shown slide does NOT
        # enter image-gone — the last decoded slide holds until the next
        # advance (the canvas holds the last decoded slide).
        ...
    best    = pick_best(settled, snapshot)            # §5.2 (live mode) → path | None
    if best is None:
        show_waiting()                                # R8 (text hidden in --fullscreen,
                                                      #   R16)
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
        # R24 fit pass — once, on the first displayed load, before the swap:
        if not fitted and fit_mode != "off" and not fullscreen:
            size = fit_window(fit_mode, pixbuf.width, pixbuf.height,
                              box_w, box_h, screen_w, screen_h, header_h, sf)
            #    (box/screen = the window's *current* monitor, §12.7)
            if size: window.resize(*size)          # canvas + header (§12.7)
            fitted = True
        picture.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))   # §13.2 (non-deprecated)
        snapshot = Snapshot(path, mtime_ns, size, pixbuf.width, pixbuf.height)
        if not fullscreen:                            # R16: image only, no header
            header.update(basename, f"{w}×{h}", mtime_local)
        hide_waiting()

on_cycle_tick():                                      # main thread, CYCLE_CHECK_MS
    if not cycle_mode: return                        # timer disarmed on exit anyway
    if now_mono < next_advance_mono: return          # fixed deadline (R28)
    next_advance_mono = now_mono + cycle_s           # next interval = full cycle time
    interval_start_mono = next_advance_mono
    ordered = current scan's settled list (order_cands)   # §5.5
    if ordered is empty:                             # R8 — mode stays active
        show_waiting()
        return
    if snapshot is None:                             # no display yet / resumed after empty
        target = ordered[-1] if start_oldest else ordered[0]  # --cycle: oldest first (R29)
        start_oldest = False
    else:
        anchor = nav_anchor(ordered, snapshot.path, snapshot)   # §5.5 (virtual ok)
        target = cycle_target(ordered, anchor, failed_versions)
    if target and target's version != snapshot.version:
        request_load(target)                         # ordinary decode (R7/R15)

on_cycle_adjust(delta):                              # Up = +1, Down = -1 (R28)
    cycle_s = max(MIN_CYCLE_S, cycle_s + delta)      # floor 1 s (Down at 1 s: no-op)
    if cycle_mode:                                   # rescale the current interval:
        elapsed = now_mono - interval_start_mono     #   elapsed time is preserved
        next_advance_mono = now_mono + max(0.0, cycle_s - elapsed)
        # cycle_s < elapsed → deadline in the past → advance at the next tick
    update the `· cycle {cycle_s}s` indicator
```

`pick_best` returns the same path+version as the snapshot → nothing happens (no decode).

`r` (R24, §4.4): re-runs `fit_window` on the *snapshot's* dimensions and
`window.resize` when the result is defined — no `fitted` bookkeeping, no rescan;
no-op in `off` mode, in `--fullscreen`, and with no snapshot on display.

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
    │                    + " · cycle {N}s" while in cycle mode (R28; hidden in --fullscreen, R16)
    │                    or "no file" in the idle state (R22)
    └── Gtk.Overlay          (left double-click → toggle full screen, R19)
        ├── Gtk.Picture        (hexpand/vexpand, content_fit=CONTAIN, can_shrink=True;
        ├── Gtk.Label          (feedback overlay, R30: bottom center — halign
                                CENTER, valign END + bottom margin = 10% of the
                                window height, kept on resize; 2.5 em
                                pale-yellow text, #ffffb5, on a semi-transparent
                                gray shade, rgba(70,70,70,.65) + padding +
                                rounded corners; `riview-feedback` CSS class;
                                hidden by default; `cycle on: {N}s` /
                                `pause` / `newest live image` / `cycle: {N}s`;
                                1 s one-shot hide, §5.8)
        ├── Gtk.Label / box    (keyboard help, R32: centered — halign/valign
                                CENTER, normal font size (≈1×, not 2.5×), same
                                #ffffb5-on-gray family, `riview-help` CSS class;
                                hidden by default; §5.9)
        ├── Gtk.Label          (prompt info, R33: bottom-center column — halign
                                CENTER, valign END + bottom margin = 22 % of
                                the canvas height (re-computed at show time,
                                on full-screen toggle, on display change, and
                                at an r re-fit — 1.8.2, and live on a
                                windowed resize — 1.8.3); word-wrapped at
                                80 % of the rendered image width (capped at
                                80 % of the canvas, floored at 50 % — 1.8.2),
                                elided beyond 50 %
                                of the canvas height (`…` on the last visible
                                line); 1.5 em pale-yellow text, #ffffb5, on
                                the rgba(70,70,70,.65) shade, `riview-info`
                                CSS class; hidden by default; no timer —
                                stays until `i` again, text updated on every
                                display change, §5.10)
        └── Gtk.Box (center)
            └── Gtk.Label      (waiting/idle state, wrapped, max 60 chars, class
                                riview-waiting; never shown in --fullscreen:
                                "Waiting for images…" /
                                IDLE_TEXT (R22) /
                                IMAGE_GONE_TEXT (R23) /
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
  is never shown, so the window contains only the black canvas and the image —
  except the canvas overlays (R30 feedback, R32 help, R33 prompt info —
  below).
- **Feedback overlay (R30, §5.8):** a `Gtk.Label` in the same `Gtk.Overlay`
  (bottom center: `halign=CENTER`, `valign=END`; the bottom margin = 10% of
  the **canvas** height is computed at **show time** from the canvas
  container's (`Gtk.Overlay`) current allocated height (`get_height`) — no
  resize signal is tracked:
  GTK4 has no window size-changed signal and a 1 s transient does not need
  live tracking; the two window signals tried first do not exist on this
  box's build — `window-handle-size-changed` needs a newer libadwaita,
  `size-allocate` is a GTK3 signal GTK4 removed), CSS
  class `riview-feedback` (added to the existing
  `STYLE_PROVIDER_PRIORITY_USER` provider — R17 bullet): `color: #ffffb5`
  (slightly yellowish), `font-size: 2.5em` (≈ 2.5× the normal size),
  `background-color: rgba(70, 70, 70, 0.65)` (the semi-transparent gray shade
  behind/around the text, with `padding: 10px 18px` and
  `border-radius: 8px`, that tones down the image brightness where the
  message shows), hidden by default.  The key handler shows it (text per §5.8)
  only when a feedback keypress is
  effective (windowed **or** full-screen mode), and arms/restarts a 1 s
  one-shot `GLib.timeout_add` hide (no-argument callback, §13.2); a further
  feedback keypress replaces the text and restarts the timer; `_set_fullscreen`
  hides it immediately; it is never shown at startup. Purely cosmetic — it
  touches no cycle, selection, decode, or sizing state.
- **Keyboard help (R32, §5.9):** a `Gtk.Label` (or a `Gtk.Box` of lines) in the
  same `Gtk.Overlay`, centered (`halign=CENTER`, `valign=CENTER`), normal font
  size (≈1× — not 2.5×), the same `#ffffb5`-on-`rgba(70,70,70,0.65)` family under
  the `riview-help` CSS class (added to the same USER-priority provider, R17
  bullet); hidden by default; the text is the normative §5.9 list. The key
  handler shows it on `h`/`?` (hiding an active R30 feedback first — the two
  never coexist); any subsequent keypress hides it *before* normal dispatch
  (bound keys then execute as usual; their R30 feedback may show after the
  dismissal). Purely cosmetic — it touches no cycle, selection, decode, or
  sizing state; cycle slides continue underneath.
- **Prompt info overlay (R33, §5.10):** a `Gtk.Label` in the same
  `Gtk.Overlay`, bottom-center column (`halign=CENTER`, `valign=END`), the
  same `#ffffb5`-on-`rgba(70,70,70,0.65)` family under the `riview-info` CSS
  class (same USER-priority provider, R17 bullet) at `font-size: 1.5em`;
  hidden by default. `show_info()` (from `i`) first dismisses the help (the
  R32 dismiss-then-dispatch path — the two never coexist), runs
  `extract_prompt` (§12.11) on the **currently displayed file** (the
  snapshot's path; `no information` when no image is displayed — waiting /
  idle / image-gone — or when the file carries no prompt), sets the text,
  positions the label (bottom margin 22 % of the canvas height; wrap width
  `min(0.8·canvas_w, max(0.8·image_w, 0.5·canvas_w))` — 1.8.2 patch: the
  column hugs the rendered on-canvas image width (the current R24 layout's
  letterbox extent), capped at 80 % of the canvas, floored at 50 % of the
  canvas; the pre-patch rule is the `image_w ≥ canvas_w` special case;
  a line budget derived from the font's line
  height elides content beyond 50 % of the canvas height, the last visible
  line ending in `…` — both margins re-computed at show time from the canvas
  container's allocated size, as R30's 10 % margin; **1.8.3: a windowed
  resize reflows live** — `_info_poll()` (the GLib timeout contract:
  zero arguments, a `True` return keeps the source — §13.2) is a **50 ms**
  `GLib.timeout_add` source installed by `show_info()` and removed by
  `hide_info()` / shutdown via `GLib.source_remove` (zero cost when
  hidden): each poll compares the canvas's allocated size against the
  last applied size and, on change, re-runs the layout half of
  `info_update()` — wrap / elision / margin — from the cached **full**
  (unelided) extracted text, no extraction; a resize always forces a
  redraw, so the reflow follows the drag within one poll period (~50 ms
  — imperceptible). The frame-clock tick (`_info_tick(frameclock)`) was
  the original 1.8.3 mechanism, but this PyGObject invokes tick
  callbacks with a non-standard argument count — a TypeError on the
  first frame (the §13.2 convention family) — hence the timeout), and
  shows it. **Update on display change:** the display-swap
  path (the `_on_load_ok` handler that installs a new snapshot, §12.5) calls
  `info_update()` whenever the overlay is visible: re-run the extraction on
  the new snapshot's file and **re-apply the text and the wrap width** (the
  rendered image width can change between slides — 1.8.2); visibility kept — a
  bounded (8 MiB) synchronous file read on the main thread, at most a few
  milliseconds for expected file sizes. `h`/`?` hide an active info overlay
  before showing the help (no restore); `i` with the help displayed is
  handled by the R32 dismiss-then-dispatch path. `_set_fullscreen` **keeps**
  the overlay and re-runs the positioning (new canvas dimensions) when
  visible; an `r` re-fit re-runs it while visible (1.8.2 — a re-fit can change
  the rendered image width). `do_shutdown` hides it (removing the poll,
  1.8.3). No timer of its own (unlike R30's one-shot
  hide). Purely cosmetic — it touches no cycle, selection, decode, or sizing
  state; cycle slides continue underneath, updating the text.
- **Window fit (R24):** the window is sized through two paths. **Early fit**
  (at construction, §5.6): if a candidate is already settled, the size is the
  `fit_window` result for that file's `probe_dimensions` header size (header
  height = the 47 px fallback, unallocated) and is applied as
  `set_default_size` *before presentation* — the only reliable client-side
  window sizing on this binding. **Fit pass / `r`** (post-map): the portable
  `_resize_window` helper (§13.2) — `resize(w, h)` where the binding exposes
  it (GTK < 4.14); pre-presentation `set_default_size(w, h)`; post-map, a
  `set_size_request(w, h)` minimum *grows* the window to the target and a
  short timer releases the clamp (`set_size_request(-1, -1)`) once the window
  reports the size (or after 2 s), so it stays freely user-resizable; a target
  at or below the current size is left alone (compositor-mediated on Wayland).
  The monitor box comes from **the monitor the window is currently on** —
  `display.get_monitor_at_surface(window)` — with fallback to
  `get_primary_monitor()` (where the binding exposes it) and then
  `get_monitors()[0]`; the pre-image default (construction, window not placed
  yet) uses the same fallback chain directly. The monitor's pixel size comes
  from `get_geometry()` (logical px — the GTK3-era `get_width()/get_height()`
  were never in the GTK 4 gir, §13.2). The scale factor is the window's own
  (`get_scale_factor()` — the current monitor's in mixed-DPI), and `header_h`
  from `header.get_height()` (GTK ≥ 4.10; `get_allocated_height` is deprecated
  and this binding warns about it — §13.2), fallback 47 px when not yet
  allocated. The post-map resize and the paintable swap happen in the same
  main-thread step (§12.5), so the window size and the image land together.
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

### 12.9 Keyboard shortcuts & signal handling (R18, R23, R24, R25, R26, R27, R28)

- **Keys:** a `Gtk.EventControllerKey` on the window handles `key-pressed`: `q` →
  `window.close()` (last-window close quits the `Gio.Application`, exit 0); `f` → toggle
  per the window's own `fullscreen_mode` flag (the only code that changes it —
  deterministic, no compositor round-trip); `Esc` → un-fullscreen, only when currently
  full-screened. A key is acted on only when `state` carries no modifier beyond
  `SHIFT_MASK`/`LOCK_MASK` (the binding exposes no `IS_*` masks, §13.2), so `Ctrl+q` etc.
  are not consumed. The handler returns `True` to consume the event.
- **Movement keys (R23/R25/R26, §5.5):** `Left`/`Right`/`Home`/`End`/`p` are
  handled in the same handler, same modifier rules (bare key or Shift only;
  windowed and full-screen alike). Each is **two-phase** (rev 1.5): *attempt*,
  then `pinned_path = the displayed path` (the pin phase — a no-change attempt
  therefore still pins, freezing the live display). `Left`/`Right` (`_nav`):
  the navigation list is the current scan's settled candidates in `order_cands`
  order; the anchor is `nav_anchor(ordered, cur, snapshot)` — the displayed
  path's own entry when it is a settled candidate, else `(cur, the snapshot's
  mtime_ns)` (virtual position for image-gone / rewrite-in-flight); `nav_target`
  yields the first candidate strictly on the requested side of the anchor
  (`(mtime, path)` tuple order), or `None` → the display is unchanged. A
  resolved target that differs from the display issues an ordinary decode
  request (dual-buffered; fast successive keypresses supersede via the
  generation counter, §12.5). `Home`/`End` (`_jump`): same scan; the target is
  the list's first / last entry (absolute — no anchor), `None` when the list is
  empty. `p` (`_pause`): no attempt; pins the displayed path. `n`: `pinned_path
  = None` (live mode) + an immediate rescan (cheap, §6.2) — the newest settled
  candidate displays per R1. All movement keys and `p` have no observable effect
  in the idle state (R22); in the waiting state there is nothing to pin. A file
  target (R21, rev 1.7.4) starts with `pinned_path` = the target file (manual
  mode) and an immediate first load — this full key table applies from there.

  **Keyboard help (R32, rev 1.7 amendment 4):** `h`/`?` call `show_help()` (which
  first hides any active R30 feedback — the two never coexist). While the help is
  visible (`help_visible`), the key handler first sets `help_visible = False` and
  then dispatches the key through the normal path: bound keys execute as usual
  (their R30 feedback may then show — e.g. `n` → `newest live image`); `h`/`?`
  dispatch to nothing (dismiss-only, no re-show); unbound keys are ignored. The
  help is purely cosmetic (R28 clock, R3 selection, R7 decode, R24 sizing
  untouched — cycle slides continue underneath; a later press acts on the current
  slide). Nothing shown at startup; `--print` unaffected.

  **Prompt information (R33, rev 1.8):** `i` toggles the overlay via
  `show_info()` / `hide_info()`. `show_info()` runs `extract_prompt` (§12.11)
  on the **currently displayed file** (the snapshot's path; `no information`
  when no image is displayed — waiting, idle, image-gone — or when none is
  found), sets the label text, and shows it; with the help displayed, the
  R32 dismiss-then-dispatch path closes the help first (the two never
  coexist). The display-swap path (§12.5) re-runs the extraction on the new
  file whenever the overlay is visible and updates the text in place
  (update-on-swap, §5.10). `h`/`?` hide an active info overlay before
  showing the help (no restore — no state is remembered). A full-screen
  toggle keeps the overlay and re-runs its positioning from the new canvas
  dimensions. `do_shutdown` hides it. `i` shows no R30 feedback.

  **Prompt copy (R34, rev 1.8 amendment 5):** `Ctrl+C` is the key handler's
  single exception to the bare-keys modifier gate (Ctrl — plus Shift — +
  `c`, matched before the gate): it calls `copy_prompt()`, which runs
  `extract_prompt` (§12.11) on the **currently displayed file** (the
  snapshot's path); when a prompt is found it writes it to the standard
  system clipboard — the C ABI call
  `gdk_clipboard_set_text(gdk_display_get_clipboard(display), text, -1)`
  (NUL-terminated UTF-8, multi-line prompts included), resolved from
  `libgtk-4.so.1` with standard-library **ctypes** only — this system's
  PyGObject typelib (GDK 4.14, reduced introspection) exposes the
  `Gdk.Clipboard` object but **no text-clipboard helpers** (`Gtk.Clipboard`
  is GTK 3; the GTK 4 text helpers — `Gtk.Text.copy_content`, `Gdk.Text` —
  are absent from the typelib and the library's exports here) — and shows
  the R30 overlay `prompt copied`; when there is no displayed image or no
  prompt it does nothing (no clipboard write, no overlay). With the help
  displayed, the R32 dismiss-then-dispatch path runs first (the help is
  dismissed, then the copy — and its `prompt copied` overlay — proceeds).
  The R33 info overlay is left in place. Purely cosmetic beyond the
  clipboard write.

  While in **cycle mode** (R27), every one of these keys
  first stops the cycle (`cycle_mode = False`, `next_advance_mono = None`,
  indicator cleared) and then applies the semantics above against the
  currently displayed slide (a settled candidate — the anchor is its own
  entry).
- **Cycle keys (R27/R28, §5.7):** `c` — idle state: no-op; already cycling:
  no-op; else (live, manual, or the waiting state — armed) →
  `pinned_path = None`, `cycle_mode = True`,
  `interval_start_mono = next_advance_mono = now_mono + cycle_s` (first
  advance after a full interval), start the `CYCLE_CHECK_MS` (250 ms)
  deadline-check timeout, show the `· cycle {N}s` indicator.
  `space` (R31): dispatch in the same handler — while cycling, the `p`
  path (`_cycle_stop` + `_pause`); otherwise the `c` path (`_cycle_start`);
  the overlay shows the dispatched action's text (R30).
  **Startup (`--cycle`, R29):** the flag sets `cycle_mode = True`,
  `start_oldest = True`, `pinned_path = None` at process start (before any
  display); the first tick selects the **oldest** settled candidate
  (`ordered[-1]`, §12.5), clears `start_oldest`, and from there on the cycle
  runs as above (first advance a full interval after the first display). For a
  **file target** (R21, rev 1.7.4) the first slide is the **target file**
  instead of the oldest — it is already displayed (immediate load, pinned) at
  process start, so the first tick simply selects it.
  `cycle_s` is `--cycle-time`, else `--cycle`'s value, else the 9 s default
  (validated in §4.2 — when both give a time, `--cycle-time` takes
  precedence, rev 1.7.3). `Up`/`Down` —
  `on_cycle_adjust(±1)` (§12.5): `cycle_s` clamped to the 1 s floor, and
  while cycling the **current** interval is rescaled — the deadline becomes
  `now + (cycle_s − elapsed)` (elapsed preserved; a new time below the
  elapsed time pulls the advance forward to the next tick); update the
  indicator; work outside cycle mode as well (stored value only — no
  deadline exists). `f`/`Esc`/`r`/canvas double-click — no effect on cycle
  mode. The deadline check (§12.5 `on_cycle_tick`) runs on the main thread
  via `GLib.timeout_add(CYCLE_CHECK_MS, …)` (no-argument callback, §13.2)
  and is disarmed on cycle exit and on window close. `--cycle-time` feeds
  the initial `cycle_s` (validated ≥ 1 in `validate()`, exit 2 otherwise).
- **Feedback overlay (R30, §5.8):** after a feedback keypress (`c`/`p`/`n`/
  `Up`/`Down`/`space` — the latter showing the text of its dispatched action,
  R31) has been processed, when the keypress was **effective** (the named
  change happened — §5.8 mirrors the no-op rules), the handler — in windowed
  and full-screen modes alike — sets the overlay label's text (`cycle on:
  {N}s` / `pause` / `newest live image` / `cycle: {N}s`), shows it, and
  arms/restarts the 1 s one-shot hide timeout (main thread, no-argument
  callback, §13.2). No-op keypresses leave the label untouched (both modes —
  rev 1.7.1); `_set_fullscreen` (the `f`/`Esc`/double-click path) hides it
  immediately. The overlay touches none of `cycle_mode`, `cycle_s`, or the
  deadline (cosmetic, R28).
- **Fit key (R24, §5.6):** `r`/`R` (same bare-key/Shift rules as R18) → `_refit()`:
  when a snapshot is on display, `fit_mode != "off"`, and the window is not
  full-screened, compute `fit_window(...)` from the snapshot's dimensions and
  `window.resize(...)` when defined; otherwise a no-op. `r` does not touch
  `pinned_path` or `fitted` and issues no rescan.
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
  `False` (one-shot). **Closure calling convention (latent-defect fix, found while
  verifying case 43):** this GLib/PyGObject invokes the `unix_signal_add` closure with
  **no arguments** (user_data None — the C-doc "passed the signal number" convention
  does not hold here), so the signature is `_on_signal(self, signum=None)` — both
  conventions accepted. With a required `signum`, the first terminal `Ctrl+C` printed a
  `TypeError` and the one-shot source was consumed, so only the second press (Python's
  default SIGINT path) exited.

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
  - `file` (R21, rev 1.7.4) — watcher on the *containing* directory; the candidate
    set is the directory's full candidate list **plus the target file** (its own
    extension bypasses `--extensions`, §5.1); the view **starts in manual mode**:
    `pinned_path` = the target file, with an **immediate** first load (no settle
    wait — not through the settle-gated pin branch of `on_rescan`). The existing
    R14 recheck machinery is reused as-is: deletion of the file (or of its
    directory) lands in the image-gone state (pin persists, R23); recreation
    (after it settles) restores the display.
  - `none` (R22) — no watcher, no decoder, no pump; label = `IDLE_TEXT` (wrapped, max
    60 chars), subtitle `no file`.
- **File-target settle (rev 1.7.4):** the first display is immediate (above);
  subsequent in-place updates of the pinned file are settle-gated as usual
  (R4/R6 — the file must be static for the window before it reloads).
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

### 12.11 Prompt extraction (R33, rev 1.8)

```
extract_prompt(path, bound=8 MiB) -> str | None:
    data = read(path, first `bound` bytes)         # OSError -> None
    if PNG (magic \x89PNG):
        walk the chunks after the 8-byte signature
        (4-byte BE length + 4cc + body + CRC); for a tEXt / zTXt / iTXt
        chunk with key in {parameters, prompt, Prompt, Comment} (zTXt:
        zlib-decompress the body after key + method byte; iTXt: skip the
        lang tag and the UTF-8 flag):
            return split_parameters(decode-utf8-replace(body))
        return None                                 # first match wins;
                                                    # no such key -> None
    if JPEG (\xff\xd8):    payload = the APP1 "Exif\0\0" segment
    if WebP (RIFF/WEBP):   payload = the "EXIF" chunk
        return tiff_usercomment(payload)            # tag 0x9286, CIPA ASCII
                                                    # or Unicode, padding
                                                    # stripped; None if absent
    return None                                     # unknown format

split_parameters(value) -> str:
    # stable-diffusion.cpp / SD.Next convention: the prompt first, then
    # metadata line(s) beginning with one of the keys below
    for i, line in enumerate(value.split("\n")):
        if line.strip() starts with one of
           ("Steps:", "CFG scale:", "Sampler:", "Seed:", "Size:"):
            return value[:i].rstrip()
    return value.rstrip("\n")
```

The `prompt_extract` prototype (a standalone script next to `riview`, not
imported by it) implements this algorithm; it was validated against
`lemonade` (stable-diffusion.cpp service) images, where the prompt arrives in
a `tEXt` chunk with key `parameters`, the metadata line following the
prompt. The source set in §5.10 is the **change point** as other generators
are used (e.g. ComfyUI's JSON `prompt` chunk, A1111 variants) — the
`split_parameters` split keys and the chunk/key set are the two knobs.

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
- **This PyGObject's calling conventions deviate from the C docs in both
  directions (1.8.1 / 1.8.3):** `unix_signal_add` closures are invoked
  with **zero arguments** (not the C-doc signal number — §12.9), and
  `add_tick_callback` (frame-clock) callbacks are invoked with a
  **non-standard argument count** — `TypeError: takes 2 positional
  arguments but 3 were given` for a `(self, frameclock)` signature
  (found while verifying 1.8.3). The zero-argument `GLib.timeout_add`
  convention is consistent throughout this program by contrast (cycle
  tick, R30 timer, deferred reposition, recheck) — periodic observation
  uses that, not the frame clock (§12.7).
- **Launch-context probe (R22):** `os.open("/dev/tty")` succeeds iff the process has a
  controlling terminal (verified headless and in terminals). `DESKTOP_STARTUP_ID` is the
  startup-notification launch-id set per launch by conforming launchers (GNOME/COSMIC shell
  integrations); its presence is sufficient for GUI context but its absence is *not* proof
  of a terminal.
- `Gdk.Display.get_monitor_at_surface(window)` (installed typelib 4.14.5) returns the
  monitor a window is currently on — the R24 fit budget/cap and `r` are measured on
  it. **Caveat:** this system's PyGObject binding (3.48.2) does **not** expose
  `Gdk.Display.get_primary_monitor()` / `get_monitor(n)` (deprecated in GTK 4.14,
  hidden by PyGObject), and the GTK 4 gir has no `Gdk.Monitor.get_width()` /
  `get_height()` at all (GTK3-era API) — so `riview` ≤ 1.1.0's `_init_size()`
  silently degraded to the 1280×960 fallback on every GTK 4 machine. Monitor
  pixel size therefore comes from `get_geometry()` (the monitor's rectangle in
  the display's coordinate space, logical px). Window resizing (§12.7):
  `resize()` where exposed (GTK < 4.14), else `set_default_size()` **before
  presentation only** — verified no-op on a mapped window on this binding /
  Wayland-COSMIC — else, post-map and grow-only, a `set_size_request()`
  minimum released on the next settle (shrink is compositor-mediated on
  Wayland; GTK 4.14 deprecated `gtk_window_resize()` for exactly this reason).
  Also deprecated in this GTK: `Gtk.Widget.get_allocated_height()` (use
  `get_height()`, 4.10) — PyGObject emits a `DeprecationWarning` for it, so
  the header height is read via `get_height()` first. Portable chains (§12.7):
  monitor `get_monitor_at_surface` → `get_primary_monitor` (if present) →
  `get_monitors()[0]`; monitor size `get_geometry` → `get_width` / `get_height`
  (if present); header height `get_height` → `get_allocated_height` (only when
  `get_height` is absent — calling the deprecated method even to probe a zero
  allocation emits a `DeprecationWarning`).
- **PyGObject GLib timeout contract:** `GLib.timeout_add(interval, fn)` invokes
  `fn()` with **no arguments** — the C `g_source_func(source, user_data)`
  signature does not apply to Python callbacks. A mismatched signature raises
  `TypeError` on every tick, and the post-map fit's clamp release (§12.7) then
  never runs — the `set_size_request` minimum stays in place and the window is
  **permanently unshrinkable by hand** (observed on COSMIC, GTK 4.14.5). The
  release is regression-tested with a real `GLib.MainLoop` spin (§11 case 8h).
- **Post-map grow requires a verified current size (`RESIZE_TOL`, 8 px).**
  The current window size is queried via `get_width()` / `get_height()`
  (GTK ≥ 4.10), falling back to `get_allocated_width` / `get_allocated_height`
  (only when `get_width` is absent — on the installed binding the allocated
  pair is deprecated and warns), then `gtk_window_get_size()` — **observed
  reporting 0×0 on a mapped window** (Wayland/COSMIC, GTK 4.14.5 /
  PyGObject 3.48.2), so it is a last resort only. The post-map fit grow is
  issued only when the current size is verified smaller than the target by
  more than the tolerance on at least one axis; when the size is
  unverifiable (0×0) the grow is skipped. Reason: on COSMIC a min-size
  change — **including the later clamp release** — can make the compositor
  re-apply the window's **remembered size**. Observed: the fit pass saw a
  0×0 current size and issued a blind `set_size_request(1455, 1502)` even
  though the window was already 1455×1502 (early fit); the window snapped
  to a smaller non-ratio size exactly when the release
  (`set_size_request(-1, -1)`) ran. With the verified-size rule the fit
  pass is a no-op in the common case (early fit already sized the window),
  so no min-size change ever happens.
- **`RIVIEW_DEBUG=1`:** traces the fit/resize decisions to stderr (early fit,
  fit pass, `r`, each `_resize_window` branch, clamp release) and logs every
  window size change with a timestamp (`SIZE t+…s: old -> new`, 100 ms poll)
  — the diagnostic for compositor-side resize interference: with the
  verified-size rule the fit pass is a no-op in the common case, so any
  logged size change after presentation is not caused by riview's resize
  code. Silent by default.
- **COSMIC window-size clamping (upstream bug, D15):** the COSMIC
  compositor reconfigures mapped windows larger than a certain size — there
  are upstream bug reports, and the behavior is **not** related to the
  window's position on screen (observed on Pop!_OS 24.04 / COSMIC: a
  1455×1502 `ratio`-fit window was reconfigured to 1455×1230 within ~200 ms
  of mapping, and every grow past the limit was clamped back; a 512×559
  `exact`-fit window was unaffected). riview cannot prevent the reconfigure
  from the client side; the workaround (D15) caps the `ratio` fit box at
  1600×1200 logical px so the fitted window stays below the clamping
  threshold. The `SIZE` watch (§13.2, `RIVIEW_DEBUG=1`) and the late check
  after a reached grow log any reconfigure, so a future COSMIC fix can be
  detected and the cap raised or deleted.

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
