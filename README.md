# 종착역이 없는 열차

사용자가 제공한 열차 시나리오·챗봇 시스템 기획서와 9장의 인물·UI 레퍼런스를 기반으로 만든 자유 대화형 추리 게임입니다. 기존 5-chatbot-base의 Flask 진입점, 서비스, 세 화면과 폴더 구성을 확장했습니다.

실제 OpenAI 모델로 사용자의 문장을 해석하고 NPC의 말투를 생성합니다. 서버가 아이템·조사 기록·출입·퍼즐·최종 기회·엔딩을 결정합니다. 별도의 데모 실행 모드는 없습니다.

## 이번 수정본 v1.1

2026년 11월 1일 검수 보고서의 F01~F13과 추가 UI 요청을 반영했습니다. v1.0의 Flask·서비스·템플릿·정적 자산·SQLite 틀을 유지하며 기존 경로를 삭제하거나 이동하지 않았습니다. `.env`는 원본 바이트를 그대로 사용합니다.

- 상단에 항상 보이는 7칸 열차 지도, 배경 위 조사점과 인물의 마우스·키보드 강조.
- 인물 클릭 즉시 첫 대사, 현재 상대 표시, 명확한 대화 마치기와 탐색 복귀.
- 열차 안 6개 장소의 서로 다른 배경. 5명 인물의 기본/상황 표정 각 2장. 오프닝과 GOOD/BAD 엔딩은 영상으로 재생합니다.
- 문서·안내서·점검 장치의 배경 흐림과 검은 집중 패널. 여러 아이템 획득도 각 알림으로 확인.
- 장면 이동에만 실제 대기 시간의 열차 로딩. 일반 대화·보관함·문서·레버 조작에는 전면 로딩을 쓰지 않습니다.
- 물건 동일성·특징의 원문 근거·미언급과 부정 구분. 대사에서 공개한 핵심 사실과 저장 상태의 동기화.

## 실행

ZIP을 풀고 **app.py, requirements.txt, .env가 보이는 폴더**를 VS Code로 여세요. Python 3.12를 권장합니다. 최초 패키지 설치와 실제 AI 대화에는 인터넷 연결이 필요합니다.

Conda를 사용한다면 아래 블록 전체를 **프로젝트 루트의 VS Code PowerShell**에서 실행하세요. `train-chatbot`이 있으면 재사용하고 없으면 Python 3.12 환경을 만듭니다. 설치와 앱 실행 모두 해당 Conda 환경에서 수행합니다.

```powershell
$ErrorActionPreference = "Stop"
if (!(Test-Path .\app.py) -or !(Test-Path .\requirements.txt)) { throw "app.py와 requirements.txt가 있는 폴더에서 실행해 주세요." }
if (!(Test-Path .\.env)) { throw "원본 .env 파일이 없습니다. 제공된 ZIP의 프로젝트 폴더를 확인해 주세요." }
if (!(Get-Command conda -ErrorAction SilentlyContinue)) { throw "Conda를 사용할 수 있는 VS Code 터미널에서 실행해 주세요." }
$trainEnvHash = (Get-FileHash .\.env -Algorithm SHA256).Hash
$trainEnvList = & conda env list --json
if ($LASTEXITCODE -ne 0) { throw "Conda 환경 목록을 확인하지 못했습니다." }
$trainCondaEnvs = ($trainEnvList -join "`n") | ConvertFrom-Json
$trainExists = @($trainCondaEnvs.envs | Where-Object { (Split-Path $_ -Leaf) -eq "train-chatbot" }).Count -gt 0
if (!$trainExists) {
    & conda create -n train-chatbot python=3.12 pip -y
    if ($LASTEXITCODE -ne 0) { throw "Conda 환경 생성에 실패했습니다." }
}
& conda run -n train-chatbot python -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 이상이 필요합니다.'"
if ($LASTEXITCODE -ne 0) { throw "train-chatbot의 Python 버전을 확인해 주세요." }
& conda run --no-capture-output -n train-chatbot python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "의존성 설치에 실패했습니다. 위 오류를 확인해 주세요." }
if ((Get-FileHash .\.env -Algorithm SHA256).Hash -ne $trainEnvHash) { throw "원본 .env의 바이트가 달라졌습니다." }
& conda run --no-capture-output -n train-chatbot python app.py
```

실행 뒤 브라우저에서 **http://127.0.0.1:5000/** 을 여세요. 터미널은 열린 채로 두고 종료는 Ctrl+C를 사용합니다. 다음 실행은 `conda run --no-capture-output -n train-chatbot python app.py` 한 줄이면 됩니다. `conda run`을 쓰므로 별도 활성화 스크립트나 실행 정책 변경이 필요하지 않습니다.

venv를 선호한다면 Windows VS Code PowerShell에서 아래 블록을 실행할 수 있습니다. 기존 .venv가 있으면 재사용합니다. 가상환경 활성화 스크립트를 실행하지 않으므로 실행 정책을 바꿀 필요가 없습니다.

```powershell
$ErrorActionPreference = "Stop"
if (!(Test-Path .\app.py)) { throw "app.py가 있는 프로젝트 폴더에서 실행해 주세요." }
if (!(Test-Path .\.env)) { throw "원본 .env가 없습니다. 제공된 ZIP에 포함된 파일을 확인해 주세요." }
if (!(Test-Path .\.venv\Scripts\python.exe)) {
    $trainBootstrap = $null
    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            $trainProbe = & python -c "import sys; assert sys.version_info >= (3, 10); print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0) { $trainBootstrap = [string]($trainProbe | Select-Object -Last 1) }
        } catch { }
    }
    if (!$trainBootstrap -and (Get-Command py -ErrorAction SilentlyContinue)) {
        try {
            $trainProbe = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0) { $trainBootstrap = [string]($trainProbe | Select-Object -Last 1) }
        } catch { }
    }
    if (!$trainBootstrap) { throw "Python 3.12를 설치하거나 Conda 환경에서 다시 실행해 주세요." }
    & $trainBootstrap -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "가상환경 생성이 완료되지 않았습니다." }
}
$trainPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $trainPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "의존성 설치가 완료되지 않았습니다. 인터넷과 Python 버전을 확인해 주세요." }
& $trainPython app.py
```

브라우저에서 http://127.0.0.1:5000/ 으로 들어가세요. 터미널은 서버가 실행되는 동안 열어둡니다. 중단은 Ctrl+C입니다. 이미 설치한 뒤에는 `.\.venv\Scripts\python.exe app.py`로 실행합니다.

macOS/Linux에서는 `python3.12 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, `.venv/bin/python app.py` 순서로 실행합니다. 프로젝트 경로에 한글이나 공백이 있어도 서버 내부 파일은 app.py 기준의 절대 경로로 읽습니다.

5000번 포트가 이미 사용 중이라면 환경 파일을 고치지 않고 현재 PowerShell에서 `$env:PORT="5001"`을 실행한 뒤 서버를 켜세요. 주소도 http://127.0.0.1:5001/ 로 바꿉니다.

## 원본 환경 파일

.env는 원본 207바이트를 그대로 계승했습니다. 새로 생성하거나 수정·삭제하지 마세요. .env.example을 복사하는 절차도 없습니다.

- 포함 변수: OPENAI_API_KEY, OPENAI_MODEL.
- 원본 모델: gpt-4o-mini.
- reasoning 또는 reasoning_effort 옵션을 보내지 않습니다.
- 원본 SHA-256: d3def77ab6bf0e4a90ce14fed512ab520b763261ba29b94a3676e7bb779db77e.
- 키 값은 문서·프런트 코드·화면에 복사하지 않았습니다. .env는 public 폴더 밖에 있습니다.
- 원본 베이스와 같이 비어 있지 않은 프로세스 환경 변수가 있으면 우선 적용하고, 없으면 프로젝트의 .env를 읽습니다.

개인 실행용 ZIP에는 원본 .env가 포함됩니다. 공개 Git 저장소에는 기존 제외 규칙을 유지합니다.

## 플레이 방법

첫 화면에서 열차에 오르고 이름을 입력하면 새 조사를 시작합니다. 이어서 조사하기는 같은 브라우저에 연결된 진행을 불러옵니다.

질문·조사·이동·소품 사용을 채팅으로 요청할 수 있습니다. 예를 들어 ‘창밖을 자세히 본다’, ‘2호차로 이동한다’, ‘승차권을 읽어본다’처럼 현재 하려는 행동을 입력합니다. 인물의 이름을 직접 부르거나 화면에서 상대를 선택할 수 있습니다. 같은 의미의 표현을 허용하며 고정 문장을 암기할 필요는 없습니다.

- **보관함:** 실제 획득한 물건만 표시합니다. 열람과 최종 증거 제출은 별도입니다.
- **미니맵:** 게임 상단의 일자 안내도에 항상 표시됩니다. 현재 위치·방문·잠금 상태를 확인하고 이동합니다. `4호차 ↔ 승무원실 ↔ 기관실` 순서로 연결되며, 4호차 문은 승무원실로, 승무원실 안의 문은 기관실로 이동합니다. 각 문의 실제 진입 조건을 만족해야 이동할 수 있습니다.
- **대화:** 배경의 인물을 클릭하면 첫 대사가 나옵니다. 현재 상대를 크게 보여주며 ‘대화 마치기 · 주변 보기’로 탐색으로 돌아옵니다. 이름을 말하거나 대화 종료를 채팅으로 요청해도 됩니다.
- **질문 참고:** 상대와 공개 단계에 맞는 참고 문장을 접어 둡니다. 정답 선택 버튼은 두지 않고 직접 입력합니다.
- **집중 조사:** 안내문·소지품·점검 덮개·제어 장치는 흐린 배경 위 둥근 검은 패널에서 확인합니다. 닫기 버튼과 Esc로 주변으로 돌아옵니다.
- **획득 알림:** 새 아이템의 이름·도상·보관 완료를 표시하며 여러 개를 얻으면 순서대로 표시합니다. 집중 화면 안에서도 보입니다.
- **기록:** 실제 대화와 확인된 사실을 다시 읽습니다. NPC 대사의 필수 사실은 ‘대화에서 확인한 사실’에도 보존합니다.
- **힌트:** 직접 요청할 때만 다음 조사 방향을 알려줍니다.
- **수동 레버:** 실제 드래그·터치, 버튼·키보드 또는 명시적인 채팅으로 조작합니다.
- **최종 제출:** 취소할 수 있는 준비 단계와 되돌릴 수 없는 확정을 분리합니다.

창 닫기나 새로고침은 포기가 아닙니다. 포기는 설정에서 별도로 최종 확인합니다. 일반 대화 오류나 초중반 퍼즐 오답만으로 게임을 종료하지 않습니다.

## 게임 범위

4개 객차, 승무원실, 기관실의 6개 장소와 탐험가·노인·청소원·승무원·기관사 5명이 등장합니다. 오프닝 영상을 마치면 1호차에서 조사를 시작합니다. 핵심 퍼즐은 승차권 찾기, 승무원실 비상 개방, 현재 연도 증명, 분기기 입력입니다. 친밀도·의심도·체력·제한 시간이나 새 조연·단서는 추가하지 않았습니다.

정확한 목적지 이름은 승무원실의 보고서를 실제 조사한 뒤에 공개합니다. 초기 API 응답·미니맵·추천·문서·NPC 대사에서 미리 알려주지 않습니다. 사용자가 먼저 쓴 정답을 따라 말하며 단계를 건너뛰지도 않습니다.

자료의 모호한 부분은 다음처럼 원래 단서를 유지하며 연결했습니다.

- 출발 시각은 원문 본문의 23:59로 통일했습니다.
- 신문은 2016년 실종 사건의 과거 기록입니다. 새로운 2026년 기사나 발행일을 만들어 넣지 않았습니다. 신문을 연도 증거로 선택하면 최초 소지한 2026년 승차권과 함께 대조한다고 제출 확인 화면에 표시합니다.
- 노인에게 승차권 원본을 돌려줘도 보관함에는 조사 기록이 남습니다. 보고서 전달도 같은 방식입니다.
- 정답을 최종 확정하면 즉시 GOOD 엔딩 영상을 재생합니다. 별도 출입문 칸이나 하차 행동은 없습니다.
- 마지막 쿠키는 원문에 있는 아지산과 생존의 여운만 사용합니다. 성립하지 않는 애너그램 변환 규칙을 새로 만들지 않았습니다.

<details>
<summary>제작자용 최종 판정과 엔딩</summary>

목적지는 아지산역, 최종 비밀번호는 네 자리 2026입니다. 게임의 연도는 이야기 속 값으로 고정하고 실행하는 컴퓨터의 연도를 사용하지 않습니다.

현재 승차권 또는 신문을 올바른 증거로 최종 제출하면 제어 권한이 생깁니다. 올바른 목적지와 비밀번호를 최종 확정하면 즉시 GOOD가 발생하고 굿엔딩 영상을 재생합니다. 이전 저장 기록이 정차/하차 대기 상태라면 이어서 GOOD 영상을 볼 수 있습니다.

잘못된 증거를 최종 제출하거나, 형식에 맞는 잘못된 목적지·비밀번호를 최종 확정하거나, 명시적으로 포기를 확정하면 BAD와 배드엔딩 영상을 제공합니다. 엔딩의 신문 기사 화면은 제거했습니다. 입력란이 비어 있거나 네 자리 숫자가 아닌 경우에는 마지막 기회를 소모하지 않습니다.

더블 클릭·동일 요청 재전송은 저장된 결과를 그대로 반환합니다. 새로운 요청으로 종료된 게임의 상태를 되돌릴 수 없습니다.

</details>

## 폴더 구성

기존 베이스의 36개 파일 경로와 14개 폴더 항목을 유지했습니다. 기존 파일을 삭제·이동·이름 변경하지 않았고, 이미지·폰트만 기존 정적 자산 폴더에 더했습니다. .env는 같은 경로와 바이트를 유지합니다.

| 폴더 | 역할 |
| --- | --- |
| 프로젝트 루트 | app.py, 환경·의존성·Docker 설정과 이 README |
| config | 작품 소개, 5명 인물, 아이템과 문서 정의. 서버 전용 |
| services | 입력 해석·대화, 진행·저장, 허용 자료 조회, 이미지 선택 |
| templates | 시작·소개·게임 화면의 Jinja HTML |
| public | Flask가 브라우저에 제공하는 정적 자산 루트 |
| public/assets/css | 화면 스타일, 로컬 한글 폰트, 폰트 이용 허락문 |
| public/assets/js | 채팅 요청, 보관함·미니맵·조작 UI, 복구와 재시도 |
| public/assets/images | 6개 장소 배경·5명 인물의 두 표정·신문 자료 사진·보존한 원본 로고 |
| data | 실행 후 SQLite 진행 저장 파일 생성 위치 |
| data/knowledge | 인물별 사실과 공개 조건을 담은 원본 자료 |
| data/images | 사용 이미지·레퍼런스·생성 지침을 설명하는 문서 |
| tests | 실제 API 비용 없이 실행하는 회귀 검사 |
| docs | 구조·실행·모델·협업·배포에 관한 문서 |

public/assets도 원본의 상위 폴더로 유지합니다. 폴더 개수의 14에는 ZIP의 프로젝트 루트와 이 상위 폴더가 포함됩니다. .venv와 캐시, 저장 DB는 실행 중 생기는 파일이며 배포 ZIP에 넣지 않습니다.

## 파일별 역할

| 파일 | 현재 역할 |
| --- | --- |
| app.py | 기존 Flask 진입점. 페이지·게임·채팅·문서 API, JSON·쿠키·출처 검증과 오류 응답 |
| services/__init__.py | 기존 ChatbotService 내보내기 |
| services/chatbot_service.py | GameEngine, GameStore, ChatbotService. 장소·아이템·공개 조건·퍼즐·엔딩·SQLite·중복 요청 처리 |
| services/generator.py | DemoGenerator 이름을 보존한 실제 모델 연결. JSON Schema 의도·대상·동일 물건·극성·원문 근거 해석과 승인된 말투 선택 |
| services/retriever.py | 공개 조건·NPC·허용 사실 ID로 필터링하여 KnowledgeHit 반환 |
| services/image_selector.py | 확정된 장소·시야·NPC에 맞는 배경과 인물 이미지 선택 |
| config/chatbot_config.json | 인물 성격·말투·위치와 소품·문서 내용. 전체 내용을 프런트로 전달하지 않음 |
| data/knowledge/example_lore.md | 기존 가상 자료를 열차 시나리오의 인물별 사실로 교체. fact 메타데이터와 공개 조건 포함 |
| data/knowledge/README.md | 자료 조회 방식과 공개 조건 설명 |
| data/images/README.md | 19개 게임 자산의 역할·원본 레퍼런스·생성 지침과 한글 문서 표현 원칙 |
| templates/index.html | 목재 객차 배경의 시작 화면 |
| templates/detail.html | 스포일러 없는 소개, 조작 안내, 이름 입력 |
| templates/chat.html | 장면·대화·자유 입력·보관함·지도·기록·퍼즐 패널의 HTML 구조 |
| public/assets/css/style.css | 목재·황동·종이 UI, 반응형 배치, 레버·입력 장치·엔딩 스타일 |
| public/assets/js/chatbot.js | 요청 ID·리비전 처리, UI 조작과 텍스트 표시, 네트워크 실패 재시도, 저장 복구 |
| public/assets/css/NanumGothic.ttf | 로컬 배포하는 한글 기본 글꼴 |
| public/assets/css/NanumGothicBold.ttf | 한글 굵은 글꼴 |
| public/assets/css/FONT_LICENSE.txt | Nanum Gothic의 SIL Open Font License 원문 |
| public/assets/images/scene_01.png | 사용자가 제공한 빈 목재 객차 배경 |
| public/assets/images/scene_02.png | 같은 그림체로 제작한 승무원실 배경 |
| public/assets/images/scene_03.png | 같은 그림체로 제작한 기관실 배경 |
| public/assets/images/scene_04.png | 이전 승강장 장면의 보존 자산. 현재 게임에서는 사용하지 않음 |
| public/assets/images/evidence_01.png | 원문에 있는 신문의 과거 열차 사진. 식별명은 정확한 HTML 텍스트로 표시 |
| public/assets/images/portrait_01.png | 탐험가 투명 인물 자산 |
| public/assets/images/portrait_02.png | 노인 투명 인물 자산 |
| public/assets/images/portrait_03.png | 청소원 투명 인물 자산 |
| public/assets/images/portrait_04.png | 승무원 투명 인물 자산 |
| public/assets/images/portrait_05.png | 기관사 투명 인물 자산 |
| public/assets/images/scene_05.png | 2호차. 탐험가가 앉는 긴 좌석과 중앙 통로 |
| public/assets/images/scene_06.png | 3호차. 꺼진 전등·커피 자국·청소 도구 |
| public/assets/images/scene_07.png | 4호차. 닫힌 승무원실 문·카드 인식기·오른쪽 하단 덮개 |
| public/assets/images/scene_08.png | 같은 4호차의 문 개방 상태. 기존 승무원실 내부와 연결 |
| public/assets/images/portrait_06.png | 탐험가의 유쾌한 설명 표정 |
| public/assets/images/portrait_07.png | 승차권을 돌려받은 노인의 안도 표정 |
| public/assets/images/portrait_08.png | 외형을 확인하는 청소원의 표정·손짓 |
| public/assets/images/portrait_09.png | 출입을 막는 승무원의 제지 표정·손짓 |
| public/assets/images/portrait_10.png | 연도 증거를 인정한 기관사의 놀란 표정 |
| public/assets/images/hateslop-logo.png | 원본 베이스 로고 파일 보존 |
| tests/test_smoke.py | 화면·API·정상/실패 경로·저장·동시성 관련 기본 회귀 검사 |
| requirements.txt | Flask, python-dotenv, OpenAI, SOCKS 지원 httpx, Linux용 Gunicorn |
| Dockerfile | 기존 Python 3.12·Gunicorn 컨테이너 빌드 |
| docker-compose.yml | 로컬 컨테이너 실행과 진행 데이터 볼륨 |
| .python-version | 원본 Python 3.12 기준 |
| .gitignore | 환경·가상환경·SQLite 및 실행 부산물 제외 |
| .dockerignore | 원본 환경·불필요한 로컬 자료의 이미지 빌드 제외 |
| .gitattributes | 원본 Git 텍스트 속성 보존 |
| .env | 원본 키와 모델. 수정·삭제하지 않음 |

## docs 파일 안내

| 파일 | 역할 |
| --- | --- |
| docs/ARCHITECTURE.md | 현재 게임의 요청 흐름, 상태 소유권, 저장·자료·이미지 경계 |
| docs/LOCAL_SETUP.md | 현재 제품의 Windows·Conda·venv 실행과 문제 해결 |
| docs/MODEL_SETUP.md | 실제 의도 해석·NPC 생성과 원본 환경 연결 |
| docs/MODEL_CHOICE.md | 원본 모델 선택 관련 참고 문서 |
| docs/ADVANCED_TOPICS.md | 검색·평가·메모리 확장의 공통 참고 문서 |
| docs/DEPLOYMENT.md | 현재 저장 방식과 공개 배포 시 구분할 사항 |
| docs/DOCKER-GUIDE.md | 기존 Docker 경로와 진행 보존 |
| docs/RENDER-GUIDE.md | Render 배포의 공통 참고 문서. 현재 SQLite 지속성은 DEPLOYMENT도 확인 |
| docs/PROJECT_GUIDE.md | 원본 과제의 공통 목표와 제출 기준 안내 |
| docs/TEAM_WORKFLOW.md | 원본 Git 협업 가이드 |

과제의 외부 공지나 배포 서비스 정책은 이 ZIP을 제작하면서 최신 여부를 다시 검증한 범위가 아닙니다. 이 README는 현재 실제 제품의 실행·구조 기준입니다.

## 데이터 흐름

1. 브라우저가 기존 /, /detail, /chat 화면을 엽니다.
2. /api/game에서 저장 상태를 읽습니다. 새 조사는 /api/game/new로 만듭니다.
3. 채팅 또는 화면 조작은 /api/chat으로 요청 ID와 현재 리비전을 보냅니다.
4. 자연어는 실제 모델로 의도·부정·정정·대상을 해석합니다. 구조화한 화면 조작은 같은 엔진 규칙에 연결합니다.
5. 엔진이 현재 장소·보유·공개 조건을 확인하고 변경안을 계산합니다.
6. AI는 실제 입력 의미를 해석하고, 해당 NPC의 승인된 말머리 중 상황에 맞는 표현을 선택합니다. 단서·숫자·행동 결과가 든 핵심 대사는 서버가 원문 기준으로 그대로 붙입니다. 화면에 표시하는 문장도 이 조합과 일치하는지 검증합니다. 모형의 임의 대사를 핵심 사실로 저장하지 않습니다.
7. 상태·대화·처리 결과를 함께 저장하고 공개 가능한 데이터만 반환합니다.
8. 브라우저가 장면·보관함·대사·퍼즐을 갱신합니다. 답변 텍스트는 HTML로 실행하지 않습니다.

현재 검색은 작은 고정 세계관에 맞춘 조건별 자료 조회입니다. 벡터 임베딩·ChromaDB를 사용했다고 표시하지 않습니다. 이미지도 현재 상태에 맞춘 준비 자산 선택이며, 플레이할 때마다 이미지를 실시간 생성하는 기능은 아닙니다.

## API

| 경로 | 역할 |
| --- | --- |
| GET /health | 앱 프로세스 응답 확인. 외부 AI 연결 성공을 보증하는 검사는 아님 |
| GET /api/game | 현재 브라우저에 연결된 진행 상태 조회 |
| POST /api/game/new | 명시적으로 새 게임 생성, 무작위 게임 식별 쿠키 발급 |
| POST /api/chat | message 또는 action 중 하나를 처리 |
| GET /api/item/아이템ID | 실제 보유한 문서의 내용만 제공. 조사 상태 변경은 채팅·보관함 조작 경로에서 처리 |

기존 reply·image·sources를 유지하고 game·scene·ui·events를 확장했습니다. sources는 검색된 허용 자료의 이름이며 엄밀한 문장별 인용 목록이 아닙니다. 사용자 이름이 같아도 게임 식별자가 다르면 저장이 분리됩니다.

일반 API 오류는 형식을 검증하여 400/403/404/409/413을 반환합니다. 실제 AI 장애는 503과 재시도 안내로 처리하고 해당 턴의 상태 변경을 저장하지 않습니다. 이미 확정된 최종 요청을 같은 ID로 다시 보내면 동일한 저장 결과를 반환합니다.

## 저장과 복구

실행 시 data/train_state.sqlite3가 생성됩니다. 게임 상태·최근 대화·사건·동일 요청 결과를 저장합니다. SQLite WAL과 트랜잭션, 요청 리비전과 처리 예약으로 충돌을 관리합니다. 모델 응답을 기다리는 동안 긴 쓰기 잠금을 잡지 않습니다.

진행은 동일 서버 데이터와 동일 브라우저 쿠키가 있어야 복구됩니다. 새 브라우저·쿠키 삭제·저장 파일 삭제는 기존 기록과의 연결을 잃게 합니다. 로그인이나 계정 간 동기화는 구현하지 않았습니다. 종료된 게임은 새 게임으로 재도전합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

자동 검사는 모의 모델을 사용하므로 실제 API를 과금하지 않습니다. 정상 탈출의 두 증거·목적지 별칭·공백 조합, 오답 증거·오답 비밀번호·포기, 선행 조건, 부정문 판정 결과, 출처 공개, 저장 복구, 요청 재전송과 입력 검증을 검사합니다. 자연어 모델 자체의 품질은 별도 실제 연결 검수로 확인합니다.

최종 검수 수치와 실제 실행 환경은 이 문서 마지막의 ‘제작 검수 결과’에 기록합니다. 자동 검사 결과를 실제 모델의 모든 가능한 답변에 대한 보증으로 취급하지 않습니다.

## 알려진 범위

실제 대화는 외부 API 인증·사용 한도·인터넷에 영향을 받습니다. 실패 시 진행을 보존하고 재시도할 수 있으며, 모델 응답이 구조적으로 불완전하면 성공을 임의로 만들지 않습니다. 대화가 모호하면 확인을 요청합니다.

기본 제공 결과물은 VS Code에서 실행하는 단일 Flask 프로젝트입니다. 공개 URL 배포는 별도 작업이며, 서버 없는 환경의 임시 파일 시스템을 SQLite의 지속 저장소로 가정하면 안 됩니다. 실제 배포 환경을 정하면 그 환경의 저장소와 접근 정책을 확인해야 합니다.

## v1.1 추가 규칙과 수정 위치

| 항목 | 처리 | 주요 파일 |
| --- | --- | --- |
| F01·F11 | 배제 절 전체 재검색 제거. 실제 실행 대상 보존. 단독 수락·도움 약속만 문맥 보정 | services/generator.py `_ground` |
| F02·F04·F10 | 같은 분실물에만 특징 누적. 특징별 원문 근거 검증. 미언급 유지, 명시적 부정 제거, 정정 복구 | generator.py `grounded_features`, chatbot_service.py `talk` |
| F03 | 승인된 말머리와 서버 핵심 대사를 결합. 새 물건·역명·암호·잘못된 필수 사실을 생성 출력으로 확정하지 않음 | generator.py `generate`, `approved_reply` |
| F05 | 현재 인물·단계별 참고 질문. 최신 UI 요청에 따라 선택지 버튼 대신 접힌 참고 문장으로 제공 | chatbot_service.py `suggestions`, chatbot.js |
| F06 | 인사·업무 반복·연도 주장·모름 구분. NPC별 최근 이력 분리 | generator.py, chatbot_service.py `talk` |
| F07·F08 | 원본 반환 완료 재검사. 반환 전 필수 열람을 명확히 안내하고 보관함 연결 | chatbot_service.py `present` |
| F09 | 분실 사실과 외형 사실 분리. 외형 질문 동의어와 증언 지급을 같은 사건에 연결 | example_lore.md, generator.py, chatbot_service.py |
| F12 | 꺼진 전등 + 손전등의 제한 시야 유지. 정차 뒤에만 표시 시계 초 단위 재가동 | image_selector.py, chatbot.js, style.css |
| F13 | 기관사의 증명 전/후 현재 인식 연도를 구분하고 서버 대사로 고정 | chatbot_config.json, chatbot_service.py, generator.py |

승차권·보고서 반환 버튼과 NPC 클릭은 구조화된 서버 행동을 사용합니다. 이미 정해진 버튼 동작을 AI로 다시 해석하지 않습니다. 자유 채팅은 같은 엔진 판정에 연결됩니다.

### 실제 대화와 사실 보호

`DemoGenerator`는 베이스와의 호환을 위해 이름을 유지하지만 실제 OpenAI API를 사용합니다. 별도 데모 실행 모드는 없습니다. 원본 모델과 키는 `.env`에서 읽으며 reasoning 옵션을 추가하지 않습니다.

검수 F03을 해결하기 위해 NPC 문장 전체를 자유 재서술시키지 않습니다. 실제 모델의 역할은 입력 의미 해석과 허용된 말머리의 상황별 선택입니다. 핵심 사실은 원문에 맞춘 서버 문장 그대로 주 화면에 표시됩니다. 모델이 역명·암호·새 아이템·개인 과거사를 임의로 넣은 출력은 승인 문장으로 대체합니다. API 연결 실패는 대체 성공으로 꾸미지 않고 503과 재시도로 처리합니다.

### 행동 반응의 경계

- 현장의 인물을 밀치거나 위협하는 명시적 행동에는 물러섬·제지 같은 인물 반응을 줍니다. 진행 플래그, 아이템, 출입 허가, 마지막 입력 기회와 엔딩은 바꾸지 않습니다.
- 앉기·손짓처럼 가능한 비핵심 행동은 짧게 반응합니다. 새 단서나 보상을 만들지 않습니다.
- 소지하지 않은 총 발사·순간이동처럼 불가능한 실행 입력은 `ui.ignored`로 처리합니다. NPC 대사·대화 이력·퍼즐 상태를 갱신하지 않고 입력란 아래 작은 상태 표시만 남깁니다. 요청 중복 처리를 위한 리비전 증가는 게임 진행 변화가 아닙니다.
- 부정·가정·타인의 행동 서술은 실제 공격으로 실행하지 않습니다. 현재 없는 인물을 원격으로 공격하거나 대화할 수 없습니다.
- 게임 종료는 기존의 확정 포기·오답 증거 확정·마지막 제어 입력 오답뿐입니다.

### 장면 로딩 범위

시작/이어서 조사하기에서 게임으로 진입할 때, 미니맵·채팅으로 장소가 바뀔 때 사용합니다. 이전 화면 위 반투명 검정, 중앙 흰색 열차 선화와 ‘로딩’을 표시합니다. 요청과 필요한 이미지의 다운로드·디코딩이 끝나면 즉시 닫습니다. 인위적인 최소 대기 시간, 가짜 진행률, 고정된 몇 초짜리 연출은 없습니다. 빠른 전환은 아주 짧게 보일 수 있습니다.

일반 NPC 대기, 인물 선택/대화 종료, 문서·보관함·기록 열람, 점검 덮개·레버 조작에는 전면 로딩을 표시하지 않습니다. 채팅 대기는 입력창·기록 상태와 비활성 전송 버튼으로 알립니다. 오류에서도 전면 로딩을 해제하고 같은 요청 번호로 재시도합니다.

공식 참고 자료는 [Underground Blossom](https://www.rustylake.com/adventure-games/underground-blossom.html)의 장소별 point-and-click 탐색과 [Unity 비동기 장면 로드](https://docs.unity3d.com/ScriptReference/SceneManagement.SceneManager.LoadSceneAsync.html)입니다. ‘큰 장면 전환에만 쓰고 실제 준비가 끝나면 닫기’는 이를 참고한 이 프로젝트의 설계 판단이며, 특정 게임의 모든 로딩 정책을 그대로 복제했다는 뜻은 아닙니다.

### 원문에서 모호했던 항목의 처리

출발은 원문 본문의 23:59, 보고서는 2016년 폐쇄 예정 기록, 현재 연도 증거는 2026년 자기 승차권과 과거 신문의 대조를 유지합니다. 아지산/생존은 기존 쿠키이며 새 암호로 만들지 않습니다. 별도 운행 이상 기록 아이템·구조 퍼즐·부산의 새로운 개인 추억은 추가하지 않습니다. 현재 승차권에는 원문에서 확인된 연도·열차·탑승 정보를 표시하고, 정해지지 않은 도착역 훼손 설정은 제거했습니다.

## 제작 검수 결과

검수 환경은 Linux/Python 3.12와 Chromium입니다. 이번 수정본 자체의 검사 결과를 아래에 기록합니다. 이전 v1.0의 검수 수치와 합산하지 않습니다.

| 검사 | 이번 수정본 결과 |
| --- | --- |
| 자동 회귀 검사 | 74개 통과. 새 가상환경 설치 후 압축 해제본에서도 74개 통과 |
| 실제 AI 주요 반례 | 대상 배제·외형 질문·동일 물건 누적·부정 정정·인사 반복·연도 주장·수락·공격·불가능 행동·누설 요청 등 17종 최종 확인. 발견한 실패 3종은 수정 후 재검사 통과 |
| 실제 AI 전체 플레이 | 자기 승차권 증거 경로 43단계 GOOD, 신문 증거 경로 41단계 GOOD. 자유 입력은 실제 원본 모델 사용, 고정 UI 행동은 서버 규칙 사용 |
| 브라우저 기본 동선 | 20개 항목 통과. 실제 드래그·NPC 첫 대사·종료·문서 집중·손전등·정차 시계·GOOD/BAD·저장 복구 확인 |
| 브라우저 추가 경계 검사 | 8개 항목 통과. 일반 대화·문서에서 로딩 비남용, 실제 이동 로딩, 이미지 실패 후 복구, 이동 네트워크 실패, 채팅 이동, 모바일 지도 스크롤 확인 |
| 화면 크기 | 데스크톱 1440×1100, 모바일 390×844. 페이지 JavaScript 오류 없음 |
| 압축 해제 실행 | 한글·공백 경로에 풀어 새 Python 환경 설치. 다른 작업 디렉터리에서 앱 시작, 25개 화면·자산 HTTP200 |
| 저장 복구 | 서버 종료·재시작 뒤 같은 브라우저 쿠키와 SQLite 조사 상태 복구 |
| 환경 보호 | .env 207바이트와 SHA-256 원본 동일. 앱에서 /.env 요청 HTTP404 |
| 이미지 | PNG 20개 정상 디코딩. 게임 이미지 19개와 보존한 로고 1개 |
| 파일·폴더 | v1.0의 49개 파일 모두 유지. 기존 이미지 폴더에 PNG 9개 추가, 총 58개 파일·14개 폴더 항목 |
| 패키지 | ZIP CRC 정상, 누락·삭제 경로 없음, 실제 키가 .env 외의 파일에 포함되지 않음 |

실제 API 검사 중 일시적인 연결 실패가 관찰되었습니다. 이때 진행을 보존한 동일 요청 재시도를 거쳐 플레이를 완료했습니다. API 연결 성공을 보장하거나 실패를 게임 성공으로 바꾸는 기능은 없습니다. 위 수치는 모의 검사와 실제 API 검사를 구분한 결과이며 모든 가능한 자연어를 보증하지 않습니다.

Windows 실기기, 실제 Conda 설치, Docker 데몬, 공개 URL 배포와 다수 사용자 부하 시험은 수행하지 않았습니다. 해당 환경까지 오류가 없다고 보증하지 않습니다. 실제 AI는 외부 인증·사용 한도·네트워크 상태에 영향을 받으며, 연결 실패 시 진행을 보존한 재시도를 제공합니다.
