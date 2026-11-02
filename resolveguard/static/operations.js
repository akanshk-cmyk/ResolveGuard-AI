'use strict';
let runs = [], accessToken = '';
const el = id => document.getElementById(id);
async function get(path) {
  const response = await fetch(path, {headers: {Authorization: `Bearer ${accessToken}`}, cache: 'no-store'});
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}
function compare() {
  const base = runs.find(r => r.id === el('baseline').value);
  const current = runs.find(r => r.id === el('comparison').value);
  if (!base || !current) return;
  const compatible = base.dataset_sha256 === current.dataset_sha256 && base.fixture_sha256 === current.fixture_sha256;
  const delta = {};
  for (const key of ['intent_accuracy','deterministic_journey_pass_rate','fraud_recall']) {
    delta[key] = typeof current.metrics[key] === 'number' && typeof base.metrics[key] === 'number' ? current.metrics[key] - base.metrics[key] : null;
  }
  el('difference').textContent = JSON.stringify({comparable_dataset_and_fixtures: compatible, warning: compatible ? null : 'Different datasets or fixtures: score differences cannot establish improvement.', delta}, null, 2);
  el('details').textContent = JSON.stringify(current, null, 2);
}
async function refresh() {
  try {
    const data = await get('/api/operations'); runs = data.runs;
    const generation = data.generation;
    el('generation').textContent = generation?.sample_count
      ? `${generation.sample_count} generation attempts. p95 provider step: ${generation.p95_ms === null ? 'Unavailable' : generation.p95_ms.toFixed(1) + ' ms'}. Fallbacks: ${generation.fallback_count}. Over budget: ${generation.over_budget_count}. End-to-end chat latency is shown separately.`
      : 'No generation measurements recorded. Live replies are opt-in; unknown measurements are not reported as zero.';
    el('status').textContent = `${runs.length} evaluation batches. Refreshed ${new Date().toLocaleTimeString()}.`;
    el('runtime').textContent = data.runtime.sample_count ? `${data.runtime.sample_count} recent executions. Error rate: ${(data.runtime.error_rate * 100).toFixed(1)}%. p95: ${data.runtime.p95_ms.toFixed(1)} ms.` : 'No runtime observations collected. Historical evaluation results are available below.';
    el('alerts').replaceChildren();
    const emptyMessage = data.runtime.sample_count ? 'No active threshold alerts in the available observations.' : 'Alert status is unavailable until runtime observations are collected.';
    for (const alert of data.alerts.length ? data.alerts : [{message:emptyMessage}]) {const li = document.createElement('li'); li.textContent = alert.message; el('alerts').append(li);}
    el('trends').replaceChildren();
    for (const run of runs.slice(-50)) {
      const row = document.createElement('tr'), label = document.createElement('td'); label.textContent = run.label; row.append(label);
      for (const key of ['deterministic_journey_pass_rate','intent_accuracy','fraud_recall','p95_local_mock_latency_ms']) {
        const cell = document.createElement('td'), value = run.metrics[key]; cell.textContent = typeof value !== 'number' ? 'Unavailable' : key.includes('latency') ? value.toFixed(1) : `${(value * 100).toFixed(1)}%`;
        if (typeof value === 'number' && !key.includes('latency')) {const bar = document.createElement('progress'); bar.max = 1; bar.value = value; cell.append(bar);} row.append(cell);
      }
      el('trends').append(row);
    }
    for (const name of ['baseline','comparison']) {
      const selected = el(name).value; el(name).replaceChildren();
      for (const run of runs) {const option = document.createElement('option'); option.value = run.id; option.textContent = run.label; el(name).append(option);}
      if (runs.some(r => r.id === selected)) el(name).value = selected; else if (name === 'comparison' && runs.length) el(name).value = runs.at(-1).id;
    }
    compare();
  } catch (error) {el('status').textContent = error.message;}
}
el('access').addEventListener('submit', event => {event.preventDefault(); accessToken = el('token').value; el('token').value = ''; refresh();});
for (const id of ['baseline','comparison']) el(id).addEventListener('change', compare);
el('trace').addEventListener('click', async () => {try {el('traces').textContent = JSON.stringify(await get(`/api/traces/${el('comparison').value}`), null, 2);} catch (error) {el('status').textContent = error.message;}});
setInterval(() => {if (accessToken) refresh();}, 15000);
