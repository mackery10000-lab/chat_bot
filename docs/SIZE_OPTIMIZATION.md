# 용량 최적화와 기능 검증

작업일: 2026-11-02. 용량 단위 MiB는 1,048,576바이트다.

## 적용한 최적화

| 대상 | 적용 내용 | 측정 결과 |
| --- | --- | --- |
| 검수 임시 파일 | Chromium 검수 프로필 4개, 저장 기록이 없는 중복 배포 검수본 4개 정리 | 1,822,488,581바이트 확보 |
| 이미지 | PNG의 IDAT 압축만 zlib level 9로 변경 | 114,093,368 → 105,904,770바이트, 7.18% 감소 |
| 배포용 Python | 사용하지 않는 ensurepip·Tk·IDLE 등의 설치/GUI 도구 제외 | 압축 해제 기준 약 7.08MiB 감소 |
| 배포 이미지 | 현재 실행 코드에서 참조하지 않는 이전 제작 자료 8개 제외 | 압축 해제 기준 17,723,833바이트 감소 |
| 배포 생성 | 최대 ZIP 압축, 검증한 임시 ZIP만 최종 파일로 교체 | 중단·실패 시 이전 정상 ZIP 보존 |

이미지 94개 중 실제 PNG 93개는 압축 해제한 이미지 데이터와 모든 비이미지 청크가 기존 배포본과 정확히 같다. 92개 파일만 작아졌으며, 더 커지는 결과는 적용하지 않았다. 기존 `scene_01.png`는 실제 내용이 JPEG여서 그대로 보존했다. 해상도·색상·알파·메타데이터·이미지 URL을 변경하지 않았다. 등록된 강조 레이어 12개의 1,202,100픽셀 원본 일치도 확인했다.

배포에서 제외하는 원본은 `scene_02.png`, `scene_03.png`, `scene_05.png`부터 `scene_08.png`, `inventory/scrapbook.png`, `inventory/warning.png`다. 이 파일들은 프로젝트에 모두 남아 있다. 빌드 시 실행 코드·설정·템플릿·웹 코드에 파일명이 등장하면 자동으로 배포에 다시 포함한다. 실제 배경, 모든 인물 표정, 강조 마스크, 인벤토리·문서, 글꼴, 음성·영상은 보존한다.

게임 저장 데이터와 API 설정은 건드리지 않는다. 정리 도구는 검수본에 게임 기록이 한 개라도 있거나 `.env` 설정이 있으면 제외한다. 원본 참고 그림·스크립트·검수 결과와 화면도 남긴다. SSL, 인증서, SQLite, OpenAI SDK와 의존 라이브러리는 배포에 유지한다.

## 오류 점검과 재현

새 패키징 도구는 프로젝트의 Python으로 재빌드할 때 같은 파일을 자신에게 복사하던 문제를 해결했다. 정리 도구도 Windows에서 SQLite 파일 핸들을 명시적으로 닫도록 검증했다.

확장된 실제 플레이 검사에서 정차 후 안내도의 `출입구`가 현재 위치라는 이유로 비활성화되는 오류를 발견해 수정했다. 서버가 하차를 허용하는 상태에서는 현재 위치의 출입구 버튼도 누를 수 있다. 다른 현재 위치 버튼과 게임 종료 후 입력 잠금은 유지한다. 안내서 열람 조건, 문 열기, 다이얼과 취소 후 복원, 출입구 실제 클릭, 성공·실패 엔딩을 포함한 집중 검사 24개가 통과했다.

아래 검사들은 별도 임시 저장과 오프라인 응답을 사용한다. 실제 API 호출 비용이나 기존 게임 저장의 변경 없이 실행한다.

명령은 개발용 프로젝트 소스 폴더에서 실행한다. 실행용 ZIP에는 개발 도구와 테스트를 포함하지 않는다.

```powershell
runtime/python.exe -B -X utf8 -m unittest discover -s tests -q
node tools/check_dialogue_ui.mjs
node tools/check_gameplay_ui.mjs
powershell -NoProfile -ExecutionPolicy Bypass -File tools/check_scene_registration.ps1
runtime/python.exe -I -B -X utf8 tools/build_portable.py --reuse-runtime
runtime/python.exe -I -B -X utf8 tools/verify_portable.py --browser
```

검사 범위는 기관사와 다른 인물의 대화·선택지·직접 입력·새로고침, 인벤토리·증거 제출·취소, 손전등, 이름 입력·시작 화면, 창문 영상, 덮개·레버·문손잡이 퍼즐, 분기기 다이얼·최종 확인·취소, 정차·하차와 엔딩이다. 음악 재생·반복·볼륨·음소거·페이지 이동 후 재생 유지도 실제 Chromium으로 검사한다. JavaScript 예외와 이미지/API 요청 실패도 수집한다.

배포 검증은 ZIP 전체와 현재 소스의 일치를 검사한 뒤 새로 압축을 풀어 실행기, 서버, 동영상 Range 응답, SSL 인증서, SQLite, AI SDK 응답 파싱을 확인한다. `--browser`를 붙이면 압축을 푼 게임을 대상으로 같은 게임플레이 브라우저 검사를 실행한다.

## 용량 재증가 방지

새 게임플레이 검사와 배포 검증은 실행 후 임시 브라우저 프로필과 압축 해제본을 자동으로 정리한다. 브라우저 검사 결과는 `.local/gameplay-ui-qa/`, 대화 검사는 `.local/dialogue-ui-qa/`, PNG 압축 기록은 `.local/size-optimization/png-lossless-report.json`에 남는다.

기존 검사에서 남은 생성 파일은 아래 명령으로 미리 확인한 뒤 정리할 수 있다. 브라우저 검사가 모두 끝난 후 실행한다.

```powershell
runtime/python.exe -B -X utf8 tools/clean_generated.py
runtime/python.exe -B -X utf8 tools/clean_generated.py --apply
```

이전 `.local/refresh-portable.py` 대신 추적되는 `tools/build_portable.py --reuse-runtime`을 사용해야 최적화된 배포 구성을 유지한다.
