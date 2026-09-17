# Brag Plan: Devansh OS

## What is this app?
A self-hosted, always-on dark dashboard that watches your actual life — GitHub, LeetCode, gym, sleep, Claude usage — and tells you, in red, exactly what you haven't done. There is no pause button.

## The angle
The joke is the "no kill switch" philosophy delivered completely straight, like a compliance system. This isn't a productivity app that cheers you on — it's a surveillance system for your own laziness with zero forgiveness setting. The video plays it as deadpan as the product itself: calm typography, cold color, no hype music, just facts landing like verdicts. The funnier we make it feel, the less funny we make it sound.

## Hook (first 2-3 seconds)
Black screen. Terminal-mono text types out, no fanfare:
`Gym: last activity 6 days ago.`
Beat. Then, flat, smaller: `It knows.`

## Key moments (the middle)
- The neglect banner itself, live from the product: `✕ 1 critical  ! 2 warning`, red/amber chips landing one by one (Gym 6d ago, LeetCode 3d ago, Sleep 5.4h avg).
- The activity heatmap grid filling in — dense terminal squares (commits/solved/workout/sleep rows), same dark palette as the real dashboard.
- The Life-in-Weeks calendar: full-viewport 52×90 grid of your entire life in weeks, the current week pulsing, a milestone flag pinned to one cell — memento mori, rendered as a UI feature.

## Outro / punchline
Cut to the "no kill switch" line, typed out cold: `No rest mode. No vacation mode. No pause button. Ever.` Hold. Then the wordmark: `◐ Devansh OS` with the tagline `it just tells you the truth.`

## User flow worth showing
1. Entry: dashboard loads, header clock ticking, "today: 1 workout · 4 commits" summary chip.
2. Key action: the neglect panel resolves to red/amber criticals with real "last activity Nd ago" copy.
3. Result: user opens the Life Calendar overlay — the full life-in-weeks grid, current week pulsing, one milestone flag visible.

## Tone
- Preset: deadpan
- Creative direction: a surveillance system for your own laziness, presented with zero remorse
- Interpretation: long holds, minimal motion, monospace type doing the talking. No swooshes, no triumphant swells — cuts are clean and a little cold. Humor comes entirely from the gap between how serious the delivery is and how petty the thing being reported is (you didn't go to the gym).

## Format: landscape — 1920x1080
## Duration: 19s

## Visual identity (from the project)
- Background: `#0a0c0f` (near-black), panels `#11141a` / `#161a21`
- Accent: crit red `#cf5772`, warn amber `#d0a83e`, ok green `#3f9a5a`, info blue `#4391d6`
- Text: `#c9d1dc` (body), `#eef2f7` (strong), `#6b7480` (dim)
- Display/body font: Inter (sans), with monospace (`ui-monospace` / JetBrains Mono / SF Mono) for data, clock, and terminal-style copy — mix both, monospace carries the punchlines
- Strongest visual element: the neglect banner's red/amber chip row, and the Life-in-Weeks 52×90 grid with a pulsing current-week cell

## Share copy (draft)
I built a dashboard that has no forgiveness setting. It just tells you what you didn't do.

## Audio direction
- Role: sparse, cold, restrained — accents, not a bed that carries the emotion
- Music: `happy-beats-business-moves-vol-10-by-ende-dot-app.mp3` (60s track, 109.96 BPM), used at low volume, ducked well under the typed text and UI sounds — its "happy" energy is intentionally undercut by flat delivery, not leaned into
- Music treatment: start near-silent under the hook, fade up slightly through the neglect/heatmap section, dip again for the outro line, hard fade out under the final wordmark
- Music cue guidance: preset read from `happy-beats-business-moves-vol-10` cues. Strong cues cluster at 15.82s, 18.01s, 18.55s, 20.19s, 20.74s, 21.83s, 22.92s, 24.01s — track runs faster than our 19s target, so treat these as a rough tempo reference (~0.55s/beat) rather than literal timestamp targets; snap only the outro wordmark landing to the nearest beat if it falls naturally. Restraint note: deadpan tone — use cues sparingly, prefer a dry key-tick or UI blip over a musical hit for reveals.
- Audio-reactive treatment: none — keep the surface still and let type/UI sounds carry rhythm
- SFX posture: sparse; a dry terminal key-tick under typed text, a single low UI "alert" blip when the neglect banner turns red, a soft card-arrival tick for each chip/heatmap fill-in
- Audio-coupled moments: hook line types with key ticks; neglect chips arrive one by one with a tick each; heatmap cells fill with a very quiet rapid patter, not a swell
- Restraint rule: no whoosh, no rising synth swell, no triumphant hit on the punchline — the joke dies if the audio tries too hard

## Storyboard

### Scene 1 — The verdict — 3s
Black screen, terminal-mono text types out center-frame: `Gym: last activity 6 days ago.` Hold 1s after typing completes. Then a flat, smaller line fades in beneath: `It knows.`
Sequential/interaction: yes — the headline types out character by character
Audio intent: cold, still, almost silent — a system stating a fact, not an ad
Audio-coupled idea: typing key-ticks synced to characters
Music: near-silent, barely-there bed starting under the second line
Transition mood: hard cut → Scene 2

### Scene 2 — Neglect panel — 4s
Recreate the real neglect banner: `NEGLECT DETECTION  ✕ 1 critical  ! 2 warning`, then the three rows land one by one — `✕ Gym: last activity 6 days ago`, `! LeetCode: last activity 3 days ago`, `! Sleep: 7-day avg 5.4h`. Red/amber color exactly as the product.
Sequential/interaction: yes — three neglect rows arrive one at a time, each with a tick sound
Audio intent: procedural, deadpan — like a system log, not a drumroll
Audio-coupled idea: one dry tick per row arrival; single low blip on the "1 critical" chip
Music: quiet bed present, no swell
Transition mood: clean hard cut → Scene 3

### Scene 3 — Activity grid — 4s
The real dashboard's heatmap grid fills in — commits / solved / workout / sleep rows of small terminal squares in the dark palette, populating left to right quickly.
Sequential/interaction: yes — heatmap cells populate in a fast rapid patter (not per-cell reveals, a quick fill)
Audio intent: mechanical, ticking, still cold
Audio-coupled idea: quiet rapid patter texture, very low in the mix
Music: bed holds steady, slight lift
Transition mood: clean crossfade → Scene 4

### Scene 4 — Life in Weeks — 5s
Cut to the full-viewport Life Calendar: 52×90 grid of tiny squares, most filled and dim, the current week's cell pulsing, one milestone flag icon pinned. Title overlay: "Life in Weeks — every box is one week."
Sequential/interaction: none — one held wide shot, the pulse is the only motion
Audio intent: quiet, still — this is the most serious beat, give it space
Audio-coupled idea: none, let the pulse breathe without a sound cue
Music: dips slightly lower here
Transition mood: slow crossfade → Scene 5

### Scene 5 — Outro / punchline — 3s
Typed line, cold and center: `No rest mode. No vacation mode. No pause button. Ever.` Hold, then hard cut to wordmark: `◐ Devansh OS` with tagline `it just tells you the truth.`
Sequential/interaction: yes — punchline types out, then wordmark appears
Audio intent: flat delivery to the end — no triumphant hit
Audio-coupled idea: key ticks on the typed line only; silence under the wordmark
Music: fades out under the typed line, gone by the wordmark
Transition mood: hard cut → end

**Music mood for this video:** deadpan (an upbeat bed intentionally undercut — used quiet and restrained throughout)
**Audio summary:** A near-silent, ticking, procedural soundscape — typing key-ticks and one low alert blip carry the rhythm, the music bed stays low and disappears entirely by the punchline, so nothing softens the deadpan delivery.
