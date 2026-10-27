/* Fybroc CPQ demo: state, rendering, actions, PDF export. Requires cpq-logic.js loaded first. */
/* ===================== UI ===================== */
const ACCOUNTS = [
  {id:'KPE', name:'Keystone Process Equipment', type:'Distributor', disc:0.32, contacts:[{name:'Rachel Malone', email:'rmalone@keystoneprocess.example'},{name:'Dev Patel', email:'dpatel@keystoneprocess.example'}]},
  {id:'GCF', name:'Gulf Coast Fluid Systems', type:'Distributor', disc:0.28, contacts:[{name:'Marcus Lee', email:'mlee@gulfcoastfluid.example'}]},
  {id:'CCS', name:'Cascade Chemical Supply', type:'Distributor', disc:0.30, contacts:[{name:'Ana Torres', email:'atorres@cascadechem.example'},{name:'Quotes desk (no portal login)', email:'quotes@cascadechem.example', nologin:true}]},
  {id:'NBW', name:'Northbridge Water Skids', type:'OEM', disc:0.38, netOnly:true, contacts:[{name:'Tom Becker', email:'tbecker@northbridgeskids.example'}]}
];
const ACC = id => ACCOUNTS.find(a => a.id === id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const money = n => (n < 0 ? '\u2212$' : '$') + Math.abs(Math.round(n)).toLocaleString('en-US');
const todayISO = () => new Date().toISOString().slice(0, 10);
const fmtDate = d => new Date(d + 'T12:00:00').toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
const monthsAgo = d => Math.max(0, Math.round((Date.now() - new Date(d + 'T12:00:00')) / (30.44 * 864e5)));
let S, uid = 1;
const entryTitle = e => e.vendor ? `${e.vendor} ${e.series}: ${e.desc}` : e.desc;
const libText = e => [e.code, e.vendor, e.series, e.desc].join(' ').toLowerCase();
const matchSearch = (e, q) => String(q || '').toLowerCase().split(/\s+/).filter(Boolean).every(t => libText(e).includes(t));
const nid = () => 'L' + (uid++);

function mkLine(qty, designation, description, series, over, requests, ae) {
  return {id: nid(), qty, designation, description, cfg: defaultCfg(series, over), requests: requests || {}, ae: Object.assign({cf:{}}, ae || {})};
}
function seed() {
  uid = 1;
  S = {aeSearch:{}, libSearch:'', role:'dist', acct:'KPE', view:{name:'log'}, modal:null, draft:null, aeForm:{}, registry:{bySpec:{}, byItem:{}}, nextQuote:1005, toast:null,
    lib:{
      seal:[
        {code:'X01', vendor:'John Crane', series:'5610', desc:'Double cartridge, tungsten carbide vs silicon carbide faces, FKM', date:'2026-08-11', quote:'Q26-0981',
          fields:{sealOption:'Supplied by Fybroc', sealMfg:'John Crane', sealType:'Custom Seal Type', sealMat:'Silcar vs Silcar', sealElast:'FKM', sealGuard:'Not Supplied by Fybroc'},
          rows:[{d:'John Crane 5610 seal, TC/SiC', cost:1200, margin:40, ref:'JC quote 26-0418'},{d:'Gland modification for 5610', cost:500, margin:55, ref:'Standard 5610 gland mod'}]},
        {code:'X02', vendor:'Flowserve', series:'QBQ', desc:'Double cartridge, SiC vs SiC, PTFE', date:'2024-02-20', quote:'Q24-0212',
          fields:{sealOption:'Supplied by Fybroc', sealMfg:'Flowserve', sealType:'Custom Seal Type', sealMat:'Silcar vs Silcar', sealElast:'PTFE', sealGuard:'Not Supplied by Fybroc'},
          rows:[{d:'Flowserve QBQ cartridge seal', cost:1850, margin:40, ref:'Flowserve quote FS-3391'}]},
        {code:'X03', vendor:'John Crane', series:'5610', desc:'Double cartridge, carbon vs silicon carbide faces, EPR', date:'2025-11-03', quote:'Q25-1406',
          fields:{sealOption:'Supplied by Fybroc', sealMfg:'John Crane', sealType:'Custom Seal Type', sealMat:'Carbon vs Ceramic', sealElast:'EPR', sealGuard:'Not Supplied by Fybroc'},
          rows:[{d:'John Crane 5610 seal, C/SiC', cost:980, margin:40, ref:'JC quote 25-1187'},{d:'Gland modification for 5610', cost:500, margin:55, ref:'Standard 5610 gland mod'}]},
        {code:'X04', vendor:'AESSEAL', series:'CURC', desc:'Single cartridge, SiC vs SiC, FKM', date:'2026-03-14', quote:'Q26-0402',
          fields:{sealOption:'Supplied by Fybroc', sealMfg:'Custom Seal Mfg', sealType:'Custom Seal Type', sealMat:'Silcar vs Silcar', sealElast:'FKM', sealGuard:'Not Supplied by Fybroc'},
          rows:[{d:'AESSEAL CURC cartridge seal', cost:1100, margin:40, ref:'AESSEAL quote A-55821'}]}
      ],
      motor:[
        {code:'X01', desc:'Baldor TEFC, 575 V 3/60, premium efficiency', date:'2026-06-20', quote:'Q26-0877',
          fields:{motorOption:'Supplied by Fybroc', motorControl:'Single Speed', rpm:'1800', hp:'25', voltage:'Custom', hz:'3ph - 60 hz', enclosure:'TEFC', motorMfg:'Baldor'},
          rows:[{d:'575 V winding premium over 230/460', cost:640, margin:35, ref:'Baldor quote BQ-77120'}]}
      ],
      special:[
        {code:'X00001', desc:'Titanium casing hardware', date:'2026-05-02', quote:'Q26-0790', fields:{special:'Titanium casing hardware'},
          rows:[{d:'Titanium studs, nuts and washers', cost:980, margin:50, ref:'Supplier estimate'}]}
      ]
    },
    quotes:[]};
  S.quotes.push({no:'Q26-1001', account:'KPE', contact:0, project:'Riverside WWTP chemical feed', ref:'KPE-24318', status:'Released', created:'2026-09-24', updated:'2026-09-29',
    lines:[mkLine(2,'P-101A/B','Sodium hypochlorite transfer','1500',{size:'2x3x10',material:'VR-1A',trim:'9.250',sealType:'8-1T Double Inside',coupling:'Coupling Included',couplingGuard:'Steel',baseplate:'Baseplate Included',hardware:HW_SEP,bpHw:'316 SS',motorOption:'Supplied by Fybroc',rpm:'3600',hp:'10',enclosure:'TEFC SD'}),
           mkLine(1,'P-140','Ferric chloride unloading','1500',{size:'1x1.5x8',material:'VR-1',trim:'7.250',sealType:'8B2 Single Outside',coupling:'Coupling Included',couplingGuard:'Steel',baseplate:'Baseplate Included',motorOption:'Supplied by Fybroc',rpm:'3600',hp:'5'})],
    history:[{at:'2026-09-24',who:'Rachel Malone',text:'Quote created'},{at:'2026-09-29',who:'Rachel Malone',text:'Quote confirmed'}]});
  S.quotes.push({no:'Q26-1002', account:'GCF', contact:0, project:'Bayport scrubber recirculation', ref:'GC-7781', status:'With applications', created:'2026-10-13', updated:'2026-10-13',
    lines:[mkLine(1,'P-310','Scrubber recirculation, option A','1500',{size:'3x4x13',material:'VR-1A',trim:'12.000',sealMfg:'John Crane',sealType:'Custom Seal Type',sealMat:'Silcar vs Silcar',coupling:'Coupling Included',couplingGuard:'316 SS',baseplate:'Baseplate Included',motorOption:'Supplied by Fybroc',rpm:'1800',hp:'40'},
             {seal:'John Crane 5610 double cartridge, tungsten carbide vs silicon carbide faces, FKM. Plant standard per spec 44-2.'}),
           mkLine(1,'P-311','Sump return, option B','5500',{size:'2x3x10',material:'VR-1A',trim:'9.000',setting:'6',shaft:'Hastelloy C',sleeve:'Hast-C',perf:'Wit Perf Test',motorOption:'Supplied by Fybroc',rpm:'3600',hp:'15'})],
    history:[{at:'2026-10-13',who:'Marcus Lee',text:'Quote created'},{at:'2026-10-13',who:'Marcus Lee',text:'Sent to applications: custom mechanical seal, witnessed performance test'}]});
  S.quotes.push({no:'Q26-1003', account:'NBW', contact:0, project:'Skid package NB-12', ref:'NB12-REV2', status:'Draft', created:'2026-10-14', updated:'2026-10-14',
    lines:[mkLine(3,'Skid pos. 4','Caustic dosing transfer','5500',{size:'1x1.5x8',material:'VR-1',trim:'7.000',setting:'3',motorOption:'Installed by Fybroc',rpm:'3600',hp:'3'})],
    history:[{at:'2026-10-14',who:'Tom Becker',text:'Quote created'}]});
  S.quotes.push({no:'Q26-1004', account:'CCS', contact:0, project:'Mill effluent neutralization', ref:'CCS-0912', status:'Completed by applications', created:'2026-10-08', updated:'2026-10-10',
    lines:[mkLine(1,'P-22','Lime slurry recirculation','1500',{size:'4x6x13',material:'EY-2',trim:'11.500',sealType:'RAC Single Outside',special:'Titanium casing hardware'},{special:'Customer spec calls for titanium on all wetted fasteners.'},{special:'X00001'})],
    history:[{at:'2026-10-08',who:'Ana Torres',text:'Quote created'},{at:'2026-10-08',who:'Ana Torres',text:'Sent to applications: special requirement'},{at:'2026-10-10',who:'Applications team',text:'Reused X00001 (titanium casing hardware). Customer notified.'}]});
  // register item numbers for seeded lines
  S.quotes.forEach(q => q.lines.forEach(l => lineCalc(l)));
}

/* ---------- Line / quote calculations ---------- */
const libGet = (kind, code) => (S.lib[kind] || []).find(e => e.code === code);
function lineCalc(line) {
  const c = line.cfg, kinds = customKinds(c), cfs = cfItems(c), customs = {};
  kinds.forEach(k => { if (line.ae[k]) customs[k] = line.ae[k]; });
  const enc = encodeSpec(c, customs), pr = priceCfg(c);
  let list = pr.total; const pend = [];
  kinds.forEach(k => { const e = line.ae[k] && libGet(k, line.ae[k]); if (e) list += entryList(e); else pend.push(k); });
  cfs.forEach(k => { const v = line.ae.cf[k]; if (v && v.price !== '' && v.price != null) list += +v.price; else pend.push('cf:' + k); });
  const item = enc.pending ? null : itemFor(enc.spec, c.series, S.registry);
  return {enc, spec: enc.spec, item, list, pend, kinds, cfs, lead: leadWeeks(c), pr};
}
function quoteCalc(q) {
  const a = ACC(q.account); let list = 0, net = 0, pend = 0, lead = 0;
  const lines = q.lines.map(l => { const r = lineCalc(l); const unitNet = Math.round(r.list * (1 - a.disc));
    if (r.pend.length) pend += r.pend.length; else { list += r.list * l.qty; net += unitNet * l.qty; } lead = Math.max(lead, r.lead); return Object.assign(r, {unitNet}); });
  return {lines, list, net, pend, lead};
}
const getQ = no => S.quotes.find(q => q.no === no);
const getL = (q, id) => q.lines.find(l => l.id === id);
function canEdit(q) {
  if (q.status === 'Released') return false;
  if (S.role === 'ae') return true;
  return q.account === S.acct && q.status !== 'With applications';
}
function log(q, text) { q.history.push({at: todayISO(), who: S.role === 'ae' ? 'Applications team' : ACC(q.account).contacts[q.contact].name, text}); q.updated = todayISO(); }
function pendLabel(p) { if (p.startsWith('cf:')) { const k = p.slice(3); return `Consult factory: ${FIELD[k].label.toLowerCase()}`; } return `Custom ${KIND_LABEL[p].toLowerCase()}`; }

/* ---------- Rendering ---------- */
const STATUS_CLS = {'Draft':'st-draft','With applications':'st-ae','Completed by applications':'st-done','Released':'st-rel'};
function pill(st) { return `<span class="pill ${STATUS_CLS[st]}">${esc(st)}</span>`; }
function render() {
  const app = document.getElementById('app');
  const v = S.view.name;
  let body = '';
  if (v === 'log') body = vLog(); else if (v === 'quote') body = vQuote(); else if (v === 'config') body = vConfig();
  else if (v === 'lookup') body = vLookup(); else if (v === 'queue') body = vQueue(); else if (v === 'ae') body = vWork();
  else if (v === 'library') body = vLibrary(); else if (v === 'data') body = vData();
  app.innerHTML = vHeader() + `<main class="main ${v === 'config' ? 'main-wide' : ''}">${body}</main>` + vModal() + (S.toast ? `<div class="toast" role="status">${esc(S.toast)}</div>` : '');
  const vk = v + '|' + (S.view.q || '') + '|' + (S.view.l || '') + '|' + (S.draft ? S.draft.lineId + S.draft.q : '');
  if (vk !== S._vk) { window.scrollTo(0, 0); S._vk = vk; }
  if (S.scrollOpts) { const o = document.querySelector('.cfg'); if (o && o.getBoundingClientRect().top < 0) o.scrollIntoView({block:'start'}); S.scrollOpts = false; }
  if (S.focusKey) { const el = document.getElementById('f-' + S.focusKey); if (el) { el.scrollIntoView({block:'center', behavior:'smooth'}); el.classList.add('focus-flash'); } S.focusKey = null; }
}
function vHeader() {
  const qCount = S.quotes.filter(q => q.status === 'With applications').length;
  const tab = (id, label, extra) => `<button class="tab ${S.view.name === id || (id === 'log' && ['quote','config'].includes(S.view.name)) || (id === 'queue' && S.view.name === 'ae') ? 'on' : ''}" data-a="nav" data-v="${id}">${label}${extra || ''}</button>`;
  return `<header class="top">
    <div class="brand"><span class="mark">Fybroc</span><span class="brand-sub">Quote tool demo</span></div>
    <nav class="tabs">${tab('log','Quotes')}${tab('lookup','Look up a pump')}${S.role === 'ae' ? tab('queue','Applications queue', qCount ? ` <span class="count">${qCount}</span>` : '') + tab('library','Custom codes') : ''}${tab('data','Data model')}</nav>
    <div class="who">
      <div class="seg" role="group" aria-label="View as">
        <button class="${S.role === 'dist' ? 'on' : ''}" data-a="role" data-v="dist">Distributor</button><button class="${S.role === 'ae' ? 'on' : ''}" data-a="role" data-v="ae">Applications</button>
      </div>
      ${S.role === 'dist' ? `<select data-c="acct" aria-label="Company">${ACCOUNTS.map(a => `<option value="${a.id}" ${a.id === S.acct ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select>` : ''}
      <button class="link" data-a="reset" title="Reset all demo data">Reset demo</button>
    </div>
  </header>
  <div class="demo-note">Demo only. Prices are made up, accounts are fictional, and everything resets when the page reloads.</div>`;
}

/* Quote log */
function vLog() {
  const qs = S.quotes.filter(q => S.role === 'ae' || q.account === S.acct).slice().sort((a, b) => b.no.localeCompare(a.no));
  const rows = qs.map(q => { const t = quoteCalc(q), a = ACC(q.account);
    return `<tr class="click" data-a="openQuote" data-q="${q.no}">
      <td class="mono strong">${q.no}</td>${S.role === 'ae' ? `<td>${esc(a.name)}<div class="sub">${a.type}</div></td>` : ''}
      <td>${esc(q.project) || '<span class="sub">No project name</span>'}<div class="sub">${esc(q.ref)}</div></td>
      <td class="num">${q.lines.length}</td><td>${pill(q.status)}${t.pend ? `<div class="sub amber">${t.pend} item${t.pend > 1 ? 's' : ''} with applications</div>` : ''}</td>
      <td class="num">${t.pend ? '<span class="sub">Pending</span>' : money(t.net)}</td><td class="sub">${fmtDate(q.updated)}</td></tr>`; }).join('');
  return `<div class="page-head"><div><h1>Quotes</h1><p class="lede">${S.role === 'ae' ? 'Every quote from every account. The quote log is visible to the distributor for their own quotes.' : `Quotes for ${esc(ACC(S.acct).name)}.`}</p></div>
    <button class="btn primary" data-a="newQuote">New quote</button></div>
    ${qs.length ? `<div class="tablewrap"><table class="grid"><thead><tr><th>Quote</th>${S.role === 'ae' ? '<th>Company</th>' : ''}<th>Project and reference</th><th class="num">Lines</th><th>Status</th><th class="num">Net total</th><th>Updated</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<div class="empty"><p>No quotes yet for this company.</p><button class="btn primary" data-a="newQuote">Start a quote</button></div>`}`;
}

/* Quote workspace */
function vQuote() {
  const q = getQ(S.view.q); if (!q) return '<p>Quote not found.</p>';
  const a = ACC(q.account), t = quoteCalc(q), ed = canEdit(q), net = a.netOnly;
  const contact = a.contacts[q.contact];
  const lines = q.lines.map((l, i) => { const r = t.lines[i];
    const status = r.pend.length ? r.pend.map(p => `<span class="chip amber">${esc(pendLabel(p))}</span>`).join('') :
      (r.kinds.length || r.cfs.length ? `<span class="chip blue">Priced by applications</span>` : `<span class="chip green">Standard</span>`);
    return `<tr>
      <td class="num">${i + 1}</td>
      <td>${ed ? `<input class="in qty" type="number" min="1" value="${l.qty}" data-c="lineField" data-l="${l.id}" data-k="qty" aria-label="Quantity">` : l.qty}</td>
      <td>${ed ? `<input class="in" value="${esc(l.designation)}" placeholder="Designation" data-c="lineField" data-l="${l.id}" data-k="designation" aria-label="Designation"><input class="in" value="${esc(l.description)}" placeholder="Description" data-c="lineField" data-l="${l.id}" data-k="description" aria-label="Description">` : `<div class="strong">${esc(l.designation)}</div><div class="sub">${esc(l.description)}</div>`}</td>
      <td><div class="strong">${l.cfg.series} ${l.cfg.size}, ${l.cfg.material}</div><div class="sub">${esc(lineBrief(l.cfg))}</div><div class="chips">${status}</div></td>
      <td><div class="mono strong">${r.item || '<span class="sub">Assigned after pricing</span>'}</div><div class="mono sub">${r.spec}</div></td>
      <td class="num">${r.lead} wk</td>
      ${net ? '' : `<td class="num">${r.pend.length ? '<span class="sub">Pending</span>' : money(r.list)}</td><td class="num sub">${Math.round(a.disc * 100)}%</td>`}
      <td class="num">${r.pend.length ? '<span class="sub">Pending</span>' : money(r.unitNet)}</td>
      <td class="num strong">${r.pend.length ? '' : money(r.unitNet * l.qty)}</td>
      <td><div class="acts">
        ${ed ? `<button class="btn sm" data-a="editLine" data-l="${l.id}">Edit</button>` : ''}
        ${S.role === 'ae' && (r.kinds.length || r.cfs.length) && q.status !== 'Released' ? `<button class="btn sm ${r.pend.length ? 'amber' : ''}" data-a="openWork" data-q="${q.no}" data-l="${l.id}">${r.pend.length ? 'Finish items' : 'Custom pricing'}</button>` : ''}
        <button class="btn sm ghost" data-a="specSheet" data-l="${l.id}">Spec sheet</button>
        ${ed ? `<button class="btn sm ghost" data-a="dupLine" data-l="${l.id}">Copy</button><button class="btn sm ghost danger" data-a="removeLine" data-l="${l.id}" aria-label="Remove line ${i + 1}">Remove</button>` : ''}
      </div></td></tr>`; }).join('');
  let actions = '';
  if (S.role === 'dist') {
    if (q.status === 'With applications') actions = `<p class="note amber-note">The applications team is finishing ${t.pend} item${t.pend === 1 ? '' : 's'} on this quote. You will get an email when it is complete.</p>`;
    else if (q.status === 'Released') actions = `<button class="btn" data-a="copyQuote">Copy to a new quote</button>`;
    else if (t.pend) actions = `<button class="btn primary amber" data-a="sendAE">Send to applications for pricing</button><span class="sub">Custom and consult-factory items are priced by the applications team.</span>`;
    else actions = `<button class="btn primary" data-a="confirmQuote" ${q.lines.length ? '' : 'disabled'}>Confirm quote</button><span class="sub">Confirming locks the quote and gives you the final PDF.</span>`;
  } else {
    if (q.status === 'Released') actions = `<button class="btn" data-a="copyQuote">Copy to a new quote</button>`;
    else if (t.pend) actions = `<span class="note amber-note">${t.pend === 1 ? '1 item still needs' : t.pend + ' items still need'} pricing. Use Finish items on each line.</span>`;
    else if (q.status !== 'Completed by applications') actions = `<button class="btn primary" data-a="completeNotify" ${q.lines.length ? '' : 'disabled'}>Complete and notify customer</button>`;
    else actions = `<span class="sub">Completed and sent to the customer. Waiting for them to confirm.</span>`;
  }
  return `<button class="link back" data-a="nav" data-v="log">All quotes</button>
  <div class="page-head"><div><h1><span class="mono">${q.no}</span> ${pill(q.status)}</h1><p class="lede">${esc(a.name)}, ${a.type}. ${net ? 'Net pricing.' : `List less ${Math.round(a.disc * 100)}%.`}</p></div>
    <div class="head-acts"><button class="btn" data-a="previewQuote">Preview quote</button><button class="btn" data-a="pdfQuote" ${t.pend ? 'disabled title="Available when pricing is complete"' : ''}>Download PDF</button></div></div>
  <section class="qmeta">
    <label>Contact${ed ? `<select class="in" data-c="qField" data-k="contact">${a.contacts.map((c, i) => `<option value="${i}" ${i === q.contact ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select>` : `<span>${esc(contact.name)}</span>`}</label>
    <label>Project name${ed ? `<input class="in" value="${esc(q.project)}" data-c="qField" data-k="project" placeholder="For example Austin WWTP chemical feed">` : `<span>${esc(q.project)}</span>`}</label>
    <label>Reference number${ed ? `<input class="in" value="${esc(q.ref)}" data-c="qField" data-k="ref" placeholder="Your reference">` : `<span>${esc(q.ref)}</span>`}</label>
    <label>Created<span>${fmtDate(q.created)}</span></label>
  </section>
  <div class="tablewrap"><table class="grid lines"><thead><tr><th class="num">#</th><th>Qty</th><th>Designation and description</th><th>Pump</th><th>Item and spec number</th><th class="num">Lead</th>${net ? '' : '<th class="num">Unit list</th><th class="num">Disc.</th>'}<th class="num">Unit net</th><th class="num">Ext. net</th><th></th></tr></thead>
  <tbody>${lines || `<tr><td colspan="11" class="emptyrow">No pumps on this quote yet. Configure one below or start from a spec or item number.</td></tr>`}</tbody>
  ${q.lines.length ? `<tfoot><tr><td colspan="${net ? 7 : 9}" class="num">Net total${t.pend ? ' (excluding items still with applications)' : ''}</td><td class="num strong big">${money(t.net)}</td><td></td></tr></tfoot>` : ''}</table></div>
  ${ed ? `<section class="addbar"><div><span class="lbl">Configure a pump</span><button class="btn" data-a="addLine" data-s="1500">1500 series, horizontal</button><button class="btn" data-a="addLine" data-s="5500">5500 series, vertical</button></div>
    <div><span class="lbl">Start from an existing pump</span><input id="q-spec" class="in mono" placeholder="Item or spec number" aria-label="Item or spec number"><button class="btn" data-a="addFromSpec">Start from this pump</button></div></section>` : ''}
  <section class="actions">${actions}</section>
  <section class="history"><h2>Activity</h2><ol>${q.history.slice().reverse().map(h => `<li><span class="sub">${fmtDate(h.at)}</span> ${esc(h.who)}: ${esc(h.text)}</li>`).join('')}</ol></section>`;
}
function lineBrief(c) {
  const b = [`Trim ${c.trim}`];
  if (c.series === '1500') b.push(c.sealOption === 'Supplied by Fybroc' ? (customKinds(c).includes('seal') ? 'Custom seal' : `Seal ${c.sealType.split(' ')[0]}`) : c.sealOption);
  else b.push(c.settingMode === 'Standard Setting' ? `Setting ${c.setting}` : `Length ${c.length} in`);
  b.push(c.motorOption === 'By Others' ? 'Motor by others' : `${c.hp} HP ${c.rpm} RPM motor${c.motorOption === 'Installed by Fybroc' ? ' (customer supplied)' : ''}`);
  if (c.series === '1500' && c.baseplate === 'Baseplate Included') b.push('Baseplate');
  return b.join(', ');
}

/* Configurator */
function startDraft(q, line, series, fromItem) {
  const cfg = line ? JSON.parse(JSON.stringify(line.cfg)) : defaultCfg(series);
  S.draft = {q: q.no, lineId: line ? line.id : null, cfg, requests: line ? {...line.requests} : {}, ae: line ? JSON.parse(JSON.stringify(line.ae)) : {cf:{}},
    qty: line ? line.qty : 1, designation: line ? line.designation : '', description: line ? line.description : '', group: 'pump', msgs: [], changed: [], fromItem: fromItem || null,
    origSpec: line && !fromItem ? lineCalc(line).spec : null};
  S.view = {name:'config'};
}
function draftLine() { const d = S.draft; return {qty: d.qty, cfg: d.cfg, ae: d.ae, requests: d.requests}; }
function vConfig() {
  const d = S.draft, c = d.cfg, q = getQ(d.q), r = lineCalc(draftLine()), a = ACC(q.account);
  const groups = groupsFor(c.series);
  const priceBy = {}; r.pr.items.forEach(i => { priceBy[i.key] = (priceBy[i.key] || 0) + i.amt; if (i.cf) priceBy[i.key] = 'CF'; });
  const kinds = r.kinds;
  // Summary (left)
  const summary = groups.map(([g, gl]) => {
    const fs = fieldsFor(c.series).filter(f => f.group === g && isVisible(f, c));
    let rows = fs.map(f => { const val = c[f.key]; const p = f.key === 'size' ? 0 : priceBy[f.key]; const isCustom = f.custom && val === f.custom;
      return `<button class="srow ${isCustom ? 'custom' : ''}" data-a="jump" data-g="${g}" data-k="${f.key}"><span class="sl">${esc(f.label)}</span><span class="sv">${esc(val)}${f.ui === 'number' ? ' in' : ''}</span><span class="sp">${isCustom ? 'Applications' : p === 'CF' ? 'Consult factory' : p ? money(p) : ''}</span></button>`; }).join('');
    if (g === 'pump') rows = `<div class="srow base"><span class="sl">Base pump</span><span class="sv">${c.series} ${esc(c.size)}</span><span class="sp">${money(priceBy.size)}</span></div>` + rows;
    if (g === 'motor' && c.motorOption !== 'By Others') rows += `<div class="srow derived"><span class="sl">Motor frame</span><span class="sv">${esc(frameFor(c) || '-')}</span><span class="sp"></span></div>`;
    if (g === 'special') rows = c.special ? `<button class="srow custom" data-a="jump" data-g="special" data-k="special"><span class="sl">Requirement</span><span class="sv">${esc(c.special)}</span><span class="sp">Applications</span></button>` : `<button class="srow" data-a="jump" data-g="special" data-k="special"><span class="sl">None</span><span class="sv"></span><span class="sp"></span></button>`;
    return `<div class="sgroup ${d.group === g ? 'on' : ''}"><h3><button class="link" data-a="grp" data-v="${g}">${gl}</button></h3>${rows}</div>`; }).join('');
  // Options (right)
  const baseTotal = r.pr.total;
  const fields = d.group === 'special' ? vSpecial(c) : fieldsFor(c.series).filter(f => f.group === d.group && isVisible(f, c)).map(f => vField(f, c, baseTotal, kinds)).join('');
  const groupTabs = groups.map(([g, gl]) => `<button class="gtab ${d.group === g ? 'on' : ''}" data-a="grp" data-v="${g}">${gl}${(g === 'seal' && kinds.includes('seal')) || (g === 'motor' && kinds.includes('motor')) || (g === 'special' && kinds.includes('special')) ? '<span class="dot" aria-label="custom"></span>' : ''}</button>`).join('');
  const missingReq = S.role === 'dist' && kinds.some(k => k !== 'special' && !(d.requests[k] || '').trim() && !d.ae[k]);
  const pendingNow = r.pend.length;
  const gi = groups.findIndex(([g]) => g === d.group);
  return `<div class="cfg-head">
    <div><button class="link back" data-a="cancelCfg">Back to ${q.no}</button>
    <h1>${d.lineId ? 'Edit line' : 'New line'}: Fybroc ${c.series} ${c.series === '1500' ? 'horizontal' : 'vertical'}</h1>
    ${d.fromItem ? `<p class="lede">Started from ${esc(d.fromItem)}. Any change gives the pump a new spec and item number.</p>` : ''}</div></div>
  <section class="plate" aria-label="Spec number">
    <div class="plate-row">${r.enc.segs.map((s, i) => `<div class="seg ${s.pending ? 'pending' : ''} ${d.changed.includes(i) ? 'flash' : ''}" title="${esc(s.label)}"><span class="code">${esc(s.code)}</span><span class="cap">${esc(s.label)}</span></div>`).join('<span class="dash">-</span>')}</div>
    <div class="plate-foot"><span>Item number <b class="mono">${r.item || 'assigned after applications prices the custom items'}</b></span>${d.origSpec && d.origSpec !== r.spec ? `<span class="plate-warn">Changed from ${esc(d.origSpec)}</span>` : ''}</div>
    ${d.msgs.length ? `<div class="plate-msg" role="status">${d.msgs.map(m => `<p>${esc(m)}</p>`).join('')}</div>` : ''}
  </section>
  <div class="cfg">
    <aside class="summary"><h2>Configuration</h2>${summary}</aside>
    <section class="opts"><div class="gtabs">${groupTabs}</div>${fields}
      <div class="gnav">${gi > 0 ? `<button class="btn ghost" data-a="grp" data-v="${groups[gi - 1][0]}">Previous: ${groups[gi - 1][1]}</button>` : '<span></span>'}${gi < groups.length - 1 ? `<button class="btn" data-a="grp" data-v="${groups[gi + 1][0]}">Next: ${groups[gi + 1][1]}</button>` : ''}</div>
    </section>
  </div>
  <footer class="cfg-foot">
    <div class="ff"><label>Qty<input class="in qty" type="number" min="1" value="${d.qty}" data-i="draftField" data-k="qty"></label>
      <label>Designation<input class="in" value="${esc(d.designation)}" data-i="draftField" data-k="designation" placeholder="P-101"></label>
      <label class="grow">Description<input class="in" value="${esc(d.description)}" data-i="draftField" data-k="description" placeholder="Service or option note"></label></div>
    <div class="fp">
      <div><span class="sub">${a.netOnly ? 'Unit net' : 'Unit list'}</span><b>${pendingNow ? `${money(a.netOnly ? r.list * (1 - a.disc) : r.list)} + items for applications` : money(a.netOnly ? r.list * (1 - a.disc) : r.list)}</b></div>
      <div><span class="sub">Lead time</span><b>${r.lead} weeks</b></div>
      <button class="btn ghost" data-a="cancelCfg">Cancel</button>
      <button class="btn primary ${pendingNow ? 'amber' : ''}" data-a="saveLine" ${missingReq ? 'disabled title="Describe each custom item for the applications team first"' : ''}>${d.lineId ? 'Save changes' : 'Add to quote'}</button>
    </div>
    ${missingReq ? `<p class="sub amber-t foot-warn">Describe the custom item for the applications team before saving.</p>` : ''}
  </footer>`;
}
function deltaLabel(f, v, c, baseTotal, kinds) {
  if (v === c[f.key]) return '';
  if (f.custom && v === f.custom) return 'Applications prices this';
  const nc = normalize({...c, [f.key]: v}, f.key).cfg;
  const nk = customKinds(nc); if (nk.some(k => !kinds.includes(k))) return 'Applications prices this';
  if (cfItems(nc).includes(f.key) && !cfItems(c).includes(f.key)) return 'Consult factory';
  const dlt = priceCfg(nc).total - baseTotal;
  return dlt === 0 ? 'No change' : (dlt > 0 ? '+' : '') + money(dlt);
}
function vField(f, c, baseTotal, kinds) {
  const opts = optionsFor(f, c), sd = stdOf(f, c);
  let control = '';
  if (f.ui === 'select') {
    const shown = f.hideBlocked ? opts.filter(o => !o.blocked) : opts;
    const blocked = shown.filter(o => o.blocked);
    control = `<select class="in sel" data-c="setSel" data-k="${f.key}" aria-label="${esc(f.label)}">${shown.map(o => `<option value="${esc(o.v)}" ${o.v === c[f.key] ? 'selected' : ''} ${o.blocked ? 'disabled' : ''}>${esc(o.v)}${o.v === sd ? ' (standard)' : ''}${o.blocked ? ' (not available)' : ''}</option>`).join('')}</select>
      ${f.key === 'trim' ? `<p class="hint">Trim range for ${esc(c.size)}: ${TRIM_RANGE[c.size][0].toFixed(3)} to ${TRIM_RANGE[c.size][1].toFixed(3)} in. A trimmed impeller adds ${money(PRICE.trim)}.</p>` : ''}
      ${blocked.length ? `<p class="hint">${esc(blocked[0].blocked)}</p>` : ''}
      ${f.key === 'size' ? `<p class="hint">Group ${sizeGroup(c.size)} size. Lead time ${leadWeeks(c)} weeks.</p>` : ''}`;
  } else if (f.ui === 'number') {
    const mx = f.maxFn ? f.maxFn(c) : f.max;
    control = `<input class="in num-in" type="number" min="${f.min}" max="${mx}" value="${c[f.key]}" data-c="setNum" data-k="${f.key}" aria-label="${esc(f.label)}"><p class="hint">${f.min} to ${mx} in.${mx < f.max ? ' ' + esc(R('CT21')) : ''}</p>`;
  } else {
    const shownR = f.hideBlocked ? opts.filter(o => !o.blocked) : opts, hiddenR = opts.filter(o => o.blocked);
    let hideHint = '';
    if (f.hideBlocked && hiddenR.length) hideHint = f.key === 'hp' ? `Horsepower above ${shownR.length ? shownR[shownR.length - 1].v : 0} HP is not available for the ${c.size} at ${c.rpm} RPM.` : f.key === 'rpm' ? `${hiddenR.map(o => o.v).join(' and ')} RPM is not available for the ${c.size}.` : '';
    control = `<div class="radios">${shownR.map(o => { const on = o.v === c[f.key]; const isC = f.custom && o.v === f.custom;
      return `<button class="opt ${on ? 'on' : ''} ${isC ? 'is-custom' : ''}" data-a="set" data-k="${f.key}" data-v="${esc(o.v)}" ${o.blocked ? 'disabled' : ''} aria-pressed="${on}">
        <span class="radio" aria-hidden="true"></span><span class="ov">${esc(o.v)}${o.v === sd ? ' <em class="std">Standard</em>' : ''}${o.blocked ? `<span class="why">${esc(o.blocked)}</span>` : ''}</span>
        <span class="od">${o.blocked ? '' : esc(deltaLabel(f, o.v, c, baseTotal, kinds))}</span></button>`; }).join('')}</div>${hideHint ? `<p class="hint">${esc(hideHint)}</p>` : ''}`;
  }
  let extra = '';
  const kindFor = {sealType:'seal', motorMfg:'motor'};
  if (f.key === 'sealType' && kinds.includes('seal')) extra = vRequest('seal', 'Describe the seal you need: manufacturer, model, faces, elastomers, drawings or plant standard.');
  if (f.key === 'motorMfg' && kinds.includes('motor')) extra = vRequest('motor', 'Describe the motor you need: voltage, enclosure, area classification or other requirements.');
  if (f.key === 'perf' || f.key === 'mountPlate') { const cf = cfItems(c); if (cf.length) extra = `<p class="hint amber-t">${cf.map(k => FIELD[k].label).join(', ')}: the applications team adds the price before the quote can be confirmed.</p>`; }
  return `<div class="field" id="f-${f.key}"><h3>${esc(f.label)}</h3>${control}${extra}</div>`;
}
function vRequest(kind, ph) {
  const d = S.draft, assigned = d.ae[kind] && libGet(kind, d.ae[kind]);
  return `<div class="req"><label for="req-${kind}">Request for the applications team</label>
    <textarea id="req-${kind}" class="in" rows="3" data-i="req" data-k="${kind}" placeholder="${esc(ph)}">${esc(d.requests[kind] || '')}</textarea>
    ${assigned ? `<p class="hint">Currently priced as ${assigned.code}: ${esc(entryTitle(assigned))}.</p>` : `<p class="hint">This sets the ${KIND_LABEL[kind].toLowerCase()} segment to X?? until the applications team assigns a custom code and price.</p>`}</div>`;
}
function vSpecial(c) {
  const d = S.draft;
  return `<div class="field" id="f-special"><h3>Special requirements</h3>
    <p class="hint">For anything the configurator does not cover, such as titanium casing hardware. Text here sends the line to the applications team and adds an X code to the end of the spec number.</p>
    <textarea class="in" rows="4" data-i="special" placeholder="Describe the requirement">${esc(c.special)}</textarea>
    ${c.special ? `<label class="req" for="req-special">Supporting notes (optional)<textarea id="req-special" class="in" rows="2" data-i="req" data-k="special">${esc(d.requests.special || '')}</textarea></label>` : ''}</div>`;
}

/* Applications worksheet */
function vWork() {
  const q = getQ(S.view.q), l = getL(q, S.view.l); if (!q || !l) return '<p>Line not found.</p>';
  const r = lineCalc(l), a = ACC(q.account), idx = q.lines.indexOf(l) + 1;
  const cards = r.kinds.map(k => vKindCard(q, l, k)).join('') + r.cfs.map(k => vCfCard(l, k)).join('');
  const t = quoteCalc(q);
  const head = `<button class="link back" data-a="openQuote" data-q="${q.no}">Back to ${q.no}</button>
  <div class="page-head"><div><h1>Finish line ${idx} of ${q.no}</h1><p class="lede">${esc(a.name)}. ${esc(l.designation)} ${esc(l.description)}</p></div></div>
  <section class="plate small"><div class="plate-row">${r.enc.segs.map(s => `<div class="seg ${s.pending ? 'pending' : ''}" title="${esc(s.label)}"><span class="code">${esc(s.code)}</span><span class="cap">${esc(s.label)}</span></div>`).join('<span class="dash">-</span>')}</div>
    <div class="plate-foot"><span>Item number <b class="mono">${r.item || 'assigned once every X?? has a code'}</b></span><span>Standard content ${money(r.pr.total)} list</span></div></section>
  ${cards}`;
  const nextL = q.lines.find(x => x !== l && lineCalc(x).pend.length);
  return `${head}<section class="actions">${t.pend ? `<span class="note amber-note">${t.pend} item${t.pend === 1 ? '' : 's'} left on this quote.</span>${nextL && !r.pend.length ? `<button class="btn primary amber" data-a="openWork" data-q="${q.no}" data-l="${nextL.id}">Next line with open items</button>` : ''}` : q.status === 'Completed by applications' ? '<span class="sub">Quote already completed.</span>' : `<button class="btn primary" data-a="completeNotify">Complete and notify customer</button>`}
  <button class="btn ghost" data-a="openQuote" data-q="${q.no}">Back to quote</button></section>`;
}
function vKindCard(q, l, kind) {
  const code = l.ae[kind], e = code && libGet(kind, code), fk = l.id + ':' + kind;
  const sel = kind === 'special' ? `<p><b>Requirement:</b> ${esc(l.cfg.special)}</p>` :
    `<dl class="dl">${CUSTOM_FIELDS[kind].filter(k => isVisible(FIELD[k], l.cfg)).map(k => `<dt>${esc(FIELD[k].label)}</dt><dd>${esc(l.cfg[k])}</dd>`).join('')}</dl>`;
  const req = l.requests[kind];
  let body;
  if (e) {
    body = `<div class="assigned"><div><span class="code-badge">${e.code}</span> ${esc(entryTitle(e))}</div>${vRowsTable(e.rows, false)}<p class="strong">List adder ${money(entryList(e))}</p>
      <button class="btn sm ghost" data-a="changeCode" data-kind="${kind}" data-l="${l.id}">Change</button></div>`;
  } else {
    const knownVendor = ['John Crane','Flowserve','Flex-a-seal'].includes(l.cfg.sealMfg) ? l.cfg.sealMfg : '';
    if (!S.aeForm[fk]) S.aeForm[fk] = {vendor: kind === 'seal' ? knownVendor : '', series: '', desc: (kind === 'special' ? l.cfg.special : req) || '', rows: kind === 'seal' ? [{d:'Seal (vendor quote)', cost:'', margin:40, ref:''},{d:'Gland or cover modification', cost:'', margin:55, ref:''}] : kind === 'motor' ? [{d:'Motor premium over standard', cost:'', margin:35, ref:''}] : [{d:'Material and labor', cost:'', margin:50, ref:''}]};
    const f = S.aeForm[fk];
    if (S.aeSearch[fk] === undefined) S.aeSearch[fk] = kind === 'seal' ? knownVendor : '';
    const all = (S.lib[kind] || []).slice().reverse(), past = all.filter(e => matchSearch(e, S.aeSearch[fk]));
    const nextCode = nextCodeFor(kind), isSeal = kind === 'seal';
    const dups = isSeal && f.vendor.trim() && f.series.trim() ? all.filter(e => (e.vendor || '').toLowerCase() === f.vendor.trim().toLowerCase() && (e.series || '').toLowerCase() === f.series.trim().toLowerCase()) : [];
    const vendors = [...new Set(all.map(e => e.vendor).filter(Boolean))];
    body = `<h4>Reuse a past code</h4>
      <div class="search"><input id="srch-${fk}" class="in" value="${esc(S.aeSearch[fk])}" data-i="aeSearch" data-f="${fk}" placeholder="${isSeal ? 'Search vendor, series or description, for example John Crane 5610' : 'Search codes'}" aria-label="Search past codes"><span class="sub">${past.length} of ${all.length} codes</span></div>
      ${past.length ? `<div class="tablewrap"><table class="grid compact"><thead><tr><th>Code</th>${isSeal ? '<th>Vendor</th><th>Series</th>' : ''}<th>Description</th><th>Priced</th><th class="num">List adder</th><th></th></tr></thead><tbody>
      ${past.map(p => { const m = monthsAgo(p.date); return `<tr><td class="mono strong">${p.code}</td>${isSeal ? `<td>${esc(p.vendor)}</td><td class="mono">${esc(p.series)}</td>` : ''}<td>${esc(p.desc)}<div class="sub">${p.rows.map(r => esc(r.ref)).filter(Boolean).join(', ')}</div></td><td>${fmtDate(p.date)}${m > 12 ? `<div class="sub amber-t">${m} months old. Get a fresh vendor quote before reusing.</div>` : `<div class="sub">${m} month${m === 1 ? '' : 's'} ago</div>`}</td><td class="num">${money(entryList(p))}</td><td><button class="btn sm" data-a="useCode" data-kind="${kind}" data-code="${p.code}" data-l="${l.id}">Use ${p.code}</button></td></tr>`; }).join('')}</tbody></table></div>` : `<p class="sub">${all.length ? 'No past codes match this search.' : 'No past codes in this category.'}</p>`}
      <h4>Or create ${nextCode}</h4>
      ${isSeal ? `<div class="form2"><label class="blk">Vendor<input class="in" list="vendors-${l.id}" value="${esc(f.vendor)}" data-i="aeDesc" data-c="aeForm" data-f="${fk}" data-k="vendor" placeholder="John Crane"></label><datalist id="vendors-${l.id}">${vendors.map(v => `<option value="${esc(v)}">`).join('')}</datalist>
        <label class="blk">Vendor part number or series<input class="in mono" value="${esc(f.series)}" data-i="aeDesc" data-c="aeForm" data-f="${fk}" data-k="series" placeholder="5610"></label></div>
        ${dups.length ? `<p class="hint amber-t">${dups.length} existing code${dups.length === 1 ? '' : 's'} for ${esc(f.vendor)} ${esc(f.series)}: ${dups.map(e => `${e.code} (${esc(e.desc)})`).join(', ')}. Reuse one above if it matches.</p>` : ''}` : ''}
      <label class="blk">${isSeal ? 'Description' : 'Spec sheet description'}<input class="in" value="${esc(f.desc)}" data-i="aeDesc" data-f="${fk}" data-k="desc" placeholder="${isSeal ? 'Arrangement, faces, elastomers' : 'What the customer gets'}"></label>
      ${vRowsTable(f.rows, true, fk)}
      <div class="row-acts"><button class="btn sm ghost" data-a="addRow" data-f="${fk}">Add cost line</button><span class="tot" data-calc="${fk}">${calcText(f.rows)}</span></div>
      <button class="btn primary" data-a="assignNew" data-kind="${kind}" data-l="${l.id}">Assign ${nextCode} and save price</button>`;
  }
  return `<section class="card ${e ? '' : 'pending-card'}"><header><h2>${KIND_LABEL[kind]}</h2>${e ? '<span class="chip blue">Priced</span>' : '<span class="chip amber">Needs a code and price</span>'}</header>
    <div class="cols"><div><h4>What was selected</h4>${sel}</div><div><h4>Request from ${esc(ACC(q.account).name)}</h4><blockquote>${esc(req || 'No note provided.')}</blockquote></div></div>${body}</section>`;
}
function calcText(rows) { const cost = rows.reduce((t, r) => t + (+r.cost || 0), 0), list = rows.reduce((t, r) => t + rowList(r), 0);
  return `Cost ${money(cost)}. List adder ${money(list)}.${list ? ` Blended margin ${Math.round((1 - cost / list) * 100)}%.` : ''}`; }
function vRowsTable(rows, editable, fk) {
  return `<div class="tablewrap"><table class="grid compact rows"><thead><tr><th>Cost line</th><th class="${editable ? '' : 'num'}">Cost</th><th class="${editable ? '' : 'num'}">Margin %</th><th class="num">List</th><th>Reference or note</th></tr></thead><tbody>
  ${rows.map((r, i) => editable ? `<tr><td><input class="in" value="${esc(r.d)}" data-i="aeRow" data-f="${fk}" data-r="${i}" data-k="d" aria-label="Cost line"></td>
    <td><input class="in num-in" type="number" value="${esc(r.cost)}" data-i="aeRow" data-f="${fk}" data-r="${i}" data-k="cost" aria-label="Cost"></td>
    <td><input class="in num-in" type="number" value="${esc(r.margin)}" data-i="aeRow" data-f="${fk}" data-r="${i}" data-k="margin" aria-label="Margin percent"></td>
    <td class="num" data-rowlist="${fk}:${i}">${money(rowList(r))}</td>
    <td><input class="in" value="${esc(r.ref)}" data-i="aeRow" data-f="${fk}" data-r="${i}" data-k="ref" placeholder="Vendor quote no., date" aria-label="Reference"></td></tr>`
    : `<tr><td>${esc(r.d)}</td><td class="num">${money(+r.cost)}</td><td class="num">${r.margin}%</td><td class="num">${money(rowList(r))}</td><td class="sub">${esc(r.ref)}</td></tr>`).join('')}</tbody></table></div>`;
}
function vCfCard(l, k) {
  const v = l.ae.cf[k];
  return `<section class="card ${v ? '' : 'pending-card'}"><header><h2>Consult factory: ${esc(FIELD[k].label)}</h2>${v ? '<span class="chip blue">Priced</span>' : '<span class="chip amber">Needs a price</span>'}</header>
    <p>Selected: <b>${esc(l.cfg[k])}</b>. The selection is standard, so the spec number does not change. Only the price comes from the factory.</p>
    <div class="cf-row"><label>List price<input class="in num-in" type="number" id="cf-p-${l.id}-${k}" value="${v ? esc(v.price) : ''}"></label>
    <label class="grow">Note<input class="in" id="cf-n-${l.id}-${k}" value="${v ? esc(v.note) : ''}" placeholder="Basis for the price, for example test lab quote and date"></label>
    <button class="btn ${v ? '' : 'primary'}" data-a="cfSave" data-k="${k}" data-l="${l.id}">${v ? 'Update price' : 'Save price'}</button></div></section>`;
}
function nextCodeFor(kind) { const n = (S.lib[kind] || []).length + 1; return kind === 'special' ? 'X' + String(n).padStart(5, '0') : 'X' + String(n).padStart(2, '0'); }

/* Applications queue */
function vQueue() {
  const qs = S.quotes.filter(q => q.status === 'With applications' || (q.status !== 'Released' && quoteCalc(q).pend));
  const rows = qs.map(q => { const t = quoteCalc(q), a = ACC(q.account);
    return q.lines.map((l, i) => { const r = t.lines[i]; if (!r.pend.length && !r.kinds.length && !r.cfs.length) return '';
      return `<tr><td class="mono strong">${q.no}</td><td>${esc(a.name)}<div class="sub">${esc(q.project)}</div></td><td>Line ${i + 1}: ${esc(l.designation)}<div class="sub">${l.cfg.series} ${esc(l.cfg.size)}</div></td>
      <td>${r.pend.length ? r.pend.map(p => `<span class="chip amber">${esc(pendLabel(p))}</span>`).join('') : '<span class="chip blue">Priced</span>'}</td><td class="sub">${fmtDate(q.updated)}</td>
      <td><button class="btn sm ${r.pend.length ? 'amber' : ''}" data-a="openWork" data-q="${q.no}" data-l="${l.id}">${r.pend.length ? 'Open worksheet' : 'Review'}</button></td></tr>`; }).join(''); }).join('');
  return `<div class="page-head"><div><h1>Applications queue</h1><p class="lede">Lines with custom selections, special requirements, or consult-factory prices. Distributors start these; the applications team finishes them in the same tool.</p></div></div>
  ${rows ? `<div class="tablewrap"><table class="grid"><thead><tr><th>Quote</th><th>Company and project</th><th>Line</th><th>Needs</th><th>Received</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty"><p>Nothing waiting. New requests appear here when a distributor sends a quote to applications.</p></div>'}`;
}

/* Custom code library */
function vLibrary() {
  return `<div class="page-head"><div><h1>Custom codes</h1><p class="lede">Every X code the applications team has assigned. A code replaces only the spec segment it affects, so a reorder by spec or item number recalls the exact custom item and its price basis.</p></div></div>
  <div class="search lib-search"><input id="lib-search" class="in" value="${esc(S.libSearch)}" data-i="libSearch" placeholder="Search every code, for example John Crane 5610" aria-label="Search custom codes"></div>
  ${['seal','motor','special'].map(k => { const list = (S.lib[k] || []).filter(e => matchSearch(e, S.libSearch)); return `<section class="card"><header><h2>${KIND_LABEL[k]} codes</h2><span class="sub">${list.length} of ${(S.lib[k] || []).length}. Replaces the ${k === 'seal' ? 'mechanical seal segment' : k === 'motor' ? 'motor assembly segment' : 'end of the spec number as an extra segment'}</span></header>
    <div class="tablewrap"><table class="grid compact"><thead><tr><th>Code</th>${k === 'seal' ? '<th>Vendor</th><th>Series</th>' : ''}<th>Description</th><th>Cost lines</th><th class="num">List adder</th><th>Priced</th><th>First quote</th></tr></thead><tbody>
    ${list.map(e => `<tr><td class="mono strong">${e.code}</td>${k === 'seal' ? `<td>${esc(e.vendor)}</td><td class="mono">${esc(e.series)}</td>` : ''}<td>${esc(e.desc)}</td><td class="sub">${e.rows.map(r => `${esc(r.d)}: ${money(+r.cost)} at ${r.margin}%${r.ref ? ` (${esc(r.ref)})` : ''}`).join('<br>')}</td><td class="num">${money(entryList(e))}</td><td>${fmtDate(e.date)}</td><td class="mono">${esc(e.quote)}</td></tr>`).join('')}
    </tbody></table></div></section>`; }).join('')}`;
}

/* Lookup */
function vLookup() {
  const lk = S.lookup || {};
  const samples = Object.entries(S.registry.byItem).slice(0, 4);
  let result = '';
  if (lk.error) result = `<div class="msgs err" role="alert"><p>${esc(lk.error)}</p></div>`;
  else if (lk.res) {
    const {cfg, customs} = lk.res, line = {qty:1, cfg, ae:Object.assign({cf:{}}, customs), requests:{}}, r = lineCalc(line);
    const targets = S.quotes.filter(q => canEdit(q));
    result = `<section class="card"><header><h2>${esc(r.item || '')}</h2><span class="mono sub">${esc(r.spec)}</span></header>
      <p class="strong">${esc(shortDesc(cfg))}</p>${vSpecTables(cfg, customs, true)}
      <div class="lk-acts"><button class="btn" data-a="lkSpec">Open spec sheet</button>
      <span class="lbl">Start a new line from this pump on</span><select id="lk-target" class="in">${targets.map(q => `<option value="${q.no}">${q.no} ${esc(q.project)}</option>`).join('')}<option value="__new">A new quote</option></select>
      <button class="btn primary" data-a="lkStart">Start from this pump</button></div>
      <p class="hint">Starting from a pump copies every selection. Save it unchanged to reorder the same item number, or change anything, such as removing the motor, to get a new spec and item number.</p></section>`;
  }
  return `<div class="page-head"><div><h1>Look up a pump</h1><p class="lede">Enter an item number or a spec number to see exactly what that pump is, then reorder it or use it as the starting point for a new quote.</p></div></div>
  <section class="lookup"><input id="lk-input" class="in mono big-in" value="${esc(lk.input || '')}" placeholder="Item number such as F1500-123456, or a full spec number" aria-label="Item or spec number"><button class="btn primary" data-a="lookup">Look up</button></section>
  <p class="sub">Try one from the seeded quotes: ${samples.map(([item, spec]) => `<button class="link mono" data-a="lkExample" data-v="${item}">${item}</button>`).join(', ')}</p>
  ${result}`;
}
function resolveLookup(input) {
  const v = String(input || '').trim().toUpperCase();
  if (!v) return {error: 'Enter an item number or a spec number.'};
  if (/^F\d{4}-\d{6}$/.test(v)) { const spec = S.registry.byItem[v]; if (!spec) return {error: `Item ${v} has not been created yet. Item numbers exist once a configuration has been priced.`}; return decodeSpec(spec, S.lib); }
  return decodeSpec(v, S.lib);
}

/* Spec sheet tables */
function vSpecTables(c, customs, compact) {
  const groups = groupsFor(c.series).filter(([g]) => g !== 'special');
  const kinds = customKinds(c);
  let html = `<div class="spec-grid ${compact ? 'compact' : ''}">` + groups.map(([g, gl]) => {
    const rows = fieldsFor(c.series).filter(f => f.group === g && isVisible(f, c)).map(f => { const isC = f.custom && c[f.key] === f.custom;
      return `<tr><th>${esc(f.label)}</th><td>${isC ? `Custom, see note: ${KIND_LABEL[g === 'seal' ? 'seal' : 'motor']}` : esc(c[f.key]) + (f.ui === 'number' ? ' in' : '')}</td></tr>`; }).join('');
    const extra = g === 'motor' && c.motorOption !== 'By Others' ? `<tr><th>Motor frame</th><td>${esc(frameFor(c) || '-')}</td></tr>` : g === 'pump' ? `<tr><th>Series</th><td>${c.series}</td></tr>` : '';
    return `<table class="spec"><caption>${gl}</caption><tbody>${g === 'pump' ? extra + rows : rows + extra}</tbody></table>`; }).join('') + '</div>';
  const notes = [];
  kinds.forEach(k => { const e = customs[k] && libGet(k, customs[k]); notes.push(`<div class="cnote"><h4>${KIND_LABEL[k]}${e ? ` (${e.code})` : ''}</h4><p>${e ? esc(entryTitle(e)) : esc(k === 'special' ? c.special : 'Pending: the applications team is defining this item.')}</p></div>`); });
  const cn = configNotes(c);
  if (notes.length) html += `<h3 class="spec-h">Custom item notes</h3>${notes.join('')}`;
  if (cn.length) html += `<h3 class="spec-h">Configuration notes</h3><ul class="cn">${cn.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`;
  return html;
}
function specSheetHTML(q, l) {
  const r = lineCalc(l), customs = {}; r.kinds.forEach(k => { if (l.ae[k]) customs[k] = l.ae[k]; });
  return `<article class="doc"><header class="doc-h"><div><div class="mark">Fybroc</div><div class="sub">Pump specification sheet</div></div>
    <div class="doc-ids"><div><span>Item</span><b class="mono">${r.item || 'Pending'}</b></div><div><span>Spec</span><b class="mono">${esc(r.spec)}</b></div>${q ? `<div><span>Quote</span><b>${q.no}, line ${q.lines.indexOf(l) + 1}</b></div>` : ''}${l.designation ? `<div><span>Designation</span><b>${esc(l.designation)}</b></div>` : ''}</div></header>
    <p class="strong">${esc(shortDesc(l.cfg))}</p>${vSpecTables(l.cfg, customs)}</article>`;
}

/* Quote document (preview) */
function quoteDocHTML(q) {
  const a = ACC(q.account), t = quoteCalc(q), ct = a.contacts[q.contact], net = a.netOnly;
  const valid = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
  return `<article class="doc"><header class="doc-h"><div><div class="mark">Fybroc</div><div class="sub">Quotation</div></div>
    <div class="doc-ids"><div><span>Quote</span><b class="mono">${q.no}</b></div><div><span>Date</span><b>${fmtDate(q.updated)}</b></div><div><span>Valid until</span><b>${fmtDate(valid)}</b></div></div></header>
    <div class="doc-meta"><div><span class="sub">Prepared for</span><b>${esc(a.name)}</b><div>${esc(ct.name)}</div><div class="sub">${esc(ct.email)}</div></div>
    <div><span class="sub">Project</span><b>${esc(q.project) || '-'}</b><span class="sub">Reference</span><b>${esc(q.ref) || '-'}</b></div></div>
    <div class="tablewrap"><table class="grid doc-t"><thead><tr><th>Line</th><th>Qty</th><th>Designation</th><th>Item and spec number</th><th>Summary</th><th class="num">Lead</th>${net ? '' : '<th class="num">List</th><th class="num">Disc.</th>'}<th class="num">Unit net</th><th class="num">Ext. net</th></tr></thead><tbody>
    ${q.lines.map((l, i) => { const r = t.lines[i]; return `<tr><td>${i + 1}</td><td>${l.qty}</td><td>${esc(l.designation)}<div class="sub">${esc(l.description)}</div></td><td class="mono">${r.item || 'Pending'}<div class="sub">${esc(r.spec)}</div></td>
      <td>${l.cfg.series}, ${esc(l.cfg.size)}, ${esc(l.cfg.material)}<div class="sub">${esc(lineBrief(l.cfg))}</div></td><td class="num">${r.lead} wk</td>
      ${net ? '' : `<td class="num">${r.pend.length ? 'Pending' : money(r.list)}</td><td class="num">${Math.round(a.disc * 100)}%</td>`}<td class="num">${r.pend.length ? 'Pending' : money(r.unitNet)}</td><td class="num">${r.pend.length ? '' : money(r.unitNet * l.qty)}</td></tr>`; }).join('')}
    </tbody><tfoot><tr><td colspan="${net ? 7 : 9}" class="num">Total net${t.pend ? ', excluding lines still being priced' : ''}</td><td class="num strong">${money(t.net)}</td></tr></tfoot></table></div>
    <ul class="terms"><li>Prices are valid for 30 days and do not include freight.</li><li>Lead time is in weeks after receipt of an approved order.</li><li>Sale is subject to Fybroc standard terms and conditions.</li></ul></article>
    ${q.lines.map(l => specSheetHTML(q, l)).join('')}`;
}

/* Data model page (for the dev team) */
function vData() {
  const segTable = (series) => {
    const ex = series === '1500' ? defaultCfg('1500', {size:'1x2x10', material:'VR-1A', trim:'9.250', sealType:'8-1T Double Inside', motorOption:'Supplied by Fybroc', rpm:'3600', hp:'5'}) : defaultCfg('5500', {setting:'7', shaft:'316 SS'});
    const enc = encodeSpec(ex);
    const rules = series === '1500' ? [
      'Brand F + series and flange letter + size code + material code (nomenclature Attributes tab).',
      'Trim: inch letter (A = 4 in to M = 16 in) + eighth letter (A = .000 to H = .875).',
      `Pump options: base-36, mixed radix over ${PO['1500'].map(k => k === '#flush' ? 'flush + flush material (10)' : `${FIELD[k].label.toLowerCase()} (${FIELD[k].master.length})`).join(', ')}.`,
      'Seal manufacturer letter (S, J, W, F; N = no seal) + seal assembly code from the Seal Assembly tab. Custom seal: X01, X02...',
      'Drive and base: coupling + 2 × guard + 8 × baseplate + 16 × baseplate hardware + 48 × nameplate + 96 × C-face + 1, base-36 (Options tab).',
      'Motor: 000 = by others, else base-36 mixed radix over option, control, HP, RPM, voltage, hertz, enclosure, manufacturer. Custom motor: X01...',
      'Modifications: 2 = shaft grounding ring, P = paint upgrade, X = none.',
      'Testing: performance × 48 + hydro × 16 + vibration × 4 + sound, base-36.',
      'Optional: special requirement code X00001...'] : [
      'Brand F + series and flange letter + size code + material code.', 'Trim, as for the 1500.',
      `Pump options: base-36, mixed radix over ${PO['5500'].map(k => k === '#flush' ? 'flush + flush material (10)' : k === '#wetted' ? 'wetted hardware (6)' : `${FIELD[k].label.toLowerCase()} (${FIELD[k].master.length})`).join(', ')}.`,
      'Setting (01 to 19) or custom length (A0 = 18 in, base-36 steps) + tailpipe length (00 = none).',
      'Drive and base: coupling + 2 × mounting plate + 4 × nameplate + 1, base-36.', 'Motor, as for the 1500.', 'Modifications, as for the 1500.', 'Testing, as for the 1500.'];
    return `<div class="tablewrap"><table class="grid compact"><thead><tr><th>Segment</th><th>Example</th><th>Rule</th></tr></thead><tbody>${enc.segs.map((s, i) => `<tr><td>${esc(s.label)}</td><td class="mono strong">${esc(s.code)}</td><td>${esc(rules[i])}</td></tr>`).join('')}${series === '1500' ? `<tr><td>Special requirement</td><td class="mono strong">X00001</td><td>${esc(rules[8])}</td></tr>` : ''}</tbody></table></div><p class="sub mono">Example: ${esc(enc.spec)}</p>`;
  };
  const fieldTable = series => `<div class="tablewrap"><table class="grid compact"><thead><tr><th>Group</th><th>Field</th><th>Options (code index: value)</th><th>Standard</th></tr></thead><tbody>${fieldsFor(series).map(f => `<tr><td class="sub">${esc(GROUPS.find(g => g[0] === f.group)[1])}</td><td class="strong">${esc(f.label)}</td><td class="sub">${f.ui === 'number' ? `Number, ${f.min} to ${f.max}` : f.key === 'trim' ? '4.000 to 16.000 in 0.125 steps, limited by size' : f.key === 'size' ? availList(f, series).join(', ') : availList(f, series).map(v => `${f.master.indexOf(v)}: ${esc(v)}`).join(', ')}</td><td class="sub">${esc(f.stdFn ? 'Depends on size' : f.std[series])}</td></tr>`).join('')}</tbody></table></div>`;
  const cons = Object.entries(CONSTRAINTS).map(([id, [fs, d]]) => `<tr><td class="mono">${id.replace('CT', 'ConstraintTable')}</td><td>${esc(fs)}</td><td>${esc(d)}</td></tr>`).join('');
  const price = s => `<tr><th>${s} series</th>${SIZES.map(z => `<td class="num">${money(BASE[s][z])}</td>`).join('')}</tr>`;
  return `<div class="page-head"><div><h1>Data model</h1><p class="lede">The tables and rules this demo runs on, laid out for the development team. Codes come from Nomenclature V6 and availability from the constraints workbook. Prices and some rules are placeholders, marked below.</p></div>
    <button class="btn" data-a="dlData">Download as JSON</button></div>
  <section class="card"><header><h2>How numbers are assigned</h2></header>
    <p>The spec number is built from the selections, segment by segment, so it can be decoded back into a full configuration. The item number is a series prefix plus a six-digit serial. Asking for the same spec number always returns the same item number, and a configuration that has never been priced gets a new one. A custom selection only replaces the segment it affects with an X code, which the applications team assigns. Until then the segment shows X?? and no item number is issued.</p>
    <p>The combined Hardware choice is not a segment of its own. Choosing 303 SS or 316 SS fills casing, power frame, gland and baseplate hardware with that material; choosing each part separately lets them differ. Each part is still encoded individually, so the spec number decodes back to the same Hardware choice.</p>
    <p>Custom seal codes carry a vendor and a vendor part number or series, so the applications team can search the library (for example John Crane 5610) before creating a duplicate.</p></section>
  <section class="card"><header><h2>1500 spec number segments</h2></header>${segTable('1500')}</section>
  <section class="card"><header><h2>5500 spec number segments</h2></header>${segTable('5500')}</section>
  <section class="card"><header><h2>Constraint rules</h2><span class="sub">Enforced live in the configurator: blocked options show their reason, and invalid selections are corrected with a message.</span></header>
    <div class="tablewrap"><table class="grid compact"><thead><tr><th>Rule</th><th>Fields</th><th>Rule as implemented</th></tr></thead><tbody>${cons}</tbody></table></div>
    <p class="hint">Placeholders: Group 3 is assumed to be 6x8x13, 8x10x15 and 10x12x16. ConstraintTable5 and ConstraintTable25 are interpreted from their descriptions. The HP limit by size and speed (M1) stands in for pump curves.</p></section>
  <section class="card"><header><h2>1500 fields</h2></header>${fieldTable('1500')}</section>
  <section class="card"><header><h2>5500 fields</h2></header>${fieldTable('5500')}</section>
  <section class="card"><header><h2>Pricing (made up)</h2><span class="sub">List price = base by series and size + material % + adders. Net = list less the account discount.</span></header>
    <div class="tablewrap"><table class="grid compact"><thead><tr><th></th>${SIZES.map(z => `<th class="num">${z}</th>`).join('')}</tr></thead><tbody>${price('1500')}${price('5500')}</tbody></table></div>
    <p class="hint">Material adders: ${Object.entries(MAT_PCT).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(', ')}. Lead time in weeks: 1500 ${Object.values(LEAD['1500']).join(', ')}; 5500 ${Object.values(LEAD['5500']).join(', ')} for Groups 1, 2 and 3. Witnessed tests and custom mounting plates are consult factory.</p></section>
  <section class="card"><header><h2>Item number registry</h2><span class="sub">${Object.keys(S.registry.byItem).length} items this session</span></header>
    <div class="tablewrap"><table class="grid compact"><thead><tr><th>Item</th><th>Spec</th></tr></thead><tbody>${Object.entries(S.registry.byItem).map(([i, s]) => `<tr><td class="mono strong">${i}</td><td class="mono">${esc(s)}</td></tr>`).join('')}</tbody></table></div></section>`;
}

/* Modals */
function vModal() {
  const m = S.modal; if (!m) return '';
  let inner = '';
  if (m.type === 'newQuote') {
    const a = ACC(m.acct);
    inner = `<h2>New quote</h2><p class="sub">The applications team can quote for any company, including contacts who do not have a portal login.</p>
      <label class="blk">Company<select class="in" data-c="nqAcct">${ACCOUNTS.map(x => `<option value="${x.id}" ${x.id === m.acct ? 'selected' : ''}>${esc(x.name)} (${x.type})</option>`).join('')}</select></label>
      <label class="blk">Contact<select class="in" id="nq-contact">${a.contacts.map((c, i) => `<option value="${i}">${esc(c.name)}</option>`).join('')}</select></label>
      <div class="m-acts"><button class="btn ghost" data-a="closeModal">Cancel</button><button class="btn primary" data-a="createQuote">Create quote</button></div>`;
  } else if (m.type === 'spec') {
    const q = m.q ? getQ(m.q) : null; const l = q ? getL(q, m.l) : m.line;
    inner = `<div class="m-top"><h2>Spec sheet</h2><div><button class="btn" data-a="pdfSpec">Download PDF</button><button class="btn ghost" data-a="closeModal">Close</button></div></div>${specSheetHTML(q, l)}`;
  } else if (m.type === 'preview') {
    const q = getQ(m.q), t = quoteCalc(q);
    inner = `<div class="m-top"><h2>Quote preview</h2><div><button class="btn" data-a="pdfQuote" ${t.pend ? 'disabled' : ''}>Download PDF</button><button class="btn ghost" data-a="closeModal">Close</button></div></div>
      <p class="sub">The PDF contains the quote followed by one spec sheet per line.</p>${quoteDocHTML(q)}`;
  } else if (m.type === 'notify') {
    const q = getQ(m.q), a = ACC(q.account), ct = a.contacts[q.contact];
    inner = `<h2>Customer notified</h2><p class="sub">This is the email the contact receives.</p>
      <div class="email"><div class="em-h"><div><span>To</span> ${esc(ct.name)} &lt;${esc(ct.email)}&gt;</div><div><span>Subject</span> Your Fybroc quote ${q.no} is complete</div></div>
      <div class="em-b"><p>Hello ${esc(ct.name.split(' ')[0])},</p><p>The applications team has finished pricing quote ${q.no}${q.project ? ` for ${esc(q.project)}` : ''}. Review it and confirm it in the portal.</p>
      ${ct.nologin ? `<p class="amber-t">This contact has no portal login, so the email attaches the quote PDF instead of a portal link.</p>` : `<p><span class="btn primary fake">View quote in the portal</span></p>`}</div></div>
      <div class="m-acts"><button class="btn ghost" data-a="closeModal">Close</button><button class="btn primary" data-a="viewAsCustomer" data-q="${q.no}">See it as the customer</button></div>`;
  } else if (m.type === 'driveAdd') {
    const c = S.draft.cfg, base = priceCfg(c).total;
    let tc = {...c}; const rows = m.items.map(([k, v, label]) => { const before = priceCfg(normalize(tc).cfg).total; tc = normalize({...tc, [k]: v}, k).cfg; return `<li><span>${esc(label)}</span><span class="mono">+${money(priceCfg(tc).total - before)}</span></li>`; }).join('');
    inner = `<h2>Add drive and base items?</h2><p>A motor ${c.motorOption === 'Installed by Fybroc' ? 'installed' : 'supplied'} by Fybroc is normally mounted with ${c.series === '1500' ? 'a coupling, a steel coupling guard and a baseplate' : 'a coupling'}. These are now the standard selections. Add them to this pump?</p>
      <ul class="addlist">${rows}</ul><p class="sub">You can change any of them later under Drive and base.</p>
      <div class="m-acts"><button class="btn ghost" data-a="closeModal">Not now</button><button class="btn primary" data-a="driveAddYes">Add them</button></div>`;
  } else if (m.type === 'confirm') {
    inner = `<h2>${esc(m.title)}</h2><p>${esc(m.text)}</p><div class="m-acts"><button class="btn ghost" data-a="closeModal">Cancel</button><button class="btn primary" data-a="${m.yes}">${esc(m.yesLabel)}</button></div>`;
  }
  return `<div class="modal-bg" data-a="closeModalBg"><div class="modal ${['spec','preview'].includes(m.type) ? 'wide' : ''}" role="dialog" aria-modal="true">${inner}</div></div>`;
}

/* ---------- Actions ---------- */
function toast(t) { S.toast = t; clearTimeout(toast.h); toast.h = setTimeout(() => { S.toast = null; const el = document.querySelector('.toast'); if (el) el.remove(); }, 3200); }
function newQuote(acct, contact) {
  const no = 'Q26-' + (S.nextQuote++);
  const q = {no, account: acct, contact: contact || 0, project:'', ref:'', status:'Draft', created: todayISO(), updated: todayISO(), lines:[], history:[]};
  S.quotes.push(q); log(q, S.role === 'ae' ? 'Quote created by the applications team' : 'Quote created'); return q;
}
function setDraft(key, val) {
  const d = S.draft, before = lineCalc(draftLine()).enc.segs.map(s => s.code);
  const res = normalize({...d.cfg, [key]: val}, key);
  d.cfg = res.cfg; d.msgs = res.msgs;
  // drop codes for custom kinds that are no longer present, or whose selections changed
  for (const k of ['seal','motor','special']) if (!customKinds(d.cfg).includes(k)) delete d.ae[k];
  if (CUSTOM_FIELDS.seal.includes(key)) delete d.ae.seal;
  if (CUSTOM_FIELDS.motor.includes(key)) delete d.ae.motor;
  if (key === 'special') delete d.ae.special;
  for (const k of Object.keys(d.ae.cf)) if (!cfItems(d.cfg).includes(k)) delete d.ae.cf[k];
  const after = lineCalc(draftLine()).enc.segs.map(s => s.code);
  d.changed = after.map((c, i) => c !== before[i] ? i : -1).filter(i => i >= 0);
}
async function getDownloads() { try { return window.claude && window.claude.use ? await window.claude.use('downloads') : null; } catch (e) { return null; } }
async function saveFile(name, make) {
  const dl = await getDownloads();
  if (name.endsWith('.pdf') && !(window.jspdf && window.jspdf.jsPDF)) { toast('The PDF library did not load. Check the connection and reload the page.'); render(); return; }
  let data; try { data = make(); } catch (e) { toast('The file could not be built: ' + e.message); render(); return; }
  if (!dl) {
    if (window.claude) { toast('Downloads are not available in this view.'); render(); return; }
    // Standalone (outside Claude): plain browser download
    const blob = data instanceof Blob ? data : new Blob([data], {type: name.endsWith('.json') ? 'application/json' : 'application/octet-stream'});
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 5000); return;
  }
  try { await dl.save({filename: name, data}); } catch (e) { if (e && e.code !== 'declined') { toast('The download did not complete: ' + (e.message || e.code)); render(); } }
}
function act(a, ds) {
  const q = S.view.q ? getQ(S.view.q) : null;
  switch (a) {
    case 'nav': S.view = {name: ds.v}; S.modal = null; if (ds.v !== 'lookup') S.lookup = S.lookup; break;
    case 'role': S.role = ds.v; S.view = {name: 'log'}; S.modal = null; break;
    case 'reset': S.modal = {type:'confirm', title:'Reset the demo?', text:'This clears every quote and custom code created in this session and restores the starting data.', yes:'doReset', yesLabel:'Reset demo'}; break;
    case 'doReset': seed(); S.lookup = null; toast('Demo data reset.'); break;
    case 'openQuote': S.view = {name:'quote', q: ds.q}; S.modal = null; break;
    case 'newQuote': if (S.role === 'ae') S.modal = {type:'newQuote', acct:'KPE'}; else { const nq = newQuote(S.acct, 0); S.view = {name:'quote', q: nq.no}; } break;
    case 'createQuote': { const c = +document.getElementById('nq-contact').value; const nq = newQuote(S.modal.acct, c); S.modal = null; S.view = {name:'quote', q: nq.no}; break; }
    case 'closeModal': S.modal = null; break;
    case 'addLine': startDraft(q, null, ds.s); break;
    case 'addFromSpec': { const v = document.getElementById('q-spec').value; const res = resolveLookup(v);
      if (res.error) { toast(res.error); break; }
      startDraft(q, null, res.cfg.series, v.trim().toUpperCase()); S.draft.cfg = res.cfg; S.draft.ae = Object.assign({cf:{}}, res.customs); break; }
    case 'editLine': startDraft(q, getL(q, ds.l)); break;
    case 'dupLine': { const l = getL(q, ds.l); const cp = JSON.parse(JSON.stringify(l)); cp.id = nid(); q.lines.splice(q.lines.indexOf(l) + 1, 0, cp); log(q, `Copied line ${q.lines.indexOf(l) + 1}`); break; }
    case 'removeLine': { const l = getL(q, ds.l); const i = q.lines.indexOf(l); q.lines.splice(i, 1); log(q, `Removed line ${i + 1}`); break; }
    case 'specSheet': S.modal = {type:'spec', q: q.no, l: ds.l}; break;
    case 'set': { const prev = S.draft.cfg[ds.k]; setDraft(ds.k, ds.v);
      if (ds.k === 'motorOption' && prev === 'By Others' && ds.v !== 'By Others') {
        const c = S.draft.cfg, items = [];
        if (c.coupling !== 'Coupling Included') items.push(['coupling', 'Coupling Included', 'Coupling']);
        if (c.series === '1500' && c.couplingGuard === 'No Coupling Guard') items.push(['couplingGuard', 'Steel', 'Steel coupling guard']);
        if (c.series === '1500' && c.baseplate !== 'Baseplate Included') items.push(['baseplate', 'Baseplate Included', 'Baseplate']);
        if (items.length) S.modal = {type:'driveAdd', items};
      } break; }
    case 'driveAddYes': { const d = S.draft, before = lineCalc(draftLine()).enc.segs.map(x => x.code);
      const names = S.modal.items.map(i => i[2].toLowerCase());
      S.modal.items.forEach(([k, v]) => setDraft(k, v));
      const after = lineCalc(draftLine()).enc.segs.map(x => x.code); d.changed = after.map((x, i) => x !== before[i] ? i : -1).filter(i => i >= 0);
      d.msgs = []; S.modal = null; toast(`Added ${names.join(', ').replace(/, ([^,]*)$/, ' and $1')}.`); break; }
    case 'grp': S.draft.group = ds.v; S.draft.msgs = []; S.draft.changed = []; S.scrollOpts = true; break;
    case 'jump': S.draft.group = ds.g; S.focusKey = ds.k; S.draft.changed = []; break;
    case 'cancelCfg': S.view = {name:'quote', q: S.draft.q}; S.draft = null; break;
    case 'saveLine': {
      const d = S.draft, tq = getQ(d.q);
      const data = {qty: Math.max(1, +d.qty || 1), designation: d.designation, description: d.description, cfg: d.cfg, requests: d.requests, ae: d.ae};
      if (d.lineId) { Object.assign(getL(tq, d.lineId), data); log(tq, `Updated line ${tq.lines.findIndex(l => l.id === d.lineId) + 1}`); }
      else { tq.lines.push(Object.assign({id: nid()}, data)); log(tq, `Added line ${tq.lines.length}: ${d.cfg.series} ${d.cfg.size}${d.fromItem ? ` (from ${d.fromItem})` : ''}`); }
      const r = lineCalc(data);
      if (tq.status === 'Completed by applications' && r.pend.length) { tq.status = 'Draft'; }
      S.view = {name:'quote', q: tq.no}; S.draft = null;
      toast(r.pend.length ? 'Line saved. Send the quote to applications to price the custom items.' : `Line saved as ${r.item}.`); break; }
    case 'sendAE': { const t = quoteCalc(q); q.status = 'With applications';
      const needs = [...new Set(t.lines.flatMap(r => r.pend.map(pendLabel)))].join(', ').toLowerCase();
      log(q, `Sent to applications: ${needs}`); toast('Sent. The applications team has been notified.'); break; }
    case 'confirmQuote': q.status = 'Released'; log(q, 'Quote confirmed'); toast(`${q.no} confirmed. Download the PDF to send it on.`); break;
    case 'copyQuote': { const nq = newQuote(q.account, q.contact); nq.project = q.project; nq.ref = q.ref;
      nq.lines = q.lines.map(l => Object.assign(JSON.parse(JSON.stringify(l)), {id: nid()})); log(nq, `Copied from ${q.no}`); S.view = {name:'quote', q: nq.no}; break; }
    case 'previewQuote': S.modal = {type:'preview', q: q.no}; break;
    case 'pdfQuote': { const tq = S.modal && S.modal.q ? getQ(S.modal.q) : q; saveFile(`${tq.no} Fybroc quote.pdf`, () => buildPdf(tq)); return; }
    case 'pdfSpec': { const m = S.modal; const tq = m.q ? getQ(m.q) : null; const l = tq ? getL(tq, m.l) : m.line; saveFile(`${lineCalc(l).item || 'spec'} spec sheet.pdf`, () => buildPdf(tq, l)); return; }
    case 'completeNotify': { const tq = q; tq.status = 'Completed by applications'; log(tq, 'Completed by applications. Customer notified.'); S.modal = {type:'notify', q: tq.no}; break; }
    case 'viewAsCustomer': { const tq = getQ(ds.q); S.role = 'dist'; S.acct = tq.account; S.view = {name:'quote', q: tq.no}; S.modal = null; break; }
    case 'openWork': S.view = {name:'ae', q: ds.q, l: ds.l}; break;
    case 'useCode': { const l = getL(q, ds.l), e = libGet(ds.kind, ds.code); l.ae[ds.kind] = e.code; if (ds.kind !== 'special') Object.assign(l.cfg, e.fields); l.cfg = normalize(l.cfg).cfg;
      log(q, `Line ${q.lines.indexOf(l) + 1}: reused ${e.code} (${entryTitle(e)})`); toast(`${e.code} applied. Its price and description come from the library.`); break; }
    case 'changeCode': { const l = getL(q, ds.l); delete l.ae[ds.kind]; break; }
    case 'addRow': S.aeForm[ds.f].rows.push({d:'', cost:'', margin:40, ref:''}); break;
    case 'assignNew': { const l = getL(q, ds.l), fk = l.id + ':' + ds.kind, f = S.aeForm[fk];
      if (ds.kind === 'seal' && (!f.vendor.trim() || !f.series.trim())) { toast('Enter the seal vendor and the vendor part number or series.'); break; }
      if (!f.desc.trim()) { toast('Add a description first.'); break; }
      if (!f.rows.some(r => +r.cost > 0)) { toast('Enter at least one cost.'); break; }
      const code = nextCodeFor(ds.kind);
      const fields = ds.kind === 'special' ? {special: l.cfg.special} : Object.fromEntries(CUSTOM_FIELDS[ds.kind].map(k => [k, l.cfg[k]]));
      S.lib[ds.kind].push({code, vendor: ds.kind === 'seal' ? f.vendor.trim() : undefined, series: ds.kind === 'seal' ? f.series.trim() : undefined, desc: f.desc.trim(), date: todayISO(), quote: q.no, fields, rows: f.rows.filter(r => r.d || r.cost).map(r => ({...r, cost: +r.cost || 0, margin: +r.margin || 0}))});
      l.ae[ds.kind] = code; delete S.aeForm[fk];
      log(q, `Line ${q.lines.indexOf(l) + 1}: assigned ${code} (${entryTitle(S.lib[ds.kind][S.lib[ds.kind].length - 1])})`); toast(`${code} assigned. The spec number and item number are now final.`); break; }
    case 'cfSave': { const l = getL(q, ds.l); const p = document.getElementById(`cf-p-${l.id}-${ds.k}`).value, n = document.getElementById(`cf-n-${l.id}-${ds.k}`).value;
      if (p === '' || +p < 0) { toast('Enter a list price.'); break; }
      l.ae.cf[ds.k] = {price: +p, note: n}; log(q, `Line ${q.lines.indexOf(l) + 1}: priced ${FIELD[ds.k].label.toLowerCase()} at ${money(+p)}`); break; }
    case 'lookup': { const v = document.getElementById('lk-input').value; const res = resolveLookup(v); S.lookup = {input: v, res: res.error ? null : res, error: res.error}; break; }
    case 'lkExample': { const res = resolveLookup(ds.v); S.lookup = {input: ds.v, res: res.error ? null : res, error: res.error}; break; }
    case 'lkSpec': { const r = S.lookup.res; S.modal = {type:'spec', line:{qty:1, designation:'', description:'', cfg:r.cfg, ae:Object.assign({cf:{}}, r.customs), requests:{}}}; break; }
    case 'lkStart': { const t = document.getElementById('lk-target').value; const r = S.lookup.res; let tq;
      if (t === '__new') tq = newQuote(S.role === 'ae' ? 'KPE' : S.acct, 0); else tq = getQ(t);
      startDraft(tq, null, r.cfg.series, S.lookup.input.trim().toUpperCase()); S.draft.cfg = JSON.parse(JSON.stringify(r.cfg)); S.draft.ae = Object.assign({cf:{}}, r.customs); break; }
    case 'dlData': saveFile('fybroc-cpq-data-model.json', () => JSON.stringify({sizes:SIZES, sizeCodes:SIZE_CODE, materialCodes:MAT_CODE, seriesFlange:SERIES_FLANGE, trimRange:TRIM_RANGE, group3:GROUP3,
      fields: FIELDS.map(f => ({key:f.key, label:f.label, group:f.group, master:f.master, avail:f.avail, std:f.std, ui:f.ui, min:f.min, max:f.max})), pumpOptionOrder: PO,
      constraints: CONSTRAINTS, frames: FRAMES, basePrice: BASE, materialPct: MAT_PCT, adders: ADDERS, price: PRICE, leadWeeks: LEAD, customCodes: S.lib, itemRegistry: S.registry.byItem}, null, 2)); return;
  }
  render();
}
document.addEventListener('click', e => {
  const t = e.target.closest('[data-a]'); if (!t || t.disabled) return;
  if (t.dataset.a === 'closeModalBg') { if (e.target === t) { S.modal = null; render(); } return; }
  e.preventDefault(); act(t.dataset.a, t.dataset);
});
document.addEventListener('change', e => {
  const t = e.target, c = t.dataset.c; if (!c) return;
  const q = S.view.q ? getQ(S.view.q) : null;
  if (c === 'acct') { S.acct = t.value; S.view = {name:'log'}; }
  else if (c === 'nqAcct') S.modal.acct = t.value;
  else if (c === 'qField') { q[t.dataset.k] = t.dataset.k === 'contact' ? +t.value : t.value; q.updated = todayISO(); }
  else if (c === 'lineField') { const l = getL(q, t.dataset.l); l[t.dataset.k] = t.dataset.k === 'qty' ? Math.max(1, +t.value || 1) : t.value; }
  else if (c === 'setSel') setDraft(t.dataset.k, t.value);
  else if (c === 'setNum') setDraft(t.dataset.k, +t.value);
  else if (c === 'aeForm') {}
  else return;
  render();
});
document.addEventListener('input', e => {
  const t = e.target, i = t.dataset.i; if (!i) return;
  if (i === 'draftField') S.draft[t.dataset.k] = t.value;
  else if (i === 'req') { const had = !!(S.draft.requests[t.dataset.k] || '').trim(); S.draft.requests[t.dataset.k] = t.value; if (had !== !!t.value.trim()) rerenderKeepFocus(t); }
  else if (i === 'special') { S.draft.cfg.special = t.value; }
  else if (i === 'aeDesc') S.aeForm[t.dataset.f][t.dataset.k || 'desc'] = t.value;
  else if (i === 'aeSearch') { S.aeSearch[t.dataset.f] = t.value; rerenderKeepFocus(t); }
  else if (i === 'libSearch') { S.libSearch = t.value; rerenderKeepFocus(t); }
  else if (i === 'aeRow') { const f = S.aeForm[t.dataset.f], r = f.rows[+t.dataset.r]; r[t.dataset.k] = t.value;
    const cell = document.querySelector(`[data-rowlist="${t.dataset.f}:${t.dataset.r}"]`); if (cell) cell.textContent = money(rowList(r));
    const tot = document.querySelector(`[data-calc="${t.dataset.f}"]`); if (tot) tot.textContent = calcText(f.rows); }
});
document.addEventListener('focusout', e => { const t = e.target; if (t.dataset && t.dataset.i === 'special') { setDraft('special', t.value); render(); } });
function rerenderKeepFocus(t) { const id = t.id, pos = t.selectionStart; render(); const n = id && document.getElementById(id); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (e) {} } }

/* ---------- PDF ---------- */
function buildPdf(q, onlyLine) {
  const {jsPDF} = window.jspdf; const doc = new jsPDF({unit:'pt', format:'letter'});
  const W = doc.internal.pageSize.getWidth(), M = 40;
  const ink = [23, 33, 42], grey = [96, 108, 116], blue = [29, 92, 135];
  const head = (title, ids) => {
    doc.setFont('helvetica', 'bold'); doc.setFontSize(20); doc.setTextColor(...ink); doc.text('FYBROC', M, 52);
    doc.setFont('helvetica', 'normal'); doc.setFontSize(10); doc.setTextColor(...grey); doc.text(title, M, 68);
    let y = 44; ids.forEach(([k, v]) => { doc.setFontSize(8); doc.setTextColor(...grey); doc.text(k, W - M - 210, y); doc.setFontSize(9); doc.setTextColor(...ink); doc.setFont('courier', 'bold'); doc.text(String(v), W - M - 140, y); doc.setFont('helvetica', 'normal'); y += 13; });
    doc.setDrawColor(...blue); doc.setLineWidth(1.5); doc.line(M, 84, W - M, 84);
  };
  const specPage = (l, first) => {
    if (!first) doc.addPage();
    const r = lineCalc(l), customs = {}; r.kinds.forEach(k => { if (l.ae[k]) customs[k] = l.ae[k]; });
    const ids = [['Item', r.item || 'Pending'], ['Spec', r.spec]]; if (q) ids.push(['Quote', `${q.no} line ${q.lines.indexOf(l) + 1}`]); if (l.designation) ids.push(['Designation', l.designation]);
    head('Pump specification sheet', ids);
    doc.setFont('helvetica', 'bold'); doc.setFontSize(10); doc.setTextColor(...ink); doc.text(doc.splitTextToSize(shortDesc(l.cfg), W - 2 * M), M, 104);
    const c = l.cfg; let y = 120;
    groupsFor(c.series).filter(([g]) => g !== 'special').forEach(([g, gl]) => {
      const body = fieldsFor(c.series).filter(f => f.group === g && isVisible(f, c)).map(f => [f.label, f.custom && c[f.key] === f.custom ? `Custom, see note: ${KIND_LABEL[g === 'seal' ? 'seal' : 'motor']}` : String(c[f.key]) + (f.ui === 'number' ? ' in' : '')]);
      if (g === 'motor' && c.motorOption !== 'By Others') body.push(['Motor frame', frameFor(c) || '-']);
      if (g === 'pump') body.unshift(['Series', c.series]);
      doc.autoTable({startY: y, head: [[gl, '']], body, margin: {left: M, right: M}, theme: 'plain', styles: {fontSize: 8.5, cellPadding: 3, textColor: ink}, headStyles: {fontStyle: 'bold', textColor: blue, fontSize: 9.5}, columnStyles: {0: {cellWidth: 170, textColor: grey}}, didDrawCell: d => { if (d.section === 'body') { doc.setDrawColor(220, 224, 220); doc.setLineWidth(0.5); doc.line(d.cell.x, d.cell.y + d.cell.height, d.cell.x + d.cell.width, d.cell.y + d.cell.height); } }});
      y = doc.lastAutoTable.finalY + 8;
    });
    const notes = r.kinds.map(k => { const e = customs[k] && libGet(k, customs[k]); return [`${KIND_LABEL[k]}${e ? ' (' + e.code + ')' : ''}`, e ? entryTitle(e) : (k === 'special' ? c.special : 'Pending')]; });
    if (notes.length) { doc.autoTable({startY: y + 4, head: [['Custom item notes', '']], body: notes, margin: {left: M, right: M}, theme: 'plain', styles: {fontSize: 8.5, cellPadding: 3}, headStyles: {textColor: [168, 106, 12], fontSize: 9.5}, columnStyles: {0: {cellWidth: 170, fontStyle: 'bold'}}}); y = doc.lastAutoTable.finalY + 8; }
    const cn = configNotes(c);
    if (cn.length) doc.autoTable({startY: y + 4, head: [['Configuration notes']], body: cn.map(n => [n]), margin: {left: M, right: M}, theme: 'plain', styles: {fontSize: 8.5, cellPadding: 3}, headStyles: {textColor: blue, fontSize: 9.5}});
  };
  if (onlyLine) specPage(onlyLine, true);
  else {
    const a = ACC(q.account), t = quoteCalc(q), ct = a.contacts[q.contact], net = a.netOnly;
    const valid = new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10);
    head('Quotation', [['Quote', q.no], ['Date', fmtDate(q.updated)], ['Valid until', fmtDate(valid)]]);
    doc.setFontSize(8); doc.setTextColor(...grey); doc.text('Prepared for', M, 106); doc.text('Project', W / 2, 106); doc.text('Reference', W / 2, 140);
    doc.setFontSize(10); doc.setTextColor(...ink); doc.setFont('helvetica', 'bold'); doc.text(a.name, M, 119); doc.text(q.project || '-', W / 2, 119); doc.text(q.ref || '-', W / 2, 153);
    doc.setFont('helvetica', 'normal'); doc.text(ct.name, M, 132); doc.setTextColor(...grey); doc.text(ct.email, M, 145);
    const headRow = ['#', 'Qty', 'Designation', 'Item / spec number', 'Summary', 'Lead'].concat(net ? [] : ['List', 'Disc.']).concat(['Unit net', 'Ext. net']);
    const body = q.lines.map((l, i) => { const r = t.lines[i]; return [i + 1, l.qty, `${l.designation}\n${l.description}`, `${r.item}\n${r.spec}`, `${l.cfg.series}, ${l.cfg.size}, ${l.cfg.material}\n${lineBrief(l.cfg)}`, `${r.lead} wk`]
      .concat(net ? [] : [money(r.list), Math.round(a.disc * 100) + '%']).concat([money(r.unitNet), money(r.unitNet * l.qty)]); });
    const numCols = net ? [5, 6, 7] : [5, 6, 7, 8, 9];
    const cs = {0: {cellWidth: 18}, 1: {cellWidth: 26}, 3: {font: 'courier', fontSize: 7, cellWidth: 118}}; numCols.forEach(i => cs[i] = Object.assign(cs[i] || {}, {halign: 'right'}));
    doc.autoTable({startY: 170, head: [headRow], body, foot: [[{content: 'Total net', colSpan: headRow.length - 1, styles: {halign: 'right'}}, {content: money(t.net), styles: {halign: 'right'}}]],
      margin: {left: M, right: M}, theme: 'striped', styles: {fontSize: 7.5, cellPadding: 4, textColor: ink, valign: 'top'}, headStyles: {fillColor: ink, textColor: 255, fontSize: 7.5}, footStyles: {fillColor: [236, 238, 234], textColor: ink, fontStyle: 'bold'}, columnStyles: cs});
    let y = doc.lastAutoTable.finalY + 22;
    doc.setFontSize(8); doc.setTextColor(...grey);
    ['Prices are valid for 30 days and do not include freight.', 'Lead time is in weeks after receipt of an approved order.', 'Sale is subject to Fybroc standard terms and conditions. One specification sheet per line follows.'].forEach(s => { doc.text(s, M, y); y += 12; });
    q.lines.forEach(l => specPage(l, false));
  }
  const n = doc.getNumberOfPages();
  for (let i = 1; i <= n; i++) { doc.setPage(i); doc.setFontSize(7.5); doc.setTextColor(...grey); doc.text(`Page ${i} of ${n}`, W - M, doc.internal.pageSize.getHeight() - 24, {align: 'right'}); doc.text('Demo document. Prices are illustrative.', M, doc.internal.pageSize.getHeight() - 24); }
  return doc.output('blob');
}

seed(); render();
