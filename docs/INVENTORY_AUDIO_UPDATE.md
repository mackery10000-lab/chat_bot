# 인벤토리 이미지·본문 폰트·배경음악

적용일: 2026-11-02.

## 적용

- 제공한 `OG 르네상스 비밀.ttf`를 `public/assets/css/OG-Renaissance-Secret.ttf`로 저장했다. 일반 대화, 입력창, 단어와 목록, 일반 UI 문구에 적용한다. 제목의 기존 서체와 이미지 안 글씨, 타자기 서체는 별도로 유지한다.
- 제공한 `MP_왜 나를 피하는거야_.mp3`를 `public/assets/audio/train-theme.mp3`로 저장했다. 두 파일 모두 SHA-256 비교로 원본 바이트와 동일함을 확인했다.
- 공통 `audio.js`가 시작·발권·게임 화면에서 같은 음악을 반복 재생한다. 자동 재생이 제한되는 브라우저에서는 첫 클릭/키 입력으로 시작한다. 음량과 음소거를 저장하고 화면 이동 시 재생 위치를 이어받는다. 시작 화면의 소리 버튼·음량 설정과 게임 메뉴의 음악 설정을 실제 오디오에 연결했다.
- 수집품 책의 우측 상단 사진과 손글씨 장식, 테이프로 붙인 프레임, 상세 책의 종이 클립과 흐린 인장, 닳은 검은 종이 선택지를 이미지로 적용했다. 아이템 그림은 기존 제공 원본을 유지한다.
- 설명 12개와 버튼 12개는 PNG다. 설명은 기존 D2 Coding 타자기 서체로 인쇄했다. 노인의 증언 4가지 상태와 반환한 승차권 기록을 구분한다. 아직 얻지 않은 단서는 해당 상태의 이미지와 대체 텍스트에 표시하지 않는다.
- 상세 설명에 HTML 문단이나 표를 올리지 않는다. 화면 크기에 맞춰 페이지 이미지를 표시하고 목록은 페이지를 넘긴다. 인벤토리 안 스크롤과 뒤쪽 게임 화면의 스크롤바는 인벤토리를 연 동안 숨긴다. 닫으면 원래 화면 스크롤이 복구된다.

## 제작 파일

| 자산 | 경로 |
| --- | --- |
| 수집품 책 | `public/assets/images/inventory/book-overview.png` |
| 상세 책 | `public/assets/images/inventory/book-detail.png` |
| 모바일용 한 페이지 | `public/assets/images/inventory/record-paper.png` |
| 테이프 사진 프레임 | `public/assets/images/inventory/photo-mount.png` |
| 검은 종이 원본 | `public/assets/images/inventory/action-blank.png` |
| 인쇄된 설명과 버튼 | `public/assets/images/inventory/records/`, `actions/` |
| 설명·문구 원본 | `public/assets/images/inventory/print-source.json` |

책·프레임·검은 종이는 내장 `image_gen`으로 생성/편집했다. CLI/API 대체 경로는 사용하지 않았다. 실제 문구는 생성 모델에 맡기지 않고 서버의 문서 내용을 결정적으로 PNG로 인쇄했다.

## 최종 이미지 프롬프트

첫 번째와 두 번째 첨부 이미지는 각각 수집품 책과 상세 화면의 **시각적 참고**다. 게임에 없는 열쇠·카드·사진 아이템을 추가하라는 지시로 사용하지 않았다.

### 수집품 책

참고: 첫 번째 인벤토리 이미지. 불투명 배경.

```text
Edit the reference image into a production UI background bitmap for exactly this vintage railway inventory. Preserve the reference's exact subdued grey-beige aged paper, creases, tiny stains, thin double-page center seam, flat front-on orthographic presentation, understated pencil ruling, worn corners, and the small old railway photograph taped at the upper right corner. Keep the typography already at the top: INVENTORY, 13-FRI, the tiny railway insignia and handwritten 'Collected Items / Case. 13 - Fri'. The book must fill the entire rectangular image edge to edge at approximately 1.28:1 width/height with no surrounding desk or perspective. IMPORTANT remove ALL eight inventory items, their individual photo frames, tapes, captions and writing from the body of the book, leaving a large blank usable area beneath the header, with only very faint vertical column divisions and faint horizontal guides. This image is a background to which actual owned items will be added in software. Keep the upper right decorative photo. No sample items, no new object names, no extra readable text, no extra floating interface, no fantasy props. Reproduce the quiet old-paper visual of the supplied reference, not a bright yellow modern parchment or exaggerated leather book.
```

### 상세 책

참고: 두 번째 인벤토리 이미지. 불투명 배경.

```text
Create a clean empty UI background bitmap by editing the supplied vintage railway inventory detail reference. Isolate ONLY the open two-page book on the right, exclude the entire dark item list on the left. Remove the ticket, all titles, all paragraph text, table text and the close X tab. Leave the authentic original blank old grey-beige paper with faint writing rules, uneven layered page edges, narrow central vertical binding crease at 44% width, tiny stains, vintage restrained monochrome brown tones. Preserve the long authentic metal paperclip at the top left of the left page and the faint partial circular railway stamp at the bottom right. Keep thin subtle field divider lines on the right page if natural. Flat orthographic front-on scan of the book, edge to edge, 1.45:1 landscape. Left page will hold an item, right page will hold actual rendered description, so no text or illustrated objects in either page. No big glossy fantasy leather binding, no vivid orange/yellow colors, no desk, no shadows outside the book. Match the reference exactly in overall worn feel, subdued texture, paperclip and light stamp detail.
```

상세 책의 최종 편집: 생성된 상세 책을 편집 대상으로 사용했다. 문단을 가로지르는 배경 가로줄만 제거했다.

```text
Precise minimal edit to this production UI book background: remove ONLY the long horizontal ruled lines INSIDE the right-hand page. Keep the very faint marginal frame near the edges if desired, but the main writing area must be plain aged paper so later typewritten paragraphs will not be struck through by existing horizontal rules. Preserve the book silhouette, native aspect ratio, dimensions, aged pale grey-beige paper color, stained texture, fine cracks, center binding at the same exact location, layered page edges, long metal paperclip at upper left, and the faint circular railway stamp at the lower right. Do not add any text, objects, icons, buttons or additional decoration. Both pages remain empty usable old paper. This is the same image with interior right-page horizontal lines cleanly removed.
```

### 검은 종이 버튼

새 자산, 투명 배경.

```text
Production game UI bitmap asset: one single wide horizontal old black paper choice button on a fully transparent background. Aspect ratio approximately 6.5:1, centered panel fills almost the entire canvas. Charcoal ink black faded paper, delicate distressed bronze-beige hairline double border with small bevel-clipped corners, authentic frayed uneven paper edges and subtle tiny beige scratches, softly creased fibers, old 1930s railway investigation scrapbook aesthetic. Quiet tactile almost-black background, slightly lighter middle, no gloss, no gradients resembling modern UI. NO TEXT, no symbols, no icons, no words, no shadows that occupy broad margins, no multiple buttons, no mockup page. Leave wide clear dark center for a later typewritten beige label.
```

### 테이프 프레임

새 자산, 투명 배경과 투명한 가운데 영역.

```text
One single authentic aged scrapbook photo mounting frame as a transparent PNG game UI asset. A rectangular portrait-ish old off-white paper photo border, ratio approximately 0.95:1 width/height, with a completely transparent empty central opening for inserting an actual item photograph. The mount is faded dusty beige, naturally torn worn paper edges, subtly stained and greyed, flat orthographic front scan. Two small real translucent aged masking-tape strips overlapping the top left and top right corners at slightly different angles, realistic tape fibers and uneven torn ends, faint believable contact shadows. Low saturation old railway evidence scrapbook visual, no saturated yellow parchment, no shiny plastic. The center opening MUST be transparent; no photo, object, text, illustration, or grid inside. Outside the mount transparent too. One frame only, no background scene, no UI mockup.
```

## 검증과 재생성

- 자동 테스트: `runtime/python.exe -m unittest discover -s tests -q` — 106개 통과.
- 실제 Chromium 검수: `.local/verify-inventory-audio.mjs`. 1440×1000, 1024×768, 768×1024, 390×844, 320×568에서 책·설명·목록의 영역과 스크롤 여부, 실제 PNG 렌더링, 폰트 구분을 검사했다. 손전등 사용, 보고서 열람 확인, 최종 증거 제출의 확인·취소, 증언별 이미지, 실제 아이템 획득 알림을 임시 게임 저장소에서 확인했다.
- 음악은 실제 MP3로 사용자 입력 후 재생, 음소거, 음량, 화면 이동 후 이어 듣기, 곡 끝을 넘겨 반복 재생되는 동작을 검사했다.
- 브라우저 결과와 스크린샷: `.local/inventory-audio-qa/result.json`, 같은 폴더의 PNG 파일.
- JavaScript 문법 검사와 `runtime/python.exe -I -B launch_game.py --check` 통과.

문구나 게임 문서를 변경하면 아래 두 단계를 차례로 실행한다.

```powershell
./runtime/python.exe tools/export_inventory_records.py
powershell -NoProfile -ExecutionPolicy Bypass -File tools/print_inventory_art.ps1
```

첫 단계는 서버의 실제 문서·상태별 내용을 내보낸다. 두 번째 단계는 설명과 선택지 문구를 PNG로 인쇄하고, 모바일용 종이를 상세 책에서 추출한다. 이 과정은 게임 판정이나 저장 기록을 변경하지 않는다.
