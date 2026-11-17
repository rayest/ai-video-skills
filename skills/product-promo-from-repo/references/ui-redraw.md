# Redrawing the product UI from the repo

The film shows the product, so every screen must be the real product — but you do not need the product running. Rebuild the screens in HTML from the source. This is faster and more reliable than launching the app and mocking its backend to take screenshots (in an earlier film that path cost dozens of steps: missing deps, crashes on `{}` responses, auth gates; the user stopped it and asked for a redraw).

## Where each piece comes from

| On screen | Read it from |
| --- | --- |
| Navigation labels, order, groups, page titles and subtitles | the nav/router component (e.g. `AppNavigation.tsx` with a `pages` array) |
| Field labels, placeholders, button text, empty states | the page components; grep for CJK strings: `grep -oP "[\x{4e00}-\x{9fff}][^<>'\"{}]{0,40}" File.tsx` |
| Colours, radii, font sizes, widths | the CSS the component uses (`grep -n "\.class-name" src/**/*.css`) |
| Catalog names (templates, plans, categories) | backend seed / defaults files (e.g. `video_templates/infrastructure/defaults.py`) |
| Data shapes (what a result row contains) | the TS types (`types.ts`, `model.ts`) — show the real fields, fill them with demo values |
| Logo, thumbnails, icons | copy the files from the repo (`src/assets/`, `public/`) into `assets/` |

Grep the code for the old product name before you start: if the brand was renamed, the latest branch is where the new name lives.

Anything not in the source — search results, authors, like counts, generated copy — is demo data: make it plausible for the user's market, keep it consistent across scenes, and label the product shots `演示数据 · 虚构` (bottom-right, out of the way of the topbar).

## The shell pattern

Build the app at its own logical size (1600 x 900 works for a desktop app) inside a `.cam` wrapper with `transform-origin: 0 0`, then move the camera instead of the UI:

```js
// app point (px, py) at frame centre at scale s
const cam = (s, px, py) => ({ scale: s, x: 960 - s * px, y: 540 - s * py });
tl.set("#dc-cam", cam(1.2, 800, 450), 0);             // whole app fills 1920x1080 (establish)
tl.to("#dc-cam", { ...cam(2.0, 720, 500), duration: 0.6, ease: "power2.inOut" }, 1.95); // isolate
```

Body text in the real UI is 11–15 px; at scale 2.0–2.4 it reads at 26 px+. Wide shots only establish where we are; the beat's text must be read in a push.

The sidebar + topbar repeat in every product scene, so generate them from one small helper and emit the scene files from a generator. After the first generation treat the HTML as the source — hand edits land there, and re-running the generator overwrites them.

Put the cursor inside the app (`.app` coordinates), so its targets are the same numbers as the layout.

## Coordinate pitfalls (each one cost a fix round)

- `position: absolute` children of a padded container are placed from its **padding box**: `left: 0` inside `.content { padding: 22px 32px }` is at the content's outer edge, not +32. Compute targets from that.
- Compute every cursor target and every camera centre from the layout numbers, then snapshot the moment of each click and look: a cursor 40 px off a button reads as a miss.
- A frame-level element that must match an in-cam element (e.g. the preview that grows into the payoff) needs its frame rect = `cam.x + s * appX`, `cam.y + s * appY`, size × s.
