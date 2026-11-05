# Imported puzzle scenes

Artwork and CSS originate from the user-provided `lever-box.zip` and
`dial-puzzle.zip`. Image files retain their original bytes, dimensions, and
relative control coordinates. `public/assets/js/puzzles.js` adapts the supplied
lever motion and circular dial interaction for the game.

Each scene runs inside a Shadow DOM so its styles do not affect the game HUD.
Fonts use the existing local game font; there are no external font requests.

The lever sends the existing cover, lever-down, and door-handle operations.
The dial sends destination and four digits to `prepare_control`, then uses the
existing confirmation flow. Server rules still enforce evidence, permissions,
the single remaining attempt, and both endings. The standalone demo's embedded
answer and unrestricted retries are not used.
