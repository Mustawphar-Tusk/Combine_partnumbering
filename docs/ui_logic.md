/* Fybroc CPQ demo: data, constraints, spec number encode/decode, pricing. No DOM access. */
/* ===================== FYBROC CPQ DEMO: DATA + LOGIC (no DOM) ===================== */
const B36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
function b36(n, w) { let s = ''; do { s = B36[n % 36] + s; n = Math.floor(n / 36); } while (n > 0); return s.padStart(w, '0'); }
function unb36(s) { let n = 0; for (const ch of s) { const i = B36.indexOf(ch); if (i < 0) return NaN; n = n * 36 + i; } return n; }
function mixEnc(idx, rad) { let n = 0; for (let i = 0; i < idx.length; i++) n = n * rad[i] + idx[i]; return n; }
function mixDec(n, rad) { const out = []; for (let i = rad.length - 1; i >= 0; i--) { out[i] = n % rad[i]; n = Math.floor(n / rad[i]); } return n === 0 ? out : null; }

/* ---------- Reference data (from Nomenclature_V6 + Dependance Tree) ---------- */
const SIZES = ['1x1.5x6','1.5x3x6','2x3x6','1x1.5x8','1.5x3x8','2x3x8','3x4x8','1x2x10','1.5x3x10','2x3x10','3x4x10','4x4x10','4x6x10','2x3x13','3x4x13','4x6x13','6x8x13','8x10x15','10x12x16'];
const SIZE_CODE = {'1x1.5x6':'1','1x1.5x8':'2','1x2x10':'3','1.5x3x10':'4','1.5x3x6':'5','1.5x3x8':'6','2x3x6':'7','2x3x8':'8','2x3x10':'9','2x3x13':'A','3x4x8':'C','3x4x10':'D','3x4x13':'E','4x4x10':'F','4x6x10':'G','4x6x13':'I','6x8x13':'J','8x10x15':'M','10x12x16':'O'};
const TRIM_RANGE = {'1x1.5x6':[4,6.25],'1.5x3x6':[4,6.25],'2x3x6':[4,6],'1x1.5x8':[5.5,7.5],'1.5x3x8':[5.5,8.375],'2x3x8':[5.5,8.375],'3x4x8':[5.5,8],'1x2x10':[6,10],'1.5x3x10':[6,9.75],'2x3x10':[6,10],'3x4x10':[6,10],'4x4x10':[6,9.5],'4x6x10':[8,10.75],'2x3x13':[9,13],'3x4x13':[9,13],'4x6x13':[9,13],'6x8x13':[10,13.5],'8x10x15':[12,15],'10x12x16':[11,16]};
const GROUP3 = ['6x8x13','8x10x15','10x12x16']; // ASSUMPTION: Group 3 = largest frames
function sizeGroup(s) { if (GROUP3.includes(s)) return 3; return +String(s).split('x')[2] <= 8 ? 1 : 2; }
const MAT_CODE = {'VR-1':'1','VR-1 BPO/DMA':'7','VR-1A':'5','VR-1A BPO/DMA':'V','VR-1V':'3','EY-2':'2'};
const SERIES_FLANGE = {'1500':{'ANSI Flange':'A','DIN/ISO Flange':'I','JIS Flange':'M'}, '5500':{'ANSI Flange':'G','DIN/ISO Flange':'U','JIS Flange':'W'}}; // 5500 DIN/JIS = placeholder letters
const TRIMS = []; for (let x = 4; x <= 16.0001; x += 0.125) TRIMS.push(x.toFixed(3));
function trimCode(t) { const v = +t, inch = Math.floor(v + 1e-9), fr = Math.round((v - inch) / 0.125); return 'ABCDEFGHIJKLM'[inch - 4] + 'ABCDEFGH'[fr]; }
function trimDecode(code) { const i = 'ABCDEFGHIJKLM'.indexOf(code[0]), f = 'ABCDEFGH'.indexOf(code[1]); if (i < 0 || f < 0 || code.length !== 2) return null; return (i + 4 + f * 0.125).toFixed(3); }
const SETTINGS = Array.from({length:19}, (_, i) => String(i + 1));
function settingLength(n) { return 24 + 6 * (n - 1); } // PLACEHOLDER L-dimension per setting
const HP_LIST = ['1','1.5','2','3','5','7.5','10','15','20','25','30','40','50','60','75','100','125','150','200'];
const FRAMES = {'1|3600':[143,'T'],'1.5|3600':[143,'T'],'1|1800':[143,'T'],'2|3600':[145,'T'],'1.5|1800':[145,'T'],'2|1800':[145,'T'],'3|3600':[182,'T'],'3|1800':[182,'T'],'5|3600':[184,'T'],'5|1800':[184,'T'],'7.5|3600':[213,'T'],'7.5|1800':[213,'T'],'10|3600':[215,'T'],'10|1800':[215,'T'],'15|3600':[254,'T'],'15|1800':[254,'T'],'20|3600':[256,'T'],'20|1800':[256,'T'],'25|3600':[284,'TS'],'25|1800':[284,'T'],'30|3600':[286,'TS'],'30|1800':[286,'T'],'40|3600':[324,'TS'],'40|1800':[324,'T'],'50|3600':[326,'TS'],'50|1800':[326,'T'],'60|3600':[364,'TS'],'60|1800':[364,'T'],'75|3600':[365,'TS'],'75|1800':[365,'T'],'100|3600':[405,'TS'],'1|1200':[145,'T'],'1.5|1200':[182,'T'],'2|1200':[184,'T'],'3|1200':[213,'T'],'5|1200':[215,'T'],'7.5|1200':[254,'T'],'10|1200':[256,'T'],'15|1200':[284,'T'],'20|1200':[286,'T'],'25|1200':[324,'T'],'30|1200':[326,'T'],'40|1200':[364,'T'],'50|1200':[365,'T'],'60|1200':[404,'T'],'100|1800':[405,'T'],'75|1200':[405,'T'],'125|1800':[444,'T'],'100|1200':[444,'T'],'125|1200':[445,'T'],'150|1800':[445,'T'],'200|1800':[447,'T']};
function frameFor(c) {
  if (!c.hp || !c.rpm) return null;
  let f = null;
  if (c.rpm === '900') { const i = HP_LIST.indexOf(c.hp); const nx = HP_LIST[i + 1]; f = nx ? FRAMES[nx + '|1200'] : null; }
  else f = FRAMES[c.hp + '|' + c.rpm];
  if (!f) return null;
  const sfx = c.series === '5500' ? (f[1] === 'TS' ? 'TSC' : 'TC') : f[1];
  return f[0] + sfx;
}
// PLACEHOLDER curve rule: max motor HP by impeller diameter and speed
function maxHp(size, rpm) {
  const d = +String(size).split('x')[2];
  const t = d <= 6 ? {3600:15,1800:3,1200:1.5,900:1} : d <= 8 ? {3600:40,1800:7.5,1200:3,900:2} : d <= 11 ? {3600:75,1800:15,1200:7.5,900:5} : d <= 13 ? {3600:0,1800:60,1200:25,900:15} : {3600:0,1800:200,1200:75,900:40};
  return t[rpm] || 0;
}

const SEAL_TYPES = ['8B2 Single Outside','RAC Single Outside','8-1T Double Inside','RXO Double Inside','CRO Double Inside'];
const SEAL_MATS = ['Carbon vs Ceramic','Silcar vs Silcar'];
const ELAST = ['FKM','EPR','PTFE'];
const SEAL_MFG_LETTER = {'Standard Offering':'S','John Crane':'J','Flowserve':'W','Flex-a-seal':'F'}; // W = placeholder for Flowserve
const SEAL_BY_MFG = { // ASSUMPTION for ConstraintTable25
  'Standard Offering': SEAL_TYPES,
  'John Crane': ['8B2 Single Outside','8-1T Double Inside'],
  'Flowserve': ['RAC Single Outside','RXO Double Inside','CRO Double Inside'],
  'Flex-a-seal': ['RAC Single Outside','8-1T Double Inside','RXO Double Inside'],
  'Custom Seal Mfg': []
};

/* ---------- Constraint catalogue (IDs match the Dependance Tree workbook) ---------- */
const CONSTRAINTS = {
  CT1:  ['Alt Size × Coupling Guard', 'Group 3 coupling guards in aluminum (non-sparking) are not allowed.'],
  CT2:  ['Alt Size × Flange Type', 'A 2x3x13 1500 or 1530 cannot be made in ISO or JIS.'],
  CT3:  ['Alt Size × Flush', '5500 only: Group 3 internal flush not allowed.'],
  CT4:  ['Alt Size × Impeller Trim', 'Impeller trim must be inside the size\u2019s trim range.'],
  CT5:  ['Alt Size × Pump Material', 'Some materials cannot be made in some sizes. Demo rule: VR-1V and EY-2 are not offered in Group 3 sizes.'],
  CT6:  ['Alt Size × Shaft Material', '5500 only: Group 3 pumps with a wrapped shaft not allowed.'],
  CT7:  ['Casing Drains × Pump Material', 'VR-1V casings cannot have casing drains.'],
  CT8:  ['Cyclone Separator × Flush', 'A cyclone separator requires a cyclone-separator bypass flush.'],
  CT9:  ['Flush × Pump Material', 'VR-1V casings cannot have taps for bypass flush options.'],
  CT10: ['Motor Option × Paint Upgrade', 'No paint upgrade when the motor is supplied by others.'],
  CT11: ['Motor Option × Shaft Grounding', 'No shaft grounding ring when the motor is supplied by others.'],
  CT12: ['Pump Material × Setting', '5500 EY-2: no intermediate bearing material, so settings 1\u20134 only.'],
  CT13: ['Pump Material × Shaft Material', '5500 only: EY-2 with wrapped shafts not allowed.'],
  CT14: ['Pump Material × Sleeve', 'No separate FRP sleeve in EY-2 or VR-1V.'],
  CT15: ['Pump Material × Suction Discharge Taps', 'VR-1V casings cannot have suction/discharge taps.'],
  CT16: ['Seal Guard × Seal Option', 'No seal gland means no seal guard.'],
  CT17: ['Seal Option × Seal Type', 'Gland must match the seal. Built into the seal assembly code.'],
  CT18: ['Setting × Shaft Material', 'Wrapped shafts only come in settings 1\u20134.'],
  CT19: ['Shaft Material × Sleeve', 'Metal sleeve must match the shaft material; wrapped shafts take only Hast-C or titanium sleeves.'],
  CT20: ['Motor Control × Shaft Grounding', 'VFDs must get a shaft grounding ring.'],
  CT21: ['Pump Material × Length', '5500 EY-2: lengths only up to the setting 4 length.'],
  CT22: ['Setting/Length × Length', 'Length is entered only when Custom Length is selected.'],
  CT23: ['Setting/Length × Setting', 'Setting is selected only when Standard Setting is selected.'],
  CT24: ['Tailpipe Option × Tailpipe Length', 'Tailpipe length is entered only when a tailpipe is supplied.'],
  CT25: ['Seal Mfg × Seal Type', 'Seal type must match the seal manufacturer.'],
  CT26: ['Seal Option × Seal Mfg', 'Seal manufacturer depends on Supplied or Installed by Fybroc.'],
  CT27: ['Wetted Hardware × Selection', 'Wetted hardware material is chosen only when Select Material is chosen.'],
  CT28: ['Flush Material × Flush', 'No flush material for internal or external flush.'],
  CT29: ['Alt Size × C-Face Adapter', 'No C-face adapter on Group 3 pumps.'],
  M1:   ['Size × Motor HP × RPM', 'Placeholder curve rule: maximum HP by impeller diameter and speed.'],
  M2:   ['Motor HP × RPM × Frame', 'Motor frame comes from the nomenclature motor table; no frame means not offered.']
};
const R = id => `${CONSTRAINTS[id][1]} (${id.replace('CT', 'ConstraintTable')})`;

/* ---------- Field catalogue ---------- */
function F(key, label, group, master, avail, std, x) { return Object.assign({key, label, group, master, avail, std: std || {}, ui: 'radio'}, x || {}); }
const MOTOR_OPT = ['By Others','Supplied by Fybroc','Installed by Fybroc'];
const HW_SEP = 'Select each part separately';
const withMotor = c => c.motorOption && c.motorOption !== 'By Others';
const FIELDS = [
  F('size','Size','pump',SIZES,{1500:'all',5500:'all'},{1500:'2x3x10',5500:'2x3x10'},{ui:'select'}),
  F('flange','Flange type','pump',['ANSI Flange','DIN/ISO Flange','JIS Flange'],{1500:'all',5500:'all'},{1500:'ANSI Flange',5500:'ANSI Flange'}),
  F('material','Pump material','pump',['VR-1','VR-1 BPO/DMA','VR-1A','VR-1A BPO/DMA','VR-1V','EY-2'],{1500:'all',5500:['VR-1','VR-1 BPO/DMA','VR-1A','VR-1A BPO/DMA','EY-2']},{1500:'VR-1',5500:'VR-1'}),
  F('trim','Impeller trim','pump',TRIMS,{1500:'all',5500:'all'},{},{ui:'select',hideBlocked:true,stdFn:c=>TRIM_RANGE[c.size][1].toFixed(3)}),
  F('settingMode','Setting or length','setting',['Standard Setting','Custom Length'],{5500:'all'},{5500:'Standard Setting'}),
  F('setting','Setting','setting',SETTINGS,{5500:'all'},{5500:'1'},{ui:'select',vis:c=>c.settingMode==='Standard Setting'}),
  F('length','Custom length (in)','setting',null,{5500:'all'},{5500:24},{ui:'number',min:18,max:200,maxFn:c=>(c.material==='EY-2'||isWrapped(c.shaft))?settingLength(4):200,vis:c=>c.settingMode==='Custom Length'}),
  F('tailpipe','Tailpipe','setting',['Not Supplied by Fybroc','Supplied by Fybroc'],{5500:'all'},{5500:'Not Supplied by Fybroc'}),
  F('tailpipeLen','Tailpipe length (in)','setting',null,{5500:'all'},{5500:12},{ui:'number',min:6,max:120,vis:c=>c.tailpipe==='Supplied by Fybroc'}),
  F('casingDrains','Casing drains','options',['Not Supplied by Fybroc','Supplied by Fybroc'],{1500:'all'},{1500:'Not Supplied by Fybroc'}),
  F('sdTaps','Suction/discharge taps','options',['No Suction Discharge Taps','Suction Discharge Taps'],{1500:'all'},{1500:'No Suction Discharge Taps'}),
  F('shaft','Shaft material','options',['303 SS','316 SS','Carp-20','Hastelloy C','Titanium','FRP Wrapped Shaft (303SS Core)','FRP Wrapped Shaft (316SS Core)'],{1500:['303 SS','316 SS'],5500:['316 SS','Carp-20','Hastelloy C','Titanium','FRP Wrapped Shaft (303SS Core)','FRP Wrapped Shaft (316SS Core)']},{1500:'303 SS',5500:'316 SS'}),
  F('sleeve','Shaft sleeve','options',['Integral','Separate FRP','316SS','Carp-20','Titanium','Hast-C','No Sleeve'],{1500:['Integral','Separate FRP','316SS','Carp-20','Titanium','Hast-C'],5500:['316SS','Carp-20','Titanium','Hast-C','No Sleeve']},{1500:'Integral',5500:'No Sleeve'}),
  F('wetted','Wetted hardware','options',['Match Shaft Material','Select Material'],{5500:'all'},{5500:'Match Shaft Material'}),
  F('wettedSel','Wetted hardware material','options',['303 SS','316 SS','Carp-20','Hastelloy C','Titanium'],{5500:'all'},{5500:'316 SS'},{vis:c=>c.wetted==='Select Material'}),
  F('pumpElast','Pump elastomers','options',ELAST,{1500:'all',5500:'all'},{1500:'FKM',5500:'FKM'}),
  F('bearing','Bearing option','options',['Oil Bath Lubrication','Re-Greaseable Bearings','Greased for Life Bearings'],{1500:'all'},{1500:'Oil Bath Lubrication'}),
  F('flush','Flush','options',['External Flush','Internal Flush','Bypass(Tapped Discharge)','Bypass(Tapped Spacer)','Bypass(Cyclone Separator)','Bypass(Cyclone Separator/Spacer)'],{1500:'all',5500:['External Flush','Internal Flush','Bypass(Tapped Discharge)','Bypass(Cyclone Separator)']},{1500:'External Flush',5500:'External Flush'}),
  F('flushMat','Flush material','options',['Not Applicable','Polypro','PTFE/PVDF'],{1500:['Polypro','PTFE/PVDF'],5500:['Polypro','PTFE/PVDF']},{1500:'Polypro',5500:'Polypro'},{vis:c=>String(c.flush).startsWith('Bypass'),hidden:'Not Applicable'}),
  F('cyclone','Cyclone separator','options',['Not Included','By Fybroc'],{1500:'all'},{1500:'Not Included'}),
  F('impBal','Impeller balance','options',['Not Supplied by Fybroc','Dynamic Balancing'],{1500:'all',5500:'all'},{1500:'Not Supplied by Fybroc',5500:'Not Supplied by Fybroc'}),
  F('hardware','Hardware','options',['303 SS','316 SS',HW_SEP],{1500:'all'},{1500:'303 SS'}),
  F('casingHw','Casing hardware','options',['303 SS','316 SS'],{1500:'all'},{1500:'303 SS'},{vis:c=>c.hardware===HW_SEP,hiddenFn:c=>c.hardware}),
  F('frameHw','Power frame hardware','options',['303 SS','316 SS'],{1500:'all'},{1500:'303 SS'},{vis:c=>c.hardware===HW_SEP,hiddenFn:c=>c.hardware}),
  F('glandHw','Gland hardware','options',['303 SS','316 SS','Carp-20','Titanium','Hastelloy C'],{1500:'all'},{1500:'303 SS'},{vis:c=>c.hardware===HW_SEP,hiddenFn:c=>c.hardware}),
  F('bpHw','Baseplate hardware','options',['303 SS','316 SS'],{1500:'all'},{1500:'303 SS'},{vis:c=>c.hardware===HW_SEP&&c.baseplate==='Baseplate Included',hiddenFn:c=>c.baseplate==='Baseplate Included'?c.hardware:'-'}),
  F('vapor','Vapor protection','options',['Vapor Shield','Vapor Seal'],{5500:'all'},{5500:'Vapor Shield'}),
  F('strainer','Strainer','options',['Not Included','Standard Strainer','Flat Screen Strainer'],{5500:'all'},{5500:'Not Included'}),
  F('sealOption','Seal option','seal',['Supplied by Fybroc','Installed by Fybroc','NoSeal Single Seal Gland','NoSeal Double Seal Gland','NoSeal NoSealGland'],{1500:'all'},{1500:'Supplied by Fybroc'}),
  F('sealMfg','Seal manufacturer','seal',['Standard Offering','John Crane','Flowserve','Flex-a-seal','Custom Seal Mfg'],{1500:'all'},{1500:'Standard Offering'},{vis:c=>['Supplied by Fybroc','Installed by Fybroc'].includes(c.sealOption),custom:'Custom Seal Mfg'}),
  F('sealType','Seal type','seal',[...SEAL_TYPES,'Custom Seal Type'],{1500:'all'},{1500:'8-1T Double Inside'},{vis:c=>c.sealOption==='Supplied by Fybroc',custom:'Custom Seal Type'}),
  F('sealMat','Seal faces','seal',SEAL_MATS,{1500:'all'},{1500:'Carbon vs Ceramic'},{vis:c=>c.sealOption==='Supplied by Fybroc'}),
  F('sealElast','Seal elastomers','seal',ELAST,{1500:'all'},{1500:'FKM'},{vis:c=>c.sealOption==='Supplied by Fybroc'}),
  F('sealGuard','Seal guard','seal',['Not Supplied by Fybroc','Supplied by Fybroc'],{1500:'all'},{1500:'Not Supplied by Fybroc'}),
  F('coupling','Coupling','drive',['No Coupling','Coupling Included'],{1500:'all',5500:'all'},{},{stdFn:c=>withMotor(c)?'Coupling Included':'No Coupling'}),
  F('couplingGuard','Coupling guard','drive',['No Coupling Guard','Steel','316 SS','Non Sparking'],{1500:'all'},{},{stdFn:c=>withMotor(c)?'Steel':'No Coupling Guard'}),
  F('baseplate','Baseplate','drive',['No Baseplate','Baseplate Included'],{1500:'all'},{},{stdFn:c=>withMotor(c)?'Baseplate Included':'No Baseplate'}),
  F('mountPlate','Mounting plate','drive',['Standard Offering','Custom Mounting Plate'],{5500:'all'},{5500:'Standard Offering'}),
  F('cface','C-face adapter','drive',['Not Included','Supplied by Fybroc'],{1500:'all'},{1500:'Not Included'}),
  F('custNameplate','Customer nameplate','drive',['Not Included','Customer'],{1500:'all',5500:'all'},{1500:'Not Included',5500:'Not Included'}),
  F('motorOption','Motor','motor',MOTOR_OPT,{1500:'all',5500:'all'},{1500:'By Others',5500:'By Others'}),
  F('motorControl','Motor control','motor',['Single Speed','VFD'],{1500:'all',5500:'all'},{1500:'Single Speed',5500:'Single Speed'},{vis:c=>c.motorOption!=='By Others'}),
  F('rpm','Motor RPM','motor',['3600','1800','1200','900'],{1500:'all',5500:'all'},{},{vis:c=>c.motorOption!=='By Others',hideBlocked:true,stdFn:c=>maxHp(c.size,'3600')>0?'3600':'1800'}),
  F('hp','Motor horsepower','motor',HP_LIST,{1500:HP_LIST.slice(0,18),5500:'all'},{1500:'5',5500:'5'},{vis:c=>c.motorOption!=='By Others',hideBlocked:true}),
  F('voltage','Motor voltage','motor',['230/460','230','460','Custom'],{1500:'all',5500:'all'},{1500:'230/460',5500:'230/460'},{vis:c=>c.motorOption==='Supplied by Fybroc',custom:'Custom'}),
  F('hz','Motor hertz','motor',['3ph - 60 hz','3ph - 50 hz'],{1500:'all',5500:'all'},{1500:'3ph - 60 hz',5500:'3ph - 60 hz'},{vis:c=>c.motorOption==='Supplied by Fybroc'}),
  F('enclosure','Motor enclosure','motor',['TEFC','TEFC SD','IEEE 841','Custom'],{1500:'all',5500:'all'},{1500:'TEFC',5500:'TEFC'},{vis:c=>c.motorOption==='Supplied by Fybroc',custom:'Custom'}),
  F('motorMfg','Motor manufacturer','motor',['Standard Offering','Baldor','TECO','Toshiba'],{1500:'all',5500:'all'},{1500:'Standard Offering',5500:'Standard Offering'},{vis:c=>c.motorOption==='Supplied by Fybroc'}),
  F('shaftGround','Shaft grounding ring','motor',['Not Included','Supplied by Fybroc'],{1500:'all',5500:'all'},{1500:'Not Included',5500:'Not Included'}),
  F('paint','Motor paint upgrade','motor',['Not Included','Supplied by Fybroc'],{1500:'all',5500:'all'},{1500:'Not Included',5500:'Not Included'}),
  F('perf','Performance testing','testing',['Not Included','Non-Wit Perf Test','Wit Perf Test','Non-Wit Perf Test NPSHR','Wit Perf Test NPSHR'],{1500:'all',5500:['Not Included','Non-Wit Perf Test','Wit Perf Test']},{1500:'Not Included',5500:'Not Included'}),
  F('hydro','Hydrotest certificate','testing',['Not Included','Non-Wit Hydro Test Certificate','Wit Hydro Test Certificate'],{1500:'all',5500:'all'},{1500:'Not Included',5500:'Not Included'}),
  F('vib','Vibration testing','testing',['Not Included','Non-Wit Vibration Testing','Wit Vibration Testing'],{1500:'all',5500:'all'},{1500:'Not Included',5500:'Not Included'}),
  F('sound','Sound level testing','testing',['Not Included','Non-Wit Sound Level Testing','Wit Sound Level Testing'],{1500:'all',5500:'all'},{1500:'Not Included',5500:'Not Included'})
];
const FIELD = Object.fromEntries(FIELDS.map(f => [f.key, f]));
const GROUPS = [['pump','Pump'],['setting','Setting and length'],['options','Pump options'],['seal','Mechanical seal'],['drive','Drive and base'],['motor','Motor'],['testing','Testing'],['special','Special requirements']];
function isWrapped(v) { return String(v || '').startsWith('FRP Wrapped'); }
function fieldsFor(series) { return FIELDS.filter(f => f.avail[series]); }
function groupsFor(series) { return GROUPS.filter(([g]) => g === 'special' || fieldsFor(series).some(f => f.group === g)); }
function availList(f, series) { const a = f.avail[series]; return a === 'all' ? f.master : a; }
function isVisible(f, c) { return !!f.avail[c.series] && (!f.vis || f.vis(c)); }
function stdOf(f, c) { return f.stdFn ? f.stdFn(c) : f.std[c.series]; }

function blockedReason(key, v, c) {
  const s = c.series, g = sizeGroup(c.size), mat = c.material;
  switch (key) {
    case 'flange': if (s === '1500' && c.size === '2x3x13' && v !== 'ANSI Flange') return R('CT2'); break;
    case 'material': if (g === 3 && (v === 'VR-1V' || v === 'EY-2')) return R('CT5'); break;
    case 'trim': { const r = TRIM_RANGE[c.size]; if (+v < r[0] - 1e-9 || +v > r[1] + 1e-9) return R('CT4'); break; }
    case 'setting': if (+v > 4 && mat === 'EY-2') return R('CT12'); if (+v > 4 && isWrapped(c.shaft)) return R('CT18'); break;
    case 'casingDrains': if (mat === 'VR-1V' && v === 'Supplied by Fybroc') return R('CT7'); break;
    case 'sdTaps': if (mat === 'VR-1V' && v !== 'No Suction Discharge Taps') return R('CT15'); break;
    case 'shaft': if (isWrapped(v) && s === '5500') { if (g === 3) return R('CT6'); if (mat === 'EY-2') return R('CT13'); if (c.settingMode === 'Standard Setting' && +c.setting > 4) return R('CT18'); if (c.settingMode === 'Custom Length' && +c.length > settingLength(4)) return R('CT18'); } break;
    case 'sleeve': {
      if (v === 'Separate FRP' && (mat === 'EY-2' || mat === 'VR-1V')) return R('CT14');
      const metal = {'316SS':'316 SS','Carp-20':'Carp-20','Titanium':'Titanium','Hast-C':'Hastelloy C'};
      if (isWrapped(c.shaft)) { if (!['Titanium','Hast-C'].includes(v)) return R('CT19'); }
      else if (metal[v] && metal[v] !== c.shaft) return R('CT19');
      break; }
    case 'flush': if (mat === 'VR-1V' && v.startsWith('Bypass')) return R('CT9'); if (s === '5500' && g === 3 && v === 'Internal Flush') return R('CT3'); break;
    case 'cyclone': if (v === 'By Fybroc' && !String(c.flush).includes('Cyclone')) return R('CT8'); break;
    case 'sealMfg': if (c.sealOption === 'Installed by Fybroc' && v === 'Custom Seal Mfg') return 'A customer-supplied seal is installed as received, so no custom selection is needed. (ConstraintTable26)'; break;
    case 'sealType': if (c.sealMfg === 'Custom Seal Mfg') { if (v !== 'Custom Seal Type') return R('CT25'); } else if (v !== 'Custom Seal Type' && !(SEAL_BY_MFG[c.sealMfg] || SEAL_TYPES).includes(v)) return R('CT25'); break;
    case 'sealGuard': if (c.sealOption === 'NoSeal NoSealGland' && v === 'Supplied by Fybroc') return R('CT16'); break;
    case 'couplingGuard': if (g === 3 && v === 'Non Sparking') return R('CT1'); break;
    case 'cface': if (g === 3 && v !== 'Not Included') return R('CT29'); break;
    case 'rpm': if (maxHp(c.size, v) <= 0) return `Not offered at ${v} RPM for this size. ${CONSTRAINTS.M1[1]}`; break;
    case 'hp': if (+v > maxHp(c.size, c.rpm)) return `Above ${maxHp(c.size, c.rpm)} HP for this size at ${c.rpm} RPM. ${CONSTRAINTS.M1[1]}`;
      if (!frameFor({...c, hp: v})) return CONSTRAINTS.M2[1]; break;
    case 'shaftGround': if (c.motorOption === 'By Others' && v !== 'Not Included') return R('CT11'); if (c.motorOption !== 'By Others' && c.motorControl === 'VFD' && v === 'Not Included') return R('CT20'); break;
    case 'paint': if (c.motorOption === 'By Others' && v !== 'Not Included') return R('CT10'); break;
  }
  return null;
}
function optionsFor(f, c) { return availList(f, c.series).map(v => ({v, blocked: blockedReason(f.key, v, c)})); }

/* Normalize: settle hidden fields, auto-correct values that a change made invalid, and report it */
function normalize(cfg, changedKey) {
  const c = {...cfg}; const msgs = [];
  for (let pass = 0; pass < 3; pass++) {
    for (const f of fieldsFor(c.series)) {
      if (!isVisible(f, c)) { c[f.key] = f.hiddenFn ? f.hiddenFn(c) : f.hidden !== undefined ? f.hidden : null; continue; }
      if (f.ui === 'number') {
        const mx = f.maxFn ? f.maxFn(c) : f.max; let v = Math.round(+c[f.key]);
        if (!isFinite(v)) v = stdOf(f, c);
        const nv = Math.min(mx, Math.max(f.min, v));
        if (nv !== +c[f.key] && c[f.key] != null && pass === 0 && f.key !== changedKey) msgs.push(`${f.label} limited to ${nv} in: ${R('CT21')}`);
        c[f.key] = nv; continue;
      }
      const opts = optionsFor(f, c), cur = opts.find(o => o.v === c[f.key]);
      if (cur && !cur.blocked) continue;
      const sd = stdOf(f, c), sdOpt = opts.find(o => o.v === sd && !o.blocked);
      const pick = sdOpt || opts.find(o => !o.blocked);
      const old = c[f.key];
      c[f.key] = pick ? pick.v : null;
      if (old != null && cur && cur.blocked && pick) msgs.push(`${f.label} changed from \u201c${old}\u201d to \u201c${pick.v}\u201d. ${cur.blocked}`);
    }
  }
  if (c.special == null) c.special = '';
  return {cfg: c, msgs: [...new Set(msgs)]};
}
function defaultCfg(series, over) {
  const base = {series, special: ''};
  for (const f of fieldsFor(series)) base[f.key] = null;
  Object.assign(base, over || {});
  // first pass fills standards
  let c = {...base};
  for (const f of fieldsFor(series)) if (c[f.key] == null) c[f.key] = f.ui === 'number' ? stdOf(f, c) : stdOf(f, c);
  return normalize(c).cfg;
}

/* ---------- Custom / consult-factory detection ---------- */
const CF_KEYS = {mountPlate:'Custom Mounting Plate', perf:['Wit Perf Test','Wit Perf Test NPSHR'], hydro:'Wit Hydro Test Certificate', vib:'Wit Vibration Testing', sound:'Wit Sound Level Testing'};
function customKinds(c) {
  const k = [];
  if (c.series === '1500' && c.sealOption === 'Supplied by Fybroc' && (c.sealMfg === 'Custom Seal Mfg' || c.sealType === 'Custom Seal Type')) k.push('seal');
  if (c.motorOption === 'Supplied by Fybroc' && (c.enclosure === 'Custom' || c.voltage === 'Custom')) k.push('motor');
  if ((c.special || '').trim()) k.push('special');
  return k;
}
function cfItems(c) {
  const out = [];
  for (const [key, val] of Object.entries(CF_KEYS)) { const vs = [].concat(val); if (vs.includes(c[key])) out.push(key); }
  return out;
}
const KIND_LABEL = {seal:'Mechanical seal', motor:'Motor', special:'Special requirement'};
const CUSTOM_FIELDS = {seal:['sealOption','sealMfg','sealType','sealMat','sealElast','sealGuard'], motor:['motorOption','motorControl','rpm','hp','voltage','hz','enclosure','motorMfg']};

/* ---------- Spec number encode / decode ---------- */
const FLUSH_BYPASS = ['Bypass(Tapped Discharge)','Bypass(Tapped Spacer)','Bypass(Cyclone Separator)','Bypass(Cyclone Separator/Spacer)'];
function flushCombo(c) { const i = FIELD.flush.master.indexOf(c.flush); if (i < 2) return i; return 2 + (i - 2) * 2 + ['Polypro','PTFE/PVDF'].indexOf(c.flushMat); }
function unFlushCombo(n) { if (n < 2) return {flush: FIELD.flush.master[n], flushMat: 'Not Applicable'}; const b = Math.floor((n - 2) / 2); return {flush: FLUSH_BYPASS[b], flushMat: ['Polypro','PTFE/PVDF'][(n - 2) % 2]}; }
const PO = {
  '1500': ['casingDrains','sdTaps','shaft','sleeve','casingHw','pumpElast','bearing','frameHw','glandHw','#flush','cyclone','impBal'],
  '5500': ['shaft','sleeve','#wetted','pumpElast','#flush','impBal','vapor','strainer']
};
function poRadix(series) { return PO[series].map(k => k === '#flush' ? 10 : k === '#wetted' ? 6 : FIELD[k].master.length); }
function poIdx(c) { return PO[c.series].map(k => k === '#flush' ? flushCombo(c) : k === '#wetted' ? (c.wetted === 'Match Shaft Material' ? 0 : 1 + FIELD.wettedSel.master.indexOf(c.wettedSel)) : FIELD[k].master.indexOf(c[k])); }
function sealAssy(c) {
  const gd = c.sealGuard === 'Supplied by Fybroc', o = c.sealOption;
  if (o === 'NoSeal Single Seal Gland') return gd ? 65 : 31;
  if (o === 'NoSeal Double Seal Gland') return gd ? 66 : 32;
  if (o === 'NoSeal NoSealGland') return 33;
  if (o === 'Installed by Fybroc') return gd ? 67 : 34;
  return ELAST.indexOf(c.sealElast) * 10 + SEAL_MATS.indexOf(c.sealMat) * 5 + SEAL_TYPES.indexOf(c.sealType) + 1 + (gd ? 34 : 0);
}
function unSealAssy(n, letter) {
  const mfg = Object.keys(SEAL_MFG_LETTER).find(k => SEAL_MFG_LETTER[k] === letter);
  const map = {31:['NoSeal Single Seal Gland',0],65:['NoSeal Single Seal Gland',1],32:['NoSeal Double Seal Gland',0],66:['NoSeal Double Seal Gland',1],33:['NoSeal NoSealGland',0],34:['Installed by Fybroc',0],67:['Installed by Fybroc',1]};
  const G = ['Not Supplied by Fybroc','Supplied by Fybroc'];
  if (map[n]) return {sealOption: map[n][0], sealGuard: G[map[n][1]], sealMfg: map[n][0] === 'Installed by Fybroc' ? mfg : undefined};
  let gd = 0; if (n >= 35 && n <= 64) { gd = 1; n -= 34; } if (n < 1 || n > 30) return null;
  n -= 1;
  return {sealOption:'Supplied by Fybroc', sealGuard:G[gd], sealMfg:mfg, sealElast:ELAST[Math.floor(n / 10)], sealMat:SEAL_MATS[Math.floor((n % 10) / 5)], sealType:SEAL_TYPES[n % 5]};
}
const MOTOR_RADIX = () => [2, 2, 19, 4, 3, 2, 3, 4];
function motorIdx(c) {
  const sup = c.motorOption === 'Supplied by Fybroc';
  return [MOTOR_OPT.indexOf(c.motorOption) - 1, FIELD.motorControl.master.indexOf(c.motorControl), HP_LIST.indexOf(c.hp), FIELD.rpm.master.indexOf(c.rpm),
    sup ? FIELD.voltage.master.indexOf(c.voltage) : 0, sup ? FIELD.hz.master.indexOf(c.hz) : 0, sup ? FIELD.enclosure.master.indexOf(c.enclosure) : 0, sup ? FIELD.motorMfg.master.indexOf(c.motorMfg) : 0];
}
function lenCode(L) { const v = L - 18; return String.fromCharCode(65 + Math.floor(v / 36)) + B36[v % 36]; }
function tailCode(L) { return L < 100 ? String(L).padStart(2, '0') : 'T' + B36[L - 100]; }
function optsCode(c) {
  if (c.series === '1500') {
    const n = FIELD.coupling.master.indexOf(c.coupling) + 2 * FIELD.couplingGuard.master.indexOf(c.couplingGuard) + 8 * FIELD.baseplate.master.indexOf(c.baseplate)
      + 16 * (c.bpHw === '-' ? 0 : 1 + FIELD.bpHw.master.indexOf(c.bpHw)) + 48 * FIELD.custNameplate.master.indexOf(c.custNameplate) + 96 * FIELD.cface.master.indexOf(c.cface) + 1;
    return b36(n, 2);
  }
  return b36(FIELD.coupling.master.indexOf(c.coupling) + 2 * FIELD.mountPlate.master.indexOf(c.mountPlate) + 4 * FIELD.custNameplate.master.indexOf(c.custNameplate) + 1, 2);
}
function testCode(c) {
  const i = k => FIELD[k].master.indexOf(c[k]);
  return b36(i('perf') * 48 + i('hydro') * 16 + i('vib') * 4 + i('sound'), 2);
}
/* customs: {seal:'X01'|null, motor:'X01'|null, special:'X00001'|null} */
function encodeSpec(c, customs) {
  customs = customs || {};
  const kinds = customKinds(c), s = c.series, segs = [];
  const seg = (code, label, group, pending) => segs.push({code, label, group, pending: !!pending});
  seg('F' + SERIES_FLANGE[s][c.flange] + SIZE_CODE[c.size] + MAT_CODE[c.material], 'Series, flange, size, material', 'pump');
  seg(trimCode(c.trim), 'Impeller trim', 'pump');
  seg(b36(mixEnc(poIdx(c), poRadix(s)), 4), 'Pump options', 'options');
  if (s === '1500') {
    if (kinds.includes('seal')) seg(customs.seal || 'X??', 'Mechanical seal (custom)', 'seal', !customs.seal);
    else { const L = ['NoSeal Single Seal Gland','NoSeal Double Seal Gland','NoSeal NoSealGland'].includes(c.sealOption) ? 'N' : SEAL_MFG_LETTER[c.sealMfg]; seg(L + b36(sealAssy(c), 2), 'Mechanical seal', 'seal'); }
  } else {
    seg((c.settingMode === 'Standard Setting' ? String(c.setting).padStart(2, '0') : lenCode(+c.length)) + (c.tailpipe === 'Supplied by Fybroc' ? tailCode(+c.tailpipeLen) : '00'), 'Setting or length, tailpipe', 'setting');
  }
  seg(optsCode(c), 'Drive and base options', 'drive');
  if (kinds.includes('motor')) seg(customs.motor || 'X??', 'Motor assembly (custom)', 'motor', !customs.motor);
  else seg(c.motorOption === 'By Others' ? '000' : b36(mixEnc(motorIdx(c), MOTOR_RADIX()) + 1, 3), 'Motor assembly', 'motor');
  seg((c.shaftGround === 'Supplied by Fybroc' ? '2' : 'X') + (c.paint === 'Supplied by Fybroc' ? 'P' : 'X') + 'X', 'Motor modifications', 'motor');
  seg(testCode(c), 'Testing', 'testing');
  if (kinds.includes('special')) seg(customs.special || 'X?????', 'Special requirement', 'special', !customs.special);
  return {spec: segs.map(x => x.code).join('-'), segs, pending: segs.some(x => x.pending)};
}

/* lib = custom code library {seal:[], motor:[], special:[]}; returns {cfg, customs} or {error} */
function decodeSpec(spec, lib) {
  const raw = String(spec || '').trim().toUpperCase();
  const parts = raw.split('-');
  const err = m => ({error: m});
  if (parts.length < 8) return err('A spec number has 8 segments separated by dashes, plus an optional special-requirement code.');
  const p0 = parts[0];
  if (p0.length !== 4 || p0[0] !== 'F') return err('The first segment should look like FA35: brand, series and flange, size, material.');
  const series = Object.keys(SERIES_FLANGE).find(s => Object.values(SERIES_FLANGE[s]).includes(p0[1]));
  if (!series) return err(`Series code \u201c${p0[1]}\u201d is not in this demo. Only the 1500 and 5500 series are loaded.`);
  const c = {series, special: ''}; const customs = {};
  c.flange = Object.keys(SERIES_FLANGE[series]).find(k => SERIES_FLANGE[series][k] === p0[1]);
  c.size = Object.keys(SIZE_CODE).find(k => SIZE_CODE[k] === p0[2]);
  c.material = Object.keys(MAT_CODE).find(k => MAT_CODE[k] === p0[3]);
  if (!c.size || !c.material) return err('Size or material code not recognized.');
  c.trim = trimDecode(parts[1]); if (!c.trim) return err('Impeller trim code not recognized.');
  const po = mixDec(unb36(parts[2]), poRadix(series)); if (!po || parts[2].length !== 4) return err('Pump options code not recognized.');
  PO[series].forEach((k, i) => {
    if (k === '#flush') Object.assign(c, unFlushCombo(po[i]));
    else if (k === '#wetted') { c.wetted = po[i] === 0 ? 'Match Shaft Material' : 'Select Material'; c.wettedSel = po[i] === 0 ? null : FIELD.wettedSel.master[po[i] - 1]; }
    else c[k] = FIELD[k].master[po[i]];
  });
  const findLib = (kind, code) => (lib[kind] || []).find(e => e.code === code);
  let s3 = parts[3];
  if (series === '1500') {
    if (s3[0] === 'X') { const e = findLib('seal', s3); if (!e) return err(`Custom seal code ${s3} is not in the custom code library.`); Object.assign(c, e.fields); customs.seal = s3; }
    else { const r = unSealAssy(unb36(s3.slice(1)), s3[0]); if (!r) return err('Mechanical seal code not recognized.'); Object.assign(c, r); }
  } else {
    const a = s3.slice(0, 2), t = s3.slice(2);
    if (/^[A-F]/.test(a)) { c.settingMode = 'Custom Length'; c.length = 18 + (a.charCodeAt(0) - 65) * 36 + B36.indexOf(a[1]); }
    else { c.settingMode = 'Standard Setting'; c.setting = String(+a); }
    if (t === '00') c.tailpipe = 'Not Supplied by Fybroc'; else { c.tailpipe = 'Supplied by Fybroc'; c.tailpipeLen = t[0] === 'T' ? 100 + B36.indexOf(t[1]) : +t; }
  }
  const on = unb36(parts[4]) - 1; if (!(on >= 0)) return err('Drive and base code not recognized.');
  if (series === '1500') {
    let n = on;
    c.cface = FIELD.cface.master[Math.floor(n / 96)]; n %= 96; c.custNameplate = FIELD.custNameplate.master[Math.floor(n / 48)]; n %= 48;
    const hw = Math.floor(n / 16); c.bpHw = hw === 0 ? '-' : FIELD.bpHw.master[hw - 1]; n %= 16;
    c.baseplate = FIELD.baseplate.master[Math.floor(n / 8)]; n %= 8; c.couplingGuard = FIELD.couplingGuard.master[Math.floor(n / 2)]; c.coupling = FIELD.coupling.master[n % 2];
  } else {
    c.coupling = FIELD.coupling.master[on % 2]; c.mountPlate = FIELD.mountPlate.master[Math.floor(on / 2) % 2]; c.custNameplate = FIELD.custNameplate.master[Math.floor(on / 4)];
  }
  const m = parts[5];
  if (m[0] === 'X') { const e = findLib('motor', m); if (!e) return err(`Custom motor code ${m} is not in the custom code library.`); Object.assign(c, e.fields); customs.motor = m; }
  else if (m === '000') { c.motorOption = 'By Others'; }
  else {
    const mi = mixDec(unb36(m) - 1, MOTOR_RADIX()); if (!mi) return err('Motor assembly code not recognized.');
    c.motorOption = MOTOR_OPT[mi[0] + 1]; c.motorControl = FIELD.motorControl.master[mi[1]]; c.hp = HP_LIST[mi[2]]; c.rpm = FIELD.rpm.master[mi[3]];
    if (c.motorOption === 'Supplied by Fybroc') { c.voltage = FIELD.voltage.master[mi[4]]; c.hz = FIELD.hz.master[mi[5]]; c.enclosure = FIELD.enclosure.master[mi[6]]; c.motorMfg = FIELD.motorMfg.master[mi[7]]; }
  }
  c.shaftGround = parts[6][0] === '2' ? 'Supplied by Fybroc' : 'Not Included';
  c.paint = parts[6][1] === 'P' ? 'Supplied by Fybroc' : 'Not Included';
  let t = unb36(parts[7]); if (!(t >= 0)) return err('Testing code not recognized.');
  c.perf = FIELD.perf.master[Math.floor(t / 48)]; t %= 48; c.hydro = FIELD.hydro.master[Math.floor(t / 16)]; t %= 16; c.vib = FIELD.vib.master[Math.floor(t / 4)]; c.sound = FIELD.sound.master[t % 4];
  if (parts[8]) { const e = findLib('special', parts[8]); if (!e) return err(`Special requirement code ${parts[8]} is not in the custom code library.`); c.special = e.fields.special; customs.special = parts[8]; }
  if (series === '1500') { const hw = [c.casingHw, c.frameHw, c.glandHw].concat(c.bpHw === '-' ? [] : [c.bpHw]);
    c.hardware = hw.every(v => v === hw[0]) && ['303 SS','316 SS'].includes(hw[0]) ? hw[0] : HW_SEP; }
  // fill anything still undefined with standards, then verify round trip
  const filled = defaultCfg(series, Object.fromEntries(Object.entries(c).filter(([, v]) => v !== undefined)));
  const back = encodeSpec(filled, customs).spec;
  if (back !== raw) return err('This number decodes, but the configuration breaks a constraint rule, so it is not a valid spec number.');
  return {cfg: filled, customs};
}

/* ---------- Item numbers: same spec always returns the same item ---------- */
function fnv(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function itemFor(spec, series, registry) {
  if (registry.bySpec[spec]) return registry.bySpec[spec];
  let n = 100000 + fnv(spec) % 900000, id;
  while (registry.byItem[id = `F${series}-${n}`]) n = n >= 999999 ? 100000 : n + 1;
  registry.bySpec[spec] = id; registry.byItem[id] = spec; return id;
}

/* ---------- Pricing (MADE-UP numbers for demo) ---------- */
const BASE = {
  '1500': {'1x1.5x6':6400,'1.5x3x6':6900,'2x3x6':7300,'1x1.5x8':7600,'1.5x3x8':8100,'2x3x8':8600,'3x4x8':9400,'1x2x10':9100,'1.5x3x10':9700,'2x3x10':10300,'3x4x10':11200,'4x4x10':12100,'4x6x10':13300,'2x3x13':14200,'3x4x13':15400,'4x6x13':17100,'6x8x13':22800,'8x10x15':31500,'10x12x16':38900},
  '5500': {'1x1.5x6':9300,'1.5x3x6':10000,'2x3x6':10600,'1x1.5x8':11000,'1.5x3x8':11700,'2x3x8':12500,'3x4x8':13600,'1x2x10':13200,'1.5x3x10':14100,'2x3x10':14900,'3x4x10':16200,'4x4x10':17500,'4x6x10':19300,'2x3x13':20600,'3x4x13':22300,'4x6x13':24800,'6x8x13':33100,'8x10x15':45700,'10x12x16':56400}
};
const MAT_PCT = {'VR-1':0,'VR-1 BPO/DMA':0.06,'VR-1A':0.10,'VR-1A BPO/DMA':0.16,'VR-1V':0.28,'EY-2':0.40};
const LEAD = {'1500':{1:6,2:8,3:12}, '5500':{1:8,2:10,3:14}};
const ADDERS = { // number, [g1,g2,g3], or 'CF' (consult factory)
  casingDrains:{'Supplied by Fybroc':180}, sdTaps:{'Suction Discharge Taps':240},
  shaft:{'316 SS':[310,420,560],'Carp-20':[900,1150,1500],'Hastelloy C':[1600,2050,2700],'Titanium':[2400,3100,4100],'FRP Wrapped Shaft (303SS Core)':[1100,1400,1900],'FRP Wrapped Shaft (316SS Core)':[1250,1600,2150]},
  sleeve:{'Separate FRP':420,'316SS':380,'Carp-20':690,'Titanium':1150,'Hast-C':980},
  wettedSel:{'Carp-20':450,'Hastelloy C':900,'Titanium':1300},
  casingHw:{'316 SS':120}, pumpElast:{'PTFE':260}, bearing:{'Re-Greaseable Bearings':140,'Greased for Life Bearings':220},
  frameHw:{'316 SS':90}, glandHw:{'316 SS':60,'Carp-20':210,'Titanium':520,'Hastelloy C':460},
  flush:{'Bypass(Tapped Discharge)':280,'Bypass(Tapped Spacer)':340,'Bypass(Cyclone Separator)':520,'Bypass(Cyclone Separator/Spacer)':600},
  flushMat:{'PTFE/PVDF':190}, cyclone:{'By Fybroc':1450}, impBal:{'Dynamic Balancing':380},
  vapor:{'Vapor Seal':650}, strainer:{'Standard Strainer':420,'Flat Screen Strainer':310},
  sealOption:{'Installed by Fybroc':350,'NoSeal Double Seal Gland':240}, sealGuard:{'Supplied by Fybroc':260},
  coupling:{'Coupling Included':[320,560,980]}, couplingGuard:{'Steel':240,'316 SS':680,'Non Sparking':520},
  baseplate:{'Baseplate Included':[1850,2900,4700]}, bpHw:{'316 SS':[120,180,260]},
  mountPlate:{'Custom Mounting Plate':'CF'}, cface:{'Supplied by Fybroc':950}, custNameplate:{'Customer':75},
  motorOption:{'Installed by Fybroc':450}, shaftGround:{'Supplied by Fybroc':380}, paint:{'Supplied by Fybroc':420},
  perf:{'Non-Wit Perf Test':1450,'Wit Perf Test':'CF','Non-Wit Perf Test NPSHR':2600,'Wit Perf Test NPSHR':'CF'},
  hydro:{'Non-Wit Hydro Test Certificate':500,'Wit Hydro Test Certificate':'CF'},
  vib:{'Non-Wit Vibration Testing':650,'Wit Vibration Testing':'CF'}, sound:{'Non-Wit Sound Level Testing':600,'Wit Sound Level Testing':'CF'}
};
const PRICE = {trim:250, perSetting:[520,650,880], customCut:400, perInch:[45,55,70], tailBase:900, tailPerInch:40,
  seal:{'8B2 Single Outside':1350,'RAC Single Outside':1600,'8-1T Double Inside':2950,'RXO Double Inside':3400,'CRO Double Inside':3200}, sealSilcar:1.45, sealPTFE:220,
  sealMfg:{'Standard Offering':1,'John Crane':1.06,'Flowserve':1.08,'Flex-a-seal':0.97},
  motor:{'1':640,'1.5':720,'2':780,'3':910,'5':1180,'7.5':1620,'10':1950,'15':2700,'20':3350,'25':4100,'30':4750,'40':6200,'50':7400,'60':8900,'75':10800,'100':14200,'125':17900,'150':21000,'200':27500},
  rpmF:{'3600':1,'1800':1.05,'1200':1.35,'900':1.7}, encF:{'TEFC':1,'TEFC SD':1.12,'IEEE 841':1.3}, mfgF:{'Standard Offering':1,'Baldor':1.08,'TECO':0.97,'Toshiba':1.04}, vertical:1.12, hz50:1.05};
const ADDER_ORDER = ['casingDrains','sdTaps','shaft','sleeve','wettedSel','casingHw','pumpElast','bearing','frameHw','glandHw','flush','flushMat','cyclone','impBal','vapor','strainer','sealOption','sealGuard','coupling','couplingGuard','baseplate','bpHw','mountPlate','cface','custNameplate','motorOption','shaftGround','paint','perf','hydro','vib','sound'];
function priceCfg(c) {
  const s = c.series, g = sizeGroup(c.size), items = [];
  const add = (key, label, amt, cf) => items.push({key, label, amt: cf ? 0 : Math.round(amt), cf: !!cf});
  const base = BASE[s][c.size];
  add('size', `Base pump ${s} ${c.size}`, base);
  if (MAT_PCT[c.material]) add('material', `Material ${c.material}`, base * MAT_PCT[c.material]);
  if (+c.trim < TRIM_RANGE[c.size][1] - 1e-9) add('trim', `Impeller trim ${c.trim}`, PRICE.trim);
  if (s === '5500') {
    if (c.settingMode === 'Standard Setting') { if (+c.setting > 1) add('setting', `Setting ${c.setting}`, (+c.setting - 1) * PRICE.perSetting[g - 1]); }
    else add('length', `Custom length ${c.length} in`, PRICE.customCut + Math.max(0, c.length - 24) * PRICE.perInch[g - 1]);
    if (c.tailpipe === 'Supplied by Fybroc') add('tailpipeLen', `Tailpipe ${c.tailpipeLen} in`, PRICE.tailBase + PRICE.tailPerInch * c.tailpipeLen);
  }
  const kinds = customKinds(c);
  for (const key of ADDER_ORDER) {
    if (!FIELD[key].avail[s]) continue;
    const a = ADDERS[key] && ADDERS[key][c[key]]; if (a == null) continue;
    if (a === 'CF') add(key, `${FIELD[key].label}: ${c[key]}`, 0, true);
    else add(key, `${FIELD[key].label}: ${c[key]}`, Array.isArray(a) ? a[g - 1] : a);
  }
  if (s === '1500' && c.sealOption === 'Supplied by Fybroc' && !kinds.includes('seal')) {
    let p = PRICE.seal[c.sealType] * (c.sealMat === 'Silcar vs Silcar' ? PRICE.sealSilcar : 1) * PRICE.sealMfg[c.sealMfg] + (c.sealElast === 'PTFE' ? PRICE.sealPTFE : 0);
    add('sealType', `Seal ${c.sealType}, ${c.sealMat}`, p);
  }
  if (c.motorOption === 'Supplied by Fybroc' && !kinds.includes('motor')) {
    const p = PRICE.motor[c.hp] * PRICE.rpmF[c.rpm] * PRICE.encF[c.enclosure] * PRICE.mfgF[c.motorMfg] * (s === '5500' ? PRICE.vertical : 1) * (c.hz === '3ph - 50 hz' ? PRICE.hz50 : 1);
    add('hp', `Motor ${c.hp} HP ${c.rpm} RPM ${c.enclosure}`, p);
  }
  const total = items.reduce((t, i) => t + i.amt, 0);
  return {items, total, cf: items.filter(i => i.cf).map(i => i.key)};
}
function leadWeeks(c) { return LEAD[c.series][sizeGroup(c.size)]; }
function rowList(r) { const m = Math.min(0.95, Math.max(0, (+r.margin || 0) / 100)); return Math.round((+r.cost || 0) / (1 - m) / 10) * 10; }
function entryList(e) { return e.rows.reduce((t, r) => t + rowList(r), 0); }

/* ---------- Descriptions ---------- */
function shortDesc(c) {
  const parts = ['PUMP', 'FYBR', c.series, c.size, c.material, `${c.trim} TRIM`];
  if (c.series === '1500') {
    parts.push(`${c.shaft.replace(' SS', '')} SHAFT`);
    if (c.sealOption === 'Supplied by Fybroc') parts.push(c.sealType === 'Custom Seal Type' || c.sealMfg === 'Custom Seal Mfg' ? 'CUSTOM SEAL' : `${c.sealType.split(' ')[0]}-${c.sealMat === 'Silcar vs Silcar' ? 'SC/SC' : 'C/CR'}`);
    else parts.push(c.sealOption.toUpperCase());
  } else {
    parts.push(c.settingMode === 'Standard Setting' ? `S-${String(c.setting).padStart(2, '0')}` : `L=${c.length}IN`);
    parts.push(`${c.shaft.replace('FRP Wrapped Shaft', 'WRAPPED').replace(' SS', '')} SHAFT`);
  }
  if (c.motorOption !== 'By Others') parts.push(`${c.hp}HP ${c.rpm}`);
  return parts.join(', ');
}
function configNotes(c) {
  const n = [];
  if (c.series === '1500' && c.flush === 'Internal Flush' && c.sealOption === 'Supplied by Fybroc' && /Double/.test(c.sealType)) n.push('Double seal with internal flush: an external barrier fluid source is still required.');
  if (c.motorControl === 'VFD' && c.motorOption !== 'By Others') n.push('Shaft grounding ring included because a VFD is selected (ConstraintTable20).');
  if (c.motorOption === 'By Others' && c.coupling === 'Coupling Included') n.push('Motor by others: coupling is bored to suit the motor frame stated on the order.');
  if (String(c.flush).includes('Cyclone') && c.cyclone === 'Not Included') n.push('Cyclone bypass flush selected without a cyclone separator from Fybroc.');
  return n;
}

if (typeof module !== 'undefined') module.exports = {FIELDS, FIELD, GROUPS, defaultCfg, normalize, encodeSpec, decodeSpec, priceCfg, itemFor, customKinds, cfItems, optionsFor, fieldsFor, shortDesc, frameFor, entryList};
