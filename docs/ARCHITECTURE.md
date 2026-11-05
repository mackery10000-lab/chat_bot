# 종착역이 없는 열차 v1.1 구조

원래 app.py와 services·config·templates·public·data·tests를 유지한다. 별도 게임 루트나 프런트 프로젝트를 만들지 않는다. .env는 원본 바이트 그대로다.

1. app.py는 기존 페이지와 JSON API, 무작위 게임 쿠키, 길이·자료형·출처·오류 응답을 담당한다.
2. generator.py의 interpret는 실제 모델 JSON Schema로 행동·대상·부정·동일 물건·특징 근거를 해석한다. 최종 실행 절에서만 대상을 정규화하고 다른 명시적 행동을 단순 수락으로 덮어쓰지 않는다.
3. chatbot_service.py 안의 GameEngine이 장소·소유·열람·원본 반환·대화·퍼즐·엔딩을 판정한다. 외형 사실 공개와 증언 아이템은 같은 서버 사건이다. 미언급은 이전 특징을 지우지 않는다.
4. retriever.py는 허용 fact_id·인물·공개 조건으로 자료를 먼저 제한한다. 분실 사실과 외형 사실을 분리한다.
5. generate는 해당 NPC의 승인된 말머리를 실제 모델로 고른다. 서버 확정 대사를 그대로 결합하며, approved_reply는 허용 조합 외의 임의 사실·문장·정답을 주 화면과 이력에 확정하지 않는다.
6. 같은 파일의 GameStore가 상태·이력·동일 요청 결과를 SQLite에 함께 커밋한다. AI 실패 시 턴을 커밋하지 않고 예약을 해제한다. 마지막 기회는 최종 확인에서만 소비한다.
7. image_selector.py는 열차 안 6개 장소, 문 개방, 손전등 시야, 현재 NPC와 표정에 따라 배경·인물·조사점 좌표를 제공한다. 마지막 제어 장치의 정답을 확정하면 즉시 GOOD이 되며 별도 출입문/승강장 장소는 없다. 엔딩은 game.ending_video로 영상을 제공한다.
8. 기존 chatbot.js와 style.css가 일자 미니맵, 배경 조사점, 대화 시작·종료, 집중 조사, 획득 알림, 실제 준비 시간의 장면 로딩을 구현한다.

화면 클릭의 select_npc·present·end_talk·operate·read_item도 자유 채팅과 같은 엔진을 쓴다. 화면에서 정한 행동을 다시 AI 해석에 보내지 않는다. select_npc는 첫 인사를 즉시 반환하고 화자를 보존한다.

요청 본문은 message 또는 action 중 하나다. 응답은 기존 reply·image·sources와 game·scene·ui·events를 유지한다. sources는 허용 자료 제목으로서 문장별 인용을 뜻하지 않는다. ui.ignored의 빈 reply는 불가능한 행동을 의도적으로 무시한 경우이며 API 실패와 다르다.

장면 이미지의 다운로드·디코딩은 반영 전에 기다린다. 실패 시 마지막 요청 ID를 보존하여 서버에서 이미 커밋되었어도 같은 결과를 안전하게 다시 받을 수 있다. 장면 이동 중인 dialog는 닫아 중앙 로딩이 가려지지 않게 한다. 문서/장치 확대는 dialog의 반투명 검은 패널과 흐린 backdrop을 사용한다.

전체 역할표, 실행 코드, 수정 항목, 실제 검증 범위는 루트 README를 확인한다.
