# Hyperframes Composition Brief: Devansh OS

## Objective
Create a short launch-style brag video for Devansh OS, a self-hosted personal observability dashboard.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 19 seconds (15-25s range)

## Source Material
- Project root: `/Users/devansh/DevDaddy/devansh OS`
- Primary files read: `README.md`, `web/index.html`, `web/src/input.css`, `web/static/js/life.js`
- Product name: Devansh OS
- Tagline / strongest claim: "No kill switch" — no rest mode, no vacation mode, no pause button, ever
- Key UI or visual moment to recreate:
  - The neglect banner: `NEGLECT DETECTION  ✕ 1 critical  ! 2 warning` with red/amber row chips
  - The activity heatmap grid (commits / solved / workout / sleep rows, small terminal squares)
  - The Life-in-Weeks calendar: 52×90 grid, current week pulsing, one milestone flag pinned
- Copy that must appear verbatim:
  - "Gym: last activity 6 days ago."
  - "It knows."
  - "NEGLECT DETECTION"
  - "✕ Gym: last activity 6 days ago"
  - "! LeetCode: last activity 3 days ago"
  - "! Sleep: 7-day avg 5.4h"
  - "Life in Weeks — every box is one week"
  - "No rest mode. No vacation mode. No pause button. Ever."
  - "◐ Devansh OS"
  - "it just tells you the truth."

## Creative Direction
- Tone preset: deadpan
- Creative direction: a surveillance system for your own laziness, presented with zero remorse
- Interpretation: long holds, minimal motion, monospace type doing the talking. No swooshes, no triumphant swells, cuts are clean and a little cold. The humor is entirely in the gap between how seriously the product reports things and how petty the thing being reported is.
- Angle: This isn't a productivity app that cheers you on — it's a compliance system for your own life, delivered completely straight. The "no kill switch" philosophy (no excuses, no pause button, ever) is the whole joke, played dead serious.
- Hook: Black screen. Terminal-mono text types out: "Gym: last activity 6 days ago." Beat. Then flat and smaller: "It knows."
- Outro / punchline: Typed cold: "No rest mode. No vacation mode. No pause button. Ever." Hold, hard cut to wordmark "◐ Devansh OS" with tagline "it just tells you the truth."
- Avoid:
  - Generic SaaS language ("streamline", "boost productivity")
  - Abstract filler visuals, particle systems, waveform/equalizer graphics
  - Any triumphant/uplifting musical swell that undercuts the deadpan delivery
  - Unrelated visual redesign — stay inside the product's real dark terminal-dashboard aesthetic

## Visual Identity
- Background: `#0a0c0f` (near-black), panels `#11141a` / `#161a21`, borders `#1f242d` / `#2a313c`
- Text: `#c9d1dc` (body), `#eef2f7` (strong headings), `#6b7480` / `#474e58` (dim/secondary)
- Accent: crit red `#cf5772`, warn amber `#d0a83e`, ok green `#3f9a5a`, info blue `#4391d6`
- Display font: Inter (sans) for headings/wordmark; fall back to system sans stack `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- Body font: monospace stack `ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace` — used for typed lines, clock, data, and terminal-style copy
- Visual references from the project: dense terminal-dashboard framing (border-boxed panels, small-caps section labels like "NEGLECT DETECTION" / "SYSTEMS" / "ACTIVITY" / "TIMELINE"), the ◐ logo mark, heatmap grid of small squares, the 52×90 Life-in-Weeks grid with a pulsing current-week cell and inline flag icon for milestones

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. The verdict — 3s — hook line types out ("Gym: last activity 6 days ago."), then "It knows." fades in below
2. Neglect panel — 4s — real neglect banner recreated, 3 rows (critical/warning) land one by one in red/amber
3. Activity grid — 4s — heatmap grid (commits/solved/workout/sleep) fills in quickly, dark terminal squares
4. Life in Weeks — 5s — full-viewport 52×90 grid, current week pulsing, one milestone flag, title caption
5. Outro / punchline — 3s — cold typed line, hold, hard cut to wordmark + tagline

## Audio
- Audio role: sparse, cold accents — not a bed that carries emotion
- Audio arc: near-silent under the hook, low bed rises slightly through the neglect/heatmap section, dips again into the Life in Weeks beat (held quiet), fades to nothing under the punchline and wordmark
- Music: `happy-beats-business-moves-vol-10-by-ende-dot-app.mp3` (60s, ~109.96 BPM), kept low in the mix throughout — deliberately undercutting its "happy" energy rather than leaning into it
- Music treatment: fade in low under Scene 1's second line, small lift through Scenes 2-3, dip for Scene 4, hard fade to silence during Scene 5's typed line so the wordmark lands in near-silence
- Music cue guidance: preset at `skills/brag/assets/music/cues/happy-beats-business-moves-vol-10-by-ende-dot-app.music-cues.json` / `.md`. Strong cues cluster 15.82-24.01s; track tempo (~0.55s/beat) is a rough reference only since the video is 19s — do not force literal timestamp reuse. If useful, beat-lock the Scene 4→5 transition or the final wordmark landing to the nearest strong cue within ±0.15s; otherwise use natural timing for readability.
- Audio-reactive treatment: none — keep the surface still, let typing/UI sounds carry rhythm instead of visual pulsing to the music
- Audio-coupled moments:
  - Scene 1 hook line — typing key-ticks synced to characters
  - Scene 2 neglect rows — one dry tick per row arrival, single low alert blip on the "1 critical" chip
  - Scene 3 heatmap fill — quiet rapid patter texture, low in the mix
  - Scene 4 Life in Weeks — no sound cue, let the pulse hold in near-silence
  - Scene 5 punchline — key ticks on the typed line only, then silence under the wordmark
- SFX selection guidance: dry terminal key-ticks for all typed text; a single low "alert" blip for the critical neglect chip; a soft card-arrival tick for each neglect row and heatmap fill moment. Keep everything quiet and mechanical, never bright or celebratory.
- SFX analysis guidance: use `skills/brag/assets/sfx/sfx-analysis.md` if present; prefer low high-frequency-risk sounds since ticks repeat several times across the video.
- Exact SFX choice: Hyperframes should choose filenames, timestamps, density, and volume based on the implemented animation.
- Audio files: copy `happy-beats-business-moves-vol-10-by-ende-dot-app.mp3` and any Hyperframes-selected SFX into `brag-output/composition/assets/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). `/brag` is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (the neglect banner, heatmap grid, and Life-in-Weeks grid all qualify — use all three).
- Keep all text readable in the final render (respect the reading-time floors from the plan).
- Keep the video within 15-25 seconds (target 19s).
- Include the planned music/SFX layer — audio was not disabled.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints; ignore cues that hurt readability, scene pacing, or the product story.
- Major reveals may move toward nearby strong cues within about 0.15s. Smaller entrances may align to nearby beat points within about 0.10s. Use only 1-3 strong cue locks in this 19s video.
- Use SFX to support motion and interaction: card sounds for neglect-row/heatmap reveals, a restrained low blip for the critical alert, key/click sounds for typed text, restraint everywhere else.
- Honor the planned music treatment: quiet start, slight lift mid-video, fade to silence under the punchline/wordmark.
- Audio-reactive treatment is intentionally none for this video — do not wire visuals to RMS/frequency data.
- Use local assets for audio and any required runtime/media dependencies when possible.
- Run `hyperframes check` before render — it is brag's single gate.
