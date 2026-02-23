const statusEl = document.getElementById('status');
const fields = {
  cp_state: document.getElementById('cp_state'),
  cp_vp: document.getElementById('cp_vp'),
  cp_vn: document.getElementById('cp_vn'),
  cp_pwm: document.getElementById('cp_pwm'),
  cp_set: document.getElementById('cp_set'),
  pp_state: document.getElementById('pp_state'),
  wdt_status: document.getElementById('wdt_status'),
  last_ts: document.getElementById('last_ts'),
  log: document.getElementById('log'),
};

let ws;
let reconnectTimer;

function fmtTs(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString();
}

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok ? 'status ok' : 'status bad';
}

function applyState(data) {
  fields.cp_state.textContent = data.cp_state_detected ?? '—';
  fields.cp_vp.textContent = data.cp_voltage_pos ?? '—';
  fields.cp_vn.textContent = data.cp_voltage_neg ?? '—';
  fields.cp_pwm.textContent = data.cp_pwm_duty ?? '—';
  fields.cp_set.textContent = data.cp_set_state ?? '—';
  fields.pp_state.textContent = data.pp_state ?? '—';
  fields.wdt_status.textContent = data.watchdog_status ?? '—';
  fields.last_ts.textContent = fmtTs(data.last_message_ts);
  if (Array.isArray(data.raw_log_tail)) {
    fields.log.textContent = data.raw_log_tail.join('\n');
  }
}

function connect() {
  ws = new WebSocket(`ws://${window.location.host}/ws`);

  ws.onopen = () => {
    setStatus('Connected', true);
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'snapshot' || msg.type === 'update') {
      applyState(msg.data);
    }
  };

  ws.onclose = () => {
    setStatus('Disconnected - retrying', false);
    reconnectTimer = setTimeout(connect, 1500);
  };
}

function send(action, value) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: action, value }));
}

for (const btn of document.querySelectorAll('button[data-action]')) {
  btn.addEventListener('click', () => {
    send(btn.dataset.action, btn.dataset.value);
  });
}

connect();