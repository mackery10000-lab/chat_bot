# Render 배포 가이드

현재 베이스를 Render의 공개 웹 서비스로 배포하는 절차입니다. 기본 Flask 앱을 그대로 쓰는 **Python 런타임**과 Docker를 선택하는 **Docker 런타임**을 안내합니다. 두 방법 중 하나만 고르면 됩니다. Render 화면의 이름이나 제공 조건은 바뀔 수 있으므로 배포 전에 [Render Flask 가이드](https://render.com/docs/deploy-flask)와 [웹 서비스 문서](https://render.com/docs/web-services)도 확인하세요.

## 1. 배포 전 확인

- 로컬에서 화면과 `/api/chat` 응답을 확인합니다. 현재 환경 연결판은 기존 모델을 호출합니다.
- `python -m unittest discover -s tests -v`를 실행합니다.
- GitHub 저장소에 배포할 브랜치를 push하고, Render가 그 저장소에 접근할 수 있는지 확인합니다.
- 실제 모델을 연결했다면 필요한 비밀 환경 변수를 확인합니다. OpenAI API 키는 운영진이 제공합니다.
- `.env`, API 키, 비밀번호가 Git에 들어가지 않았는지 `git status --short`로 확인합니다.

## 2. Render에서 Web Service 만들기

1. [Render Dashboard](https://dashboard.render.com/)에 로그인합니다.
2. **New → Web Service**를 선택합니다.
3. GitHub 저장소를 연결하고 배포할 저장소와 브랜치를 고릅니다. 저장소가 목록에 없다면 Render의 GitHub 연결 설정에서 해당 저장소 접근을 허용합니다.
4. 서비스 이름과 지역을 정하고 Root Directory를 확인합니다. `app.py`가 저장소 루트에 있으면 Root Directory는 비워 둡니다.
5. 사용할 컴퓨팅 플랜을 고릅니다. 무료 플랜을 선택한다면 유휴 시간에 서비스가 멈추는 조건과 저장소 제약을 확인하세요.
6. 아래 둘 중 한 가지 런타임 설정을 선택합니다.

### 방법 A: Python 런타임

| 설정 | 입력값 |
| --- | --- |
| Language | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app` |
| Python 버전 | 저장소 루트의 `.python-version` 확인 |

`requirements.txt`에 Gunicorn이 포함돼 있어야 합니다. 현재 베이스는 Windows가 아닌 운영체제에서 설치하도록 설정되어 있습니다.

### 방법 B: Docker 런타임

| 설정 | 입력값 |
| --- | --- |
| Language | `Docker` |
| Dockerfile Path | 저장소 루트의 `Dockerfile` |
| Docker Command | 비워 둠. Dockerfile의 `CMD`를 사용합니다. |

`docker-compose.yml`은 로컬 개발용입니다. Render에서 Docker 런타임을 선택하면 `Dockerfile`을 사용하며 Compose 파일은 실행하지 않습니다. 로컬 이미지 빌드와 파일 변경은 [Docker 개발 가이드](DOCKER-GUIDE.md)를 참고하세요.

## 3. 환경 변수 설정

실제 모델을 연결한 경우 서비스 설정의 **Environment** 페이지에서 필요한 값을 추가합니다.

| Key | Value |
| --- | --- |
| `OPENAI_API_KEY` | 운영진이 제공한 API 키 |
| `OPENAI_MODEL` | `gpt-4o-mini` |

실제 모델 대화에는 API 키가 필요합니다. 원본 파일은 Git에 넣지 않고 플랫폼의 비밀 환경 변수로 전달합니다. `PORT`는 Render가 서비스 실행 환경에 제공하므로 직접 고정하지 말고 앱이 환경 변수 값을 사용하도록 둡니다. 비밀 값은 README·저장소·빌드 명령에 적지 마세요. [Render 환경 변수 설정](https://render.com/docs/configure-environment-variables)

## 4. 배포하고 접속하기

1. 설정을 확인하고 **Create Web Service**를 누릅니다.
2. 서비스의 **Events** 또는 **Deploys** 페이지에서 빌드와 배포 진행 상태를 확인합니다.
3. 로그에 빌드 실패나 앱 시작 오류가 없는지 확인합니다. 상태가 Live가 되면 서비스 페이지의 `https://<서비스이름>.onrender.com` 주소를 엽니다.
4. 공개 주소에서 다음 항목을 확인합니다.

   - `/`, `/detail`, `/chat` 화면
   - `/assets/css/style.css`, `/assets/js/chatbot.js`, 로고 이미지
   - `/health` 상태 응답
   - 채팅 메시지 전송과 JSON 응답
   - 모델을 연결했다면 실제 모델 답변과 API 실패 처리

화면만 열리는 것으로는 배포 확인이 끝나지 않습니다. 브라우저 개발자 도구의 **Network**에서 `POST /api/chat` 상태와 응답을 확인하고, 서버 오류가 있으면 Render의 **Logs**에서 원인을 찾으세요.

## 5. 변경 사항 배포하기

GitHub 저장소에서 Render에 연결한 브랜치에 변경이 push되면 자동으로 빌드·배포됩니다. 팀 작업은 기능 브랜치에서 검토를 마친 뒤 `main`에 Pull Request를 합치고, Render가 새 커밋을 배포하도록 운영하는 방식을 권장합니다.

환경 변수를 바꿨다면 Environment 페이지에서 저장하고 배포를 진행합니다. 코드 변경 없이 다시 올려야 하면 서비스의 **Deploys → Manual Deploy → Deploy latest commit**을 선택합니다. 메뉴 이름은 Render 대시보드 업데이트에 따라 달라질 수 있습니다. [Render 배포 방식](https://render.com/docs/deploys)

## 6. 자주 발생하는 문제

| 증상 | 확인할 내용 |
| --- | --- |
| 빌드가 실패함 | Build 로그에서 첫 오류를 찾습니다. Root Directory, Python 버전, `requirements.txt`, 패키지 이름을 확인합니다. |
| 빌드는 끝났지만 앱이 시작되지 않음 | Start Command가 `app:app`을 가리키는지, Gunicorn이 설치됐는지, 앱이 `$PORT`에 바인딩하는지 확인합니다. Runtime Logs도 확인합니다. |
| 페이지는 보이지만 CSS·JS·이미지가 없음 | Network에서 실패한 URL과 상태 코드를 확인합니다. 파일이 저장소에 있고 Flask 또는 배포 구조가 그 경로를 제공하는지 확인합니다. |
| 채팅 요청이 `500`으로 실패함 | `POST /api/chat` 응답과 Runtime Logs를 함께 확인합니다. 모델 연결 시 환경 변수의 이름과 설정 여부를 확인하되 키 값은 로그나 질문에 붙이지 않습니다. |
| 첫 요청이 오래 걸림 | Free 웹 서비스는 15분간 요청이 없으면 중지될 수 있고, 다시 시작하는 데 약 1분이 걸릴 수 있습니다. [현재 Free 서비스 제한](https://render.com/docs/free)을 확인하세요. |
| 재시작·재배포 뒤 파일로 저장한 데이터가 사라짐 | Render 파일 시스템은 기본적으로 임시 저장소입니다. 실행 중 생성하는 ChromaDB 인덱스·업로드 파일·SQLite 데이터를 로컬 파일에만 보관하지 말고, 요구에 맞는 외부 데이터 저장소를 설계하세요. Free 웹 서비스는 Persistent Disk를 지원하지 않습니다. [파일 저장소 안내](https://render.com/docs/disks) |
| 저장소를 연결할 수 없음 | Render의 GitHub 연결 설정에서 저장소 접근 권한을 확인한 뒤 다시 연결합니다. |

Free 서비스의 수면·저장소·사용량 조건은 변경될 수 있습니다. 현재 제한은 배포 전에 Render 공식 문서에서 다시 확인하세요. 이 안내에는 Render 요금이나 특정 플랜을 필수로 정하지 않았습니다.
