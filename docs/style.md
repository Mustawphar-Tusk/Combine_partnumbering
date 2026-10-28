:root{--ink:#17212a;--ink-2:#55636c;--paper:#eceeea;--panel:#fbfbf9;--rule:#c6ccc5;--rule-2:#dfe3de;--blue:#1d5c87;--blue-ink:#fff;--blue-bg:#dde9f2;--amber:#9a5f08;--amber-bg:#f5e7cc;--green:#2a6c45;--green-bg:#dbeadf;--red:#a3362b;--plate:#22303a;--plate-ink:#eef2ef;--plate-cap:#93a3ab;
  color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ink:#e4e9e5;--ink-2:#9eaab0;--paper:#12171b;--panel:#1a2126;--rule:#34403f;--rule-2:#262f33;--blue:#72aedb;--blue-ink:#0c1822;--blue-bg:#1b3040;--amber:#e3a64a;--amber-bg:#3a2c14;--green:#7fc79a;--green-bg:#1b3125;--red:#e58276;--plate:#0b1013;--plate-ink:#e9eeeb;--plate-cap:#7d8d95;color-scheme:dark}}
:root[data-theme="dark"]{--ink:#e4e9e5;--ink-2:#9eaab0;--paper:#12171b;--panel:#1a2126;--rule:#34403f;--rule-2:#262f33;--blue:#72aedb;--blue-ink:#0c1822;--blue-bg:#1b3040;--amber:#e3a64a;--amber-bg:#3a2c14;--green:#7fc79a;--green-bg:#1b3125;--red:#e58276;--plate:#0b1013;--plate-ink:#e9eeeb;--plate-cap:#7d8d95;color-scheme:dark}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Archivo",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--panel)}
.mono,code,.code{font-family:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
h1,h2,h3,h4{font-stretch:87%;line-height:1.2;margin:0}
h1{font-size:1.75rem;font-weight:750;letter-spacing:-.01em;display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
h2{font-size:1.15rem;font-weight:700}h3{font-size:1rem;font-weight:700}h4{font-size:.9rem;font-weight:700;margin:1rem 0 .4rem}
button{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:20;background:var(--panel);border-bottom:1px solid var(--rule);display:flex;align-items:center;gap:1.25rem;padding:.6rem 1.25rem;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:.6rem}
.mark{font-weight:800;font-stretch:75%;font-size:1.45rem;letter-spacing:.01em;color:var(--blue)}
.brand-sub{font-size:.8rem;color:var(--ink-2)}
.tabs{display:flex;gap:.1rem;flex:1;flex-wrap:nowrap;overflow-x:auto;min-width:0}
.tab{background:none;border:0;padding:.45rem .6rem;white-space:nowrap;border-radius:6px;cursor:pointer;color:var(--ink-2);font-weight:600}
.tab:hover{color:var(--ink);background:var(--rule-2)}.tab.on{color:var(--ink);box-shadow:inset 0 -2px 0 var(--blue);border-radius:0}
.count{display:inline-block;min-width:1.3em;padding:0 .35em;border-radius:9px;background:var(--amber);color:var(--panel);font-size:.75rem;text-align:center}
.who{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:7px;overflow:hidden}
.seg button{border:0;background:var(--panel);padding:.35rem .7rem;cursor:pointer;font-size:.85rem;font-weight:600;color:var(--ink-2)}
.seg button.on{background:var(--ink);color:var(--panel)}
.who select{max-width:15rem}
.who-ae{font-size:.85rem;color:var(--ink-2)}
.demo-note{font-size:.78rem;color:var(--ink-2);text-align:center;padding:.3rem 1rem;border-bottom:1px solid var(--rule-2)}
.main{max-width:1240px;margin:0 auto;padding:1.5rem 1.25rem 4rem}.main-wide{max-width:1400px;padding-bottom:9rem}
.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin:0 0 1.25rem;flex-wrap:wrap}
.lede{color:var(--ink-2);margin:.35rem 0 0;max-width:70ch}
.head-acts{display:flex;gap:.5rem;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--rule);background:var(--panel);border-radius:7px;padding:.5rem .9rem;cursor:pointer;font-weight:600;font-size:.9rem;white-space:nowrap}
.btn:hover:not([disabled]){border-color:var(--ink-2)}
.btn.primary{background:var(--blue);border-color:var(--blue);color:var(--blue-ink)}
.btn.primary.amber{background:var(--amber);border-color:var(--amber);color:var(--panel)}
.btn.amber{border-color:var(--amber);color:var(--amber)}
.btn.ghost{background:transparent;border-color:transparent}.btn.ghost:hover{border-color:var(--rule)}
.btn.danger{color:var(--red)}
.btn.sm{padding:.28rem .55rem;font-size:.8rem}
.btn[disabled]{opacity:.45;cursor:not-allowed}
.btn.fake{pointer-events:none}
.link{background:none;border:0;padding:0;color:var(--blue);cursor:pointer;font-weight:600;text-decoration:underline;text-underline-offset:2px}
.back{display:inline-block;margin-bottom:.6rem;text-decoration:none}.back::before{content:"\2190  "}
.in{font:inherit;font-size:.9rem;font-weight:400;color:var(--ink);background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:.42rem .55rem;width:100%}
textarea.in{resize:vertical;line-height:1.45}
.in.qty{width:4.2rem}.num-in{max-width:8rem}
select.in{cursor:pointer}
.tablewrap{overflow-x:auto;border:1px solid var(--rule);border-radius:8px;background:var(--panel)}
table.grid{width:100%;border-collapse:collapse;font-size:.88rem}
.grid th{text-align:left;font-size:.75rem;font-weight:700;color:var(--ink-2);padding:.55rem .7rem;border-bottom:1px solid var(--rule);white-space:nowrap;background:var(--panel)}
.grid td{padding:.6rem .7rem;border-bottom:1px solid var(--rule-2);vertical-align:top}
.grid tbody tr:last-child td{border-bottom:0}
.grid tfoot td{border-top:1px solid var(--rule);padding:.7rem}
.grid.compact td{padding:.4rem .6rem}.grid.compact th{padding:.4rem .6rem}
.grid .num{text-align:right;white-space:nowrap}
tr.click{cursor:pointer}tr.click:hover td{background:var(--rule-2)}
.lines td .in{margin-bottom:.25rem;min-width:9rem}.lines td .in.qty{min-width:0;width:3.6rem}
.acts{display:flex;flex-wrap:wrap;gap:.3rem;min-width:11rem}
.sub{color:var(--ink-2);font-size:.8rem}.strong{font-weight:700}.big{font-size:1.1rem}
.amber,.amber-t{color:var(--amber)}
.pill{display:inline-block;font-size:.75rem;font-weight:700;padding:.15rem .55rem;border-radius:20px;font-stretch:100%;letter-spacing:0;vertical-align:middle}
.st-draft{background:var(--rule-2);color:var(--ink-2)}.st-ae{background:var(--amber-bg);color:var(--amber)}.st-done{background:var(--blue-bg);color:var(--blue)}.st-rel{background:var(--green-bg);color:var(--green)}
.chips{display:flex;flex-wrap:wrap;gap:.25rem;margin-top:.3rem}
.chip{display:inline-block;font-size:.72rem;font-weight:600;padding:.1rem .45rem;border-radius:4px;margin-right:.2rem}
.chip.amber{background:var(--amber-bg);color:var(--amber)}.chip.blue{background:var(--blue-bg);color:var(--blue)}.chip.green{background:var(--green-bg);color:var(--green)}
.empty{border:1px dashed var(--rule);border-radius:8px;padding:2.5rem;text-align:center;color:var(--ink-2)}
.emptyrow{text-align:center;color:var(--ink-2);padding:2rem!important}
.qmeta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:1rem;margin-bottom:1rem}
.qmeta label{display:flex;flex-direction:column;gap:.3rem;font-size:.75rem;font-weight:700;color:var(--ink-2)}.qmeta label span{font-size:.95rem;color:var(--ink);font-weight:600}
.addbar{display:flex;flex-wrap:wrap;gap:1rem 2rem;margin:1rem 0;padding:1rem;border:1px dashed var(--rule);border-radius:8px}
.addbar>div{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}.addbar .in{width:16rem}
.lbl{font-size:.8rem;font-weight:700;color:var(--ink-2)}
.actions{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;margin:1.25rem 0}
.note{margin:0;padding:.6rem .8rem;border-radius:6px}.amber-note{background:var(--amber-bg);color:var(--amber)}
.history{margin-top:2rem}.history ol{list-style:none;padding:0;margin:.5rem 0;font-size:.85rem}.history li{padding:.3rem 0;border-bottom:1px solid var(--rule-2)}
/* Spec plate */
.main-wide .plate{position:sticky;top:3.55rem;z-index:12;padding:.7rem 1.2rem .55rem;box-shadow:0 6px 14px rgba(0,0,0,.12)}
.cfg{scroll-margin-top:11rem}
.plate{background:var(--plate);color:var(--plate-ink);border-radius:10px;padding:1rem 1.2rem .8rem;margin:1rem 0;overflow-x:auto}
.plate-row{display:flex;align-items:flex-start;gap:.2rem;min-width:max-content}
.plate .seg{display:flex;flex-direction:column;align-items:center;border:0;border-radius:6px;padding:.25rem .35rem;transition:background .6s}
.plate .code{font-family:"IBM Plex Mono",monospace;font-size:1.65rem;font-weight:600;letter-spacing:.04em}
.plate .cap{font-size:.62rem;color:var(--plate-cap);max-width:8.5rem;text-align:center;line-height:1.2;margin-top:.15rem}
.plate .dash{font-family:"IBM Plex Mono",monospace;font-size:1.65rem;color:var(--plate-cap);padding-top:.25rem}
.plate .seg.pending .code{color:var(--amber);text-decoration:underline dotted;text-underline-offset:5px}
.plate .seg.flash{animation:flash 1.4s ease-out}
@keyframes flash{0%{background:rgba(114,174,219,.45)}100%{background:transparent}}
.plate-foot{display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:.6rem;padding-top:.55rem;border-top:1px solid rgba(255,255,255,.12);font-size:.82rem;color:var(--plate-cap)}
.plate-foot b{color:var(--plate-ink);font-weight:600}
.plate.small .code,.plate.small .dash{font-size:1.15rem}
.msgs{background:var(--amber-bg);color:var(--amber);border-radius:8px;padding:.55rem .9rem;margin:-.25rem 0 1rem;font-size:.85rem}.msgs p{margin:.15rem 0}
.msgs.err{background:#f6dcd8;color:var(--red)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .msgs.err{background:#3a1d1a}}
/* Configurator */
.cfg{display:grid;grid-template-columns:minmax(300px,5fr) 7fr;gap:1.25rem;align-items:start}
.summary{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:.8rem;position:sticky;top:11rem;max-height:calc(100vh - 18rem);overflow:auto}
.summary h2{font-size:.95rem;margin:.1rem .3rem .5rem}
.sgroup{margin-bottom:.4rem}.sgroup h3{font-size:.82rem;padding:.35rem .3rem .2rem}.sgroup h3 .link{color:var(--ink);text-decoration:none}
.sgroup.on h3 .link{color:var(--blue)}
.srow{display:grid;grid-template-columns:9.5rem 1fr auto;gap:.5rem;width:100%;text-align:left;background:none;border:0;border-radius:4px;padding:.22rem .3rem .22rem 1rem;font-size:.8rem;cursor:pointer}
.srow:hover{background:var(--rule-2)}.srow .sl{color:var(--ink-2)}.srow .sv{color:var(--blue)}.srow .sp{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.srow.base,.srow.derived{cursor:default}.srow.base .sv,.srow.derived .sv{color:var(--ink)}
.srow.custom .sv,.srow.custom .sp{color:var(--amber);font-weight:600}
.opts{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:0 1rem 1rem}
.gtabs{display:flex;gap:.15rem;overflow-x:auto;border-bottom:1px solid var(--rule);margin:0 -1rem 1rem;padding:0 .6rem}
.gtab{background:none;border:0;padding:.75rem .65rem .6rem;cursor:pointer;font-weight:600;font-size:.85rem;color:var(--ink-2);white-space:nowrap;position:relative}
.gtab.on{color:var(--ink);box-shadow:inset 0 -2px 0 var(--blue)}
.gtab .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--amber);margin-left:.35rem;vertical-align:middle}
.field{padding:.6rem 0 .9rem;border-bottom:1px solid var(--rule-2)}.field:last-of-type{border-bottom:0}
.field h3{font-size:.92rem;margin-bottom:.45rem}
.field.focus-flash{animation:ff 1.6s ease-out}@keyframes ff{0%{background:var(--blue-bg)}100%{background:transparent}}
.radios{display:flex;flex-direction:column;gap:.25rem}
.opt{display:grid;grid-template-columns:1.1rem 1fr auto;gap:.6rem;align-items:start;text-align:left;width:100%;background:transparent;border:1px solid var(--rule-2);border-radius:6px;padding:.45rem .6rem;cursor:pointer;font-size:.88rem}
.opt:hover:not([disabled]){border-color:var(--ink-2)}
.opt.on{border-color:var(--blue);background:var(--blue-bg)}
.opt.is-custom.on{border-color:var(--amber);background:var(--amber-bg)}
.opt[disabled]{cursor:not-allowed;color:var(--ink-2);border-style:dashed}
.radio{width:14px;height:14px;border-radius:50%;border:2px solid var(--rule);margin-top:.2rem}
.opt.on .radio{border-color:var(--blue);background:radial-gradient(circle,var(--blue) 45%,transparent 50%)}
.opt.is-custom.on .radio{border-color:var(--amber);background:radial-gradient(circle,var(--amber) 45%,transparent 50%)}
.ov em.std{font-style:normal;font-size:.7rem;font-weight:700;color:var(--green);margin-left:.35rem}
.why{display:block;font-size:.75rem;color:var(--ink-2);margin-top:.15rem;line-height:1.35}
.od{font-size:.8rem;color:var(--ink-2);white-space:nowrap;font-variant-numeric:tabular-nums}
.hint{font-size:.8rem;color:var(--ink-2);margin:.4rem 0 0}
.req{display:block;margin-top:.7rem;padding:.7rem;border-left:3px solid var(--amber);background:var(--amber-bg);border-radius:0 6px 6px 0;font-size:.82rem;font-weight:700;color:var(--amber)}
.req textarea{margin-top:.35rem;font-weight:400}.req .hint{color:var(--amber)}
.gnav{display:flex;justify-content:space-between;margin-top:1rem;gap:.5rem}
.cfg-foot{position:fixed;left:0;right:0;bottom:0;z-index:15;background:var(--panel);border-top:1px solid var(--rule);padding:.7rem 1.25rem calc(.7rem + env(safe-area-inset-bottom,0px));display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;align-items:flex-end;box-shadow:0 -6px 16px rgba(0,0,0,.06)}
.ff{display:flex;gap:.6rem;flex:1;min-width:280px;flex-wrap:wrap}.ff label{display:flex;flex-direction:column;font-size:.72rem;font-weight:700;color:var(--ink-2);gap:.2rem}.ff .grow{flex:1;min-width:10rem}
.fp{display:flex;gap:1.2rem;align-items:center;flex-wrap:wrap}.fp>div{display:flex;flex-direction:column}.fp b{font-size:1.1rem;font-variant-numeric:tabular-nums}
.foot-warn{width:100%;margin:0;text-align:right}
/* Cards, worksheet */
.card{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:1rem 1.1rem;margin:0 0 1rem}
.card>header{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:.6rem}
.pending-card{border-left:4px solid var(--amber)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1.25rem}
.dl{display:grid;grid-template-columns:auto 1fr;gap:.2rem .8rem;font-size:.85rem;margin:0}.dl dt{color:var(--ink-2)}.dl dd{margin:0}
blockquote{margin:0;padding:.6rem .8rem;background:var(--rule-2);border-radius:6px;font-size:.88rem}
.code-badge{font-family:"IBM Plex Mono",monospace;font-weight:600;background:var(--ink);color:var(--panel);padding:.1rem .4rem;border-radius:4px;margin-right:.3rem}
.assigned{display:flex;flex-direction:column;align-items:flex-start;gap:.6rem;margin-top:.8rem}.assigned>.tablewrap{align-self:stretch}
.blk{display:block;font-size:.8rem;font-weight:700;color:var(--ink-2);margin:.5rem 0}.blk .in{margin-top:.25rem}
.rows .in{min-width:6rem}
.row-acts{display:flex;justify-content:space-between;align-items:center;margin:.5rem 0 .9rem;flex-wrap:wrap;gap:.5rem}.tot{font-size:.88rem;font-weight:600}
.cf-row{display:flex;gap:.8rem;align-items:flex-end;flex-wrap:wrap}.cf-row label{display:flex;flex-direction:column;font-size:.75rem;font-weight:700;color:var(--ink-2);gap:.25rem}.cf-row .grow{flex:1;min-width:14rem}
/* Lookup */
.lookup{display:flex;gap:.6rem;margin-bottom:.6rem}.big-in{font-size:1.05rem;padding:.6rem .75rem}
.lk-acts{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin-top:1rem}.lk-acts select{width:auto;max-width:22rem}
/* Spec tables and documents */
.spec-grid{display:grid;align-items:start;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.8rem 1.4rem;margin-top:.6rem}
table.spec{width:100%;border-collapse:collapse;font-size:.82rem}
.spec caption{text-align:left;font-weight:700;font-stretch:87%;font-size:.9rem;padding:.2rem 0;color:var(--blue);border-bottom:1.5px solid var(--blue)}
.spec th{text-align:left;font-weight:400;color:var(--ink-2);padding:.22rem .5rem .22rem 0;width:48%;vertical-align:top}.spec td{padding:.22rem 0;border-bottom:1px solid var(--rule-2)}
.spec-h{font-size:.92rem;margin:1rem 0 .4rem;color:var(--amber)}
.cnote{border-left:3px solid var(--amber);padding:.3rem .7rem;margin:.4rem 0;font-size:.85rem}.cnote h4{margin:0 0 .15rem}.cnote p{margin:0}
.cn{font-size:.85rem;margin:.3rem 0;padding-left:1.2rem}
.doc{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:1.4rem;margin:1rem 0}
.doc-h{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;border-bottom:2px solid var(--blue);padding-bottom:.7rem;margin-bottom:.9rem}
.doc-ids{display:grid;grid-template-columns:auto auto;gap:.2rem 1.4rem;font-size:.8rem;align-content:start}.doc-ids>div{display:flex;gap:.5rem;align-items:baseline}.doc-ids span{color:var(--ink-2)}
.doc-meta{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;font-size:.88rem}.doc-meta>div{display:flex;flex-direction:column}
.doc-t{font-size:.8rem}
.terms{font-size:.8rem;color:var(--ink-2);padding-left:1.1rem}
/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(10,16,20,.55);z-index:50;display:flex;align-items:flex-start;justify-content:center;padding:calc(3rem + env(safe-area-inset-top,0px)) 1rem 2rem;overflow:auto}
.modal{background:var(--paper);border-radius:10px;padding:1.3rem;width:min(520px,100%);box-shadow:0 20px 50px rgba(0,0,0,.3)}
.modal.wide{width:min(1040px,100%)}
.modal h2{margin-bottom:.5rem}
.m-top{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}.m-top>div{display:flex;gap:.5rem}
.m-acts{display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem}
.email{border:1px solid var(--rule);border-radius:8px;background:var(--panel);overflow:hidden}
.em-h{padding:.7rem .9rem;border-bottom:1px solid var(--rule-2);font-size:.85rem}.em-h span{display:inline-block;width:4.5rem;color:var(--ink-2)}
.em-b{padding:.4rem .9rem .8rem;font-size:.9rem}
.toast{position:fixed;left:50%;bottom:calc(1.2rem + env(safe-area-inset-bottom,0px));transform:translateX(-50%);background:var(--ink);color:var(--panel);padding:.65rem 1rem;border-radius:8px;z-index:60;font-size:.88rem;max-width:min(560px,92vw);box-shadow:0 8px 24px rgba(0,0,0,.25)}
.main-wide ~ .toast{bottom:calc(6.5rem + env(safe-area-inset-bottom,0px))}
@media (max-width:900px){.main-wide .plate{position:static}.tabs{order:3;flex-basis:100%}.cfg{grid-template-columns:1fr}.summary{position:static;max-height:none}.cols{grid-template-columns:1fr}.doc-meta{grid-template-columns:1fr}.top{gap:.6rem}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}

.plate-msg{margin-top:.5rem;padding:.45rem .7rem;border-radius:6px;background:rgba(227,166,74,.16);color:#f2c47c;font-size:.82rem}.plate-msg p{margin:.1rem 0}.plate-warn{color:#f2c47c}

.search{display:flex;gap:.8rem;align-items:center;margin:.2rem 0 .6rem}.search .in{max-width:30rem}
.lib-search{margin-bottom:1rem}
.form2{display:grid;grid-template-columns:1fr 1fr;gap:0 1rem}
.addlist{list-style:none;padding:0;margin:.6rem 0;border:1px solid var(--rule);border-radius:8px;background:var(--panel)}
.addlist li{display:flex;justify-content:space-between;padding:.55rem .8rem;border-bottom:1px solid var(--rule-2)}.addlist li:last-child{border-bottom:0}
@media (max-width:900px){.form2{grid-template-columns:1fr}}


# Logic for Dean spec number

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode(n: int, width: int) -> str:
    """Turn an integer into a base-36 string, left-padded with '0' to `width`.
    encode(87265, 4) -> "1VC1"     encode(1, 4) -> "0001"
    Hint: loop while n > 0: take n % 36, look up DIGITS[...], then n //= 36.
    Collect the characters, reverse them, then use str.rjust(width, "0").
    """
    if n == 0:
        return "0".rjust(width, "0")
    
    chars = []
    while n > 0:
        chars.append(DIGITS[n % 36])
        n //= 36

    result = "".join(reversed(chars))
    if len(result) > width:
        raise ValueError(f"Encoded value '{result}' exceeds specified width {width}.")     
              
    return result.rjust(width, "0")