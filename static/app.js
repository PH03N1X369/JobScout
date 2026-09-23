(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const DAY = 86400000;
  const PAGE_SIZE = 40;
  const MAX_UPLOAD = 5 * 1024 * 1024;
  const MATCH_LABEL = { strong: 'Strong match', good: 'Good match', partial: 'Partial match' };
  const DATE_PHRASE = { '1': 'in the past 24 hours', '3': 'in the past 3 days', '7': 'in the past week', '14': 'in the past 2 weeks', '30': 'in the past month' };

  // Per-browser preferences only; nothing here needs to be durable.
  const prefs = {
    get(key, fallback) {
      try { const v = localStorage.getItem('jobscout.' + key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem('jobscout.' + key, JSON.stringify(value)); } catch { /* storage unavailable */ }
    },
  };

  const state = {
    profile: null,
    skillOn: new Map(),
    titleOn: new Map(),
    keywords: prefs.get('keywords', []),
    jobs: [],
    sources: [],
    scanned: 0,
    searched: false,
    stale: false,
    date: prefs.get('date', '7'),
    from: '',
    to: '',
    sort: prefs.get('sort', 'relevance'),
    workType: prefs.get('workType', 'any'),
    loc: null,        // resolved form of what's typed in Location (drives the job board links)
    searchLoc: null,  // the location the current results were searched with
    tip: null,
    text: '',
    hiddenSources: new Set(),
    shown: PAGE_SIZE,
  };

  const el = {
    form: $('#search-form'),
    resumeInput: $('#resume-input'),
    dropzone: $('#dropzone'),
    dropzoneText: $('#dropzone-text'),
    resumeStatus: $('#resume-status'),
    profile: $('#profile'),
    titleChips: $('#title-chips'),
    skillChips: $('#skill-chips'),
    toggleAll: $('#toggle-all-skills'),
    tagInput: $('#tag-input'),
    keywordChips: $('#keyword-chips'),
    keywordInput: $('#keyword-input'),
    location: $('#location-input'),
    locationHint: $('#location-hint'),
    searchBtn: $('#search-btn'),
    searchError: $('#search-error'),
    sourcesNote: $('#sources-note'),
    dateFilter: $('#date-filter'),
    customRange: $('#custom-range'),
    dateFrom: $('#date-from'),
    dateTo: $('#date-to'),
    sort: $('#sort-select'),
    workType: $('#work-type'),
    textFilter: $('#text-filter'),
    sourceRow: $('#source-row'),
    sourceChips: $('#source-chips'),
    boards: $('#boards'),
    boardsQuery: $('#boards-query'),
    boardLinks: $('#board-links'),
    summary: $('#summary'),
    notices: $('#notices'),
    list: $('#job-list'),
    showMore: $('#show-more'),
    empty: $('#empty-state'),
    template: $('#job-template'),
  };

  // ------------------------------------------------------------ helpers --

  function setStatus(node, text, kind = '') {
    node.textContent = text || '';
    node.className = 'status' + (kind ? ' ' + kind : '');
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function selected(map) {
    return [...map].filter(([, on]) => on).map(([name]) => name);
  }

  function relativeTime(t) {
    const hours = (Date.now() - t) / 3600000;
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${Math.floor(hours)}h ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    if (days < 30) { const w = Math.floor(days / 7); return w === 1 ? '1 week ago' : `${w} weeks ago`; }
    const m = Math.floor(days / 30);
    return m <= 1 ? '1 month ago' : `${m} months ago`;
  }

  function isRemote(job) {
    return job.remote === true || /\b(remote|anywhere|worldwide)\b/i.test(job.location || '');
  }

  function markStale() {
    if (!state.searched) return;
    state.stale = true;
    el.searchBtn.querySelector('.btn-label').textContent = 'Update results';
  }

  // ------------------------------------------------------------- resume --

  el.resumeInput.addEventListener('change', () => {
    if (el.resumeInput.files[0]) uploadResume(el.resumeInput.files[0]);
  });
  ['dragenter', 'dragover'].forEach((type) => el.dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    el.dropzone.classList.add('drag');
  }));
  ['dragleave', 'drop'].forEach((type) => el.dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    el.dropzone.classList.remove('drag');
  }));
  el.dropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file) uploadResume(file);
  });

  async function uploadResume(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt', 'md'].includes(ext)) {
      setStatus(el.resumeStatus, 'Please choose a PDF, DOCX, or TXT file.', 'error');
      return;
    }
    if (file.size > MAX_UPLOAD) {
      setStatus(el.resumeStatus, 'That file is larger than 5 MB.', 'error');
      return;
    }
    el.dropzoneText.replaceChildren(make('strong', '', file.name), document.createTextNode(' · click to replace'));
    el.dropzone.classList.add('has-file');
    setStatus(el.resumeStatus, 'Reading resume…');

    const body = new FormData();
    body.append('resume', file);
    try {
      const res = await fetch('/api/parse-resume', { method: 'POST', body });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not read that resume.');
      state.profile = data;
      state.skillOn = new Map(data.skills.map((s) => [s.name, true]));
      state.titleOn = new Map(data.titles.map((t) => [t, true]));
      const found = data.skills.length + data.titles.length;
      setStatus(el.resumeStatus,
        found ? `Found ${data.skills.length} skills and ${data.titles.length} likely role${data.titles.length === 1 ? '' : 's'}.`
              : 'No familiar skills found. Add keywords below instead.',
        found ? 'ok' : '');
    } catch (err) {
      state.profile = null;
      state.skillOn = new Map();
      state.titleOn = new Map();
      setStatus(el.resumeStatus, networkMessage(err), 'error');
    }
    el.resumeInput.value = '';
    renderProfile();
    renderBoards();
    markStale();
  }

  function renderProfile() {
    const p = state.profile;
    el.profile.hidden = !p || (!p.skills.length && !p.titles.length);
    if (el.profile.hidden) return;
    renderToggleChips(el.titleChips, p.titles.map((name) => ({ name })), state.titleOn);
    renderToggleChips(el.skillChips, p.skills, state.skillOn);
    el.titleChips.parentElement.hidden = !p.titles.length;
    el.skillChips.parentElement.hidden = !p.skills.length;
    updateToggleAll();
  }

  function renderToggleChips(container, items, map) {
    container.replaceChildren(...items.map((item) => {
      const chip = make('button', 'chip', item.name);
      chip.type = 'button';
      chip.setAttribute('aria-pressed', String(!!map.get(item.name)));
      if (item.count > 1) chip.append(make('span', 'count', `×${item.count}`));
      chip.addEventListener('click', () => {
        map.set(item.name, !map.get(item.name));
        chip.setAttribute('aria-pressed', String(map.get(item.name)));
        updateToggleAll();
        renderBoards();
        markStale();
      });
      return chip;
    }));
  }

  function updateToggleAll() {
    const any = selected(state.skillOn).length + selected(state.titleOn).length > 0;
    el.toggleAll.textContent = any ? 'Deselect all' : 'Select all';
  }

  el.toggleAll.addEventListener('click', () => {
    const value = el.toggleAll.textContent === 'Select all';
    for (const map of [state.skillOn, state.titleOn]) for (const key of map.keys()) map.set(key, value);
    renderProfile();
    renderBoards();
    markStale();
  });

  // ----------------------------------------------------------- keywords --

  function addKeywords(text) {
    for (const raw of text.split(',')) {
      const k = raw.trim();
      if (k && k.length <= 80 && state.keywords.length < 10 &&
          !state.keywords.some((x) => x.toLowerCase() === k.toLowerCase())) {
        state.keywords.push(k);
      }
    }
    onKeywordsChanged();
  }

  function onKeywordsChanged() {
    prefs.set('keywords', state.keywords);
    renderKeywords();
    renderBoards();
    markStale();
  }

  function renderKeywords() {
    el.keywordChips.replaceChildren(...state.keywords.map((k, i) => {
      const chip = make('span', 'chip keyword', k);
      const remove = make('button', '', '×');
      remove.type = 'button';
      remove.setAttribute('aria-label', `Remove ${k}`);
      remove.addEventListener('click', () => {
        state.keywords.splice(i, 1);
        onKeywordsChanged();
        el.keywordInput.focus();
      });
      chip.append(remove);
      return chip;
    }));
    el.keywordInput.placeholder = state.keywords.length ? 'Add another…' : 'e.g. python, product manager';
  }

  el.keywordInput.addEventListener('keydown', (e) => {
    const value = el.keywordInput.value.trim();
    if ((e.key === 'Enter' || e.key === ',') && value) {
      e.preventDefault();
      addKeywords(value);
      el.keywordInput.value = '';
    } else if (e.key === ',') {
      e.preventDefault();
    } else if (e.key === 'Backspace' && !el.keywordInput.value && state.keywords.length) {
      state.keywords.pop();
      onKeywordsChanged();
    }
  });
  el.keywordInput.addEventListener('input', () => {
    if (el.keywordInput.value.includes(',')) {  // pasted "a, b, c"
      const parts = el.keywordInput.value.split(',');
      el.keywordInput.value = parts.pop();
      addKeywords(parts.join(','));
    }
  });
  el.keywordInput.addEventListener('blur', () => {
    if (el.keywordInput.value.trim()) {
      addKeywords(el.keywordInput.value);
      el.keywordInput.value = '';
    }
  });
  el.tagInput.addEventListener('click', (e) => {
    if (e.target === el.tagInput || e.target === el.keywordChips) el.keywordInput.focus();
  });
  let lookupTimer;
  el.location.addEventListener('input', () => {
    prefs.set('location', el.location.value);
    clearTimeout(lookupTimer);
    lookupTimer = setTimeout(lookupLocation, 250);
    renderBoards();
    markStale();
  });

  async function lookupLocation() {
    const q = el.location.value.trim();
    try {
      const res = await fetch('/api/location?q=' + encodeURIComponent(q));
      if (q !== el.location.value.trim()) return;  // typed more since
      state.loc = await res.json();
    } catch {
      state.loc = null;
    }
    renderLocationHint();
    renderBoards();
  }

  function renderLocationHint() {
    const p = state.loc;
    let text = 'Leave blank to see jobs anywhere.';
    if (p?.kind === 'city') text = `Jobs in ${p.label}, plus remote jobs open to ${p.country_name}.`;
    else if (p?.kind === 'country') text = `Jobs in ${p.label}, plus remote jobs open to ${p.label}.`;
    else if (p?.kind === 'remote') text = 'Remote jobs only, from anywhere.';
    else if (p?.kind === 'unknown') text = `“${p.label}” isn't a place JobScout knows yet, so it matches that text, plus remote jobs open worldwide.`;
    el.locationHint.textContent = text;
  }

  // ------------------------------------------------------------- search --

  el.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (el.keywordInput.value.trim()) {
      addKeywords(el.keywordInput.value);
      el.keywordInput.value = '';
    }
    const skills = selected(state.skillOn);
    const titles = selected(state.titleOn);
    if (!state.keywords.length && !skills.length && !titles.length) {
      setStatus(el.searchError, 'Upload a resume or add at least one keyword.', 'error');
      return;
    }
    setStatus(el.searchError, '');
    setLoading(true);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: state.keywords, skills, titles, location: el.location.value.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Search failed. Please try again.');
      state.jobs = data.jobs.map((job, rank) => ({
        ...job,
        rank,
        time: job.postedAt ? Date.parse(job.postedAt) : null,
        sourceGroup: job.source.split(' · ')[0],
        haystack: [job.title, job.company, job.location, job.snippet, ...job.tags].join(' ').toLowerCase(),
      }));
      state.sources = data.sources;
      state.scanned = data.scanned;
      state.searchLoc = data.location;
      state.tip = data.tip;
      state.searched = true;
      state.stale = false;
      state.shown = PAGE_SIZE;
      state.hiddenSources.clear();
      el.searchBtn.querySelector('.btn-label').textContent = 'Find jobs';
    } catch (err) {
      setStatus(el.searchError, networkMessage(err), 'error');
    } finally {
      setLoading(false);
      render();
    }
    if (window.matchMedia('(max-width: 900px)').matches) {
      $('.toolbar').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });

  function networkMessage(err) {
    return err instanceof TypeError ? 'Could not reach the JobScout server. Is it still running?' : err.message;
  }

  function setLoading(on) {
    el.searchBtn.disabled = on;
    el.searchBtn.classList.toggle('loading', on);
    el.searchBtn.querySelector('.btn-label').textContent = on ? 'Searching…' : (state.stale ? 'Update results' : 'Find jobs');
    if (on) {
      el.empty.hidden = true;
      el.showMore.hidden = true;
      el.summary.textContent = 'Searching job sources…';
      el.list.replaceChildren(...Array.from({ length: 4 }, () => make('li', 'skeleton')));
    }
  }

  // ------------------------------------------------------------ filters --

  el.dateFilter.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-days]');
    if (!btn) return;
    state.date = btn.dataset.days;
    if (state.date !== 'custom') prefs.set('date', state.date);
    state.shown = PAGE_SIZE;
    render();
    if (state.date === 'custom' && !state.from) el.dateFrom.focus();
  });
  el.dateFilter.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    const buttons = [...el.dateFilter.querySelectorAll('button')];
    const i = buttons.findIndex((b) => b.dataset.days === state.date);
    const next = buttons[(i + (e.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length];
    next.click();
    next.focus();
  });
  for (const input of [el.dateFrom, el.dateTo]) {
    input.addEventListener('change', () => {
      state.from = el.dateFrom.value;
      state.to = el.dateTo.value;
      state.shown = PAGE_SIZE;
      render();
    });
  }
  el.sort.addEventListener('change', () => {
    state.sort = el.sort.value;
    prefs.set('sort', state.sort);
    render();
  });
  el.workType.addEventListener('change', () => {
    state.workType = el.workType.value;
    prefs.set('workType', state.workType);
    state.shown = PAGE_SIZE;
    render();
  });
  el.textFilter.addEventListener('input', () => {
    state.text = el.textFilter.value.trim().toLowerCase();
    state.shown = PAGE_SIZE;
    render();
  });
  el.showMore.addEventListener('click', () => {
    state.shown += PAGE_SIZE;
    render();
  });

  function dateRange(key = state.date) {
    if (key === 'all') return null;
    if (key === 'custom') {
      if (!state.from && !state.to) return null;
      return {
        from: state.from ? new Date(state.from + 'T00:00:00').getTime() : -Infinity,
        to: state.to ? new Date(state.to + 'T23:59:59.999').getTime() : Infinity,
      };
    }
    return { from: Date.now() - Number(key) * DAY, to: Infinity };
  }

  function inRange(job, range) {
    if (!range) return true;
    return job.time !== null && job.time >= range.from && job.time <= range.to;
  }

  function passesOtherFilters(job) {
    if (state.workType === 'remote' && !isRemote(job)) return false;
    if (state.workType === 'onsite' && isRemote(job)) return false;
    if (state.hiddenSources.has(job.sourceGroup)) return false;
    if (state.text && !job.haystack.includes(state.text)) return false;
    return true;
  }

  // ------------------------------------------------------------- render --

  function render() {
    renderDateButtons();
    renderBoards();
    if (!state.searched) {
      el.sourceRow.hidden = true;
      el.summary.textContent = '';
      el.list.replaceChildren();
      el.showMore.hidden = true;
      setEmpty('Find jobs that fit you',
        'Upload your resume and/or add keywords, then press Find jobs. Use the date filter above to show only recent listings.');
      return;
    }

    renderSourceChips();
    renderNotices();

    const base = state.jobs.filter(passesOtherFilters);
    const range = dateRange();
    const visible = base.filter((j) => inRange(j, range));
    if (state.sort === 'newest') {
      visible.sort((a, b) => (b.time ?? -Infinity) - (a.time ?? -Infinity) || a.rank - b.rank);
    }

    renderSummary(visible);
    const page = visible.slice(0, state.shown);
    el.list.replaceChildren(...page.map(renderJob));
    el.showMore.hidden = visible.length <= state.shown;
    el.showMore.textContent = `Show more (${visible.length - state.shown} left)`;

    if (!state.jobs.length) {
      setEmpty('No matching jobs found',
        'Try broader or different keywords, or select more skills from your resume.');
    } else if (!visible.length) {
      const anyTime = base.length;
      if (range && anyTime) {
        setEmpty('No jobs in this date range',
          `${anyTime} matching job${anyTime === 1 ? ' is' : 's are'} outside it.`,
          { label: 'Show any time', onClick: () => { state.date = 'all'; prefs.set('date', 'all'); render(); } });
      } else {
        setEmpty('No jobs match these filters', 'Try setting Work type to “Any”, clearing the text filter, or re-enabling sources.');
      }
    } else {
      el.empty.hidden = true;
    }
  }

  function renderDateButtons() {
    const base = state.searched ? state.jobs.filter(passesOtherFilters) : [];
    for (const btn of el.dateFilter.querySelectorAll('button')) {
      const key = btn.dataset.days;
      btn.setAttribute('aria-checked', String(key === state.date));
      btn.tabIndex = key === state.date ? 0 : -1;
      let n = btn.querySelector('.n');
      if (!state.searched || (key === 'custom' && !dateRange('custom'))) {
        if (n) n.remove();
        continue;
      }
      if (!n) { n = make('span', 'n'); btn.append(n); }
      const range = dateRange(key);
      n.textContent = base.filter((j) => inRange(j, range)).length;
    }
    el.customRange.hidden = state.date !== 'custom';
  }

  function renderSourceChips() {
    const counts = new Map();
    for (const job of state.jobs) counts.set(job.sourceGroup, (counts.get(job.sourceGroup) || 0) + 1);
    el.sourceRow.hidden = counts.size < 2;
    el.sourceChips.replaceChildren(...[...counts].sort((a, b) => b[1] - a[1]).map(([name, count]) => {
      const chip = make('button', 'chip', name);
      chip.type = 'button';
      chip.setAttribute('aria-pressed', String(!state.hiddenSources.has(name)));
      chip.append(make('span', 'count', count));
      chip.addEventListener('click', () => {
        if (state.hiddenSources.has(name)) state.hiddenSources.delete(name); else state.hiddenSources.add(name);
        state.shown = PAGE_SIZE;
        render();
      });
      return chip;
    }));
  }

  function renderNotices() {
    const failed = state.sources.filter((s) => s.error);
    el.notices.replaceChildren(...failed.map((s) =>
      make('p', 'notice', `Couldn't load ${s.name} (${s.error}). Showing results from the other sources.`)));
    if (state.tip) el.notices.append(make('p', 'notice info', state.tip));
  }

  function renderSummary(visible) {
    const count = visible.length;
    const when = state.date === 'custom'
      ? (dateRange() ? 'in your date range' : '')
      : DATE_PHRASE[state.date] || '';
    const okSources = state.sources.filter((s) => !s.error && s.count).length;
    const parts = [];
    const loc = state.searchLoc;
    if (loc && ['city', 'country', 'unknown'].includes(loc.kind)) {
      const local = visible.filter((j) => j.locationMatch === 'local').length;
      const openTo = loc.country_name ? `open to ${loc.country_name}` : 'open worldwide';
      parts.push(`${local} in ${loc.label}`, `${count - local} remote ${openTo}`);
    }
    parts.push(`${state.jobs.length} relevant out of ${state.scanned.toLocaleString()} listings from ${okSources} source${okSources === 1 ? '' : 's'}`);
    el.summary.replaceChildren(
      make('strong', '', `${count} job${count === 1 ? '' : 's'}`),
      document.createTextNode(`${when ? ' posted ' + when : ''} · ${parts.join(' · ')}`),
    );
  }

  function renderJob(job) {
    const node = el.template.content.firstElementChild.cloneNode(true);
    const title = node.querySelector('.job-title');
    title.textContent = job.title;
    title.href = job.url;
    node.querySelector('.view-btn').href = job.url;

    const match = node.querySelector('.match');
    match.textContent = MATCH_LABEL[job.match];
    match.classList.add(job.match);
    match.title = `Relevance score ${Math.round(job.score * 100)}/100`;

    node.querySelector('.company').textContent = job.company;
    node.querySelector('.location').textContent = job.location;
    const localBadge = node.querySelector('.local-badge');
    localBadge.hidden = job.locationMatch !== 'local' || !state.searchLoc;
    if (!localBadge.hidden) localBadge.textContent = `In ${state.searchLoc.label}`;
    node.querySelector('.remote-badge').hidden = !isRemote(job) || /\bremote\b/i.test(job.location);
    node.querySelector('.salary').textContent = job.salary || '';
    node.querySelector('.job-type').textContent = job.jobType || '';
    node.querySelector('.snippet').textContent = job.snippet;

    const posted = node.querySelector('.posted');
    if (job.time) {
      posted.textContent = relativeTime(job.time);
      posted.dateTime = job.postedAt;
      posted.title = new Date(job.time).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
      posted.classList.toggle('fresh', Date.now() - job.time < 3 * DAY);
    } else {
      posted.textContent = 'Date unknown';
    }
    node.querySelector('.source').textContent = `via ${job.source}`;

    const matched = node.querySelector('.matched');
    for (const k of job.matched.keywords) matched.append(make('span', 'tag kw', k));
    if (job.matched.title) matched.append(make('span', 'tag role', 'Role match'));
    for (const s of job.matched.skills.slice(0, 6)) matched.append(make('span', 'tag', s));
    return node;
  }

  function setEmpty(heading, text, action) {
    el.empty.hidden = false;
    el.empty.querySelector('h3').textContent = heading;
    const p = el.empty.querySelector('p');
    p.textContent = text;
    el.empty.querySelector('.secondary-btn')?.remove();
    if (action) {
      const btn = make('button', 'secondary-btn', action.label);
      btn.type = 'button';
      btn.addEventListener('click', action.onClick);
      el.empty.append(btn);
    }
  }

  // --------------------------------------------------------- job boards --
  // Deep links that open each board's own search with the same query and
  // date window. Boards only accept certain windows, so we round up to the
  // nearest one they support (never narrower than what was asked).

  function roundUp(options, days) {
    return options.find((o) => o >= days);
  }

  function withParams(base, params) {
    const url = new URL(base);
    for (const [k, v] of Object.entries(params)) {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
    }
    return url.toString();
  }

  // Country sites for boards that have them; anything else uses the .com site.
  const INDEED_HOST = {
    IN: 'in.indeed.com', GB: 'uk.indeed.com', CA: 'ca.indeed.com', AU: 'au.indeed.com', NZ: 'nz.indeed.com',
    DE: 'de.indeed.com', FR: 'fr.indeed.com', NL: 'nl.indeed.com', ES: 'es.indeed.com', IT: 'it.indeed.com',
    IE: 'ie.indeed.com', SG: 'sg.indeed.com', AE: 'ae.indeed.com', MY: 'malaysia.indeed.com', PH: 'ph.indeed.com',
    ZA: 'za.indeed.com',
  };
  const GLASSDOOR_HOST = {
    IN: 'www.glassdoor.co.in', GB: 'www.glassdoor.co.uk', CA: 'www.glassdoor.ca', AU: 'www.glassdoor.com.au',
    DE: 'www.glassdoor.de', FR: 'www.glassdoor.fr', NL: 'www.glassdoor.nl', IE: 'www.glassdoor.ie', SG: 'www.glassdoor.sg',
  };
  const isUS = (country) => !country || country === 'US';
  const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  // Each builder returns a URL, or null when the board doesn't serve that country.
  const BOARDS = [
    ['LinkedIn', ({ q, loc, days, remote }) => withParams('https://www.linkedin.com/jobs/search/', {
      keywords: q, location: loc, f_TPR: days ? `r${days * 86400}` : null, f_WT: remote ? '2' : null })],
    ['Naukri', ({ q, loc, days, country }) => country !== 'IN' ? null
      : withParams(`https://www.naukri.com/${slug(q)}-jobs${loc && loc.toLowerCase() !== 'india' ? '-in-' + slug(loc) : ''}`, {
        k: q, l: loc, jobAge: days ? roundUp([1, 3, 7, 15, 30], days) : null })],
    ['Indeed', ({ q, loc, days, remote, country }) => withParams(`https://${INDEED_HOST[country] || 'www.indeed.com'}/jobs`, {
      q, l: loc || (remote ? 'Remote' : ''), fromage: days ? roundUp([1, 3, 7, 14], days) : null })],
    ['Glassdoor', ({ q, loc, days, remote, country }) => withParams(`https://${GLASSDOOR_HOST[country] || 'www.glassdoor.com'}/Job/jobs.htm`, {
      'sc.keyword': q, locKeyword: loc, fromAge: days ? roundUp([1, 3, 7, 14, 30], days) : null, remoteWorkType: remote ? '1' : null })],
    ['ZipRecruiter', ({ q, loc, days, remote, country }) => !isUS(country) ? null
      : withParams('https://www.ziprecruiter.com/jobs-search', {
        search: q, location: loc || (remote ? 'Remote' : ''), days: days ? roundUp([1, 5, 10, 30], days) : null })],
    ['Google Jobs', ({ q, loc, days, remote }) => {
      const chip = days ? { 1: 'today', 3: '3days', 7: 'week', 30: 'month' }[roundUp([1, 3, 7, 30], days)] : null;
      return withParams('https://www.google.com/search', {
        q: `${q} jobs${remote ? ' remote' : ''}${loc ? ' in ' + loc : ''}`, ibp: 'htl;jobs', htichips: chip ? `date_posted:${chip}` : null });
    }],
    ['Dice', ({ q, loc, days, remote, country }) => !isUS(country) ? null
      : withParams('https://www.dice.com/jobs', {
        q, location: loc, 'filters.postedDate': days ? { 1: 'ONE', 3: 'THREE', 7: 'SEVEN' }[roundUp([1, 3, 7], days)] : null,
        'filters.workplaceTypes': remote ? 'Remote' : null })],
  ];

  function boardQuery() {
    if (state.keywords.length) return state.keywords.slice(0, 3).join(' ');
    const titles = selected(state.titleOn);
    if (titles.length) return titles[0];
    return selected(state.skillOn).slice(0, 2).join(' ');
  }

  function boardDays() {
    if (state.date === 'all') return null;
    if (state.date === 'custom') {
      return state.from ? Math.max(1, Math.ceil((Date.now() - new Date(state.from + 'T00:00:00')) / DAY)) : null;
    }
    return Number(state.date);
  }

  function renderBoards() {
    const q = boardQuery();
    el.boards.classList.toggle('disabled', !q);
    const days = boardDays();
    const when = days ? (DATE_PHRASE[String(days)] || `in the past ${days} days`) : 'any time';
    el.boardsQuery.textContent = q ? `for “${q}”, posted ${when}` : 'Add keywords or upload a resume to enable these links.';
    const typedRemote = state.loc?.kind === 'remote';
    const params = {
      q,
      loc: typedRemote ? '' : el.location.value.trim(),
      days,
      remote: typedRemote || state.workType === 'remote',
      country: state.loc?.country || null,
    };
    const links = [];
    for (const [name, build] of BOARDS) {
      const href = q ? build(params) : '#';
      if (href === null) continue;
      const a = make('a', '', name);
      a.target = '_blank';
      a.rel = 'noopener';
      a.href = href;
      links.push(a);
    }
    el.boardLinks.replaceChildren(...links);
  }

  // --------------------------------------------------------------- init --

  async function loadSources() {
    try {
      const res = await fetch('/api/sources');
      const list = await res.json();
      const on = list.filter((s) => s.enabled);
      const off = list.filter((s) => !s.enabled);
      const line = make('p');
      line.append(document.createTextNode('Listings from '));
      on.forEach((s, i) => {
        const a = make('a', '', s.name);
        a.href = s.homepage;
        a.target = '_blank';
        a.rel = 'noopener';
        line.append(a, document.createTextNode(i < on.length - 2 ? ', ' : i === on.length - 2 ? ' and ' : '.'));
      });
      el.sourcesNote.replaceChildren(line);
      if (off.length) {
        el.sourcesNote.append(make('p', '',
          `Add ${off.map((s) => s.name).join(' or ')} API keys to .env to also include LinkedIn, Indeed and Glassdoor listings (see README).`));
      }
    } catch { /* note is optional */ }
  }

  el.location.value = prefs.get('location', '');
  el.sort.value = state.sort;
  el.workType.value = state.workType;
  renderKeywords();
  render();
  loadSources();
  if (el.location.value.trim()) lookupLocation();
})();
