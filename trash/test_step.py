import re, sys, bocconcini_memory as t
F = "Il sistema registra un picco della CPU. "
A = [("batteria","ALFA-1"),("password","OMEGA-9"),("satellite","TITANO-3"),("backup","BETA-7")]
d = F * 800
for i,(n,c) in enumerate(A):
    k = len(d)*(i+1)//5
    d = d[:k]+" Il codice di %s e' %s. "%(n,c)+d[k:]
class R:
    def __init__(s,x): s.text=x
class C:
    def __init__(s): s.p=[]
    def chat_full(s,**k):
        s.p.append(k["prompt"])
        return R(" ".join(re.findall(r"[A-Z]+-[0-9]", k["prompt"])))
c = C()
o = t.ask_stepwise(c, d, "codici", targets=[n for n,_ in A])
print("per sub-call:", [len(re.findall(r"[A-Z]+-[0-9]",p)) for p in c.p[:4]])
print("biggest:", o["meta"]["biggest_prompt_chars"])
print("answer:", o["text"])
if "--live" in sys.argv:
    import time, bocconcini as b
    z = time.time()
    r = t.ask_stepwise(b.LlamaCppClient(), d, "codici", targets=[n for n,_ in A])
    print("LIVE %.0fs biggest=%d" % (time.time()-z, r["meta"]["biggest_prompt_chars"]))
    print("live answer:", r["text"][:200])
import sys
if "--live" in sys.argv:
    import time, bocconcini as b
    z = time.time()
    r = t.ask_stepwise(b.LlamaCppClient(), d, "codici", targets=[n for n,_ in A])
    print("LIVE %.0fs biggest=%d" % (time.time()-z, r["meta"]["biggest_prompt_chars"]))
    print("live:", r["text"][:200])
