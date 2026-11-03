# 13-Fri UI artwork

Generated raster assets for the image-based train game interface. All assets were created with the built-in `image_gen` tool using the user's supplied game UI references. Transparent PNG alpha is preserved. The application uses these local files directly.

| Files | Purpose |
| --- | --- |
| `menu-card.png`, `inventory-card.png`, `journal-card.png`, `hint-card.png` | Matching worn dark clipboard tool buttons with ivory pictograms and paper labels |
| `dialogue-paper.png` | Dialogue paper, empty burgundy speaker tab, metal paperclip, faded railway masthead |
| `note-paper.png` | Shared blank paper for requested hints and map labels |
| `choice-paper.png` | Flat narrow paper strips for the two contextual action choices; generation prompt in [CHOICE_PROMPT.md](CHOICE_PROMPT.md) |
| `hint-paper.png` | Burgundy premium paper with a fine antique gold rule for the single requested hint action; edit prompt in [HINT_PROMPT.md](HINT_PROMPT.md) |
| `archive-paper.png` | Shared archival paper for documents, notice and ending |
| `chat-input.png` | Distressed dark input frame with ivory paper send area and printed airplane |
| `train-route.png` | Seven connected cutaway train interiors: four passenger cars, crew room, exit vestibule, final engine control room |
| `ticket-item.png`, `flashlight-item.png`, `book-item.png` | Illustrated inventory objects |

The speaker, dialogue, input and location labels remain live HTML. Map locations retain their original game IDs, navigation actions and locked/current states.

HUD cards render at a fixed 64×64 CSS pixels across viewport sizes. The map retains its native 3:1 ratio on a fixed 1000px canvas, with horizontal scrolling in narrower viewports. The dialogue paper keeps its visible 2045:502 ratio. The input uses a sliced border image, keeping the paper send area and its pictogram at a fixed size while the blank center adapts to the available width. The original PNGs are unchanged.

The current location is shown as a five-second translucent overlay when entering a location; the permanent paper location/time plaque is removed.

The action area normally shows two ordinary scene or character interactions, independent of the unfinished quest step. Neither button automatically advances a puzzle. Requesting a hint replaces them with exactly one actionable priority task on burgundy paper, marked HINT. Using that card or performing another interaction restores the normal choices. The hint action is authorized on the server only after an explicit hint request; evidence and final control input still require the player's own decisions. Sliced border images preserve the paper ends while live Korean labels wrap.

Character interactions draw on the authored dialogue: reasons for boarding, familiar scenery, the elder's recent memories, the cleaner's work, the attendant's concern and the driver's difficulty stopping. Asked topics move behind other questions for that character. This conversation history changes the available small talk without advancing quest flags, describing the lost ticket, selecting evidence or filling the final code.

## Generation prompts

All requests: production game artwork matching the supplied sepia night-train UI references; natural worn materials rather than flat vector shapes; no modern glossy styling. The following are the final prompt briefs. Full generation prompts are preserved in [PROMPTS.md](PROMPTS.md).

- Tool cards: isolated transparent worn black-olive clipboard with aged ivory edging and small metal top clip, printed ivory menu lines / briefcase / journal / light bulb, cream paper footer reading MENU / INVENTORY / JOURNAL / HINT. Each generated separately.
- Dialogue: long pale ivory archival paper with fine fibers and subtle stains, thin worn double ink border, folded bottom-left corner exposing burgundy backing, empty burgundy speaker tab, old metal paperclip upper right, faded 13-FRI / THE TRAIN THAT NEVER ARRIVES masthead at right; blank dialogue area.
- Note: blank pale ivory old paper with subtle fibers, light stains and irregular edges, landscape format.
- Archive: square blank aged ivory archival paper with faded border, small tears and folds.
- Input: long low charcoal input bar with fine distressed ivory double outline, chamfered left corners and blank dark interior; rightmost 12 percent pale paper with a dark printed paper airplane pointing upper right; transparent exterior; no baked placeholder.
- Route: old sepia parchment chart with seven connected, enclosed cutaway train sections; four passenger cars, crew room, exit vestibule, then the engine control room inside the final carriage; engraved circular medallions, amber interior lamps, worn dark metal and brass, continuous tracks; no baked location labels or selection highlights. The exit vestibule retains the existing disembark action and station description.
- Items: isolated transparent cutouts of an aged cream railway ticket with burgundy printing, antique brass handheld flashlight, and worn burgundy railway manual with ivory pages. Each generated separately.
