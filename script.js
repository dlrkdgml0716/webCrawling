/* =====================================================
   script.js — Contest Tracker (한국 CS 공모전)
   ===================================================== */

'use strict';

let allContests = [];
let activeFilter = 'all';
let searchQuery  = '';

const grid        = document.getElementById('contestGrid');
const emptyMsg    = document.getElementById('emptyMsg');
const searchInput = document.getElementById('searchInput');
const filterWrap  = document.getElementById('filterWrap');
const updatedAt   = document.getElementById('updatedAt');
const totalCount  = document.getElementById('totalCount');
const weekCount   = document.getElementById('weekCount');
const sourceCount = document.getElementById('sourceCount');

// ── 진입점 ─────────────────────────────────────────────────
(async function init() {
  renderSkeletons(6);
  try {
    const res  = await fetch('contests.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    allContests = data.contests ?? [];
    setMeta(data);
    buildFilterButtons();
    render();
    bindEvents();
  } catch (err) {
    grid.innerHTML = `<p class="empty-msg">데이터를 불러오지 못했습니다: ${err.message}</p>`;
    console.error('[ContestTracker]', err);
  }
})();

// ── 메타 표시 ───────────────────────────────────────────────
function setMeta(data) {
  if (data.crawled_at) {
    updatedAt.textContent = new Date(data.crawled_at).toLocaleString('ko-KR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  }

  totalCount.textContent = allContests.length;

  // 마감이 7일 이내인 공모전 수
  const soon = allContests.filter(c => {
    const d = parseDeadline(c.deadline, c.dday);
    if (!d) return false;
    const diff = d - Date.now();
    return diff > 0 && diff <= 7 * 86_400_000;
  }).length;
  weekCount.textContent = soon;

  const sources = new Set(allContests.map(c => c.source).filter(Boolean));
  sourceCount.textContent = sources.size || 1;
}

// ── 필터 버튼 생성 ──────────────────────────────────────────
function buildFilterButtons() {
  const sources = [...new Set(allContests.map(c => c.source).filter(Boolean))];
  sources.forEach(src => {
    const btn = document.createElement('button');
    btn.className      = 'filter-btn';
    btn.dataset.filter = src;
    btn.textContent    = src;
    filterWrap.appendChild(btn);
  });
}

// ── 이벤트 바인딩 ───────────────────────────────────────────
function bindEvents() {
  searchInput.addEventListener('input', () => {
    searchQuery = searchInput.value.trim().toLowerCase();
    render();
  });
  filterWrap.addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    activeFilter = btn.dataset.filter;
    filterWrap.querySelectorAll('.filter-btn').forEach(b =>
      b.classList.toggle('filter-btn--active', b === btn)
    );
    render();
  });
}

// ── 렌더링 ──────────────────────────────────────────────────
function render() {
  const filtered = allContests.filter(c => {
    const matchSource = activeFilter === 'all' || c.source === activeFilter;
    const matchSearch = !searchQuery ||
      c.name.toLowerCase().includes(searchQuery) ||
      (c.org  ?? '').toLowerCase().includes(searchQuery);
    return matchSource && matchSearch;
  });

  grid.innerHTML = '';
  emptyMsg.hidden = filtered.length > 0;

  // 마감 임박순 정렬 (마감 없는 건 뒤로)
  filtered
    .sort((a, b) => {
      const da = parseDeadline(a.deadline, a.dday);
      const db = parseDeadline(b.deadline, b.dday);
      return (da ?? Infinity) - (db ?? Infinity);
    })
    .forEach(c => grid.appendChild(createCard(c)));
}

// ── 카드 생성 ───────────────────────────────────────────────
function createCard(c) {
  const article = document.createElement('article');
  article.className = 'card';

  const deadline  = parseDeadline(c.deadline, c.dday);
  const urgency   = getUrgency(deadline);
  const sourceTag = getSourceTag(c.source);
  const ddayText  = c.dday || (deadline ? formatDday(deadline) : null);

  if (urgency === 'urgent') article.classList.add('card--urgent');

  article.innerHTML = `
    <div class="card__header">
      <span class="card__source-tag ${sourceTag.cls}">${sourceTag.label}</span>
      ${ddayText
        ? `<span class="card__dday card__dday--${urgency}">${escapeHtml(ddayText)}</span>`
        : ''}
    </div>

    <h2 class="card__name">${escapeHtml(c.name)}</h2>

    <div class="card__meta">
      ${c.org ? `
      <div class="card__meta-row">
        ${iconOrg()}
        <span>${escapeHtml(c.org)}</span>
      </div>` : ''}
      ${c.deadline ? `
      <div class="card__meta-row">
        ${iconClock()}
        <span>마감&nbsp;${escapeHtml(c.deadline)}</span>
      </div>` : ''}
      ${c.category ? `
      <div class="card__meta-row">
        ${iconTag()}
        <span>${escapeHtml(c.category)}</span>
      </div>` : ''}
    </div>

    <div class="card__footer">
      <a class="card__link" href="${c.url}" target="_blank" rel="noopener">
        공모전 보러가기 ${iconArrow()}
      </a>
    </div>
  `;
  return article;
}

// ── 날짜 파싱 ───────────────────────────────────────────────
function parseDeadline(deadline, dday) {
  // "2026-04-30" 형식
  if (deadline) {
    const d = new Date(deadline);
    if (!isNaN(d)) return d;
  }
  // "D-47" 형식으로 역산
  if (dday) {
    const m = dday.match(/D[–-](\d+)/i);
    if (m) {
      const d = new Date();
      d.setDate(d.getDate() + parseInt(m[1], 10));
      return d;
    }
    if (/D\s*\+/.test(dday)) return null; // 마감 지남
  }
  return null;
}

function formatDday(date) {
  const diff = Math.ceil((date - Date.now()) / 86_400_000);
  if (diff < 0)  return '마감';
  if (diff === 0) return 'D-day';
  return `D-${diff}`;
}

// ── 긴급도 분류 ─────────────────────────────────────────────
function getUrgency(date) {
  if (!date) return 'normal';
  const days = Math.ceil((date - Date.now()) / 86_400_000);
  if (days < 0)  return 'closed';
  if (days <= 7) return 'urgent';
  if (days <= 14) return 'soon';
  return 'normal';
}

// ── 소스 태그 ───────────────────────────────────────────────
function getSourceTag(source) {
  const map = {
    '위비티':   { cls: 'tag--wevity',    label: '위비티'   },
    '링커리어': { cls: 'tag--linkareer', label: '링커리어' },
  };
  return map[source] ?? { cls: 'tag--default', label: source ?? '기타' };
}

// ── 스켈레톤 ────────────────────────────────────────────────
function renderSkeletons(n) {
  grid.innerHTML = Array.from({ length: n }, () => `
    <div class="skeleton card">
      <div class="skeleton__line skeleton__line--short"></div>
      <div class="skeleton__line skeleton__line--title"></div>
      <div class="skeleton__line skeleton__line--meta"></div>
      <div class="skeleton__line skeleton__line--meta2"></div>
    </div>`).join('');
}

// ── SVG 아이콘 ──────────────────────────────────────────────
function iconOrg() {
  return `<svg class="card__meta-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <rect x="1.5" y="6" width="13" height="8.5" rx="1" stroke="currentColor" stroke-width="1.2"/>
    <path d="M5 14.5V10h6v4.5" stroke="currentColor" stroke-width="1.2"/>
    <path d="M1.5 6l6.5-4.5L14.5 6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  </svg>`;
}
function iconClock() {
  return `<svg class="card__meta-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
    <path d="M8 5v3.5l2 1.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
  </svg>`;
}
function iconTag() {
  return `<svg class="card__meta-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M2 2h5.5l6.5 6.5-5.5 5.5L2 7.5V2z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
    <circle cx="5" cy="5" r="1" fill="currentColor"/>
  </svg>`;
}
function iconArrow() {
  return `<svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
    <path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

// ── XSS 방지 ────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;',
  }[c]));
}
