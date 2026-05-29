# 고방 찾기 (방극 기반)

본초를 입력하면 해당 본초가 포함된 처방을 자동으로 리스트업해주는 로컬(PC) 프로그램입니다.

## 실행

1. (처음 1회) `run_build_data.bat` 더블클릭 → `formulas.json` 생성
2. `run_app.bat` 더블클릭

> 네트워크 폴더(`\\mainnas\...`)에서 `cmd`로 직접 실행하면 UNC 경로 문제가 생길 수 있습니다.
> 배치파일 더블클릭이나 `python \\...\build_data.py`처럼 전체 경로를 넘기는 방식을 권장합니다.

## 검색 기능

- **포함 본초**: 찾고 싶은 본초를 쉼표·공백·슬래시로 구분해 입력
- **모드**
  - `AND`: 입력한 본초를 *모두* 포함한 처방만
  - `OR`: 입력한 본초 중 *하나라도* 포함한 처방
- **제외 본초**: 여기에 입력한 본초가 들어간 처방은 결과에서 제외

## 정규화 규칙

검색 시 아래 동의어는 자동으로 통일됩니다.

| 입력 | 통일 |
|---|---|
| 육계 | 계지 |
| 작약 / 적작약 / 백작약 / 강작약 | 백작약 |
| 생강즙 | 생강 |

**불용어(검색에서 제외):** 그램, 미청주, 반승, 반합, 반근, 말, 물, 봉, 각, 등분 등 용량·단위·용매 표현

## 파일 구조

```
gobang_finder/
├── app.py                  # Tkinter UI 프로그램
├── build_data.py           # 원문 → formulas.json 변환 스크립트
├── logging_utils.py        # 앱 로그 유틸
├── run_app.bat             # 앱 실행
├── run_build_data.bat      # 데이터 재생성
├── data/
│   ├── banggeuk_source.txt # 방극 원문
│   ├── aliases.json        # 동의어·불용어 규칙
│   └── formulas.json       # 파싱된 처방 데이터 (프로그램이 직접 사용)
└── logs/
    └── app.log             # 오류 로그 (앱 실행 시 자동 생성)
```

## 원문 수정 후 재빌드

`banggeuk_source.txt` 또는 `aliases.json`을 수정한 경우 `run_build_data.bat`을 다시 실행하면 `formulas.json`이 갱신됩니다.

## (선택) exe로 만들기

Python 없이 배포하려면 PyInstaller로 묶을 수 있습니다.

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile app.py
```

완성된 exe는 `dist/app.exe`로 생성됩니다.
