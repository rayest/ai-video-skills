---
name: product-promo-from-repo
description: Prepare a product promo / launch video (宣传片、产品介绍视频、功能演示片) for a software product whose source code is in a git repo — storylines, a shot-by-shot spec, a MiniMax voiceover (配音), an original score synthesized in code, and the product's screens redrawn in HTML from the repo's frontend and backend code. Use whenever the user wants a promo, launch film or demo video "for this app / project / repo", or gives a GitHub URL or local project and says "做个视频".
metadata:
  title: 代码仓库变宣传片
  category: 视频创作
  summary: 读代码拿到真实的功能和文案，写故事线和分镜，用 HTML 按源码重绘产品界面，配音配乐一起出。
  tags: 宣传片, 分镜, 界面重绘, 配音
  status: stable
  needs: MiniMax 语音 API Key；Python 3（含 scipy）、ffmpeg
  try: 给这个仓库做一个 40 秒的产品宣传片，要配音
---

# Product promo from a repo

A 30–45 s film that shows one viewer doing one real task in the product, with real labels from the code, a voiceover and an original score. This skill covers getting the product right from its code, the story, the voice, the music and the redrawn screens. It does not prescribe a rendering engine; pick one with the user (prefer free tools).

## 1. Read the right code

- `git fetch --all` and compare branches (`git log -1 origin/<b>` for each) before reading anything. The default branch can be stale — `main` may still be the initial commit while the product was renamed and rebuilt on `dev`. Building storylines on the wrong branch wastes a full round. If the user says the name or features changed, believe them and find the branch that has it (`git grep -c <new name> origin/<b>`).
- Collect facts, not impressions: the navigation (the product's own map of what it does), the main task flow's page components, catalog names in backend seed data, real limits and numbers (max lengths, formulas like "预估秒数 = 字数 ÷ 4.5"). Every claim in the film must trace to one of these.
- Copy the logo and thumbnails/icons from the repo into `assets/`. Check the logo has no old brand text in it.

## 2. Storylines, then stop

Write three storylines into `STORYLINES.md` (each: one-line premise, beat list with times, the transition that carries each seam) and stop for the user to pick. The one that has worked best for a multi-step product: **one object travels through the product's steps** (a found post → a topic card → a script → a finished video), entered through the cursor grabbing it. Put your recommendation first.

State the assumptions in one line: length 30–40 s, 1920×1080, music + effects, voiceover yes/no, product data on screen is demo data.

## 3. Voiceover (MiniMax)

Only when asked. Key in `$MINIMAX_API_KEY` or the first line of `~/.minimax_key`; never print it.

1. One short line per beat into `voice/script.json` (`[{"id", "text"}]`), ~4.5 Chinese characters per second, ~120–140 characters for 35–40 s. Lines are cause and effect, not slogans; the screen shows keywords, never the spoken sentence verbatim.
2. Show the user the lines, voice id and model, and get a yes — each call is billed. `python3 -I scripts/tts_minimax.py voice --dry-run` prints the character count and estimated length.
3. Generate once: `python3 -I scripts/tts_minimax.py voice [--voice ID]` → `vo-<id>.mp3` and `durations.json`. Regenerate one line with `--only id`.
4. The voice is the clock: lay scenes out from `durations.json` (each line starts ~0.15–0.25 s into its scene; scene ≈ line + 0.3–0.6 s).

## 4. Product screens: redraw from code

Don't run the app or mock its backend for screenshots; rebuild the screens in HTML from the components, CSS and backend data. Read `references/ui-redraw.md` before the first product scene.

Label demo data `演示数据 · 虚构`. Never show an old product name or logo, and never invent a button the code does not have.

## 5. Music and effects

- `scripts/score.py` synthesizes an original track whose bar grid puts a downbeat on the payoff and the logo hit a whole number of beats later (needs numpy + scipy):
  `score.py assets/bgm/score.wav --total 38.5 --bpm 104 --hook-end 4.6 --reveal 9.8 --build 24.2 --payoff 27.0 --claim 31.6 --logo-beats 13`
  Pick `--logo-beats` so `payoff + beats × 60/bpm` lands where the end card's mark lands.
- Effects from free sources (click, whoosh, pop, typing, riser, impact, sparkle). One sound per visible cause.

## 6. Spec and review

- Write `SPEC.md` before the scenes: GOAL, OUTPUT, TIME, VOICE, DATA, LOOK, OBJECTS, MOTION, SHOTS with times, BANNED, QA frames.
- Check every beat and seam: fix seams whose motion direction flips (an object leaving right must enter the next scene from the right), elements fading before they land, empty halves of a hero frame.
- Write `REVIEW.md`: creative calls, what was measured vs. only looked at, the weakest shot.
- Final audio: about -16 to -14 LUFS, true peak ≤ -1 dBTP, no clipping. Say the sound was measured, not heard.
