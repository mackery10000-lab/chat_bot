# Docker 로컬 실행

Docker Desktop 또는 Docker Engine·Compose를 준비한 뒤 프로젝트 루트에서 docker compose up --build를 실행한다. 주소는 http://127.0.0.1:5001/ 이다. VS Code에서 로컬 Python으로 실행할 때의 주소 5000과 구분한다.

원본 .env는 그대로 두고 Compose가 키와 모델을 읽게 한다. 환경 파일을 새로 만들거나 이미지에 복사하지 않는다. 의존성 변경 시 이미지를 다시 빌드한다.

기존 app.py·services·config·templates·public·tests 마운트는 유지한다. data는 이름 있는 train_state 볼륨에 보관하고 knowledge·images는 기존 읽기 전용 파일을 사용한다. 컨테이너를 다시 생성해도 볼륨이 유지되면 진행을 보존한다.

개발용 Compose의 FLASK_DEBUG는 원본과 같이 1이다. 공개 배포에는 기본 Dockerfile의 Gunicorn 명령을 사용하고 배포 환경을 별도 검수한다.

자동 검사는 컨테이너에서 python -m unittest discover -s tests -v로 실행할 수 있다. 최종 ZIP의 실제 검수 범위는 루트 README에 명시한다. Docker 데몬에서 직접 실행하지 않은 경우 실행했다고 표기하지 않는다.
