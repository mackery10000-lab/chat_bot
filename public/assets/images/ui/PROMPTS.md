# UI icon image prompts

Generated with the built-in image_gen tool (transparent PNG). The MENU asset is the design anchor, with companion buttons made by constrained edits of that raster. All final alpha channels were preserved by byte-for-byte copying into the project.

## menu-card.png

Source: C:\Users\김명준\.codex\generated_images\01a195ef-bac0-7311-8c74-6dc575cd589f\exec-3945d3d5-5e83-41c2-ac78-8856c81edce8.png

Prompt:

```text
Use case: stylized-concept
Asset type: one transparent PNG inventory-system UI button for a vintage night train mystery game.
Primary request: faithfully recreate the tactile old MENU clipboard icon shown in the user's closeup reference image: one worn, nearly black olive vertical rectangular board with a thin doubled aged ivory metal edge, gently irregular clipped upper corners and a small tarnished brass binder clip at its top. Three rough hand-painted ivory horizontal menu lines on the board. A ragged, uneven, faded cream paper ribbon pasted across the bottom with black old book serif lettering.
Text (verbatim): "MENU"
Style/medium: cutout of a physical handmade 1930s railway ephemera game prop; scanned painted material, natural paper fibers, restrained distressed wear, softly stained ivory, dull scratched metal; authentic worn object with imperfect edges and subtle warm scene lighting.
Composition/framing: a single isolated icon centered, tilted about 8 degrees counterclockwise, occupies 88% of square canvas with only a narrow transparent margin. Slight flat oblique view like supplied MENU reference. The cream ribbon overhangs both sides of the board.
Constraints: actual transparent alpha background, no scene, no ground or cast shadow beyond silhouette, no extra objects, no UI mockup, no outline around image, no additional text. Keep legible at 100px. Visually close to the user's reference.
Avoid: modern clean vector geometry, glossy 3D rendering, large white background, gold glow, decorative scrollwork, excessive damage, grunge splatter.
```

## inventory-card.png

Source: C:\Users\김명준\.codex\generated_images\01a195ef-bac0-7311-8c74-6dc575cd589f\exec-bc118f1e-8d6b-4ede-8ed4-9e1000989d52.png

Prompt:

```text
Use case: precise-object-edit
Asset type: transparent PNG vintage train mystery game UI icon, matching the provided physical MENU icon.
Primary request: make the INVENTORY companion button. Keep the board, scale, lean angle, material, worn cream border, clip, bottom paper label shape, warm lighting, transparent background, object framing, and tactile painted printed period style unchanged. Replace ONLY the three menu lines with one simple solid ivory silhouette of an old briefcase with a short arched handle, two clasp details, and a dark narrow horizontal seam, like the supplied user's inventory icon. Replace only the label word "MENU" with "INVENTORY", spelled exactly I N V E N T O R Y in the same distressed dark serif font, adjusted smaller if needed to fit comfortably centered within the same ribbon.
Text (verbatim): "INVENTORY"
Constraints: same silhouette and design family as input MENU icon, clear icon and readable label at 100px, single isolated object on actual transparent alpha background; no ground, no scene, no shadow outside silhouette. Keep the top clip completely visible inside image.
Avoid: clean vector art, modern icon style, shiny polished 3D, extra text, extra objects, dark rectangular backdrop, large empty margins.
```

## journal-card.png

Source: C:\Users\김명준\.codex\generated_images\01a195ef-bac0-7311-8c74-6dc575cd589f\exec-d750702e-8497-4d33-86f3-727238d88518.png

Prompt:

```text
Use case: precise-object-edit
Asset type: transparent PNG vintage train mystery game UI icon, matching the provided physical MENU icon.
Primary request: make the JOURNAL companion button. Keep the board, scale, lean angle, material, worn cream border, clip, bottom paper label shape, warm lighting, transparent background, object framing, and tactile painted printed period style unchanged. Replace ONLY the three menu lines with one simple ivory line drawing of an old notebook/page with a folded top corner and three short uneven horizontal writing lines. Replace only the label word "MENU" with "JOURNAL", spelled exactly J O U R N A L in the same distressed dark serif font, adjusted smaller if needed to fit comfortably centered within the same ribbon.
Text (verbatim): "JOURNAL"
Constraints: same silhouette and design family as input MENU icon, clear icon and readable label at 100px, single isolated object on actual transparent alpha background; no ground, no scene, no shadow outside silhouette. Keep the top clip completely visible inside image.
Avoid: clean vector art, modern icon style, shiny polished 3D, extra text, extra objects, dark rectangular backdrop, large empty margins.
```

## hint-card.png

Source: C:\Users\김명준\.codex\generated_images\01a195ef-bac0-7311-8c74-6dc575cd589f\exec-180fac0a-1df0-419c-9aa9-5ffe60ec38a3.png

Prompt:

```text
Use case: precise-object-edit
Asset type: transparent PNG vintage train mystery game UI icon, matching the provided physical MENU icon.
Primary request: make the HINT companion button. Keep the board, scale, lean angle, material, worn cream border, clip, bottom paper label shape, warm lighting, transparent background, object framing, and tactile painted printed period style unchanged. Replace ONLY the three menu lines with one simple ivory drawing of an incandescent lightbulb, rounded glass outline and short screw base, with three tiny short rays. Replace only the label word "MENU" with "HINT", spelled exactly H I N T in the same distressed dark serif font, adjusted smaller if needed to fit comfortably centered within the same ribbon.
Text (verbatim): "HINT"
Constraints: same silhouette and design family as input MENU icon, clear icon and readable label at 100px, single isolated object on actual transparent alpha background; no ground, no scene, no shadow outside silhouette. Keep the top clip completely visible inside image.
Avoid: clean vector art, modern icon style, shiny polished 3D, extra text, extra objects, dark rectangular backdrop, large empty margins.
```



# Paper asset prompts

Mode: built-in `image_gen`; one call per asset. Transparent background requested for all assets.

Saved deliverables (RGBA PNG, manually inspected using `view_image`):

| File | Dimensions | Alpha >= 128 bounds (inclusive) | Bytes |
| --- | --- | --- | --- |
| `public/assets/images/ui/dialogue-paper.png` | 2079 × 756 | x 18–2062; y 126–627 | 2,066,888 |
| `public/assets/images/ui/note-paper.png` | 1774 × 887 | x 30–1749; y 66–813 | 2,463,915 |
| `public/assets/images/ui/archive-paper.png` | 1254 × 1254 | x 32–1224; y 31–1228 | 2,818,805 |

Dialogue image contains transparent upper/lower padding. Display with background-size approximately `101.7% 150.6%` and background-position `50% 49.6%` to fit the visible paper+clip to its CSS container; adjust the container aspect ratio to the reference. Exact source pixels are preserved.

## dialogue

```text
Use case: ui-mockup
Asset type: production raster background asset for a vintage mystery train dialogue UI.
Primary request: recreate the material, construction and arrangement of the user's fourth reference image as closely as possible: one very wide low antique cream paper dialogue placard, complete isolated cutout with true transparent exterior.
Composition/framing: straight-on flat front view, horizontal 5:1 paper panel centered and almost filling image width, no perspective, all four edges fully visible; paper itself about 1260 by 230 proportions, with a paperclip extending above top-right and an empty name tab overlapping near the top-left. Leave the left 82 percent of the paper entirely blank for dynamic dialogue text.
Materials/textures: real scanned old book paper, pale warm gray ivory with faint fine fibers and extremely subtle small age marks, not brown parchment. Slightly uneven scuffed edge, a few tiny edge tears. Thin faded charcoal double rule border just inside edges, irregular worn print. Bottom-left paper corner is visibly chipped and folded with a dark oxblood burgundy backing glimpsed underneath; a slender dark burgundy backing also peeks along the lower edge. Small simple old steel wire paperclip attached diagonally across the upper-right corner, long narrow double-loop clip with natural metal highlights and slight tarnish, like the reference.
Name tab: small dark muted burgundy-red horizontal paper label overlaps the top-left edge, width about 15 percent of panel, distressed straight edges, completely blank inside for HTML name text. Do not place any symbols or text on the name tab.
Right-side print: reserve far right 15 percent of panel for faint low-contrast gray old railway stationery printing; a thin vertical divider at 84 percent width; large light faded serif text exactly "13-FRI"; beneath it three much smaller stacked serif lines exactly "THE TRAIN" / "THAT NEVER" / "ARRIVES". An almost illegible faint microprint line above and small thin horizontal ledger rules. Print feels sunk into paper, very light gray, readable only faintly. Left main writing area completely blank.
Lighting/mood: soft flat archival scan, no dramatic lighting, no cast shadow across the blank writing area.
Color palette: pale unsaturated ivory #d7cdb4 to #e1d8c0, charcoal-gray faded border and print, dark oxblood burgundy tab and backing, tarnished gray metal.
Constraints: a single complete reusable UI background asset with transparent surroundings, accurately preserve wide low aspect ratio, no scenery, no game screenshot, no background scene, no Korean or dialogue body text, no extra labels, no vector approximation, no CSS gradient look, no decorative flourishes beyond the exact simple construction above.
Avoid: saturated yellow paper, orange stains, brown scroll, ornate fantasy border, thick gold outline, glossy 3D render, artificial smooth gradient, dense dirty grunge, huge creases, oversized torn holes, cartoon texture, opaque checkerboard.
```

## note

```text
Use case: ui-mockup
Asset type: production raster cutout background for location cards and clue slips in a vintage mystery train UI.
Primary request: create one blank horizontal pale ivory aged paper slip with the same realistic paper material as the user's fourth dialogue reference. A carefully scanned small archival note, natural and quiet, with no writing.
Composition/framing: exact straight-on front view, single horizontal rectangular 2:1 slip, all edges fully visible, centered and almost filling canvas; true transparent exterior, no perspective; large clean blank writing area.
Materials/textures: thin old pale cream paper, warm gray ivory, fine subtle fibers, mild uneven age at the edges, a few tiny pale spots, worn slightly irregular cut edges and a barely visible small fold near one corner, small corner scuffs. The paper should feel physical and tactile yet restrained, like an authentic old train ticket backing.
Color palette: pale unsaturated cream and gray ivory matching the fourth reference, about #d7cdb4 to #e1d8c0, tiny muted gray-brown age marks. Flat soft scan lighting.
Constraints: absolutely no text, no symbols, no icons, no printed lines, no border, no tape, no pin, no paperclip, no illustration. A single paper slip cutout only. Transparent outside paper.
Avoid: yellow saturated parchment, brown leather texture, orange vignette, artificial gradients, fantasy scroll, extreme dirt or tears, glossy 3D look, decorative motifs, opaque checkerboard.
```

## archive

```text
Use case: ui-mockup
Asset type: production raster cutout background for archival documents and modal panels in a vintage mystery train UI.
Primary request: create one blank nearly square aged ivory archival paper sheet, matching the subtle actual scanned paper material of the user's fourth dialogue reference.
Composition/framing: straight-on flat front scan, approximately 1:1 paper sheet centered and nearly filling image, all edges fully visible; real transparent exterior; large empty central writing area.
Materials/textures: pale warm gray ivory paper with fine real fibers, lightly mottled soft gray age, tiny edge scuffs, slightly uneven frayed edges, small unobtrusive edge nicks, one barely visible old fold. A very thin faint double charcoal printed rectangular border inset close to the edge with naturally worn small gaps. Material of a genuine railway archive sheet, restrained, not a theatrical prop.
Color palette: low saturation pale gray ivory #d7cdb4 to #e1d8c0, faint gray printing, very soft neutral archival scan lighting.
Constraints: single blank paper sheet cutout only; absolutely no words, letters, logos, symbols, illustrations, stamps, clips, tape or ornamentation. Keep the center clean for readable dynamic interface content. Transparent outside all paper edges.
Avoid: saturated yellow parchment, dark brown paper, orange vignette, dense dirty grunge, big torn sections, artificial gradients, embossed gold frame, fantasy scroll, dramatic shadows, opaque checkerboard.
```


# Inventory item image prompts

Mode: built-in image_gen tool. All outputs request true transparent alpha backgrounds and are project assets in `public/assets/images/ui/`.

## ticket-item.png

Use case: stylized-concept. Asset type: transparent inventory object cutout for a Korean mystery game set aboard a worn 1930s night train. Create ONE aged ivory railway passenger ticket, a narrow portrait rectangle with softly abraded corners, tiny side perforations, natural paper fibers and faint old handling stains, a thin muted burgundy divider and faded railway print marks with NO readable words, no numbers. Slight three-quarter tilt but front face clear. Detailed hand-painted game illustration with physical texture and restrained amber lamplight from upper left, deep sepia shadows. Center the entire isolated object generously inside a square canvas, object occupies about 80% of height. True transparent alpha background, no setting, no tabletop, no frame, no badge. Do not use vector-style outlines, emoji, simple flat geometry, plastic shine, photoreal product backdrop, glow, or watermark.

## flashlight-item.png

Use case: stylized-concept. Asset type: transparent inventory object cutout for a Korean mystery game set aboard a worn 1930s night train. Create ONE antique handheld railway torch: short cylindrical tarnished brass and dark olive metal body, worn knurled grip, small sliding switch, broad circular head with cloudy glass lens and dark reflector. Position the entire object at a slight diagonal, head upper left and handle lower right, clear recognizable silhouette. Detailed hand-painted game illustration with physical scratches and aged metal texture, restrained amber lamplight from upper left, deep sepia shadows. Center the entire isolated object generously inside a square canvas, object occupies about 80% of height. True transparent alpha background, no setting, no tabletop, no frame, no badge. No light beam and no glow. Do not use vector-style outlines, emoji, simple flat geometry, futuristic LEDs, plastic shine, photoreal product backdrop, text, or watermark.

## book-item.png

Use case: stylized-concept. Asset type: transparent inventory object cutout for a Korean mystery game set aboard a worn 1930s night train. Create ONE small closed railway maintenance manual, portrait proportions, worn muted burgundy cloth cover with battered corners, dark brown cloth spine, thick yellowed ivory paper edges, faint small brass railway emblem on cover but NO legible lettering. Slight three-quarter angle showing front cover, spine and lower paper edge; entire book in view. Detailed hand-painted game illustration with tactile aged cloth and paper, restrained amber lamplight from upper left, deep sepia shadows. Center the entire isolated object generously inside a square canvas, object occupies about 80% of height. True transparent alpha background, no setting, no tabletop, no frame, no badge. Do not use vector-style outlines, emoji, simple flat geometry, plastic shine, photoreal product backdrop, glow, readable text, or watermark.

# Built-in image_gen prompts

## chat-input.png

Use case: ui-mockup. Asset type: single production UI chat input frame PNG, horizontal ultra-wide, transparent background outside silhouette. Match precisely the user's attached FIFTH image, not a new interpretation: antique train mystery game input bar of dark charcoal near-black translucent worn glass, hairline faded ivory rectangular outline, tiny chamfered left corners, understated natural scuffs. Exact silhouette long low bar width:height about 7.5:1. Entire rightmost 12% is a flat pale ivory aged paper rectangle with fibers/stains, faded edge and a single DARK charcoal black solid paper airplane send pictogram pointing upper right centered inside, same ink irregularity as printed antique UI icon, no border circle. Left 88% completely BLANK nearly-black charcoal interior, faint subtle dirty glass, NO text placeholder baked. Very fine double distressed ivory border top bottom left and seam before paper send area. Front-on flat scanned interface, no perspective, no cast drop shadow, no luminous gold, no decoration. Occupy nearly full canvas with tiny 2% transparent padding. Pale cream natural photographic paper matching dialogue reference4; no yellow gradient, no excessive torn corners. This will be stretched as actual background and a real editable textarea overlaid in the black space. Output isolated transparent production asset.

## train-route.png

Use case: historical-scene. Asset type: production game UI illustrated train route background, very wide horizontal strip, target 3072x768. Use the user's final attached train map as the visual reference: tightly match its tactile warm desaturated sepia distressed railway chart, photoreal painted antique black steam train broadside cross-section, dark olive-black metal, worn brass outlines, dim amber lamps illuminating car interiors, old beige brown lightly mottled paper background, railway tracks along bottom. Re-create the same visual design with SEVEN evenly spaced selectable sections left to right (each one-seventh width): 1 antique passenger compartment with wooden seats, 2 passenger compartment upholstered seats, 3 darker passenger sleeping compartment, 4 dining carriage with tables, 5 crew lounge with shelves and books, 6 black steam locomotive with a warmly lit driver's cabin and chimney emitting a little dark smoke, 7 a small misty railway platform with antique station lamp and platform canopy at the right edge. The first FIVE are physically connected antique coaches and sixth engine on continuous track; the platform is simply next to the right of the locomotive. View straight-on orthographic side cutaway like supplied reference. Keep seven visual targets centered at 7%,21%,36%,50%,64%,79%,93% width. Delicate faded horizontal ornamental rule near top. Each carriage has a small antique circular black brass-rimmed medallion centered above roof with engraved simple relevant pale ivory pictogram, tiny medallions (10% image height), all seven same material. Reserve bottom 13% clear parchment so real dynamic nameplates can be overlaid in app; no labels baked. No text, no letters, no numbers, no UI highlights, no colored selections. Composition fills width from edge to edge, five actual connected coaches followed by engine then platform, continuous ground track, no giant empty margin. Main train centered in vertical middle 28%-80%, matching reference proportions. Soft ambient old print lighting, detailed handmade realistic worn textures. Avoid simple geometric train diagrams, vector art, flat modern icons, smooth plastic, oversaturated gold, fancy fantasy embellishments, huge paper rips, giant medallions. Actual game asset.

## train-route.png — current revision: enclosed final engine room

Generated with the built-in image_gen editing tool, using the previous train-route.png as its edit target.

Use case: precise-object-edit. Edit target: the provided train-route.png production game minimap. The user requests ONLY a correction to the last two right-hand sections of this map. Preserve original canvas dimensions and landscape proportions, original sepia parchment and railway tracks, fine ornamental rule, original FIRST FIVE connected cutaway railway coaches (all their interiors, roofs, warm amber lighting, black/brass metalwork and medallions) precisely. Change ONLY the rightmost approximately 30.5% of the image. Remove the external steam locomotive, chimney, smoke, open-air station platform, station lamp and station canopy. Replace that entire right-hand region with TWO ENCLOSED CONNECTED CUTAWAY RAILWAY CARRIAGES, matching the same body height, roofline, floor, wheels and dark metal frame as first five. There must now be EXACTLY SEVEN clearly distinct enclosed interior sections in a single connected train, seven roof medallions, on the same continuous rails. Section SIX spans roughly x69.5%-84.75%, an enclosed interior exit vestibule: warmly lit dark wood corridor with a closed train door inside the carriage, small existing-style circular medallion with ivory door pictogram centered above. Section SEVEN is the FINAL far-right room, spans roughly x84.75%-100%: ENGINE CONTROL ROOM INSIDE THE TRAIN. Show its interior as a clear broadside cutaway of an enclosed passenger-sized dark carriage with surrounding roof, side walls and carriage floor. Inside the seventh room are brass pressure gauges, copper pipes, an old railway control console and levers, lit by warm amber lamps; large open side window/cutaway makes these indoor objects readable at small UI size. Final medallion at x92.5% has engraved pale ivory gear pictogram, same black/brass circular material as existing. End of final room is the train's enclosing vertical exterior end wall, not an outdoor platform. No people, no detached room, no external boiler or locomotive nose, no smokestack, no smoke, no outdoor structure. Keep all seven rooms physically attached at same height, same camera, same styling, same colors and exact aged material treatment. Preserve bottom blank parchment for live HTML nameplates. No text/letters/numbers added. The control room must be unmistakeably a room inside the last train carriage. Do not redesign the first five rooms or the rest of the existing image.
