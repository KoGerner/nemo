# Harbour, pinned for the skin (ticket 287)

Synced 2026-10-02 from the Claude Design system **AI4BCM Harbour** (project
`89a65edf-48d8-42ce-a6a9-f8fe93b79dc5`), by way of nemo_design's read-only mirror
`~/work/nemo-builds/design-2026-10-02/harbour/` (its `SYNCED.md`). `styles.css`, `tokens/*.css` and
`assets/fonts/*.woff2` are that mirror byte for byte; the fonts match `~/work/ai4bcm-site/src/assets/fonts/`.
Never edit them here: re-sync all of them from the project and change the date above.
Not from Harbour: nemo's own colours are its own file `tokens/nemo-colors.css`, imported after `colors.css`, under one comment
marking them nemo-own: the five `--color-class-*` tokens, chart A's impact classes (ticket 403 r2), and the six
`--kind-*` tokens, the graph's resource kinds (tickets 354 and 356, spec §12.14 F1; moved out of `colors.css` by
403 r5). A re-sync never touches that file, and `tokens/colors.css` is the mirror's, byte for byte.
One exception inside a Harbour file, nemo's own and kept on a re-sync: `assets/fonts/inter-var.woff2` (Inter 4.1's `InterVariable.woff2` from the rsms/inter release, sha256
693b77d4…a8e3, its OFL licence in `inter-LICENSE.txt`) and its `@font-face` at the end of `tokens/fonts.css`
(ticket 355): the graph pages' face.

`harbour.css` is nemo's own and the one stylesheet every skin page links (`<root>/harbour/harbour.css`, served
by the skin with the fonts, so no page fetches anything from off the box). It imports the tokens and the
fonts and not `tokens/base.css`, which restyles the body and the headings: 288-293 restyle each page.
`skin/tests/test_t287_one_harbour_source.py` fails any colour the skin serves that is not in `tokens/`.
