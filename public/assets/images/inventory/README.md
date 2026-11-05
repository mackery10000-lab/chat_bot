# Inventory artwork

The seven item illustrations are copied byte-for-byte from the user's
`drive-download-20261101T100753Z-1-001.zip`:

| Archive entry | Asset |
| --- | --- |
| 2026 승차권.png | ticket-current.png |
| 2016 승차권.png | ticket-old.png |
| 붉은 표시 실종 신문.png | newspaper.png |
| 손전등.png | flashlight.png |
| 구형 열차 안내서.png | facility-manual.png |
| 노인 동그라미.png | elder-testimony.png |
| 보고서.png | route-report.png |

`warning.png` preserves the additional warning artwork from the same archive.
The existing first-car warning interaction retains its previously supplied image.

`scrapbook.png` is the earlier blank book skin, retained as a source artifact.
The current UI uses `book-overview.png`, `book-detail.png`, `photo-mount.png`,
and the printed `records/` and `actions/` PNG files. Only owned items appear;
opening the collection never marks an item as read. The detail screen uses the
server's existing document response, including separate images for learned
testimony and the returned-ticket annotation. No scrolling HTML explanations
are drawn over the book.

The current image prompts, source roles, font/music integration and validation
are documented in `../../../../docs/INVENTORY_AUDIO_UPDATE.md`. Rebuild the
printed content with `runtime/python.exe tools/export_inventory_records.py`,
then `powershell -NoProfile -ExecutionPolicy Bypass -File tools/print_inventory_art.ps1`.

Earlier scrapbook generation prompt (the current UI uses the assets above):

> Use case: ui-mockup. Asset type: production bitmap skin for a vintage mystery
> train game's inventory. Input images: the last two user attachments are STYLE
> AND COMPOSITION references: open aged inventory scrapbook and its detail screen.
> Generate ONLY the empty open scrapbook itself, no items, no text anywhere, no UI
> buttons. Match the reference closely: top-down, wide landscape open antique
> dossier with two equal blank ivory parchment pages, straight central vertical
> spine at exactly 50% width, leather dark brown backing, layered battered page
> edges, faded coffee water stains, subtle creases, restrained beige grain, worn
> tabs protruding at top/bottom. One realistic aged brass paperclip at upper left
> edge. Book nearly fills image: paper readable interior from 6%-94% x and 10%-90%
> y, flat usable pages for HTML overlay. Extremely important: no inset panels, no
> lettering, no photographs, no drawings, no ticket, no preprinted rules/tables,
> no heavy central shadows on writable area, no hands. Same mature restrained
> photographic game art as references, real paper NOT synthetic orange grunge.
> Outer area truly transparent, opaque paper. Landscape 3:2 aspect ratio.

The locally bundled Korean fixed-width font is NAVER D2 Coding, from
https://github.com/naver/d2-coding-font/tree/master/fonts/ttf.
Its SIL Open Font License is included at `../../css/D2CODING_LICENSE.txt`.
No online font requests or image API calls are made during play.
