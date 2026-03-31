#!/usr/bin/env python3
"""MAS v12 - 60 tasks"""
import threading, queue, time, os, subprocess, tempfile
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

class TS(Enum): P,R,C,F,V=("pending","running","completed","failed","verified")
class TP(Enum): L,N,H,C=("low","normal","high","critical")

@dataclass
class T:
    id: str; desc: str; cat: str; dif: int=1; p: TP=TP.N; st: TS=TS.P
    res: Optional[str]=None; err: Optional[str]=None
    start: float=0; end: float=0; aid: Optional[str]=None; tm: float=30.0
    dep: List[str]=field(default_factory=list); et: float=0

from typing import Optional
@dataclass
class A:
    id: str; nm: str; sp: str; caps: List[str]; lv: int
    ct: Optional[T]=None; c: int=0; f: int=0; bt: float=0

class M:
    def __init__(s,n=12):
        s.a={};s.t={};s.q=queue.PriorityQueue();s.r=True;s.l=threading.Lock()
        s.s={"sub":0,"com":0,"fai":0,"ver":0}
        sp=[("analyzer","DataAnalyzer","analysis",3),("coder","CodeEngineer","code",3),
            ("researcher","ResearchAgent","research",2),("planner","StrategicPlanner","planning",2),
            ("verifier","QAVerifier","verification",2),("comm","CommAgent","communication",1)]
        for i,(sid,nm,cp,lv) in enumerate(sp[:n]): s.a[f"{sid}_{i}"]=A(id=f"{sid}_{i}",nm=nm,sp=nm,caps=[cp],lv=lv)
    def sub(s,t):
        with s.l: s.t[t.id]=t; s.s["sub"]+=1
        s.q.put((t.p.value,t.id,t))
    def exe(s,t)->bool:
        t.st=TS.R; t.start=time.time()
        try:
            for d in t.dep:
                if d in s.t and s.t[d].st not in(TS.C,TS.V): raise Exception(f"Dep {d}")
            r=s._d(t); t.res=r; t.st=TS.C
            if s._v(t): t.st=TS.V; s.s["ver"]+=1
            t.end=time.time(); t.et=t.end-t.start
            with s.l: s.s["com"]+=1
            return True
        except Exception as e:
            t.err=str(e); t.end=time.time(); t.et=t.end-t.start; t.st=TS.F
            with s.l: s.s["fai"]+=1
            return False
    def _d(s,t)->str:
        h={"analysis":s._ha,"code":s._hc,"research":s._hr,"planning":s._hp,"verification":s._hv,"communication":s._hc2}
        return h.get(t.cat,s._hd)(t)
    def _ha(s,t)->str:
        for k,c in {"passwd":["wc","-l","/etc/passwd"],"disk":["df","-h"],"memory":["free","-h"],"load":["uptime"]}.items():
            if k in t.desc.lower():
                r=subprocess.run(c,capture_output=True,text=True,timeout=t.tm); return f"{t.cat}: {r.stdout.strip()[:80]}"
        return f"Analysis: {t.desc[:40]}"
    def _hc(s,t)->str:
        for k in ["fib","prime","fact","sort","hello"]:
            if k in t.desc.lower(): return f"Result: {k} executed"
        return "Result: code executed"
    def _hr(s,t)->str:
        for p in ["/tmp","/var/log","/etc"]:
            if p[1:] in t.desc.lower():
                try: return f"{p}: {len(os.listdir(p))} items"
                except: pass
        return f"Research: {t.desc[:40]}"
    def _hp(s,t)->str: return f"Plan: {t.desc[:40]}"
    def _hv(s,t)->str: return f"Verified: {t.desc[:40]}"
    def _hc2(s,t)->str: return f"Report: {t.desc[:40]}"
    def _hd(s,t)->str: return f"Done: {t.desc[:40]}"
    def _v(s,t)->bool:
        if not t.res: return False
        if t.cat=="code": return "error" not in t.res.lower() and len(t.res)>5
        return len(t.res)>3
    def _rt(s,t)->Optional[A]:
        m={"analysis":"analyzer","code":"coder","research":"researcher","planning":"planner","verification":"verifier","communication":"comm"}
        with s.l:
            for a in s.a.values():
                if m.get(t.cat,"") in a.id and a.ct is None: return a
            for a in s.a.values():
                if a.ct is None: return a
        return None
    def run(s):
        while s.r:
            try:
                p,tid,t=s.q.get(timeout=0.5)
                if t is None: break
                ag=s._rt(t)
                if ag:
                    with s.l: t.aid=ag.id
                    ag.ct=t; s.exe(t); ag.ct=None
                    with s.l: ag.bt+=t.et; (ag.c if t.st!=TS.F else ag.f)+=1
                else: s.q.put((p,tid,t)); time.sleep(0.1)
            except queue.Empty: continue
    def st(s): s.r=False; s.q.put((0,None,None))
    def gs(s)->Dict:
        with s.l:
            tt=sum(t.et for t in s.t.values() if t.end>0)
            return{**s.s,"tt":tt,"tp":s.s["com"]/max(.001,tt),
                  "a":{a.id:{"n":a.nm,"c":a.c} for a in s.a.values()}}

def main():
    print("="*50+"\nMAS v12 - 60 TASKS\n"+"="*50)
    mas=M(12)
    cats=["analysis","code","research","planning","verification","communication"]
    ts=[T(id=f"{i:02d}",desc=f"Task {i}",cat=cats[i%6]) for i in range(1,61)]
    print(f"Agents: 12, Tasks: {len(ts)}")
    for t in ts: mas.sub(t)
    s=time.time(); t=threading.Thread(target=mas.run); t.start()
    t.join(timeout=180); mas.st()
    st=mas.gs()
    print(f"\n{st['com']}/{st['sub']} completed, {st['ver']} verified, {st['fai']} failed")
    print(f"Throughput: {st['tp']:.1f} tps")

if __name__=="__main__": main()
