System.register(['react', '@grafana/data'], function (exports) {
  let React, PanelPlugin;
  return {
    setters: [function (m) { React = m.default || m; }, function (m) { PanelPlugin = m.PanelPlugin; }],
    execute: function () {
      function BusinessPanel(props) {
        const [now, setNow] = React.useState(Date.now());
        const latest = React.useRef({ revision: -1 });
        const lastArrival = React.useRef(0);
        React.useEffect(() => {
          const timer = setInterval(() => setNow(Date.now()), 100);
          return () => clearInterval(timer);
        }, []);
        for (const frame of props.data.series || []) {
          const currency = frame.fields.find(field => field.labels && field.labels.currency)?.labels.currency || frame.name?.match(/currency[=:]\s*([A-Z]{3})/)?.[1];
          if (currency !== (props.options.currency || "USD")) continue;
          const row = {};
          for (const field of frame.fields) {
            const values = field.values;
            row[field.name] = values.length ? (values.get ? values.get(values.length - 1) : values[values.length - 1]) : null;
          }
          if (Number(row.revision) > latest.current.revision) { latest.current = row; lastArrival.current = Date.now(); }
        }
        const row = latest.current;
        const computedAt = Date.parse(row.computed_at);
        const stale = !Number.isFinite(computedAt) || now - lastArrival.current > 2500 || now - computedAt > 2500;
        const incomplete = Number(row.complete) !== 1;
        const quality = stale ? 'DESACTUALIZADO' : incomplete ? 'INCOMPLETO' : Number(row.fresh) !== 1 ? 'DESACTUALIZADO' : 'VIGENTE';
        const key = props.options.field || 'event_count';
        const noSample = key === 'integrity_percent' && Number(row.has_sample) !== 1;
        const alert = key === 'integrity_percent' ? Number(row[key]) >= 0 && Number(row[key]) < 100 : ['closure_gap', 'unresolved_amount'].includes(key) && Number(row[key]) > 0;
        const value = quality !== 'VIGENTE' ? quality : noSample ? 'SIN MUESTRA' : (row[key] == null ? 'SIN MUESTRA' : Number(row[key]).toLocaleString('es-EC', { maximumFractionDigits: 2 }));
        const color = noSample ? '#bbbbbb' : quality !== 'VIGENTE' ? '#f2c96d' : alert ? '#ff7373' : '#73d9a6';
        return React.createElement('section', {
          style: { padding: '12px', height: '100%', overflow: 'auto' },
          'data-bankpulse-panel': key, 'data-revision': String(row.revision), 'data-event-id': row.source_event_id || '', 'data-quality': quality
        },
          React.createElement('div', { style: { color, fontSize: '28px', fontWeight: 650 } }, value),
          React.createElement('div', { style: { color, fontSize: '12px' } }, quality + (alert ? ' · ALERTA' : '')),
          React.createElement('div', { style: { fontSize: '11px', marginTop: '8px' } }, 'Revisión ' + row.revision + ' · eventos ' + (row.event_count || 0)),
          React.createElement('div', { style: { fontSize: '10px', overflowWrap: 'anywhere' } }, 'Evento ' + (row.source_event_id || 'esperando bootstrap')),
          React.createElement('div', { style: { fontSize: '10px' } }, row.computed_at || '')
        );
      }
      exports('plugin', new PanelPlugin(BusinessPanel).setPanelOptions(builder => builder.addTextInput({ path: 'field', name: 'Campo', defaultValue: 'event_count' }).addTextInput({ path: 'currency', name: 'Moneda', defaultValue: 'USD' })));
    }
  };
});
