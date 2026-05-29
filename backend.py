from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from logging_utils import setup_file_logger

ROOT         = Path(__file__).resolve().parent
DATA_JSON    = ROOT / "data" / "formulas.json"
ALIASES_JSON = ROOT / "data" / "aliases.json"
LOG_PATH     = ROOT / "logs" / "app.log"

logger = setup_file_logger(log_path=LOG_PATH)


def load_alias_to_norm() -> dict[str, str]:
    cfg = json.loads(ALIASES_JSON.read_text(encoding="utf-8"))
    alias_to_norm: dict[str, str] = {}
    for norm, aliases in cfg.get("normalize_to", {}).items():
        for a in aliases:
            alias_to_norm[a] = norm
    return alias_to_norm


@dataclass
class Formula:
    no: int
    name: str
    herbs_norm: set[str]
    herbs_raw: list[str]
    herbs_dose: list[str | None]
    composition_raw: str | None
    raw: str


def load_formulas() -> list[Formula]:
    if not DATA_JSON.exists():
        raise FileNotFoundError(
            f"{DATA_JSON} 가 없습니다. 먼저 build_data.py를 실행해 주세요."
        )
    payload = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    return [
        Formula(
            no=int(it["no"]),
            name=str(it["name"]),
            herbs_norm=set(it.get("herbs_norm", [])),
            herbs_raw=list(it.get("herbs_raw", [])),
            herbs_dose=list(it.get("herbs_dose", [None] * len(it.get("herbs_raw", [])))),
            composition_raw=it.get("composition_raw"),
            raw=str(it["raw"]),
        )
        for it in payload.get("formulas", [])
    ]


class GobangAPI:
    """Exposed to JavaScript via window.pywebview.api."""

    def __init__(self) -> None:
        self.alias_to_norm = load_alias_to_norm()
        self.formulas      = load_formulas()
        logger.info("Loaded %d formulas, %d aliases",
                    len(self.formulas), len(self.alias_to_norm))

    # ── read-only queries ──────────────────────────────────────────────────────

    def get_formula_count(self) -> int:
        return len(self.formulas)

    def get_aliases(self) -> dict:
        try:
            data = json.loads(ALIASES_JSON.read_text(encoding="utf-8"))
            return {"ok": True, "data": data}
        except Exception as e:
            logger.exception("get_aliases error")
            return {"ok": False, "error": str(e)}

    def search(self, include_herbs: list[str], exclude_herbs: list[str], mode: str) -> dict:
        try:
            inc_set = set(include_herbs)
            exc_set = set(exclude_herbs)
            mode    = (mode or "AND").upper()

            def match_cnt(f: Formula) -> int:
                return len(inc_set & f.herbs_norm)

            def matches(f: Formula) -> bool:
                if exc_set & f.herbs_norm:
                    return False
                if mode == "OR":
                    return bool(inc_set & f.herbs_norm)
                return inc_set.issubset(f.herbs_norm)

            results = sorted(
                [f for f in self.formulas if matches(f)],
                key=match_cnt, reverse=True,
            )
            total = len(inc_set)
            return {
                "ok": True,
                "total_include": total,
                "results": [
                    {
                        "no":          f.no,
                        "name":        f.name,
                        "match_count": match_cnt(f),
                        "total":       total,
                        "full_match":  match_cnt(f) == total,
                    }
                    for f in results
                ],
            }
        except Exception as e:
            logger.exception("search error")
            return {"ok": False, "error": str(e)}

    def get_formula_detail(self, no: int) -> dict:
        try:
            for f in self.formulas:
                if f.no == no:
                    return {
                        "ok":              True,
                        "no":              f.no,
                        "name":            f.name,
                        "herbs_raw":       f.herbs_raw,
                        "herbs_dose":      f.herbs_dose,
                        "herbs_norm":      list(f.herbs_norm),
                        "composition_raw": f.composition_raw,
                        "raw":             f.raw,
                    }
            return {"ok": False, "error": f"처방 #{no}을 찾을 수 없습니다."}
        except Exception as e:
            logger.exception("get_formula_detail error")
            return {"ok": False, "error": str(e)}

    # ── file / clipboard actions ───────────────────────────────────────────────

    def save_text_file(self, text: str, default_name: str = "처방.txt") -> dict:
        import webview  # local import — only valid inside a running webview session
        windows = webview.windows
        if not windows:
            return {"ok": False, "error": "No window"}
        try:
            result = windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=("Text Files (*.txt)",),
            )
            if result:
                save_path = result[0] if isinstance(result, (list, tuple)) else result
                Path(save_path).write_text(text, encoding="utf-8")
                logger.info("Saved to %s", save_path)
                return {"ok": True, "path": str(save_path)}
            return {"ok": False, "cancelled": True}
        except Exception as e:
            logger.exception("save_text_file error")
            return {"ok": False, "error": str(e)}

    def copy_to_clipboard(self, text: str) -> dict:
        """Win32 clipboard write — works with Korean characters."""
        import ctypes
        try:
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE  = 0x0002
            encoded        = (text + "\x00").encode("utf-16-le")
            handle         = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            ptr            = ctypes.windll.kernel32.GlobalLock(handle)
            ctypes.cdll.msvcrt.memcpy(ctypes.c_char_p(ptr), encoded, len(encoded))
            ctypes.windll.kernel32.GlobalUnlock(handle)
            ctypes.windll.user32.OpenClipboard(0)
            ctypes.windll.user32.EmptyClipboard()
            ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, handle)
            ctypes.windll.user32.CloseClipboard()
            return {"ok": True}
        except Exception as e:
            logger.exception("copy_to_clipboard error")
            return {"ok": False, "error": str(e)}
