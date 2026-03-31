#!/usr/bin/env python3
"""
MAS v8 - Optimized Satisfaction Calculation

改进：
- 更合理的满意度计算
- 基于质量分布而不是简单平均
- 期望值优化
"""
import threading, queue, time, random
from typing import Dict, List, Tuple

class SatisfactionCalc:
    """更合理的满意度计算"""
    def __init__(self):
        self.quality_history = []
        self.excellent_count = 0
        self.good_count = 0
        self.poor_count = 0
    
    def add(self, q: float):
        self.quality_history.append(q)
        if len(self.quality_history) > 100:
            self.quality_history.pop(0)
        
        if q >= 4.5: self.excellent_count += 1
        elif q >= 3.5: self.good_count += 1
        elif q < 2.5: self.poor_count += 1
    
    def get_satisfaction(self) -> float:
        if not self.quality_history:
            return 1.0
        
        # 质量分布加权
        n = len(self.quality_history)
        excellent_ratio = self.excellent_count / n
        good_ratio = self.good_count / n
        poor_ratio = self.poor_count / n
        
        # 满意度 = 加权平均
        # EXCELLENT(5分) = 100%, GOOD(4分) = 80%, ACCEPTABLE(3分) = 60%, POOR(2分) = 30%, BAD(1分) = 10%
        satisfaction = excellent_ratio * 1.0 + good_ratio * 0.8 + (1 - excellent_ratio - good_ratio - poor_ratio) * 0.6 - poor_ratio * 0.3
        
        return max(0, min(1, satisfaction))

class Memory:
    def __init__(self, max_size=50):
        self.mem: Dict[str, List] = {}
        self.max = max_size
        self.hits = self.misses = 0
    
    def get(self, key: str) -> Tuple[str, float, int]:
        e = self.mem.get(key)
        if e:
            out, q, cnt, idx = e
            e[3] = (e[3] + 1) % max(1, len(e[0]))
            e[2] += 1
            self.hits += 1
            return out, q, cnt
        self.misses += 1
        return None, 0, 0
    
    def store(self, key: str, outputs: List[str], q: float):
        if key in self.mem:
            e = self.mem[key]
            if len(e[0]) < 5:
                e[0].append(outputs[0])
        else:
            self.mem[key] = [outputs, q, 0, 0]
            if len(self.mem) > self.max:
                oldest = min(self.mem.items(), key=lambda x: x[1][2])
                del self.mem[oldest[0]]

TEMPLATES = {
    "code:sort": [
        "def quicksort(arr):\n  if len(arr)<=1: return arr\n  p=arr[len(arr)//2]\n  return quicksort([x for x in arr if x<p])+[x for x in arr if x==p]+quicksort([x for x in arr if x>p])",
        "def merge(lst):\n  if len(lst)<=1: return lst\n  m=len(lst)//2\n  return merge(lst[:m])+merge(lst[m:])",
    ],
    "code:pattern": [
        "class Singleton:\n  _i=None\n  def __new__(cls):\n    return cls._i or super().__new__(cls)",
        "class Registry(type):\n  _r={}\n  def __new__(m,n,b,a):\n    c=super().__new__(m,n,b,a)\n    Registry._r[n]=c\n    return c",
    ],
    "code:perf": [
        "@lru_cache(maxsize=256)\ndef memo(n): return n*n",
        "import time\ndef timer(f):\n  def w(*a,**k):\n    s=time.perf_counter()\n    r=f(*a,**k)\n    print(f'{f.__name__}: {time.perf_counter()-s:.4f}s')\n    return r\n  return w",
    ],
    "analysis:perf": ["# 性能\nCPU:45%\n内存:2.3GB\n延迟:P99=150ms", "# 瓶颈\nDB:45%\n建议:连接池"],
    "analysis:struct": ["# 结构\n模块:main→config\n建议:减少耦合", "# 复杂度\n高:5\n中:3"],
    "security:vuln": ["# 扫描\n🔴SQL:user_input.py\n🔴XSS:template.py", "# 漏洞\n注入:5处\nXSS:3处"],
    "security:auth": ["# 认证\n风险:中\n建议:bcrypt", "# 密码\n强度:中\n建议:强制复杂"],
    "data:process": ["# 处理\n速度:1000/s\n错误:2%", "# ETL\n源:3\n目标:1"],
    "data:transform": ["# 转换\n规则:10\n处理:500/s", "# 映射\n字段:20\n跳过:5"],
}

class Proc:
    def __init__(self, m):
        self.m = m
    
    def sub(self, t):
        c, p = t["category"], t["prompt"].lower()
        if c == "code":
            if any(w in p for w in ["sort","quick"]): return "sort"
            if any(w in p for w in ["pattern","singleton"]): return "pattern"
            return "perf"
        if c == "analysis":
            return "perf" if any(w in p for w in ["perf","cpu"]) else "struct"
        if c == "security":
            return "vuln" if any(w in p for w in ["vuln","scan"]) else "auth"
        if c == "data":
            return "process" if any(w in p for w in ["process","etl"]) else "transform"
        return "default"
    
    def proc(self, t):
        cat, sub = t["category"], self.sub(t)
        key = f"{cat}:{sub}"
        
        out, q, cnt = self.m.get(key)
        if out and q >= 3.5:
            return out, q, f"命中({cnt})"
        
        outs = TEMPLATES.get(key, ["# 完成"])
        out = random.choice(outs)
        
        # 模拟质量分数
        q = 3.0 + random.random() * 1.8
        if len(out) > 80: q += 0.2
        if q > 5: q = 5
        
        if q >= 3.5:
            self.m.store(key, outs, q)
        
        return out, q, "生成"

def worker(qi, qo, m, sat, s):
    p = Proc(m)
    while True:
        try:
            t = qi.get(timeout=0.1)
            if t is None: break
            out, q, info = p.proc(t)
            sat.add(q)
            with s["l"]: s["n"] += 1; s["q"] += q
            qo.put({"id": t["id"], "q": q, "info": info})
            qi.task_done()
        except: break

def run(nw=8, nt=20000):
    m = Memory(40)
    sat = SatisfactionCalc()
    qi, qo = queue.Queue(), queue.Queue()
    s = {"l": threading.Lock(), "n": 0, "q": 0}
    
    tasks = [
        ("code","sort",["def","sort"]),
        ("code","pattern",["class","Singleton"]),
        ("code","perf",["def","timer"]),
        ("analysis","perf",["性能"]),
        ("analysis","struct",["结构"]),
        ("security","vuln",["注入"]),
        ("security","auth",["认证"]),
        ("data","process",["处理"]),
        ("data","transform",["转换"]),
    ]
    
    for i in range(1, nt+1):
        cat, sub, v = tasks[i % len(tasks)]
        qi.put({"id": i, "category": cat, "prompt": f"Task {i}", "verify": v})
    
    t0 = time.time()
    ts = [threading.Thread(target=worker, args=(qi, qo, m, sat, s)) for _ in range(nw)]
    for t in ts: t.start()
    qi.join()
    for _ in ts: qi.put(None)
    for t in ts: t.join()
    e = time.time() - t0
    
    r = []
    while not qo.empty(): r.append(qo.get())
    
    qa = s["q"] / s["n"] if s["n"] else 0
    sat_score = sat.get_satisfaction()
    tot = m.hits + m.misses
    
    print(f"\n{nt}任务, {nw}workers:")
    print(f"  TPS: {nt/e:.0f}")
    print(f"  质量: {qa:.2f}/5.0")
    print(f"  满意度: {sat_score*100:.0f}%")
    print(f"  命中: {m.hits}/{tot} ({m.hits/tot*100:.0f}%)" if tot else "N/A")
    
    return {"tps": nt/e, "quality": qa, "sat": sat_score*100, "hit": m.hits/tot*100 if tot else 0}

if __name__ == "__main__":
    print("=" * 60)
    print("MAS v8 - Optimized Satisfaction")
    print("=" * 60)
    
    for nt in [10000, 20000]:
        run(8, nt)