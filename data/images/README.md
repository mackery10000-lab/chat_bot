# 사용 이미지와 UI 제작 기준

사용자가 제공한 9장의 레퍼런스에서 인물 5명, 빈 목재 객차, 보관함·문서·제어 장치, 세로형 대화 화면을 검토했다. 게임에는 원문에 없는 열쇠·추가 책·새 단서·조연을 등록하지 않았다.

## 적용한 표현

짙은 목재와 검은 그림자, 호박색 전등, 황동 테두리, 미색 종이와 붉은 승차권을 사용한다. 작은 문서 글자와 퍼즐 입력은 실제 HTML 텍스트로 표시한다. 흐린 레퍼런스의 가짜 글자를 그대로 게임 정보로 사용하지 않는다.

레퍼런스의 화면 구성을 기존 세 HTML 파일과 CSS·JS로 구현했다. 보관함은 물건 목록과 문서 면, 미니맵은 현재 위치와 잠금, 제어 장치는 목적지와 네 자리 입력을 보여준다. 대화 상대를 고른 뒤에는 해당 인물에 집중하고, 어두운 3호차의 인물은 손전등 사용 전 공개하지 않는다.

## 최종 자산 경로

프로젝트 기준 경로이며 모두 public/assets/images 안에 있다. 실제 실행 시 /assets/images/파일명으로 제공한다.

| 파일 | 용도 | 기준 자료 |
| --- | --- | --- |
| scene_01.png | 기본 목재 객차 | 사용자 1000264287.png 원본을 그대로 복사 |
| portrait_01.png | 발목을 다친 탐험가 | 사용자 1000264286.png의 인물·복장 |
| portrait_02.png | 노인 | 사용자 1000264283.png의 인물·복장 |
| portrait_03.png | 청소원 | 사용자 1000264284.png의 인물·복장 |
| portrait_04.png | 승무원 | 사용자 1000264282.png의 인물·복장 |
| portrait_05.png | 기관사 | 사용자 1000264285.png의 인물·복장 |
| scene_02.png | 승무원실 | 시나리오의 작은 책상·서류 보관함, 동일 객차 그림체 |
| scene_03.png | 기관실 | 시나리오의 운전 레버·제어 장치·시계, 동일 그림체 |
| scene_04.png | 최종 승강장 | 시나리오의 폐쇄된 산악역과 정차한 열차 |
| evidence_01.png | 신문의 열차 자료 사진 | 원문에 명시된 옛 13-Fri 열차 사진 |

hateslop-logo.png는 원본 베이스 파일을 보존했으며 현재 게임 장면에는 사용하지 않는다. 인물 자산은 실제 알파 채널을 가진 PNG다. 배경의 그림 속 장식은 별도 획득 아이템이나 암호가 아니다.

## 생성 방식과 프롬프트 구성

생성 자산 9개는 내장 image_gen 도구로 제작했다. 별도의 CLI나 사용자의 API 키를 이미지 제작에 사용하지 않았다. 이미지 생성은 제작 과정이며 게임 실행 중 실시간 이미지 생성과 구분한다.

공통 인물 프롬프트는 다음 지침을 적용했다.

“Use case: identity-preserve. Asset type: ONE production character sprite for a Korean train mystery visual novel. The uploaded image defines the character identity and costume. Clean single-character composition, fully inside frame, hand-painted Korean graphic novel, delicate ink, textured sepia and muted warm amber lighting. Genuinely transparent alpha background. No backdrop, white rectangle, contact sheet, panels, labels, speech bubble, text or other people. Reusable sprite for a train background.”

인물별로 다음 조건을 더했다.

- 탐험가: 친근한 젊은 동아시아 남성, 헝클어진 짙은 갈색 머리, 올리브 탐험 재킷, 회색 셔츠와 갈색 바지, 배낭 끈. 발목 부상으로 앉은 자세, 무릎 위에 손을 두고 여유로운 표정. 새 단서 소품을 추가하지 않는다.
- 노인: 마른 동아시아 노인, 헝클어진 회색 머리, 깊은 주름과 피곤한 눈, 낡은 갈색 재킷과 체크 셔츠, 검은 바지와 레퍼런스의 지팡이. 앉아 지팡이에 손을 올린 자세. 승차권·커피잔을 새로 쥐여주지 않는다.
- 청소원: 인자한 중년 여성, 둥근 얼굴, 느슨한 앞머리와 낮은 머리 묶음, 소매를 걷은 청회색 작업복과 허리 청소 도구. 공손하게 두 손을 모은 자세. 명찰에는 글자를 넣지 않는다.
- 승무원: 젊은 성인 여성, 피곤하지만 주의 깊은 얼굴, 낮게 묶은 갈색 머리, 황동 장식 검은 철도 모자, 흰 블라우스, 검은 조끼와 리본, 검은 치마. 조심스럽게 손을 모은 자세.
- 기관사: 진지하고 피곤한 중년 남성, 짧은 검은 머리, 황동 띠 철도 모자, 검은 제복과 흰 셔츠·넥타이·금색 소매 장식. 격식 있는 자세.

공통 배경 프롬프트는 다음 지침을 적용했다.

“Use case: stylized-concept. Asset type: production background for a Korean train mystery game. The uploaded empty carriage defines illustration, materials and mood. One landscape scene, detailed hand-painted illustration, delicate ink, subdued amber and umber, aged dark wood, black shadow and brass accents. Grounded architecture. No contact sheet, UI panels, labels, watermark, people or added plot clues.”

장면별로 다음 범위만 사용했다.

- 승무원실: 작은 목재 책상, 글자가 없는 서류, 닫힌 서류 보관함, 따뜻한 천장등. 문에서 보는 구도. 달력·열쇠·금고·추가 수수께끼 소품은 넣지 않는다.
- 기관실: 낡은 운전 레버와 표시 없는 제어 장치, 작은 시계, 야간 창밖. 비밀번호·역명·추가 단서가 되는 글자를 넣지 않는다. 실제 장치의 숫자와 입력은 코드가 관리한다.
- 승강장: 낡은 열차가 멈춘 산악역의 승강장, 밤의 옅은 빛과 따뜻한 전등, 열린 열차 문. 읽을 수 있는 역명판이나 새로운 사건을 넣지 않는다.

## 이미지 선택과 오류 처리

services/image_selector.py가 장소·시야·선택한 NPC·정차 여부로 자산을 선택한다. 대사에 특정 단어가 들어갔다는 이유만으로 미공개 장면을 고르지 않는다. 한 장의 프로필만 고정한 구현도 아니다.

이미지가 늦게 오거나 표시되지 않아도 조사 텍스트와 서버의 진행 조건은 유지된다. UI의 드래그 좌표는 레버 조작 의도를 전달하며, 장치의 실제 성공 조건은 서버가 검증한다.

## 한글 글꼴

외부 CDN 없이 읽을 수 있도록 public/assets/css에 NanumGothic.ttf, NanumGothicBold.ttf, FONT_LICENSE.txt를 포함했다. Google Fonts의 Nanum Gothic 원본 파일과 SIL Open Font License를 사용했다.

출처: https://github.com/google/fonts/tree/main/ofl/nanumgothic

초기 검수에서 일부 배포본 폰트의 0바이트 TSI3 테이블을 Chromium이 거부하는 문제가 확인되어, 공식 배포 파일로 교체하고 실제 로딩을 다시 확인했다.

신문 자료 사진의 생성 지침: “Close side view of an old passenger train at night, only carriage body and windows. Reference railway illustration style. Faded monochrome sepia and photographic grain. Blank identification plate; the exact known train number is added in HTML. No station signs, recognizable station, landscape clues, people, extra objects, lettering or new events.” 번호 13-Fri는 원문의 단서이며 코드로 정확하게 겹쳐 표시한다.


## v1.1 추가 자산과 생성 지침

기본 참조는 v1.0의 scene_01과 portrait_01~05다. 내장 이미지 생성 도구로 원본의 세피아·먹선·낡은 목재·녹색 좌석·호박빛 조명과 인물 정체성을 유지했다. 모든 최종 자산은 기존 public/assets/images 폴더에 복사했다. 런타임 이미지 API나 추가 키는 사용하지 않는다.

| 파일 | 역할 | 최종 프롬프트의 요청과 보존 조건 |
| --- | --- | --- |
| scene_05.png | 2호차 | 참조와 같은 열차, 왼쪽 긴 녹색 벤치·오른쪽 좁은 좌석, 중앙 통로. 탐험가를 합성할 좌석 여백. 인물·새 단서·글자 없음 |
| scene_06.png | 3호차 | 같은 화풍, 꺼진 전등, 창가 좌석·테이블·커피 자국·오른쪽 청소 도구. 노인과 청소원 합성 위치. 희미한 밤빛이며 전등 복구 없음 |
| scene_07.png | 4호차 닫힌 문 | 밝은 전등, 왼쪽 빈 좌석과 승무원 위치, 오른쪽 큰 승무원실 문·빨간 카드 인식기·오른쪽 하단 닫힌 점검 덮개. 중앙 앞쪽 통로. 노란 레버 미노출 |
| scene_08.png | 4호차 열린 문 | scene_07의 문 부분만 안쪽으로 열고 scene_02의 책상·서류 보관함이 일부 보이도록 제작. 다른 가구·카메라·조명·목재와 하드웨어 유지 |
| portrait_06.png | 탐험가의 유쾌한 설명 | portrait_01 정체성·옷·배낭·붕대·앉은 자세 유지, 웃는 얼굴과 손짓만 변경. 걷거나 새 소품을 들지 않음 |
| portrait_07.png | 노인의 반환 후 안도 | portrait_02 얼굴·백발·갈색 외투·지팡이·앉은 자세 유지, 감사하는 미소만 변경 |
| portrait_08.png | 청소원의 외형 확인 질문 | portrait_03 얼굴·작업복·청소 벨트 유지, 손바닥을 펴서 묻는 자세와 표정. 새 승차권 소품 없음 |
| portrait_09.png | 승무원의 출입 제지 | portrait_04 얼굴·모자·검정 조끼·리본·복장 유지, 차분한 정지 손짓과 단호한 표정 |
| portrait_10.png | 기관사의 연도 인정 | portrait_05 얼굴·모자·금색 장식 제복 유지, 놀라 인정하는 눈빛과 손짓. 새 문서·숫자 없음 |

생성 규격은 배경 1536×1024, 인물 1024×1536, 인물은 실제 알파 투명 PNG다. 생성 결과의 색감·인물·주요 가구와 연결을 눈으로 확인하고 적용했다. 기본 배경 7장+문 상태 변형 1장, 기본 인물 5장+표정 변형 5장, 신문 자료 사진 1장으로 게임용 이미지 19장이다. 원본 로고 1장은 그대로 보존한다.

정확한 문서 내용·연도·암호·안내문은 생성 이미지에 맡기지 않고 HTML 텍스트로 표시한다. 흰 열차 로딩 로고·안내서 도식·점검 장치·제어판·아이템 도상은 작은 코드 기반 SVG/HTML/CSS로 그려 정확한 조작 위치와 내용을 유지한다. 이 도식은 새 단서나 아이템이 아니다.
