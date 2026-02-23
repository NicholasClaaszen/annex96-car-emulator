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
  wdt_status: document.getElementById('wdt_status'),
  last_ts: document.getElementById('last_ts'),
  log: document.getElementById('log'),
};

let ws;
let reconnectTimer;
const chartPwm = document.getElementById('chart_pwm');
const chartAmps = document.getElementById('chart_amps');
const chartKw = document.getElementById('chart_kw');
let pwmChart;
let ampsChart;
let kwChart;
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
  fields.wdt_status.textContent = data.watchdog_status ?? '—';
  fields.last_ts.textContent = fmtTs(data.last_message_ts);
  if (Array.isArray(data.raw_log_tail)) {
    fields.log.textContent = data.raw_log_tail.join('\n');
  }
  if (Array.isArray(data.pwm_history)) {
    renderCharts(data.pwm_history);
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

function ensureCharts() {
  if (pwmChart && ampsChart && kwChart) return;
  const gridColor = getComputedStyle(document.body).getPropertyValue('--border').trim();
  const textColor = getComputedStyle(document.body).getPropertyValue('--muted').trim();

  const commonOptions = (yTitle, yMax) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: {
        type: 'time',
        time: { unit: 'minute' },
        grid: { color: gridColor },
        ticks: { color: textColor },
        title: { display: true, text: 'Time', color: textColor },
      },
      y: {
        min: 0,
        max: yMax,
        grid: { color: gridColor },
        ticks: { color: textColor },
        title: { display: true, text: yTitle, color: textColor },
      },
    },
  });

  pwmChart = new Chart(chartPwm, {
    type: 'line',
    data: { datasets: [{ label: 'PWM Duty %', data: [], borderColor: '#4aa3a2', tension: 0.25 }] },
    options: commonOptions('PWM Duty (%)', 100),
  });

  ampsChart = new Chart(chartAmps, {
    type: 'line',
    data: { datasets: [{ label: 'Current (A)', data: [], borderColor: '#e2c044', tension: 0.25 }] },
    options: commonOptions('Current (A)', 35),
  });

  kwChart = new Chart(chartKw, {
    type: 'line',
    data: { datasets: [{ label: 'Power (kW)', data: [], borderColor: '#7c8cff', tension: 0.25 }] },
    options: commonOptions('Power (kW)', 10),
  });
}

function renderCharts(series) {
  ensureCharts();
  const maxPoints = 600;
  const data = series.slice(-maxPoints);
  const pwm = data.map(p => ({ x: p.ts * 1000, y: p.duty }));
  const amps = data.map(p => ({ x: p.ts * 1000, y: p.amps }));
  const kw = data.map(p => ({ x: p.ts * 1000, y: p.kw }));

  pwmChart.data.datasets[0].data = pwm;
  ampsChart.data.datasets[0].data = amps;
  kwChart.data.datasets[0].data = kw;
  pwmChart.update('none');
  ampsChart.update('none');
  kwChart.update('none');
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  if (pwmChart && ampsChart && kwChart) {
    pwmChart.destroy();
    ampsChart.destroy();
    kwChart.destroy();
    pwmChart = null;
    ampsChart = null;
    kwChart = null;
    ensureCharts();
  }
}

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  setTheme(current === 'dark' ? 'light' : 'dark');
});

setTheme(localStorage.getItem('theme') || 'dark');

const collapseState = JSON.parse(localStorage.getItem('collapseState') || '{}');
for (const card of document.querySelectorAll('.collapsible')) {
  const key = card.dataset.section;
  const isOpen = collapseState[key] !== false;
  card.classList.toggle('collapsed', !isOpen);
}

for (const toggle of document.querySelectorAll('.card-toggle')) {
  toggle.addEventListener('click', () => {
    const card = toggle.closest('.collapsible');
    const key = card.dataset.section;
    const nowCollapsed = !card.classList.contains('collapsed');
    card.classList.toggle('collapsed', nowCollapsed);
    collapseState[key] = !nowCollapsed;
    localStorage.setItem('collapseState', JSON.stringify(collapseState));
  });
}

connect();
