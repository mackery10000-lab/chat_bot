# 오프닝·엔딩 영상 적용

2026-11-05 요청에 따라 새 게임은 오프닝을 재생한 뒤 1호차에서 시작한다. 완료한 오프닝은 같은 탭에서 새로고침할 때 다시 재생하지 않으며, 새 게임을 시작하면 다시 재생한다.

`아지산역`과 `2026`을 최종 확정하면 즉시 GOOD이 되어 굿엔딩을 재생한다. 별도 출입문 칸과 하차 행동을 제거했다. BAD의 신문 기사 화면도 배드엔딩 영상으로 교체했다. 기존 정차/하차 대기 저장 기록은 GOOD 영상으로 이어진다.

| 전달 파일 | 적용 자산 |
| --- | --- |
| 오프닝 18초 버전.mp4 | `public/assets/videos/opening.mp4` |
| 엔딩bad.mp4 | `public/assets/videos/bad-ending.mp4` |
| good엔딩ver2.mp4 | `public/assets/videos/good-ending.mp4` |

전달받은 원본 파일은 수정하지 않았다. 오프닝은 HEVC에서 H.264/AAC MP4로 변환하고 faststart를 적용했다. 원본의 회전 정보를 반영한 표시 크기는 1080×1904다. 두 엔딩은 전달 파일 그대로 복사했다. 영상은 비율을 유지하고 자체 소리를 재생하며, 재생 중 배경음악은 일시 중지된다.

후속 요청에 따라 세 영상 모두 재생바·시간·재생 버튼·건너뛰기 없이 화면 전체에서 자동 재생한다. 클릭·터치·키보드·미디어 키로 일시 정지하거나 재생 위치와 속도를 바꿀 수 없다. 오프닝은 실제 재생이 끝난 뒤 1호차로 전환하며, 엔딩은 실제 재생이 끝난 뒤 별도 종료 화면에서 새 게임을 시작할 수 있다. 영상 위에는 버튼이나 상태 문구를 표시하지 않는다.

브라우저가 소리 있는 자동 재생을 차단하면 화면 변화 없이 음소거로 자동 재생하고 첫 실제 사용자 입력 시 소리를 복원한다. 중복된 재생 요청은 하나로 처리한다. 파일 오류나 45초 이상 재생이 진행되지 않는 경우에는 영상 화면을 닫고 기존 오류/기록 불러오기 화면으로 복구한다.

미니맵은 `1호차 → 2호차 → 3호차 → 4호차 → 승무원실 → 기관실`의 6칸으로 배치했다. 승무원실의 기존 문 개방 퍼즐은 유지한다. 새 지도는 `public/assets/images/ui/train-route-six-cars.png`(2172×724)이며, 기존 `train-route.png`는 보존했다. 클릭 영역과 로딩 화면도 새 지도를 사용한다.

## 배경 속 문으로 이동

배경에 실제로 그려진 문 윤곽을 원본 캔버스 좌표에 등록했다. 배경과 같은 이미지를 같은 위치·비율로 샘플링해 문 부분만 밝기와 발광으로 강조한다. 문은 이동 가능한 경우에만 상호작용 대상으로 나타나며, 마우스·키보드 포커스에서 강조된다. 기존 배경을 다시 그리거나 다른 문 이미지를 덧붙이지 않았다.

서버의 실제 이동 엔진이 인접 장소와 `can_enter()` 조건을 확인한 결과를 장면 선택기에 전달한다. 대화·최종 확인·정전·게임 종료 중에는 이동 문을 제공하지 않는다. 1→2호차, 2→3호차, 3→4호차, 4호차→승무원실, 승무원실→기관실이 문으로 연결된다. 4호차 문은 항상 승무원실로, 승무원실 안쪽 문은 기관실로 연결되며 각 진입 조건을 충족해야 활성화된다. 이동 엔진과 미니맵 경로도 `4호차 ↔ 승무원실 ↔ 기관실` 순서를 따른다. 기관실 배경에는 보이는 문이 없어 기존 미니맵으로 돌아간다. 승무원실의 문 개방 퍼즐은 잠겨 있을 때 유지되며, 실제 개방 조건을 충족하면 문 클릭이 입실로 연결된다.

후속 요청 적용 검증: 오프라인 단위 테스트 141개, 전체 브라우저 회귀 검사 188개 통과. 별도의 데스크톱·모바일 문 클릭 이동 검사 32개도 통과했다. 영상은 실제 재생 속도 1배에서 끝까지 재생하며 조작 UI 부재, 클릭·키보드·미디어 입력 차단, 강제 일시 정지·탐색·속도 변경 복구, 정상 종료와 새 게임 전환을 확인했다. 자동 재생 차단과 초기 요청 실패 복구도 검증했다. 영상 4개의 HTTP Range 응답도 확인했다. 실제 AI 호출은 사용하지 않았다.

## 미니맵 이미지 제작 기록

기본 내장 `image_gen__imagegen` 편집 모드를 사용했다. 편집 대상은 `public/assets/images/ui/train-route.png`, 저장 결과는 `public/assets/images/ui/train-route-six-cars.png`다. 투명 배경은 사용하지 않았다. 최종 제출 프롬프트:

```text
Use case: precise-object-edit.
Asset type: game train route minimap image.
Input image: edit target, antique sepia parchment illustrated railway train, seven cutaway carriages.
Primary request: Remove ONLY the sixth carriage from the left, the vestibule/exit carriage that has a round door medallion above it. Close the gap seamlessly by moving the rightmost engine/control carriage left so it couples directly to the fifth carriage (the library/crew room with a cap medallion). The finished image must have exactly SIX carriages in this left-to-right order: basic bench passenger room, luxury chair passenger room, sleeper bunk room, dining room, library/crew room, engine/control room. Each carriage retains its matching circular medallion. No door medallion remains.
Constraints: Preserve the detailed artwork of all six retained carriages and their icons, warm brass and wood, antique parchment, misty mountains and forest, track, lighting, black and gold framing, side-on perspective, centered long train layout. Keep the six carriages equal in width and naturally coupled into one contiguous train. Retain the same horizontal 3:1 overall aspect ratio with sufficient parchment margins above and below, the thin ornament line near the top and smooth consistent backdrop. Do not add text, numbers, labels, watermarks, additional carriages, duplicate cars, or extra medallions. Regenerate only the removed area and adjoining seamless environment as needed.
```
