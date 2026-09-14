import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../observability/grafana/plugins/bankpulse-business-panel/module.js', import.meta.url), 'utf8');
function harness() {
  let component, now = Date.now(), cursor = 0;
  const refs = [];
  class Clock extends Date { static now() { return now; } }
  const React = {
    useState: () => [now, () => {}],
    useRef: initial => refs[cursor++] ||= { current: initial },
    useEffect: () => {},
    createElement: (type, props, ...children) => ({ type, props, children })
  };
  class PanelPlugin { constructor(value) { component = value; } setPanelOptions() { return this; } }
  vm.runInNewContext(source, { Date: Clock, Number, String, setInterval: () => 0, clearInterval: () => {}, System: {
    register(_, declare) { const mod = declare(() => {}); mod.setters[0]({ default: React }); mod.setters[1]({ PanelPlugin }); mod.execute(); }
  } });
  const frame = (overrides = {}, currency = 'USD') => ({ fields: Object.entries({ revision: 7, computed_at: new Date(now).toISOString(), complete: 1, fresh: 1, source_event_id: 'expected', event_count: 42, integrity_percent: 100, has_sample: 1, ...overrides }).map(([name, value]) => ({ name, values: [value], labels: { currency } })) });
  return { frame, advance: ms => now += ms, render(frames, field = 'event_count') { cursor = 0; return component({ data: { series: frames }, options: { field, currency: 'USD' } }); } };
}
let count = 0;
const test = (name, fn) => { fn(); count++; console.log('PASS', name); };
const value = tree => tree.children[0].children[0];
const quality = tree => tree.props['data-quality'];
test('value, event and revision render together', () => { const h = harness(), t = h.render([h.frame()]); assert.equal(value(t), '42'); assert.equal(t.props['data-event-id'], 'expected'); assert.equal(t.props['data-revision'], '7'); });
test('malformed timestamp cannot look fresh', () => { const h = harness(); assert.equal(quality(h.render([h.frame({ computed_at: 'NOT_A_DATE' })])), 'DESACTUALIZADO'); });
test('USD panel excludes same-revision EUR frame', () => { const h = harness(); assert.equal(value(h.render([h.frame({ event_count: 999 }, 'EUR'), h.frame()])), '42'); });
test('old revisions cannot replace a newer value', () => { const h = harness(); h.render([h.frame()]); assert.equal(value(h.render([h.frame({ revision: 6, event_count: 999 })])), '42'); });
test('clock skew cannot defeat local freeze watchdog', () => { const h = harness(), f = h.frame({ computed_at: new Date(Date.now() + 60000).toISOString() }); h.render([f]); h.advance(2600); assert.equal(quality(h.render([f])), 'DESACTUALIZADO'); });
test('expired cohort clears previous 100 and uses neutral color', () => { const h = harness(); h.render([h.frame()], 'integrity_percent'); const t = h.render([h.frame({ revision: 8, has_sample: 0, integrity_percent: -1 })], 'integrity_percent'); assert.equal(value(t), 'SIN MUESTRA'); assert.equal(t.children[0].props.style.color, '#bbbbbb'); });
test('incomplete coverage inhibits healthy numeric value', () => { const h = harness(); assert.equal(value(h.render([h.frame({ complete: 0 })])), 'INCOMPLETO'); });
console.log(`${count} panel contract tests passed`);
