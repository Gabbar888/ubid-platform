# Frontend assets

Drop the real Karnataka government logo here.

## Where to get one

The official **Government of Karnataka emblem (Gandaberunda)** is available from:

- Wikipedia (free, public-domain rendition):
  <https://en.wikipedia.org/wiki/File:Seal_of_Karnataka.svg>
- Wikimedia Commons:
  <https://commons.wikimedia.org/wiki/Category:Coat_of_arms_of_Karnataka>
- The official Government of Karnataka website
  <https://www.karnataka.gov.in/> — right-click the emblem in the header

## File name conventions

The header loader looks for **the first file it finds** in this order:

1. `karnataka_logo.svg`   ← preferred (vector, scales perfectly)
2. `karnataka_logo.png`   ← good fallback (transparent background ideal)
3. `karnataka_logo.jpg`   ← works but no transparency
4. `logo.svg` / `logo.png` / `logo.jpg`   ← generic fallback

Drop your file here with one of those names. No code changes needed —
the header will pick it up on next Streamlit restart.

## Sizing tips

- Aspect ratio: **square** (1:1) renders best in the 64×64 crest slot.
- For PNG / JPG: at least **256×256** so it stays sharp on retina screens.
- For SVG: any size; it scales infinitely.
- If the logo has a coloured background (not transparent), best results
  come from cropping it tight to the emblem.

## Quick check

After dropping the file:

```powershell
# Restart frontend so it picks up the new asset
docker compose restart ubid-frontend
```

Then hard-refresh the browser. The crest at the top-left of the header
should now show your image instead of the hand-drawn fallback.
