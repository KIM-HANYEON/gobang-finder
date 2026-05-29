from __future__ import annotations

import json
import traceback
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from logging_utils import setup_file_logger


ROOT       = Path(__file__).resolve().parent
DATA_JSON  = ROOT / "data" / "formulas.json"
ALIASES_JSON = ROOT / "data" / "aliases.json"
LOG_PATH   = ROOT / "logs" / "app.log"

logger = setup_file_logger(log_path=LOG_PATH)

# ── Palette ────────────────────────────────────────────────────────────────────
BG         = "#1A1A1A"
PANEL      = "#222222"
CARD       = "#2A2A2A"
INPUT_BG   = "#2C2C2C"
BORDER     = "#3A3A3A"
GOLD       = "#C8A96E"
GOLD_DARK  = "#8B6914"
GOLD_DIM   = "#5C4420"
RED        = "#C0392B"
RED_DIM    = "#5A1A10"
GREEN      = "#27AE60"
TEXT       = "#EDEDEB"
TEXT_DIM   = "#999992"
TEXT_FAINT = "#555550"
SEL_BG     = "#3A3018"
ALT_ROW    = "#262626"
HL_BG      = "#4A3800"

FONT_BODY  = ("Malgun Gothic", 10)
FONT_BOLD  = ("Malgun Gothic", 10, "bold")
FONT_TITLE = ("Malgun Gothic", 14, "bold")
FONT_SMALL = ("Malgun Gothic", 9)


# ── Data layer ─────────────────────────────────────────────────────────────────

def load_alias_to_norm() -> dict[str, str]:
    cfg = json.loads(ALIASES_JSON.read_text(encoding="utf-8"))
    alias_to_norm: dict[str, str] = {}
    for norm, aliases in cfg.get("normalize_to", {}).items():
        for a in aliases:
            alias_to_norm[a] = norm
    return alias_to_norm


def normalize_herb(name: str, alias_to_norm: dict[str, str]) -> str:
    return alias_to_norm.get(name.strip(), name.strip())


@dataclass
class Formula:
    no: int
    name: str
    herbs_norm: set[str]
    herbs_raw: list[str]
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
            composition_raw=it.get("composition_raw"),
            raw=str(it["raw"]),
        )
        for it in payload.get("formulas", [])
    ]


# ── HerbTagInput ───────────────────────────────────────────────────────────────

class HerbTagInput(tk.Frame):
    """Entry that displays confirmed herbs as removable colour chips."""

    def __init__(
        self,
        master,
        placeholder: str = "본초 입력 후 Enter…",
        tag_bg: str = GOLD,
        tag_fg: str = BG,
        alias_to_norm: dict | None = None,
        on_return: Callable | None = None,
        **kw,
    ):
        super().__init__(
            master,
            bg=INPUT_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            **kw,
        )
        self._placeholder  = placeholder
        self._tag_bg       = tag_bg
        self._tag_fg       = tag_fg
        self._alias        = alias_to_norm or {}
        self._on_return_cb = on_return
        self._herbs: list[str]       = []
        self._raw_map: dict[str, str] = {}
        self._is_placeholder          = False

        self._inner = tk.Frame(self, bg=INPUT_BG)
        self._inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._entry = tk.Entry(
            self._inner,
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=GOLD,
            relief=tk.FLAT,
            font=FONT_BODY,
            bd=0,
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._entry.bind("<FocusIn>",  self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Return>",   self._handle_return)
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self.bind("<Button-1>", lambda _: self._entry.focus_set())

        self._show_placeholder()

    # ── placeholder ────────────────────────────────────────────────────────────

    def _show_placeholder(self) -> None:
        if not self._herbs:
            self._entry.delete(0, tk.END)
            self._entry.config(fg=TEXT_FAINT)
            self._entry.insert(0, self._placeholder)
            self._is_placeholder = True

    def _clear_placeholder(self) -> None:
        if self._is_placeholder:
            self._entry.delete(0, tk.END)
            self._entry.config(fg=TEXT)
            self._is_placeholder = False

    def _on_focus_in(self, _e=None) -> None:
        self._clear_placeholder()

    def _on_focus_out(self, _e=None) -> None:
        self._commit_current()
        if not self._herbs:
            self._show_placeholder()

    # ── key handling ───────────────────────────────────────────────────────────

    def _on_key_release(self, _e=None) -> None:
        if self._is_placeholder:
            return
        text = self._entry.get()
        if text.endswith(",") or text.endswith(" "):
            self._commit_current()

    def _handle_return(self, _e=None) -> None:
        self._commit_current()
        if self._on_return_cb:
            self._on_return_cb()

    # ── commit ─────────────────────────────────────────────────────────────────

    def _commit_current(self) -> None:
        if self._is_placeholder:
            return
        raw = self._entry.get().strip().rstrip(",").strip()
        if not raw:
            return
        self._entry.delete(0, tk.END)
        for word in raw.replace(",", " ").split():
            word = word.strip()
            if not word:
                continue
            norm = self._alias.get(word, word)
            if norm and norm not in self._herbs:
                display = f"{word}→{norm}" if word != norm else word
                self._herbs.append(norm)
                self._raw_map[norm] = display
                self._add_chip(norm, display)

    def _add_chip(self, norm: str, display: str) -> None:
        chip = tk.Frame(self._inner, bg=self._tag_bg, padx=6, pady=2)
        chip.pack(side=tk.LEFT, before=self._entry, padx=(0, 4))

        tk.Label(chip, text=display, bg=self._tag_bg, fg=self._tag_fg,
                 font=FONT_SMALL).pack(side=tk.LEFT)

        x_btn = tk.Label(chip, text="×", bg=self._tag_bg, fg=self._tag_fg,
                          font=FONT_SMALL, cursor="hand2", padx=2)
        x_btn.pack(side=tk.LEFT)
        x_btn.bind("<Button-1>", lambda _e, n=norm, c=chip: self._remove_chip(n, c))

    def _remove_chip(self, norm: str, chip: tk.Frame) -> None:
        if norm in self._herbs:
            self._herbs.remove(norm)
        self._raw_map.pop(norm, None)
        chip.destroy()
        if not self._herbs:
            self._show_placeholder()

    # ── public API ─────────────────────────────────────────────────────────────

    def get_herbs(self) -> list[str]:
        self._commit_current()
        return list(self._herbs)

    def clear(self) -> None:
        for w in list(self._inner.winfo_children()):
            if w is not self._entry:
                w.destroy()
        self._herbs.clear()
        self._raw_map.clear()
        self._is_placeholder = False
        self._show_placeholder()

    def set_herbs(self, herbs: list[str]) -> None:
        self.clear()
        if not herbs:
            return
        self._clear_placeholder()
        for h in herbs:
            norm = self._alias.get(h, h)
            if norm not in self._herbs:
                display = f"{h}→{norm}" if h != norm else h
                self._herbs.append(norm)
                self._raw_map[norm] = display
                self._add_chip(norm, display)


# ── SegmentButton ──────────────────────────────────────────────────────────────

class SegmentButton(tk.Frame):
    """Pill-style AND / OR toggle."""

    def __init__(self, master, values: list[str], variable: tk.StringVar, **kw):
        super().__init__(master, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1, **kw)
        self._var   = variable
        self._btns: dict[str, tk.Label] = {}

        for i, v in enumerate(values):
            if i > 0:
                tk.Frame(self, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=2)
            lbl = tk.Label(self, text=v, font=FONT_BOLD,
                            padx=14, pady=5, cursor="hand2")
            lbl.pack(side=tk.LEFT)
            lbl.bind("<Button-1>", lambda _e, val=v: variable.set(val))
            self._btns[v] = lbl

        variable.trace_add("write", lambda *_: self._refresh())
        self._refresh()

    def _refresh(self) -> None:
        cur = self._var.get()
        for v, lbl in self._btns.items():
            lbl.config(bg=GOLD, fg=BG) if v == cur else lbl.config(bg=CARD, fg=TEXT_DIM)


# ── App ────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("고방 찾기  —  방극")
        self.minsize(980, 680)
        self.configure(bg=BG)

        self._apply_ttk_style()

        self.alias_to_norm = load_alias_to_norm()
        self.formulas      = load_formulas()
        self.filtered: list[Formula]             = []
        self._id_to_formula: dict[str, Formula]  = {}
        self._current_include: set[str]          = set()

        self._build_ui()
        self._show_welcome()
        self._set_status(f"처방 {len(self.formulas)}개 로드 완료")

    # ── ttk style ──────────────────────────────────────────────────────────────

    def _apply_ttk_style(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".",              background=BG,    foreground=TEXT, font=FONT_BODY)
        s.configure("TPanedwindow",   background=BG)
        s.configure("Treeview",
                    background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                    rowheight=28,     font=FONT_BODY,  borderwidth=0)
        s.configure("Treeview.Heading",
                    background=CARD,  foreground=GOLD,  font=FONT_BOLD,
                    relief="flat",    borderwidth=0)
        s.map("Treeview",
              background=[("selected", SEL_BG)],
              foreground=[("selected", GOLD)])
        s.configure("Vertical.TScrollbar",
                    background=CARD,  troughcolor=BG,
                    bordercolor=BORDER, arrowcolor=TEXT_DIM)
        s.map("Vertical.TScrollbar", background=[("active", GOLD_DIM)])

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root_pad = tk.Frame(self, bg=BG)
        root_pad.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        self._build_search_card(root_pad)
        self._build_body(root_pad)
        self._build_bottom(root_pad)
        self._bind_shortcuts()

    def _build_search_card(self, parent: tk.Frame) -> None:
        card = tk.Frame(parent, bg=CARD)
        card.pack(fill=tk.X, pady=(0, 12))

        tk.Frame(card, bg=GOLD, height=2).pack(fill=tk.X)

        inner = tk.Frame(card, bg=CARD, padx=14, pady=12)
        inner.pack(fill=tk.X)

        # Row 0 — include herbs
        r0 = tk.Frame(inner, bg=CARD)
        r0.pack(fill=tk.X)

        tk.Label(r0, text="포함 본초", bg=CARD, fg=TEXT_DIM,
                 font=FONT_SMALL, width=7, anchor="e").pack(side=tk.LEFT, padx=(0, 8))

        self.include_input = HerbTagInput(
            r0,
            placeholder="본초 입력 후 Enter  (예: 계지, 작약)",
            tag_bg=GOLD, tag_fg=BG,
            alias_to_norm=self.alias_to_norm,
            on_return=self.on_search,
        )
        self.include_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.include_input.set_herbs(["계지", "작약"])

        tk.Frame(r0, bg=CARD, width=10).pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value="AND")
        SegmentButton(r0, ["AND", "OR"], self.mode_var).pack(side=tk.LEFT)

        tk.Frame(r0, bg=CARD, width=10).pack(side=tk.LEFT)

        self.search_btn = tk.Button(
            r0, text="검  색", command=self.on_search,
            bg=GOLD, fg=BG, activebackground=GOLD_DARK, activeforeground=TEXT,
            font=FONT_BOLD, relief=tk.FLAT, padx=18, pady=6, cursor="hand2",
        )
        self.search_btn.pack(side=tk.LEFT)

        # Row 1 — exclude herbs
        r1 = tk.Frame(inner, bg=CARD)
        r1.pack(fill=tk.X, pady=(8, 0))

        tk.Label(r1, text="제외 본초", bg=CARD, fg=TEXT_DIM,
                 font=FONT_SMALL, width=7, anchor="e").pack(side=tk.LEFT, padx=(0, 8))

        self.exclude_input = HerbTagInput(
            r1,
            placeholder="결과에서 제외할 본초 입력",
            tag_bg=RED, tag_fg=TEXT,
            alias_to_norm=self.alias_to_norm,
        )
        self.exclude_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)

    def _build_body(self, parent: tk.Frame) -> None:
        pane = tk.PanedWindow(
            parent, orient=tk.HORIZONTAL,
            bg=BG, sashwidth=6, sashrelief=tk.FLAT, sashpad=2,
        )
        pane.pack(fill=tk.BOTH, expand=True)

        # ── Left: results ──────────────────────────────────────────────────────
        left = tk.Frame(pane, bg=BG)
        pane.add(left, minsize=200, width=320)

        hdr = tk.Frame(left, bg=BG)
        hdr.pack(fill=tk.X, pady=(0, 5))
        tk.Label(hdr, text="검색 결과", bg=BG, fg=GOLD,
                 font=FONT_BOLD).pack(side=tk.LEFT)
        self._badge = tk.Label(hdr, text="", bg=GOLD_DIM, fg=GOLD,
                                font=FONT_SMALL, padx=7, pady=1)
        self._badge.pack(side=tk.LEFT, padx=(6, 0))

        tree_wrap = tk.Frame(left, bg=PANEL)
        tree_wrap.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("no", "name", "match"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("no",    text="No")
        self.tree.heading("name",  text="처방명")
        self.tree.heading("match", text="일치")
        self.tree.column("no",    width=50,  anchor="center", stretch=False)
        self.tree.column("name",  width=200, anchor="w")
        self.tree.column("match", width=60,  anchor="center", stretch=False)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_formula)
        self.tree.tag_configure("alt",  background=ALT_ROW)
        self.tree.tag_configure("full", foreground=GOLD)

        ys = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Right: detail ──────────────────────────────────────────────────────
        right = tk.Frame(pane, bg=BG)
        pane.add(right, minsize=300)

        tk.Label(right, text="처방 상세", bg=BG, fg=GOLD,
                 font=FONT_BOLD).pack(anchor="w", pady=(0, 5))

        detail_wrap = tk.Frame(right, bg=PANEL)
        detail_wrap.pack(fill=tk.BOTH, expand=True)
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)

        self.detail = tk.Text(
            detail_wrap,
            wrap=tk.WORD, bd=0, highlightthickness=0,
            padx=16, pady=14,
            bg=PANEL, fg=TEXT,
            insertbackground=GOLD,
            selectbackground=SEL_BG, selectforeground=GOLD,
            font=FONT_BODY,
            state=tk.DISABLED, cursor="arrow",
        )
        self.detail.grid(row=0, column=0, sticky="nsew")

        ds = ttk.Scrollbar(detail_wrap, orient="vertical", command=self.detail.yview)
        self.detail.configure(yscrollcommand=ds.set)
        ds.grid(row=0, column=1, sticky="ns")

        self.detail.tag_configure("title",      font=FONT_TITLE, foreground=GOLD,      spacing3=8)
        self.detail.tag_configure("section",    font=FONT_BOLD,  foreground=TEXT_DIM,  spacing1=10, spacing3=4)
        self.detail.tag_configure("divider",    foreground=TEXT_FAINT)
        self.detail.tag_configure("body",       font=FONT_BODY,  foreground=TEXT)
        self.detail.tag_configure("faint",      foreground=TEXT_FAINT)
        self.detail.tag_configure("herb_match", background=HL_BG, foreground=GOLD)
        self.detail.tag_configure("herb_norm",  foreground=TEXT)

    def _build_bottom(self, parent: tk.Frame) -> None:
        bottom = tk.Frame(parent, bg=BG)
        bottom.pack(fill=tk.X, pady=(10, 0))

        def _btn(text: str, cmd: Callable) -> tk.Button:
            return tk.Button(
                bottom, text=text, command=cmd,
                bg=CARD, fg=TEXT,
                activebackground=GOLD_DIM, activeforeground=GOLD,
                font=FONT_BODY, relief=tk.FLAT,
                padx=12, pady=5, cursor="hand2",
                highlightbackground=BORDER, highlightthickness=1,
            )

        _btn("복사",     self.copy_detail ).pack(side=tk.LEFT)
        _btn("저장",     self.save_detail ).pack(side=tk.LEFT, padx=(6, 0))
        _btn("별칭 규칙", self.show_aliases).pack(side=tk.LEFT, padx=(6, 0))
        _btn("초기화",   self.reset_search).pack(side=tk.LEFT, padx=(6, 0))

        sf = tk.Frame(bottom, bg=CARD, padx=12, pady=5)
        sf.pack(side=tk.RIGHT)
        self._status = tk.Label(sf, text="", bg=CARD, fg=TEXT_DIM,
                                 font=FONT_SMALL, anchor=tk.W)
        self._status.pack(side=tk.LEFT)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-c>", lambda _: self.copy_detail())
        self.bind("<Control-s>", lambda _: self.save_detail())
        self.bind("<Escape>",    lambda _: self.reset_search())
        self.tree.bind("<Up>",   lambda _: None)   # handled natively
        self.tree.bind("<Down>", lambda _: None)

    # ── status ─────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = TEXT_DIM) -> None:
        self._status.config(text=msg, fg=color)

    # ── detail writers ─────────────────────────────────────────────────────────

    def _detail_write(self, callback: Callable) -> None:
        self.detail.config(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        callback()
        self.detail.config(state=tk.DISABLED)
        self.detail.yview_moveto(0)

    def _show_welcome(self) -> None:
        def _write():
            d = self.detail
            d.insert(tk.END, "고방 찾기\n", "title")
            d.insert(tk.END, "─" * 36 + "\n", "divider")
            d.insert(tk.END, "\n")
            d.insert(tk.END, "사용 방법\n", "section")
            for line in [
                "①  포함 본초에 찾고 싶은 본초를 입력하고 Enter",
                "②  여러 본초는 쉼표로 구분하거나 순차 입력",
                "③  AND: 모두 포함  /  OR: 하나라도 포함",
                "④  제외 본초에 입력하면 해당 처방 결과 제외",
            ]:
                d.insert(tk.END, line + "\n", "body")

            d.insert(tk.END, "\n단축키\n", "section")
            for line in [
                "  Enter      검색 실행",
                "  Ctrl + C   상세 내용 복사",
                "  Ctrl + S   txt로 저장",
                "  Esc        검색 초기화",
            ]:
                d.insert(tk.END, line + "\n", "faint")

        self._detail_write(_write)

    def _show_empty_state(self, include: list[str]) -> None:
        def _write():
            d = self.detail
            d.insert(tk.END, "검색 결과 없음\n", "title")
            d.insert(tk.END, "─" * 36 + "\n", "divider")
            d.insert(tk.END, "\n")
            d.insert(tk.END, "  " + "  ".join(include) + "\n\n", "herb_match")
            d.insert(tk.END, "해당 조합을 포함하는 처방이 없습니다.\n", "faint")
            d.insert(tk.END, "제외 본초를 줄이거나 OR 모드를 사용해 보세요.", "faint")

        self._detail_write(_write)

    # ── search ─────────────────────────────────────────────────────────────────

    def on_search(self) -> None:
        include = self.include_input.get_herbs()
        exclude = self.exclude_input.get_herbs()

        if not include:
            messagebox.showinfo("안내", "포함 본초를 1개 이상 입력해 주세요.")
            return

        self._current_include = set(include)
        inc_set  = set(include)
        exc_set  = set(exclude)
        mode     = (self.mode_var.get() or "AND").upper()

        def match_cnt(f: Formula) -> int:
            return len(inc_set & f.herbs_norm)

        def matches(f: Formula) -> bool:
            if exc_set & f.herbs_norm:
                return False
            return bool(inc_set & f.herbs_norm) if mode == "OR" else inc_set.issubset(f.herbs_norm)

        self.filtered = sorted(
            [f for f in self.formulas if matches(f)],
            key=match_cnt, reverse=True,
        )

        self._id_to_formula.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        total = len(inc_set)
        for i, f in enumerate(self.filtered):
            cnt  = match_cnt(f)
            star = "★" if cnt == total else " "
            tags = (["alt"] if i % 2 else []) + (["full"] if cnt == total else [])
            iid  = self.tree.insert("", "end",
                                    values=(f.no, f.name, f"{star}{cnt}/{total}"),
                                    tags=tags)
            self._id_to_formula[iid] = f

        count = len(self.filtered)
        self._badge.config(text=f" {count} " if count else "")

        status = f"모드: {mode}  ·  포함: {', '.join(include)}"
        if exclude:
            status += f"  ·  제외: {', '.join(exclude)}"
        status += f"  ·  결과: {count}개"
        self._set_status(status, GREEN if count else RED)

        if self.filtered:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.see(first)
            self.on_select_formula()
        else:
            self._show_empty_state(include)

    # ── detail render ──────────────────────────────────────────────────────────

    def on_select_formula(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        f = self._id_to_formula.get(sel[0])
        if not f:
            return

        def _write():
            d = self.detail
            d.insert(tk.END, f"{f.no}.  {f.name}\n", "title")
            d.insert(tk.END, "─" * 40 + "\n", "divider")

            if f.herbs_raw:
                d.insert(tk.END, "\n구성 본초\n", "section")
                for i, herb in enumerate(f.herbs_raw):
                    norm = self.alias_to_norm.get(herb, herb)
                    tag  = "herb_match" if norm in self._current_include else "herb_norm"
                    sep  = "   " if i < len(f.herbs_raw) - 1 else ""
                    d.insert(tk.END, herb + sep, tag)
                d.insert(tk.END, "\n")

            if f.composition_raw:
                d.insert(tk.END, "\n구성 원문\n", "section")
                self._insert_highlighted(f.composition_raw + "\n")

            d.insert(tk.END, "\n원문 전체\n", "section")
            self._insert_highlighted(f.raw + "\n")

        self._detail_write(_write)

    def _insert_highlighted(self, text: str) -> None:
        if not self._current_include:
            self.detail.insert(tk.END, text, "body")
            return

        # Build target list: all raw names that map to a matched norm
        targets: list[str] = []
        for norm in self._current_include:
            targets.append(norm)
            for raw, n in self.alias_to_norm.items():
                if n == norm and raw not in targets:
                    targets.append(raw)
        targets.sort(key=len, reverse=True)   # longest first → greedy match

        i = 0
        while i < len(text):
            matched = False
            for t in targets:
                end = i + len(t)
                if text[i:end] == t:
                    self.detail.insert(tk.END, t, "herb_match")
                    i = end
                    matched = True
                    break
            if not matched:
                self.detail.insert(tk.END, text[i], "body")
                i += 1

    # ── actions ────────────────────────────────────────────────────────────────

    def copy_detail(self) -> None:
        text = self.detail.get("1.0", tk.END).strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("클립보드에 복사했습니다.", GREEN)

    def save_detail(self) -> None:
        text = self.detail.get("1.0", tk.END).strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            title="상세 내용을 txt로 저장",
        )
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        self._set_status(f"저장 완료: {Path(path).name}", GREEN)

    def reset_search(self) -> None:
        self.include_input.clear()
        self.exclude_input.clear()
        self._id_to_formula.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._badge.config(text="")
        self._current_include = set()
        self._show_welcome()
        self._set_status(f"처방 {len(self.formulas)}개 로드 완료")

    def show_aliases(self) -> None:
        cfg = json.loads(ALIASES_JSON.read_text(encoding="utf-8"))

        win = tk.Toplevel(self)
        win.title("정규화 규칙")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="정규화 규칙", bg=BG, fg=GOLD,
                 font=FONT_TITLE, padx=20, pady=14).pack(anchor="w")
        tk.Frame(win, bg=BORDER, height=1).pack(fill=tk.X, padx=14)

        # Alias table
        tbl = tk.Frame(win, bg=BG, padx=20, pady=14)
        tbl.pack(fill=tk.X)

        for col, (txt, anchor) in enumerate([("입력", "w"), ("", "center"), ("통일 표기", "w")]):
            tk.Label(tbl, text=txt, bg=BG, fg=TEXT_DIM, font=FONT_BOLD,
                     anchor=anchor, width=12 if col in (0, 2) else 3
                     ).grid(row=0, column=col, sticky="w")

        row = 1
        for norm, aliases in cfg.get("normalize_to", {}).items():
            for alias in aliases:
                if alias == norm:
                    continue
                tk.Label(tbl, text=alias, bg=BG, fg=TEXT,
                         font=FONT_BODY, anchor="w"
                         ).grid(row=row, column=0, sticky="w", pady=2)
                tk.Label(tbl, text="→", bg=BG, fg=TEXT_FAINT,
                         font=FONT_SMALL
                         ).grid(row=row, column=1, padx=8)
                tk.Label(tbl, text=norm, bg=BG, fg=GOLD,
                         font=FONT_BODY, anchor="w"
                         ).grid(row=row, column=2, sticky="w")
                row += 1

        tk.Frame(win, bg=BORDER, height=1).pack(fill=tk.X, padx=14)

        # Stopwords
        sw = tk.Frame(win, bg=BG, padx=20, pady=14)
        sw.pack(fill=tk.X)
        tk.Label(sw, text="불용어 (검색 제외)", bg=BG, fg=TEXT_DIM,
                 font=FONT_BOLD).pack(anchor="w", pady=(0, 6))
        tk.Label(sw, text="  ".join(cfg.get("stopwords", [])),
                 bg=BG, fg=TEXT_FAINT, font=FONT_SMALL,
                 wraplength=340, justify=tk.LEFT).pack(anchor="w")

        tk.Frame(win, bg=BORDER, height=1).pack(fill=tk.X, padx=14)

        tk.Button(win, text="닫  기", command=win.destroy,
                  bg=CARD, fg=TEXT, activebackground=GOLD_DIM, activeforeground=GOLD,
                  font=FONT_BODY, relief=tk.FLAT, padx=20, pady=6,
                  cursor="hand2").pack(pady=14)


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        app = App()
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            logger.exception("Unhandled exception")
        except Exception:
            pass
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "고방 찾기 오류",
            f"예기치 못한 오류가 발생했습니다.\n로그: {LOG_PATH}\n\n{err}",
        )


if __name__ == "__main__":
    main()
