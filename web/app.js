const statusEl = document.getElementById('status');
const fields = {
  cp_state: document.getElementById('cp_state'),
  cp_state_label: document.getElementById('cp_state_label'),
  cp_vp: document.getElementById('cp_vp'),
  cp_vn: document.getElementById('cp_vn'),
  cp_pwm: document.getElementById('cp_pwm'),
  cp_amps: document.getElementById('cp_amps'),
  cp_kw: document.getElementById('cp_kw'),
  mains_v: document.getElementById('mains_v'),
  cp_set: document.getElementById('cp_set'),
  pp_state: document.getElementById('pp_state'),
  wdt_status: document.getElementById('wdt_status'),
  last_ts: document.getElementById('last_ts'),
  log: document.getElementById('log'),
};

let ws;
let reconnectTimer;
const chart = document.getElementById('chart');
const ctx = chart.getContext('2d');
const themeToggle = document.getElementById('themeToggle');

const mode3Labels = {
  A1: 'A1: EV not connected (+12V DC)',
  B1: 'B1: EV connected, not ready (+9V DC)',
  C1: 'C1: EV ready/charging (+6V DC)',
  D1: 'D1: EV ready + ventilation (+3V DC)',
  A2: 'A2: State A with PWM detected',
  B2: 'B2: State B with PWM detected',
  C2: 'C2: State C with PWM detected',
  D2: 'D2: State D with PWM detected',
  E: 'E: Error condition (0V)',
  F: 'F: Fault condition (-12V)',
};

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
  fields.cp_state_label.textContent = mode3Labels[data.cp_state_detected] ?? '—';
  fields.cp_vp.textContent = data.cp_voltage_pos ?? '—';
  fields.cp_vn.textContent = data.cp_voltage_neg ?? '—';
  fields.cp_pwm.textContent = data.cp_pwm_duty ?? '—';
  if (Array.isArray(data.pwm_history) && data.pwm_history.length) {
    const last = data.pwm_history[data.pwm_history.length - 1];
    fields.cp_amps.textContent = last.amps.toFixed(2);
    fields.cp_kw.textContent = last.kw.toFixed(2);
  } else {
    fields.cp_amps.textContent = '—';
    fields.cp_kw.textContent = '—';
  }
  if (data.mains_voltage) {
    fields.mains_v.textContent = Number(data.mains_voltage).toFixed(0);
  }
  fields.cp_set.textContent = data.cp_set_state ?? '—';
  fields.pp_state.textContent = data.pp_state ?? '—';
  fields.wdt_status.textContent = data.watchdog_status ?? '—';
  fields.last_ts.textContent = fmtTs(data.last_message_ts);
  if (Array.isArray(data.raw_log_tail)) {
    fields.log.textContent = data.raw_log_tail.join('\n');
  }
  if (Array.isArray(data.pwm_history)) {
    renderChart(data.pwm_history);
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

function renderChart(series) {
  const maxPoints = 600;
  const data = series.slice(-maxPoints);
  ctx.clearRect(0, 0, chart.width, chart.height);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--panel');
  ctx.fillRect(0, 0, chart.width, chart.height);

  const padding = 30;
  const w = chart.width - padding * 2;
  const h = chart.height - padding * 2;

  const ampsMax = Math.max(6, ...data.map(p => p.amps));
  const kwMax = Math.max(1, ...data.map(p => p.kw));

  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--border');
  ctx.lineWidth = 1;
  ctx.strokeRect(padding, padding, w, h);

  const drawLine = (values, color) => {
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = padding + (i / (values.length - 1 || 1)) * w;
      const y = padding + h - (v / (values === amps ? ampsMax : kwMax)) * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
  };

  const amps = data.map(p => p.amps);
  const kws = data.map(p => p.kw);
  drawLine(amps, '#4aa3a2');
  drawLine(kws, '#e2c044');

  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--muted');
  ctx.font = '12px sans-serif';
  ctx.fillText(`Amps (max ${ampsMax.toFixed(1)})`, padding + 6, padding + 14);
  ctx.fillText(`kW (max ${kwMax.toFixed(1)})`, padding + 140, padding + 14);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  setTheme(current === 'dark' ? 'light' : 'dark');
});

setTheme(localStorage.getItem('theme') || 'dark');

connect();
