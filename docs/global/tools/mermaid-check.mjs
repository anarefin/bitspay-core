import fs from 'node:fs';
// Usage: MERMAID_NODE_MODULES=/path/to/node_modules node mermaid-check.mjs <file.md>...
// (node_modules must contain mermaid@11 and dompurify, e.g. after `npm i mermaid@11.15.0` in any folder)
const N=(process.env.MERMAID_NODE_MODULES||'./node_modules').replace(/\/?$/,'/');
globalThis.window = globalThis; // minimal shims
const dp = (await import(N+'dompurify/dist/purify.es.mjs')).default;
dp.addHook = ()=>{}; dp.removeHook = ()=>{}; dp.removeAllHooks=()=>{}; dp.sanitize = (x)=>x; dp.isSupported = true;
const { default: mermaid } = await import(N+'mermaid/dist/mermaid.core.mjs');
mermaid.initialize({ startOnLoad:false });
let total=0, bad=0;
for (const f of process.argv.slice(2)) {
  const txt = fs.readFileSync(f,'utf8');
  const re = /```mermaid\n([\s\S]*?)```/g; let m, i=0;
  while ((m = re.exec(txt))) { i++; total++;
    try { await mermaid.parse(m[1]); }
    catch(e){ bad++; const line = txt.slice(0,m.index).split('\n').length; console.log(`FAIL ${f}:${line} #${i}: ${String(e.message||e).split('\n').slice(0,3).join(' | ')}`); }
  }
}
console.log(`mermaid: ${total} diagrams, ${bad} failed`);
process.exit(bad?1:0);
