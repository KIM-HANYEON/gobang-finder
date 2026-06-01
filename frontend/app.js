'use strict';

// ── TagInput ───────────────────────────────────────────────────────────────────

class TagInput {
  constructor(container, { chipExtraClass = '', onReturn = null } = {}) {
    this.container      = container;
    this.chipExtraClass = chipExtraClass;
    this.onReturn       = onReturn;
    this.aliasMap       = {};
    this.herbs          = [];           // normalised herb names

    this._input = document.createElement('input');
    this._input.type        = 'text';
    this._input.placeholder = container.dataset.placeholder || '';
    container.appendChild(this._input);

    container.addEventListener('click', () => this._input.focus());
    this._input.addEventListener('keydown',  e => this._onKeyDown(e));
    this._input.addEventListener('input',    ()  => this._onInput());
  }

  // ── event handlers ──────────────────────────────────────────────────────────

  _onKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      this._commit();
      if (this.onReturn) this.onReturn();
      return;
    }
    if (e.key === 'Backspace' && !this._input.value && this.herbs.length) {
      this._removeByNorm(this.herbs[this.herbs.length - 1]);
    }
  }

  _onInput() {
    const v = this._input.value;
    if (v.endsWith(',') || v.endsWith(' ')) this._commit();
  }

  // ── chip management ─────────────────────────────────────────────────────────

  _commit() {
    const raw = this._input.value.replace(/[,\s]+$/, '').trim();
    if (!raw) return;
    this._input.value = '';

    for (const word of raw.split(/[,\s]+/).map(s => s.trim()).filter(Boolean)) {
      const norm = this.aliasMap[word] || word;
      if (norm && !this.herbs.includes(norm)) {
        this.herbs.push(norm);
        const display = word !== norm ? `${word}→${norm}` : word;
        this._addChip(norm, display);
      }
    }
  }

  _addChip(norm, display) {
    const chip = document.createElement('span');
    chip.className  = 'chip' + (this.chipExtraClass ? ' ' + this.chipExtraClass : '');
    chip.dataset.norm = norm;

    const label = document.createTextNode(display);
    chip.appendChild(label);

    const x = document.createElement('span');
    x.className   = 'chip__remove';
    x.textContent = '×';
    x.addEventListener('click', e => { e.stopPropagation(); this._removeByNorm(norm); });
    chip.appendChild(x);

    this.container.insertBefore(chip, this._input);
  }

  _removeByNorm(norm) {
    const i = this.herbs.indexOf(norm);
    if (i >= 0) this.herbs.splice(i, 1);
    const chip = this.container.querySelector(`.chip[data-norm="${CSS.escape(norm)}"]`);
    if (chip) chip.remove();
  }

  // ── public API ──────────────────────────────────────────────────────────────

  getHerbs() {
    this._commit();
    return [...this.herbs];
  }

  setHerbs(herbs) {
    this.clear();
    for (const h of herbs) {
      const norm = this.aliasMap[h] || h;
      if (!this.herbs.includes(norm)) {
        this.herbs.push(norm);
        const display = h !== norm ? `${h}→${norm}` : h;
        this._addChip(norm, display);
      }
    }
  }

  clear() {
    this.container.querySelectorAll('.chip').forEach(c => c.remove());
    this.herbs = [];
    this._input.value = '';
  }
}


// ── App ────────────────────────────────────────────────────────────────────────

class App {
  constructor() {
    this.formulas       = [];
    this.aliases        = {};
    this.aliasMap       = {};
    this.currentInclude = new Set();
    this.selectedNo     = null;
    this._detailText    = '';

    this._initDOM();
    this._bindEvents();
    this._bindSplitter();
    this._init();
  }

  // ── DOM init ─────────────────────────────────────────────────────────────────

  _initDOM() {
    this.$include = document.getElementById('include-input');
    this.$exclude = document.getElementById('exclude-input');
    this.$mode    = document.getElementById('mode-toggle');
    this.$results = document.getElementById('results-list');
    this.$badge   = document.getElementById('result-badge');
    this.$detail  = document.getElementById('detail-content');
    this.$status  = document.getElementById('status-text');

    this.includeInput = new TagInput(this.$include, { onReturn: () => this.search() });
    this.excludeInput = new TagInput(this.$exclude);
  }

  // ── event binding ────────────────────────────────────────────────────────────

  _bindEvents() {
    document.getElementById('search-btn').addEventListener('click', () => this.search());

    this.$mode.querySelectorAll('.seg').forEach(btn => {
      btn.addEventListener('click', () => {
        this.$mode.querySelectorAll('.seg').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    document.getElementById('btn-copy').addEventListener('click',    () => this.copyDetail());
    document.getElementById('btn-save').addEventListener('click',    () => this.saveDetail());
    document.getElementById('btn-aliases').addEventListener('click', () => this.showAliases());
    document.getElementById('btn-reset').addEventListener('click',   () => this.reset());

    document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
    document.getElementById('aliases-modal').addEventListener('click', e => {
      if (e.target === e.currentTarget) this.closeModal();
    });

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape')             { this.closeModal(); return; }
      if (e.ctrlKey && e.key === 'c')     { e.preventDefault(); this.copyDetail(); }
      if (e.ctrlKey && e.key === 's')     { e.preventDefault(); this.saveDetail(); }
    });
  }

  // ── splitter drag ────────────────────────────────────────────────────────────

  _bindSplitter() {
    const splitter     = document.getElementById('splitter');
    const resultsPanel = document.querySelector('.results-panel');
    let   dragging     = false;
    let   startX       = 0;
    let   startW       = 0;

    splitter.addEventListener('mousedown', e => {
      dragging = true;
      startX   = e.clientX;
      startW   = resultsPanel.offsetWidth;
      splitter.classList.add('dragging');
      document.body.style.cursor = 'col-resize';
      e.preventDefault();
    });

    document.addEventListener('mousemove', e => {
      if (!dragging) return;
      const delta = e.clientX - startX;
      const next  = Math.max(180, Math.min(520, startW + delta));
      resultsPanel.style.width = next + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      splitter.classList.remove('dragging');
      document.body.style.cursor = '';
    });
  }

  // ── data bootstrap ────────────────────────────────────────────────────────────

  async _init() {
    try {
      const [formulasRes, aliasesRes] = await Promise.all([
        fetch('data/formulas.json'),
        fetch('data/aliases.json'),
      ]);
      this.formulas = (await formulasRes.json()).formulas;
      this.aliases  = await aliasesRes.json();
      this._buildAliasMap();

      this._setStatus(`처방 ${this.formulas.length}개 로드 완료`, 'ok');
      this.includeInput.setHerbs(['계지', '작약']);
      this._showWelcome();
    } catch (e) {
      this._setStatus('초기화 오류: ' + e, 'err');
    }
  }

  _buildAliasMap() {
    const normMap = this.aliases.normalize_to || {};
    for (const [norm, aliases] of Object.entries(normMap)) {
      for (const alias of aliases) this.aliasMap[alias] = norm;
    }
    this.includeInput.aliasMap = this.aliasMap;
    this.excludeInput.aliasMap = this.aliasMap;
  }

  _searchLocal(includeHerbs, excludeHerbs, mode) {
    const incSet   = new Set(includeHerbs);
    const excSet   = new Set(excludeHerbs);
    const matchCnt = f => f.herbs_norm.filter(h => incSet.has(h)).length;
    const matches  = f => {
      if (f.herbs_norm.some(h => excSet.has(h))) return false;
      if (mode === 'OR') return f.herbs_norm.some(h => incSet.has(h));
      return [...incSet].every(h => f.herbs_norm.includes(h));
    };
    const results = this.formulas
      .filter(matches)
      .sort((a, b) => matchCnt(b) - matchCnt(a));
    const total = incSet.size;
    return {
      ok: true,
      total_include: total,
      results: results.map(f => ({
        no: f.no, name: f.name,
        match_count: matchCnt(f), total,
        full_match: matchCnt(f) === total,
      })),
    };
  }

  _saveFile(text, defaultName) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = defaultName;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── helpers ──────────────────────────────────────────────────────────────────

  _mode() {
    const active = this.$mode.querySelector('.seg.active');
    return active ? active.dataset.value : 'AND';
  }

  _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  _highlight(text, targets) {
    if (!targets.length) return this._esc(text).replace(/\n/g, '<br>');

    let html  = '';
    let plain = '';
    let i     = 0;

    while (i < text.length) {
      if (text[i] === '\n') {
        if (plain) { html += this._esc(plain); plain = ''; }
        html += '<br>';
        i++;
        continue;
      }

      let hit = false;
      for (const t of targets) {
        if (text.startsWith(t, i)) {
          if (plain) { html += this._esc(plain); plain = ''; }
          html += `<span class="herb-match">${this._esc(t)}</span>`;
          i   += t.length;
          hit  = true;
          break;
        }
      }
      if (!hit) { plain += text[i++]; }
    }
    if (plain) html += this._esc(plain);
    return html;
  }

  _setStatus(msg, type = '') {
    this.$status.textContent = msg;
    this.$status.className   = type;
  }

  // ── search ───────────────────────────────────────────────────────────────────

  async search() {
    const include = this.includeInput.getHerbs();
    const exclude = this.excludeInput.getHerbs();

    if (!include.length) {
      this._setStatus('포함 본초를 1개 이상 입력해 주세요.', 'err');
      return;
    }

    this.currentInclude = new Set(include);
    const mode = this._mode();

    try {
      const res = this._searchLocal(include, exclude, mode);
      if (!res.ok) { this._setStatus('검색 오류: ' + (res.error || ''), 'err'); return; }

      this._renderResults(res);

      let status = `모드: ${mode}  ·  포함: ${include.join(', ')}`;
      if (exclude.length) status += `  ·  제외: ${exclude.join(', ')}`;
      status += `  ·  결과: ${res.results.length}개`;
      this._setStatus(status, res.results.length ? 'ok' : 'err');

      if (res.results.length) {
        this._selectItem(res.results[0].no);
      } else {
        this._showEmpty(include);
      }
    } catch (e) {
      this._setStatus('오류: ' + e, 'err');
    }
  }

  // ── results ──────────────────────────────────────────────────────────────────

  _renderResults(data) {
    this.$results.innerHTML = '';
    this.$badge.textContent = data.results.length ? ` ${data.results.length} ` : '';

    for (const r of data.results) {
      const el = document.createElement('div');
      el.className   = 'result-item' + (r.full_match ? ' full-match' : '');
      el.dataset.no  = r.no;
      const star = r.full_match ? '★' : '  ';
      el.innerHTML = `
        <span class="result-no">${this._esc(r.no)}</span>
        <span class="result-name">${this._esc(r.name)}</span>
        <span class="result-match">${star}${this._esc(r.match_count)}/${this._esc(r.total)}</span>`;
      el.addEventListener('click', () => this._selectItem(r.no));
      this.$results.appendChild(el);
    }
  }

  async _selectItem(no) {
    this.$results.querySelectorAll('.result-item').forEach(el => {
      el.classList.toggle('selected', +el.dataset.no === no);
    });

    const selected = this.$results.querySelector('.result-item.selected');
    if (selected) selected.scrollIntoView({ block: 'nearest' });

    this.selectedNo = no;

    const formula = this.formulas.find(f => f.no === no);
    if (!formula) {
      this.$detail.innerHTML = `<span class="d-faint">처방을 찾을 수 없습니다.</span>`;
      return;
    }
    this._renderDetail(formula);
  }

  // ── detail ───────────────────────────────────────────────────────────────────

  _renderDetail(f) {
    const include = this.currentInclude;

    // Collect all raw/alias names that map to an included norm
    const targets = new Set(include);
    for (const [raw, norm] of Object.entries(this.aliasMap)) {
      if (include.has(norm)) targets.add(raw);
    }
    const sortedTargets = [...targets].sort((a, b) => b.length - a.length);

    let html = '';
    html += `<div class="d-title">${this._esc(f.no + '.  ' + f.name)}</div>`;
    html += `<div class="d-divider">${'─'.repeat(36)}</div>`;

    if (f.herbs_raw?.length) {
      html += `<div class="d-section">구성 본초</div><div class="d-body">`;
      const doses = f.herbs_dose || [];
      for (let i = 0; i < f.herbs_raw.length; i++) {
        const herb    = f.herbs_raw[i];
        const dose    = doses[i] ?? null;
        const norm    = this.aliasMap[herb] || herb;
        const matched = include.has(norm);
        const doseHtml = dose
          ? `<span class="herb-dose">${this._esc(dose)}</span>`
          : '';
        html += `<span class="herb-item${matched ? ' herb-match' : ''}">${this._esc(herb)}${doseHtml}</span>`;
      }
      html += `</div>`;
    }

    if (f.composition_raw) {
      html += `<div class="d-section">구성 원문</div>`;
      html += `<div class="d-body">${this._highlight(f.composition_raw, sortedTargets)}</div>`;
    }

    html += `<div class="d-section">원문 전체</div>`;
    html += `<div class="d-body">${this._highlight(f.raw, sortedTargets)}</div>`;

    this.$detail.innerHTML = html;
    this.$detail.scrollTop = 0;

    // Plain text for copy / save
    const parts = [`${f.no}. ${f.name}`, '─'.repeat(36)];
    if (f.herbs_raw?.length) {
      const doses = f.herbs_dose || [];
      const herbLine = f.herbs_raw.map((h, i) => doses[i] ? `${h}(${doses[i]})` : h).join('   ');
      parts.push('\n구성 본초\n' + herbLine);
    }
    if (f.composition_raw)   parts.push('\n구성 원문\n' + f.composition_raw);
    parts.push('\n원문 전체\n' + f.raw);
    this._detailText = parts.join('\n');
  }

  // ── placeholder screens ──────────────────────────────────────────────────────

  _showWelcome() {
    this._detailText = '';
    this.$detail.innerHTML = `
      <div class="d-title">고방 찾기</div>
      <div class="d-divider">${'─'.repeat(36)}</div>
      <div class="d-section" style="margin-top:18px">사용 방법</div>
      <div class="d-body">
        <div>①  포함 본초에 찾고 싶은 본초를 입력하고 <span class="kbd">Enter</span></div>
        <div>②  여러 본초는 쉼표로 구분하거나 순차 입력</div>
        <div>③  AND: 모두 포함 &nbsp;/&nbsp; OR: 하나라도 포함</div>
        <div>④  제외 본초에 입력하면 해당 처방을 결과에서 제외</div>
      </div>
      <div class="d-section">단축키</div>
      <div class="d-faint">
        <div><span class="kbd">Enter</span> 검색 실행</div>
        <div><span class="kbd">Ctrl+C</span> 상세 내용 복사</div>
        <div><span class="kbd">Ctrl+S</span> txt 로 저장</div>
        <div><span class="kbd">Esc</span> 검색 초기화 / 모달 닫기</div>
      </div>`;
  }

  _showEmpty(include) {
    this._detailText = '';
    const chips = include.map(h =>
      `<span class="herb-match" style="margin-right:8px;padding:1px 6px">${this._esc(h)}</span>`
    ).join('');
    this.$detail.innerHTML = `
      <div class="d-title">검색 결과 없음</div>
      <div class="d-divider">${'─'.repeat(36)}</div>
      <div class="d-body" style="margin-top:14px">${chips}</div>
      <div class="d-faint" style="margin-top:12px">
        해당 조합을 포함하는 처방이 없습니다.<br>
        제외 본초를 줄이거나 OR 모드를 사용해 보세요.
      </div>`;
  }

  // ── aliases modal ────────────────────────────────────────────────────────────

  showAliases() {
    try {
      const { normalize_to = {}, stopwords = [] } = this.aliases;
      let html = `<table class="alias-table">
        <thead><tr>
          <th>입력</th><th class="col-arrow"></th><th>통일 표기</th>
        </tr></thead><tbody>`;

      for (const [norm, aliases] of Object.entries(normalize_to)) {
        for (const alias of aliases) {
          if (alias === norm) continue;
          html += `<tr>
            <td>${this._esc(alias)}</td>
            <td class="col-arrow">→</td>
            <td class="col-norm">${this._esc(norm)}</td>
          </tr>`;
        }
      }
      html += `</tbody></table>`;

      if (stopwords.length) {
        html += `<div class="modal-section-title">불용어 (검색 제외)</div>`;
        html += `<div class="stopwords">${stopwords.map(s => this._esc(s)).join('  ')}</div>`;
      }

      html += `<div class="modal-footer">
        <button class="btn-action" id="modal-close-btn">닫  기</button>
      </div>`;

      document.getElementById('modal-body').innerHTML = html;
      document.getElementById('modal-close-btn').addEventListener('click', () => this.closeModal());
      document.getElementById('aliases-modal').classList.remove('hidden');
    } catch (e) {
      this._setStatus('별칭 규칙 로드 오류: ' + e, 'err');
    }
  }

  closeModal() {
    document.getElementById('aliases-modal').classList.add('hidden');
  }

  // ── copy / save ──────────────────────────────────────────────────────────────

  async copyDetail() {
    if (!this._detailText) return;
    try {
      await navigator.clipboard.writeText(this._detailText);
      this._setStatus('클립보드에 복사했습니다.', 'ok');
    } catch (e) {
      this._setStatus('복사 오류: ' + e, 'err');
    }
  }

  saveDetail() {
    if (!this._detailText) return;
    try {
      this._saveFile(this._detailText, '처방.txt');
      this._setStatus('저장 완료: 처방.txt', 'ok');
    } catch (e) {
      this._setStatus('저장 오류: ' + e, 'err');
    }
  }

  // ── reset ────────────────────────────────────────────────────────────────────

  reset() {
    this.includeInput.clear();
    this.excludeInput.clear();
    this.currentInclude = new Set();
    this.selectedNo     = null;
    this._detailText    = '';
    this.$results.innerHTML = '';
    this.$badge.textContent = '';
    this._showWelcome();
    this._setStatus(`처방 ${this.formulas.length}개 로드 완료`, 'ok');
  }
}

// ── Entry ─────────────────────────────────────────────────────────────────────
const app = new App();     // exposed globally so modal footer button can call app.closeModal()
