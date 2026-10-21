# Journey media

`about-asa-oz-short.mp4` — the looping film on the About page (478×850, 72 s,
muted). The poster image next to it is the first frame.

It is re-encoded rather than re-shot whenever the file changes, so the size
stays sane:

```bash
ffmpeg -i about-asa-oz-short.mp4 -an -c:v libx264 -preset slow -crf 22 \
       -pix_fmt yuv420p -movflags +faststart about-asa-oz-short.mp4
```

- `-an` drops the audio track: the video is muted and loops, so it was never
  heard.
- `crf 22` is the quality dial. At the time of writing: 13.5 MB → 7.0 MB
  (-48%), SSIM 0.988 and PSNR 44.4 dB against the previous file, which is
  visually indistinguishable.
- `-movflags +faststart` puts the index at the front so the browser can start
  playing without downloading the whole file.

Check a re-encode before committing it:

```bash
ffmpeg -i original.mp4 -i new.mp4 -lavfi ssim -f null -   # SSIM All
ffmpeg -i original.mp4 -i new.mp4 -lavfi psnr -f null -   # PSNR average
```
