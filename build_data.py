from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SOURCE_TXT = DATA_DIR / "banggeuk_source.txt"
ALIASES_JSON = DATA_DIR / "aliases.json"
OUTPUT_JSON = DATA_DIR / "formulas.json"


def _load_aliases() -> tuple[dict[str, str], set[str], tuple[str, ...]]:
    cfg = json.loads(ALIASES_JSON.read_text(encoding="utf-8"))
    normalize_to = cfg.get("normalize_to", {})
    stopwords = set(cfg.get("stopwords", []))
    suffix_stop = tuple(cfg.get("formula_suffix_stop", []))

    alias_to_norm: dict[str, str] = {}
    for norm, aliases in normalize_to.items():
        for a in aliases:
            alias_to_norm[a] = norm
    return alias_to_norm, stopwords, suffix_stop


def normalize_herb(name: str, alias_to_norm: dict[str, str]) -> str:
    name = name.strip()
    if not name:
        return name
    return alias_to_norm.get(name, name)


def _looks_like_formula(token: str, suffix_stop: tuple[str, ...]) -> bool:
    # 처방명(XX탕/XX산/XX환...)이 본초로 섞여 들어오는 것을 줄이기 위한 휴리스틱
    return any(token.endswith(suf) for suf in suffix_stop) and len(token) >= 3


def extract_herbs_with_dose(
    text: str, *, stopwords: set[str], suffix_stop: tuple[str, ...]
) -> list[tuple[str, str | None]]:
    """약재명과 용량 문자열을 함께 추출합니다.

    반환값: [(약재명, 용량문자열_or_None), ...]
    - 용량이 명시된 경우: ("계지", "8"), ("교이", "16-20그램")
    - 용량 없음:           ("복령", None)
    - 각등분:              ("감수", "등분"), ("대극", "등분"), ...
    """

    # 외부 괄호(부연 설명) 내용 제거
    clean = re.sub(r"\([^)]*\)", " ", text)

    # 각N / 각등분 처리 — 도량 없는 약재에 공통 용량 부여
    m_gak = re.search(r"각\s*(\d+(?:\.\d+)?(?:\s*(?:그램|g|cc|ml))?|등분)", clean)
    deungbun_dose: str | None = m_gak.group(1).strip() if m_gak else None
    has_deungbun = bool(deungbun_dose)

    # 기호 정리 (숫자 사이 - 는 범위 표기로 보존, . 도 소수점 보존)
    clean = (
        clean
        .replace("+", " ").replace("–", " ").replace("?", " ")
        .replace("·", " ").replace("/", " ")
    )
    clean = re.sub(r"(?<!\d)-(?!\d)", " ", clean)   # 숫자 외 하이픈 제거
    clean = re.sub(r"(?<!\d)\.(?!\d)", " ", clean)  # 숫자 외 마침표 제거

    # 약재명 + 선택적 용량
    dose_re = re.compile(
        r"([가-힣]{1,10})"
        r"(?:\s*(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\s*"
        r"(?:그램|g|cc|ml|승|합|근|냥|푼|돈|매)?))?"
    )

    results: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    for m in dose_re.finditer(clean):
        herb = m.group(1).strip()
        dose_raw = (m.group(2) or "").strip() or None

        if not herb or herb in stopwords:
            continue
        if _looks_like_formula(herb, suffix_stop):
            continue
        if herb in seen:
            continue
        seen.add(herb)

        if has_deungbun and dose_raw is None:
            dose_raw = deungbun_dose

        results.append((herb, dose_raw))

    return results


def _extract_composition_raw(chunk: str) -> str | None:
    """// · / · 무구분자 형식을 모두 처리해 구성 원문을 반환합니다."""
    lines = [l.strip() for l in chunk.split("\n")]
    first = lines[0] if lines else ""

    def _strip_outer_parens(s: str) -> str:
        """전체가 괄호로 감싸인 경우 외부 괄호를 벗깁니다 (예: 78번 처방)."""
        s = s.strip()
        if not (s.startswith("(") and s.endswith(")")):
            return s
        depth = 0
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                return s  # 중간에 닫힘 → 전체를 감싸는 것 아님
        return s[1:-1].strip()

    # 1. // 구분자 (가장 일반적)
    if "//" in first:
        return _strip_outer_parens(first.split("//", 1)[1]) or None

    # 2. 단독 / 구분자 (// 의 일부가 아닌 것, 후행 / 는 제외)
    m = re.search(r"(?<!/)/(?!/)", first)
    if m:
        after = first[m.end():].strip()
        if after:
            return after

    # 3. 구분자 없음: 마지막 한자(CJK) 이후 한글+숫자 텍스트
    last_cjk = max(
        (i for i, ch in enumerate(first) if "一" <= ch <= "鿿"),
        default=-1,
    )
    if last_cjk >= 0:
        tail = first[last_cjk + 1:].lstrip(". ")
        if tail and re.search(r"[가-힣]", tail):
            return tail

    # 4. 한자 없음: 처방명 괄호 닫힘 이후 한글+숫자 텍스트
    #    예: "117.(통맥사역탕) 감초4 건강6 부자1그램"
    m2 = re.search(r"\)\s+([가-힣].*)", first)
    if m2:
        return m2.group(1).strip() or None

    # 5. 첫 줄에 구성 없음: 바로 다음 비어있지 않은 줄 탐색
    #    예: 205번 "당귀사역탕 : ...\n\n대조12 계지 강작약 당귀..."
    for line in lines[1:]:
        if not line:
            continue
        if re.search(r"[가-힣]\d", line) or "등분" in line:
            return line
        break  # 첫 번째 비어있지 않은 줄이 구성이 아니면 포기

    return None


def _find_base_formula_name(composition_raw: str, formula_names: set[str]) -> str | None:
    """구성 문자열이 'OO탕 + ...' 처럼 다른 처방을 참조할 때 base 처방명을 찾습니다."""

    s = composition_raw.strip()
    # 긴 이름부터 매칭(예: '계지거작약탕'이 '계지탕'보다 우선)
    for name in sorted(formula_names, key=len, reverse=True):
        if s.startswith(name):
            return name
    return None


def _parse_ops(remainder: str) -> list[tuple[str, str]]:
    """'+ 본초', '- 본초' 연산을 파싱합니다.

    주의: 용량 범위(예: 6-15그램)의 '-'는 연산이 아니므로 무시합니다.
    """

    s = remainder.replace("–", "-")
    ops: list[tuple[str, str]] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in "+-":
            prev = s[i - 1] if i > 0 else " "
            # 숫자 범위(6-15) 같은 경우는 연산자가 아님
            if prev.isdigit():
                i += 1
                continue

            op = ch
            i += 1
            while i < len(s) and s[i].isspace():
                i += 1
            start = i

            while i < len(s):
                if s[i] in "+-":
                    # 다음 연산자인지 확인(숫자 범위는 제외)
                    if s[i - 1].isdigit():
                        i += 1
                        continue
                    break
                i += 1

            seg = s[start:i].strip()
            if seg:
                ops.append((op, seg))
            continue
        i += 1
    return ops


def _resolve_references(
    formulas: list["Formula"],
    *,
    alias_to_norm: dict[str, str],
    stopwords: set[str],
    suffix_stop: tuple[str, ...],
) -> None:
    """처방 구성에 '기본방 + 가감' 형태가 있으면 기본방의 약재를 상속해 확장합니다.

    예)
    - '계지탕 + 계지6'  => 계지탕 구성 + 계지
    - '계지탕 – 적작약6' => 계지탕 구성 - 작약

    여러 단계 참조를 위해 몇 회 반복하며 해석합니다.
    """

    by_name: dict[str, Formula] = {f.name: f for f in formulas}
    names = set(by_name.keys())

    def resolve_one(
        f: Formula,
    ) -> tuple[list[str], list[str | None], list[str]] | None:
        if not f.composition_raw:
            return None

        base_name = _find_base_formula_name(f.composition_raw, names)
        if not base_name or base_name == f.name:
            return None

        base = by_name.get(base_name)
        if not base or not base.herbs_norm:
            return None

        remainder = f.composition_raw.strip()[len(base_name):]
        ops = _parse_ops(remainder)
        if not ops and not remainder.strip():
            # 단순 참조 — base 그대로 상속
            return list(base.herbs_raw), list(base.herbs_dose), list(base.herbs_norm)
        if not ops:
            return None

        # base 기반으로 +/− 순차 적용
        resolved_norm = list(base.herbs_norm)
        resolved_raw  = list(base.herbs_raw)   # 원본명 상속 (이전 버그 수정)
        resolved_dose = list(base.herbs_dose)  # 용량 상속

        def extract_with_dose(seg: str) -> list[tuple[str, str, str | None]]:
            pairs = extract_herbs_with_dose(
                seg, stopwords=stopwords, suffix_stop=suffix_stop
            )
            return [(h, normalize_herb(h, alias_to_norm), d) for h, d in pairs]

        for op, seg in ops:
            rdnd = extract_with_dose(seg)
            norms_set = {n for _, n, _ in rdnd}
            if op == "+":
                for raw, norm, dose in rdnd:
                    if norm not in resolved_norm:
                        resolved_norm.append(norm)
                        resolved_raw.append(raw)
                        resolved_dose.append(dose)
            else:  # '-'
                kept = [(r, d, n) for r, d, n in zip(resolved_raw, resolved_dose, resolved_norm)
                        if n not in norms_set]
                resolved_raw  = [x[0] for x in kept]
                resolved_dose = [x[1] for x in kept]
                resolved_norm = [x[2] for x in kept]

        return resolved_raw, resolved_dose, resolved_norm

    # 여러 단계 참조를 위해 반복 (A→B→C)
    for _ in range(5):
        changed = False
        for f in formulas:
            resolved = resolve_one(f)
            if not resolved:
                continue
            herbs_raw, herbs_dose, herbs_norm = resolved
            if herbs_norm != f.herbs_norm:
                f.herbs_raw  = herbs_raw
                f.herbs_dose = herbs_dose
                f.herbs_norm = herbs_norm
                changed = True
        if not changed:
            break


@dataclass
class Formula:
    no: int
    name: str
    raw: str
    composition_raw: str | None
    herbs_raw: list[str]
    herbs_norm: list[str]
    herbs_dose: list[str | None]


def parse_source(text: str) -> list[Formula]:
    alias_to_norm, stopwords, suffix_stop = _load_aliases()

    # 번호로 시작하는 라인을 기준으로 split
    # 1.(...), 11(...), 205. ... 모두 대응
    item_re = re.compile(
        r"(?m)^\s*(\d{1,4})\s*(?:\.|\))?\s*(?=\(|[가-힣A-Za-z一-鿿])"
    )
    starts = [(m.start(), int(m.group(1))) for m in item_re.finditer(text)]
    if not starts:
        raise RuntimeError("번호 항목을 찾지 못했습니다.")

    starts.append((len(text), -1))
    formulas: list[Formula] = []

    for (pos, no), (next_pos, _) in zip(starts, starts[1:]):
        chunk = text[pos:next_pos].strip()
        if not chunk:
            continue

        # 처방명 파싱
        m_name = re.search(r"^\s*\d+\s*\.?\s*\(([^)]+)\)", chunk)
        if m_name:
            name = m_name.group(1).strip()
        else:
            # 예: 10.오두계지탕
            m2 = re.search(r"^\s*\d+\s*\.?\s*([가-힣A-Za-z0-9/]+)", chunk)
            name = (m2.group(1).strip() if m2 else f"item_{no}")

        composition_raw = _extract_composition_raw(chunk)

        # (약재명, 용량) 쌍 추출
        herb_dose_pairs: list[tuple[str, str | None]] = []
        if composition_raw:
            herb_dose_pairs = extract_herbs_with_dose(
                composition_raw, stopwords=stopwords, suffix_stop=suffix_stop
            )

        # 정규화 기준 중복 제거 (첫 등장 항목 우선)
        seen: set[str] = set()
        herbs_raw: list[str] = []
        herbs_dose: list[str | None] = []
        herbs_norm_dedup: list[str] = []
        for raw, dose in herb_dose_pairs:
            norm = normalize_herb(raw, alias_to_norm)
            if norm not in seen:
                seen.add(norm)
                herbs_raw.append(raw)
                herbs_dose.append(dose)
                herbs_norm_dedup.append(norm)

        formulas.append(
            Formula(
                no=no,
                name=name,
                raw=chunk,
                composition_raw=composition_raw,
                herbs_raw=herbs_raw,
                herbs_norm=herbs_norm_dedup,
                herbs_dose=herbs_dose,
            )
        )

    # '기본방 + 가감' 형태 해석
    _resolve_references(
        formulas,
        alias_to_norm=alias_to_norm,
        stopwords=stopwords,
        suffix_stop=suffix_stop,
    )

    return formulas


def main() -> None:
    text = SOURCE_TXT.read_text(encoding="utf-8")
    formulas = parse_source(text)

    payload = {
        "source": "방극",
        "count": len(formulas),
        "formulas": [
            {
                "no": f.no,
                "name": f.name,
                "herbs_raw": f.herbs_raw,
                "herbs_norm": f.herbs_norm,
                "herbs_dose": f.herbs_dose,
                "composition_raw": f.composition_raw,
                "raw": f.raw,
            }
            for f in formulas
        ],
    }

    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OK: wrote {OUTPUT_JSON} (formulas={len(formulas)})")


if __name__ == "__main__":
    main()
