let session = null;
let board = [];
let conflictBay = null;

const $ = (id) => document.getElementById(id);
const show = (id, visible) => $(id).classList.toggle('hidden', !visible);

function notice(message, success = false) {
  const box = $('notice');
  box.textContent = message;
  box.classList.toggle('success', success);
  show('notice', true);
  if (success) setTimeout(() => show('notice', false), 5000);
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers['Content-Type'] = 'application/json';
  if (session && options.method && options.method !== 'GET') headers['X-CSRF-Token'] = session.csrf;
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  if (!response.ok) {
    const type = response.headers.get('content-type') || '';
    const detail = type.includes('json') ? (await response.json()).detail : await response.text();
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return response.json();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function actionButton(label, action, danger = false) {
  const button = element('button', danger ? 'danger' : '', label);
  button.type = 'button';
  button.addEventListener('click', action);
  return button;
}

function renderBoard() {
  const grid = $('board');
  grid.replaceChildren();
  if (!board.length) {
    grid.append(element('p', '', 'No bays yet. An admin can create the first bay below.'));
    return;
  }
  for (const bay of board) {
    const state = bay.id === conflictBay ? 'conflict' : bay.state;
    const card = element('article', `bay-card ${state}`);
    card.setAttribute('aria-label', `Bay ${bay.label}, ${state}`);
    const top = element('div', 'bay-top');
    top.append(element('div', 'bay-label', bay.label), element('span', 'state-pill', state.toUpperCase()));
    card.append(top);
    const meta = element('p', 'bay-meta');
    if (!session) meta.textContent = bay.assignment_id ? 'SYNTHETIC STATUS · DETAILS HIDDEN' : 'NO ASSIGNMENT';
    else if (bay.unit) {
      meta.append(element('strong', '', bay.unit), document.createTextNode(` · ${bay.plate}`));
    } else meta.textContent = 'NO ACTIVE ASSIGNMENT';
    card.append(meta);
    if (session) {
      const actions = element('div', 'bay-actions');
      if (bay.assignment_id) {
        actions.append(actionButton('Record IN', () => recordMovement(bay, 'IN')));
        actions.append(actionButton('Record OUT', () => recordMovement(bay, 'OUT')));
        if (session.role === 'admin') actions.append(actionButton('End assignment', () => endAssignment(bay), true));
      }
      card.append(actions);
    }
    grid.append(card);
  }
}

function renderSession() {
  $('session-label').textContent = session ? `${session.role.toUpperCase()} / ${session.username.toUpperCase()}` : 'PUBLIC DEMO';
  show('logout', !!session);
  show('login-panel', !session);
  show('toolbar', !!session);
  show('admin-panel', session?.role === 'admin');
  show('demo-flag', !session);
  $('board-footnote').textContent = session ? 'LIVE SOCIETY BOARD · Times are recorded in UTC.' : 'SYNTHETIC PREVIEW · Sign in for current society occupancy and movements.';
}

async function refresh() {
  try {
    board = await request(session ? '/api/board' : '/api/demo-board');
    renderSession();
    renderBoard();
    const select = $('bay-select');
    select.replaceChildren();
    for (const bay of board.filter((item) => !item.assignment_id)) {
      const option = element('option', '', bay.label);
      option.value = String(bay.id);
      select.append(option);
    }
  } catch (error) { notice(error.message); }
}

async function recordMovement(bay, kind) {
  try {
    await request('/api/movements', { method: 'POST', body: JSON.stringify({ bay_id: bay.id, kind }) });
    conflictBay = null;
    notice(`${bay.label}: ${kind} recorded.`, true);
    await refresh();
  } catch (error) {
    conflictBay = bay.id;
    notice(`${bay.label}: ${error.message}`);
    renderBoard();
  }
}

async function endAssignment(bay) {
  try {
    await request(`/api/assignments/${bay.assignment_id}/end`, { method: 'POST' });
    conflictBay = null;
    notice(`${bay.label}: assignment ended.`, true);
    await refresh();
  } catch (error) {
    conflictBay = bay.id;
    notice(`${bay.label}: ${error.message}`);
    renderBoard();
  }
}

async function submitJson(event, path, payload, success) {
  event.preventDefault();
  try {
    await request(path, { method: 'POST', body: JSON.stringify(payload) });
    event.target.reset();
    notice(success, true);
    await refresh();
  } catch (error) { notice(error.message); }
}

$('login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    session = await request('/api/login', { method: 'POST', body: JSON.stringify({ username: $('username').value, password: $('password').value }) });
    $('password').value = '';
    show('notice', false);
    await refresh();
  } catch (error) { notice(error.message); }
});

$('logout').addEventListener('click', async () => {
  try { await request('/api/logout', { method: 'POST' }); } catch (_) { /* clear local view anyway */ }
  session = null;
  conflictBay = null;
  $('search-result').textContent = '';
  await refresh();
});

$('refresh').addEventListener('click', refresh);
$('search-button').addEventListener('click', async () => {
  const plate = $('plate-search').value.trim();
  if (!plate) { $('search-result').textContent = 'Enter a plate to search.'; return; }
  try {
    const result = await request(`/api/lookup?plate=${encodeURIComponent(plate)}`);
    $('search-result').textContent = `${result.plate} → ${result.label} · ${result.unit} · ${result.state.toUpperCase()}`;
    document.querySelector(`[aria-label^="Bay ${result.label},"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } catch (error) { $('search-result').textContent = error.message; }
});
$('plate-search').addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); $('search-button').click(); } });
$('bay-form').addEventListener('submit', (event) => submitJson(event, '/api/bays', { label: new FormData(event.target).get('label') }, 'Bay created.'));
$('assignment-form').addEventListener('submit', (event) => {
  const data = new FormData(event.target);
  submitJson(event, '/api/assignments', { bay_id: Number(data.get('bay_id')), unit: data.get('unit'), plate: data.get('plate') }, 'Assignment created.');
});

(async () => {
  try { session = await request('/api/me'); } catch (_) { session = null; }
  await refresh();
})();
