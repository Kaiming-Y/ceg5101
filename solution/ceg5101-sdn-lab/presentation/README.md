# Slides: From 48% Loss to Zero (CEG5101 CA2, Group 5)

Open [CEG5101_CA2_Group5_light.html](source/CEG5101_CA2_Group5_light.html) from the cloned project. It contains the speaker notes and loads the figures and three MP4 videos from the project folders, so keep the directory structure intact for offline playback.

Open the [speaker script](speaker_script.pdf), [PDF handout](CEG5101_CA2_Group5_handout.pdf), or [live demo runbook](Live_Demo_Runbook_zh.pdf) from this folder. For a live demo, run `bash code/demo/live_demo.sh` from the project root in the Mininet VM. Add `quick` for the shorter case b run. Use the [code guide](../docs/Run_Lab.md) for setup.

## Opening the deck

Double-click the HTML file, or drag it into Chrome or Edge. Test video playback on slides 2, 8 and 12 on the presentation laptop. Slides 15 and 16 have stills for slides 8 and 12.

For the talk, press `F` for full screen. The 16:9 stage scales to fit any window.

## Keys

| Key | Action |
|---|---|
| `→` `Space` `PageDown` `Enter`, or a mouse click on the slide | next step (reveal), then next slide |
| `←` `PageUp` `Backspace` | back |
| `Home` / `End` | first / last slide of the sequence |
| number + `Enter` (e.g. `1` `5` `Enter`) | jump to that slide; `Esc` cancels |
| `N` | show / hide the speaker-notes panel |
| `P` | presenter view in a second window: current slide, next step or slide, notes, timer, clock |
| `T` | show / hide an elapsed timer; `R` resets it |
| `H` | add the backup slides 17–23 to the sequence, or skip them again |
| `K` | play / pause the video on the current slide (a click on the video does the same) |
| `B` or `.` | black screen |
| `F` | full screen |
| `?` | key help |

Presenter view opens a pop-up window. If the browser blocks it, allow pop-ups for the file, or use `N` and `T` instead. The keys also work in the presenter window. Put it on the laptop screen and the main window on the projector. The timer starts on the first advance from slide 1 or when `P` or `T` is pressed.

Most presentation clickers send `PageDown` / `PageUp`, so they work without any set-up.

## Slide order

- **1–14 main slides**, in the normal sequence. Most main slides have reveal steps. Slides 8 and 12 use one click to start their video.
- **15–16 hidden still pages**, never in the normal sequence. Reach them with the button on slide 8 or 12, or with `15 Enter` / `16 Enter`. On these pages `→` (or the button) goes on to the slide after the video (9 or 13), and `←` goes back to the video slide (8 or 12).
- **17–23 backup slides**: report plots, per-case table, the 3.8 s detection, forced s5-s6 case, environment and live-demo commands, design decisions and code map, contributions and tools. They are skipped in the normal sequence. Reach them by number, or press `H` to include them. From a backup slide, `→` moves to the next physical slide.

Speaker notes are written for every main slide. Each part is labelled `[Speaker A · Kaiming]` or `[Speaker B · Danze]` and gives its target time and time slot. `[click]` marks a reveal and `[0:15]` marks a video timecode. Slide 23 lists the current contributions and tools.

## Videos

| Slide | Video | Behaviour |
|---|---|---|
| 15 | `assets/video/demo_case_b_still_1..4.png` | stills in case slide 8's video does not play |
| 16 | `assets/figures/replay_r1_still_1..4.png` | stills in case slide 12's video does not play |

Leaving a slide pauses its video. If the speaker falls behind, the partner pauses with `K` or a click on the video. The next `→` then moves on.

## Printing a PDF handout

A ready-made handout is next to the deck: `CEG5101_CA2_Group5_handout.pdf` (23 pages, one per slide, every reveal shown). To print it again yourself:

1. Open the deck in Chrome or Edge and press `Ctrl+P` (`Cmd+P` on a Mac).
2. Destination: **Save as PDF**.
3. More settings: Margins **None**, **Background graphics** on. The paper size comes from the deck itself: one 16:9 landscape page per slide.
4. Save.

The print version has all 23 slides, one per page, with every reveal shown. Videos print as their poster frame. Notes and on-screen controls are left out.
