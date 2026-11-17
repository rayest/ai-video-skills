---
name: explainer-video
description: Make a vertical explainer / review / launch short video about a topic (讲解、测评、新品介绍短视频, "XX 模型发布了，核实资料做个视频"). Verify facts against official sources, generate showcase images, write a Chinese voiceover with word timings (Doubao TTS), then render a keynote-style 1080×1920 video whose cuts land on the beat and whose pop-ins land on the spoken word, with an original score and SFX synthesized in code. Also for follow-ups on such a video (改节奏, 重新配音, 换镜头).
---

# Topic explainer short video

A 60–90 s vertical video (1080×1920) in a "keynote" look: black background, very large type, full-bleed images, beat-synced cuts, an original score and sound effects, all rendered with Python (PIL + numpy) and ffmpeg. No video editor, no stock music.

Worked example: `examples/gpt-image-2.6/` (RESEARCH.md, script.json, render.py, audio.py, build_all.sh) produced a 92 s, ~20 MB video about an image-model launch. Copy and adapt it rather than starting from zero. Its showcase images are not in the repo; generate your own with `scripts/gen_image.py`. Read `references/render-pipeline.md` before any render.

Settings come from the environment or a `.env` file (see `.env.example`). Never print keys, their lengths or prefixes.

## Content rules (learned the hard way)

- **Result in the first 2 seconds.** Open on the most impressive output, not on a title.
- **Nothing backstage on screen or in the VO**: no API relay or vendor names, no "generation failed" notes, no costs you actually paid.
- **No ad ending.** Don't pitch a service in the last third — videos that did performed badly. End on a copyable instruction card ("截图保存") plus a brand-free question for the comments.
- **Don't measure speed on a bad network.** Quote official price and speed claims and attribute them ("官方说"); don't present your own timings as facts.
- **Judge honestly.** Look at every generated image and say what is weak, not only what is strong. Crop anything resembling a real brand or store sign.

## Flow

1. **Verify.** Check every claim against the official site, docs, changelog and pricing, plus community threads. Keep `RESEARCH.md` with sources (example in the worked example). If a page returns 403, cross-check through coverage and say so.
2. **Format**: 1080×1920, 60–90 s, unless the user says otherwise.
3. **Showcase assets**: `python3 -I scripts/gen_image.py assets/<name> --prompt "..." [--size 2:3] [--ref img.png] [--gif 12:150] [--markup layer.png]`. Results and billing go to `assets/results.jsonl` (for you, never for the video).
4. **Script**: `script.json` as `{"scenes":[{"id":"s01","vo":"..."}]}`. About 6 characters per second at speech_rate 8 (520 characters ≈ 85 s). End with the CTA question. **Show the script to the user before TTS** — TTS is billed.
5. **Voice**: `python3 -I scripts/tts_doubao.py script.json build/vo [ids] [--dry-run]`. Writes `<id>.mp3` and word timings `<id>.json`.
6. **Render**: follow `references/render-pipeline.md`.
7. **Deliver**: path, duration, size, measured LUFS and peak, which stills were checked, and the 1–2 weakest shots with reasons. Ask before any billable regeneration beyond what was agreed.
