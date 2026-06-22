import os, sys, glob
sys.path.insert(0, '.')
envf = os.path.expanduser("~/.ultracode-bench/deepseek.env")
for line in open(envf):
    if '=' in line and not line.startswith('#'):
        k,v=line.strip().split('=',1); os.environ.setdefault(k,v)
from ultracode.config import UltracodeConfig
from ultracode.corpus import enumerate_corpus
from bench.deepseek_client import DeepSeekClient

REPO=os.path.expanduser("~/Projects/Notch Pal/notchi")
SYM="AppSettings"
files=sorted(glob.glob(os.path.join(REPO,"**","*.swift"),recursive=True))
# ground truth
gt={os.path.basename(f) for f in files if SYM in open(f).read()}
# one section per file (label each so the enumerator can name it)
sections=[f"FILE: {os.path.basename(f)}\n"+open(f).read() for f in files]
print(f"sections: {len(sections)} files, ground truth: {len(gt)} reference {SYM}")
c=DeepSeekClient(model="deepseek-v4-flash",max_workers=16)
cfg=UltracodeConfig(concurrency=16,max_children=8)
res=enumerate_corpus(sections, f"List the FILE name if it references the symbol `{SYM}` (output the filename only, one per line; skip files that don't).",
                     delegate_fn=c.delegate_fn, aux_call_fn=c.aux_call_fn, config=cfg,
                     concurrency=16, retry_empty=2)
items=res.items if hasattr(res,'items') else res
text=" ".join(str(x) for x in (items if isinstance(items,(list,set)) else [items]))
found={fn for fn in gt if fn in text}
u=c.usage.snapshot()
print(f"enumerate_corpus: {u['total_tokens']}tok | recall={len(found)/len(gt):.2f} ({len(found)}/{len(gt)})")
print("raw items count:", len(items) if hasattr(items,'__len__') else '?')
print("missed:", sorted(gt-found)[:12])
