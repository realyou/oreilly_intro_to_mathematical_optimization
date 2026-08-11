/* life tracker web app.
   it does exactly two kinds of writes: completing and reopening habits and tasks.
   everything else is a read. that is enforced on the server too, not just here. */

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};

const state = { view: 'today', date: null, metric: null, days: 30, poll: null };

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'life-tracker' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) { showLogin(); throw new Error('unauthenticated'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `http ${res.status}`);
  return data;
}

function status(msg, isError) {
  const s = $('#status');
  s.textContent = msg || '';
  s.className = isError ? 'error' : 'muted';
}

/* ------------------------------------------------------------------ auth */

function showLogin() {
  $('#login').classList.remove('hidden');
  $('#app').classList.add('hidden');
  if (state.poll) { clearInterval(state.poll); state.poll = null; }
}

function showApp() {
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  if (!state.poll) state.poll = setInterval(() => refresh(true), 60000);
}

$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const err = $('#login-error');
  err.classList.add('hidden');
  try {
    await api('/api/session', { method: 'POST', body: { token: $('#token').value } });
    $('#token').value = '';
    showApp();
    await boot();
  } catch (ex) {
    err.textContent = ex.message;
    err.classList.remove('hidden');
  }
});

$('#signout').addEventListener('click', async () => {
  await api('/api/session', { method: 'DELETE' }).catch(() => {});
  showLogin();
});

/* ------------------------------------------------------------------ views */

document.querySelectorAll('.tab').forEach((t) => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
    t.classList.add('active');
    state.view = t.dataset.view;
    document.querySelectorAll('.view').forEach((v) => v.classList.add('hidden'));
    $('#view-' + state.view).classList.remove('hidden');
    refresh();
  });
});

$('#prev-day').addEventListener('click', () => { state.date = shift(state.date, -1); renderToday(); });
$('#next-day').addEventListener('click', () => { state.date = shift(state.date, 1); renderToday(); });

function shift(iso, n) {
  const d = new Date(iso + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/* -------------------------------------------------------------- today view */

async function renderToday() {
  const q = state.date ? `?date=${state.date}` : '';
  let data;
  try {
    data = await api('/api/today' + q);
  } catch (ex) {
    // the server refuses to guess a date before the timezone is known. say so plainly.
    $('#today-date').textContent = 'not configured';
    $('#today-count').textContent = '';
    $('#today-list').replaceChildren();
    status(ex.message, true);
    return;
  }
  state.date = data.date;
  status('');

  $('#today-date').textContent = data.date;
  $('#today-count').textContent =
    `${data.counts.completed} of ${data.counts.total} done`;

  const open = $('#today-list');
  const done = $('#today-done');
  open.replaceChildren();
  done.replaceChildren();

  data.items.forEach((it) => (it.complete ? done : open).appendChild(itemNode(it, data.date)));

  $('#done-count').textContent = data.counts.completed;
  $('#done-wrap').classList.toggle('hidden', data.counts.completed === 0);
  $('#today-empty').classList.toggle('hidden', data.counts.total !== 0);
}

function itemNode(it, date) {
  const li = el('li', 'item' + (it.complete ? ' done' : ''));

  const box = el('button', 'check' + (it.complete ? ' on' : ''), it.complete ? '✓' : '');
  box.title = it.complete ? 'reopen' : 'complete';
  box.addEventListener('click', () => toggle(it, null, !it.complete, date));
  li.appendChild(box);

  const body = el('div', 'body');
  body.appendChild(el('div', 'title', it.title));

  const tags = el('div', 'tagrow');
  if (it.supports) tags.appendChild(el('span', 'tag', `supports: ${it.supports}`));
  if (it.kind === 'habit' && it.flexible && it.frequency) {
    tags.appendChild(el('span', 'tag flex',
      `${it.frequency.done}/${it.frequency.target} this ${it.frequency.period}`));
  }
  if (it.kind === 'habit' && !it.scheduled && !it.flexible) {
    tags.appendChild(el('span', 'tag', 'not scheduled today'));
  }
  if (it.skipped) tags.appendChild(el('span', 'tag', 'skipped — not a miss'));
  if (it.due_date) tags.appendChild(el('span', 'tag', `due ${it.due_date}`));
  if (it.blocked_reason) tags.appendChild(el('span', 'tag safety', `blocked: ${it.blocked_reason}`));
  if (it.safety_note) tags.appendChild(el('span', 'tag safety', it.safety_note));
  if (it.subtasks_total) {
    tags.appendChild(el('span', 'tag', `${it.subtasks_done}/${it.subtasks_total} steps`));
  }
  if (tags.childNodes.length) body.appendChild(tags);

  if (it.subtasks && it.subtasks.length) {
    const ul = el('ul', 'sub');
    it.subtasks.forEach((s) => {
      const sli = el('li', 'item' + (s.complete ? ' done' : ''));
      const sbox = el('button', 'check' + (s.complete ? ' on' : ''), s.complete ? '✓' : '');
      sbox.addEventListener('click', () => toggle(it, s.id, !s.complete, date));
      sli.appendChild(sbox);
      sli.appendChild(el('div', 'body', s.title));
      ul.appendChild(sli);
    });
    body.appendChild(ul);
  }

  li.appendChild(body);
  return li;
}

async function toggle(item, subtaskId, complete, date) {
  const base = item.kind === 'habit' ? '/api/habits/' : '/api/tasks/';
  const path = base + item.id + (complete ? '/complete' : '/reopen');
  const body = { date };
  if (item.kind === 'habit' && subtaskId) body.subtask_id = subtaskId;
  try {
    await api(path, { method: 'POST', body });
    await renderToday();
  } catch (ex) {
    status(ex.message, true);
  }
}

/* -------------------------------------------------------------- goals view */

async function renderGoals() {
  const { goals } = await api('/api/goals');
  const wrap = $('#goals-list');
  wrap.replaceChildren();
  if (!goals.length) {
    wrap.appendChild(el('p', 'muted', 'no goals yet. ask the agent to break an ambition down.'));
    return;
  }
  const areas = {};
  goals.forEach((g) => (areas[g.area || 'unassigned'] ||= []).push(g));

  Object.keys(areas).sort().forEach((area) => {
    wrap.appendChild(el('h3', 'area-title', area));
    areas[area].forEach((g) => wrap.appendChild(goalCard(g)));
  });
}

function goalCard(g) {
  const c = el('div', 'card');
  const head = el('div', 'row');
  head.appendChild(el('strong', null, g.title));
  head.appendChild(el('span', 'pill ' + g.status, g.status));
  c.appendChild(head);

  const dl = el('dl', 'kv');
  const add = (k, v) => { if (v) { dl.appendChild(el('dt', null, k)); dl.appendChild(el('dd', null, v)); } };
  add('outcome', g.outcome);
  add('done when', g.definition_of_done);
  add('target date', g.target_date);
  add('next review', g.next_review);
  add('next milestone', g.next_milestone ? g.next_milestone.title : null);
  if (g.status_reason) add('reason', g.status_reason);
  c.appendChild(dl);

  const p = g.progress;
  if (p.fraction !== null) {
    const bar = el('div', 'bar');
    const fill = el('span');
    fill.style.width = Math.round(p.fraction * 100) + '%';
    bar.appendChild(fill);
    c.appendChild(bar);
    c.appendChild(el('p', 'muted', `${p.met} of ${p.total} ${p.basis.replace('_', ' ')} met`));
  } else {
    c.appendChild(el('p', 'muted',
      'no success criteria or milestones defined — progress is qualitative, not a number'));
  }

  if (g.criteria.length) {
    c.appendChild(el('p', 'muted', 'success criteria'));
    const ul = el('ul', 'checklist');
    g.criteria.forEach((cr) => ul.appendChild(
      el('li', cr.met ? 'met' : '', (cr.met ? '✓ ' : '· ') + cr.description)));
    c.appendChild(ul);
  }
  if (g.habits.length) {
    c.appendChild(el('p', 'muted', 'supporting habits'));
    const ul = el('ul', 'checklist');
    g.habits.forEach((h) => ul.appendChild(el('li', '', `· ${h.title} (${h.schedule_type})`)));
    c.appendChild(ul);
  }
  if (g.next_actions.length) {
    c.appendChild(el('p', 'muted', 'next actions'));
    const ul = el('ul', 'checklist');
    g.next_actions.forEach((t) => ul.appendChild(
      el('li', '', `· ${t.title}${t.due_date ? ' — due ' + t.due_date : ''}`)));
    c.appendChild(ul);
  }
  return c;
}

/* ----------------------------------------------------------- projects view */

async function renderProjects() {
  const { projects } = await api('/api/projects');
  const wrap = $('#projects-list');
  wrap.replaceChildren();
  if (!projects.length) {
    wrap.appendChild(el('p', 'muted', 'no projects yet.'));
    return;
  }
  projects.forEach((p) => {
    const c = el('div', 'card');
    const head = el('div', 'row');
    head.appendChild(el('strong', null, p.title));
    head.appendChild(el('span', 'pill ' + p.health.health, p.health.health.replace('_', ' ')));
    c.appendChild(head);

    const dl = el('dl', 'kv');
    const add = (k, v) => { if (v) { dl.appendChild(el('dt', null, k)); dl.appendChild(el('dd', null, v)); } };
    add('status', p.status);
    add('phase', p.phase);
    add('owner', p.owner);
    add('deadline', p.deadline);
    add('blocker', p.blocker);
    add('next action', p.next_action ? p.next_action.title : '— none open —');
    if (p.kb_path) add('notes', p.kb_path);
    c.appendChild(dl);

    if (p.health.reasons.length) {
      c.appendChild(el('p', 'muted', 'why: ' + p.health.reasons.join('; ')));
    }
    const pr = p.progress;
    if (pr.fraction !== null) {
      const bar = el('div', 'bar');
      const fill = el('span');
      fill.style.width = Math.round(pr.fraction * 100) + '%';
      bar.appendChild(fill);
      c.appendChild(bar);
      c.appendChild(el('p', 'muted',
        `${pr.met} of ${pr.total} ${pr.basis.replace('_', ' ')} complete`));
    } else {
      c.appendChild(el('p', 'muted', 'no milestones or tasks defined — no progress to report'));
    }

    if (p.milestones.length) {
      const d = el('details');
      d.appendChild(el('summary', null, `milestones (${p.milestones.length})`));
      const ul = el('ul', 'checklist');
      p.milestones.forEach((m) => ul.appendChild(
        el('li', m.status === 'done' ? 'met' : '',
          `${m.status === 'done' ? '✓' : '·'} ${m.title}${m.target_date ? ' — ' + m.target_date : ''}`)));
      d.appendChild(ul);
      c.appendChild(d);
    }
    if (p.tasks.length) {
      const d = el('details');
      d.appendChild(el('summary', null, `tasks (${p.tasks.filter((t) => t.status !== 'done').length} open)`));
      const ul = el('ul', 'checklist');
      p.tasks.forEach((t) => ul.appendChild(
        el('li', t.status === 'done' ? 'met' : '', `${t.status === 'done' ? '✓' : '·'} ${t.title}`)));
      d.appendChild(ul);
      c.appendChild(d);
    }
    wrap.appendChild(c);
  });
}

/* --------------------------------------------------------------- data view */

document.querySelectorAll('#ranges button').forEach((b) => {
  b.addEventListener('click', () => {
    document.querySelectorAll('#ranges button').forEach((x) => x.classList.remove('active'));
    b.classList.add('active');
    state.days = Number(b.dataset.days);
    renderData();
  });
});

$('#metric-pick').addEventListener('change', (e) => {
  state.metric = e.target.value;
  renderChart();
});

async function renderData() {
  const summary = await api(`/api/data/summary?days=${state.days}`);

  const g = $('#data-goals');
  g.replaceChildren();
  if (!summary.goals.length) g.appendChild(el('p', 'muted', 'no active goals.'));
  summary.goals.forEach((x) => {
    const r = el('div', 'row');
    r.appendChild(el('span', null, x.title));
    r.appendChild(el('span', 'r', x.progress.fraction === null
      ? 'qualitative — no criteria set'
      : `${x.progress.met}/${x.progress.total} ${x.progress.basis.replace('_', ' ')}`));
    g.appendChild(r);
  });

  const p = $('#data-projects');
  p.replaceChildren();
  if (!summary.projects.length) p.appendChild(el('p', 'muted', 'no active projects.'));
  summary.projects.forEach((x) => {
    const r = el('div', 'row');
    r.appendChild(el('span', null, x.title));
    r.appendChild(el('span', 'r', x.progress.fraction === null
      ? 'scope not defined'
      : `${x.progress.met}/${x.progress.total} · ${x.health.health.replace('_', ' ')}`));
    p.appendChild(r);
  });

  const h = $('#data-habits');
  h.replaceChildren();
  if (!summary.habits.length) h.appendChild(el('p', 'muted', 'no active habits.'));
  summary.habits.forEach((x) => {
    const r = el('div', 'row');
    r.appendChild(el('span', null, x.title));
    let right;
    if (x.consistency === null && x.periods) {
      right = `${x.periods_met}/${x.periods_total} periods met`;
    } else if (x.consistency === null) {
      right = 'no scheduled days in range';
    } else {
      right = `${Math.round(x.consistency * 100)}% of ${x.scheduled_days} scheduled days`;
    }
    r.appendChild(el('span', 'r', right));
    h.appendChild(r);
  });

  const pick = $('#metric-pick');
  const current = state.metric;
  pick.replaceChildren();
  if (!summary.metrics.length) {
    pick.appendChild(new Option('no metrics defined', ''));
    $('#chart').replaceChildren();
    $('#chart-title').textContent = 'no metrics defined';
    $('#chart-coverage').textContent =
      'ask the agent to define one. a metric needs a unit, a range and a missing-value meaning.';
    $('#chart-estimated').textContent = '';
    return;
  }
  summary.metrics.forEach((m) => pick.appendChild(new Option(m.label, m.id)));
  state.metric = summary.metrics.some((m) => m.id === current) ? current : summary.metrics[0].id;
  pick.value = state.metric;
  await renderChart();
}

async function renderChart() {
  if (!state.metric) return;
  const s = await api(`/api/metrics/${encodeURIComponent(state.metric)}/series?days=${state.days}`);
  $('#chart-title').textContent = s.metric.label + (s.metric.unit ? ` (${s.metric.unit})` : '');

  const box = $('#chart');
  box.replaceChildren();
  const pts = s.points.filter((p) => p.value !== null && p.value !== undefined);

  if (!pts.length) {
    box.appendChild(el('p', 'muted', 'no observations in this range.'));
  } else if (s.metric.chart === 'calendar' || s.metric.type === 'boolean') {
    box.appendChild(calendar(s));
  } else if (s.metric.chart === 'distribution' || s.metric.type === 'categorical') {
    box.appendChild(distribution(s));
  } else if (s.metric.chart === 'bar') {
    box.appendChild(bars(s));
  } else {
    box.appendChild(line(s));
  }

  const c = s.coverage;
  const agg = s.aggregate;
  const aggText = agg.value === null ? 'no aggregate'
    : `${agg.aggregation}: ${round(agg.value)}${s.metric.unit ? ' ' + s.metric.unit : ''} over ${agg.n} values`;
  $('#chart-coverage').textContent =
    `${aggText} · ${c.observations} observations on ${c.days_with_data} of ${c.days_in_range} days · ${c.note}`;
  $('#chart-estimated').textContent = s.estimated_count
    ? `${s.estimated_count} of these values were estimated by the agent, not measured.`
    : '';
}

const round = (v) => (Math.abs(v) >= 100 ? Math.round(v) : Math.round(v * 100) / 100);
const svgEl = (t, attrs) => {
  const n = document.createElementNS('http://www.w3.org/2000/svg', t);
  Object.entries(attrs || {}).forEach(([k, v]) => n.setAttribute(k, v));
  return n;
};

function frame(w, h) {
  const svg = svgEl('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img' });
  return svg;
}

function line(s) {
  const W = 640, H = 220, P = 34;
  const svg = frame(W, H);
  const vals = s.points.map((p) => Number(p.value));
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = (max - min) || 1;
  const t0 = new Date(s.range.start).getTime();
  const t1 = new Date(s.range.end).getTime();
  const tspan = (t1 - t0) || 1;
  const x = (d) => P + ((new Date(d).getTime() - t0) / tspan) * (W - P * 2);
  const y = (v) => H - P - ((v - min) / span) * (H - P * 2);

  svg.appendChild(svgEl('line', { x1: P, y1: H - P, x2: W - P, y2: H - P, stroke: '#8b93a7', 'stroke-width': 1 }));
  svg.appendChild(svgEl('line', { x1: P, y1: P, x2: P, y2: H - P, stroke: '#8b93a7', 'stroke-width': 1 }));

  const d = s.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.date).toFixed(1)},${y(Number(p.value)).toFixed(1)}`).join(' ');
  svg.appendChild(svgEl('path', { d, fill: 'none', stroke: '#7aa2f7', 'stroke-width': 2 }));
  s.points.forEach((p) => {
    const c = svgEl('circle', {
      cx: x(p.date), cy: y(Number(p.value)), r: 3,
      fill: p.estimated ? '#e0af68' : '#7aa2f7',
    });
    const title = svgEl('title');
    title.textContent = `${p.date}: ${p.value}${p.estimated ? ' (estimated: ' + (p.assumption || '') + ')' : ''}`;
    c.appendChild(title);
    svg.appendChild(c);
  });

  [[max, P + 4], [min, H - P - 4]].forEach(([v, yy]) => {
    const t = svgEl('text', { x: 4, y: yy, fill: '#8b93a7', 'font-size': 11 });
    t.textContent = round(v);
    svg.appendChild(t);
  });
  const lbl = svgEl('text', { x: P, y: H - 8, fill: '#8b93a7', 'font-size': 11 });
  lbl.textContent = `${s.range.start} → ${s.range.end}`;
  svg.appendChild(lbl);
  return svg;
}

function bars(s) {
  const W = 640, H = 220, P = 34;
  const svg = frame(W, H);
  const vals = s.points.map((p) => Number(p.value));
  const max = Math.max(...vals, 0) || 1;
  const bw = Math.max(2, (W - P * 2) / s.points.length - 2);
  s.points.forEach((p, i) => {
    const h = (Number(p.value) / max) * (H - P * 2);
    const r = svgEl('rect', {
      x: P + i * ((W - P * 2) / s.points.length), y: H - P - h,
      width: bw, height: Math.max(1, h),
      fill: p.estimated ? '#e0af68' : '#7aa2f7', rx: 2,
    });
    const title = svgEl('title');
    title.textContent = `${p.date}: ${p.value}`;
    r.appendChild(title);
    svg.appendChild(r);
  });
  svg.appendChild(svgEl('line', { x1: P, y1: H - P, x2: W - P, y2: H - P, stroke: '#8b93a7' }));
  const t = svgEl('text', { x: 4, y: P + 4, fill: '#8b93a7', 'font-size': 11 });
  t.textContent = round(max);
  svg.appendChild(t);
  return svg;
}

function distribution(s) {
  const wrap = el('div');
  const entries = Object.entries(s.distribution || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map((e) => e[1]), 1);
  entries.forEach(([k, n]) => {
    const r = el('div', 'row');
    r.appendChild(el('span', null, k));
    const right = el('span', 'r', `${n}`);
    r.appendChild(right);
    const bar = el('div', 'bar');
    const fill = el('span');
    fill.style.width = Math.round((n / max) * 100) + '%';
    bar.appendChild(fill);
    wrap.appendChild(r);
    wrap.appendChild(bar);
  });
  return wrap;
}

function calendar(s) {
  const wrap = el('div', 'cal');
  const byDate = {};
  s.points.forEach((p) => { byDate[p.date] = p.value; });
  const start = new Date(s.range.start + 'T12:00:00Z');
  for (let i = 0; i < s.range.days; i++) {
    const d = new Date(start);
    d.setUTCDate(d.getUTCDate() + i);
    const iso = d.toISOString().slice(0, 10);
    const v = byDate[iso];
    const cell = el('i', v === undefined ? '' : (v ? 'on' : 'off'));
    cell.title = `${iso}: ${v === undefined ? 'no observation' : v}`;
    wrap.appendChild(cell);
  }
  return wrap;
}

/* ---------------------------------------------------------------- refresh */

async function refresh(quiet) {
  try {
    if (state.view === 'today') await renderToday();
    else if (state.view === 'goals') await renderGoals();
    else if (state.view === 'projects') await renderProjects();
    else if (state.view === 'data') await renderData();
  } catch (ex) {
    if (!quiet) status(ex.message, true);
  }
}

async function boot() {
  try {
    const settings = await api('/api/settings');
    if (!settings.timezone_configured) {
      status('timezone not configured — ask the agent to set it before logging anything dated', true);
    }
    state.date = settings.today || state.date;
  } catch (ex) { /* handled by api() */ }
  await refresh();
}

window.addEventListener('focus', () => refresh(true));
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(true); });

(async function init() {
  try {
    await api('/api/settings');
    showApp();
    await boot();
  } catch (ex) {
    showLogin();
  }
})();
