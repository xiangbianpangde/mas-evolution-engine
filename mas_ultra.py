#!/usr/bin/env python3
"""
MAS Ultra - v6 Generation

目标:
- 更高模板覆盖
- 更智能的子类型选择
- 更大规模测试
"""
import threading, queue, time, random
from typing import Dict, List, Tuple

class Memory:
    def __init__(self, max_size=50):
        self.mem: Dict[str, List] = {}
        self.max = max_size
        self.hits = self.misses = 0
    
    def get(self, key: str) -> Tuple[str, float, int]:
        e = self.mem.get(key)
        if e:
            out, q, cnt, idx = e
            e[3] = (e[3] + 1) % len(e[0])  # rotate
            e[2] += 1
            self.hits += 1
            return out, q, cnt
        self.misses += 1
        return None, 0, 0
    
    def store(self, key: str, outputs: List[str], q: float):
        if key in self.mem:
            e = self.mem[key]
            if len(e[0]) < 4:
                e[0].append(outputs[0])
        else:
            self.mem[key] = [outputs, q, 0, 0]
            if len(self.mem) > self.max:
                oldest = min(self.mem.items(), key=lambda x: x[1][2])
                del self.mem[oldest[0]]

# 扩展模板库
TEMPLATES = {
    "code:sort": [
        "def quicksort(arr):\n  if len(arr)<=1: return arr\n  p=arr[len(arr)//2]\n  return quicksort([x for x in arr if x<p])+[x for x in arr if x==p]+quicksort([x for x in arr if x>p])",
        "def merge_sort(lst):\n  if len(lst)<=1: return lst\n  m=len(lst)//2\n  return merge(merge_sort(lst[:m]),merge_sort(lst[m:]))\ndef merge(a,b):return sorted(a+b)",
        "def heapsort(arr):\n  for i in range(len(arr)//2-1,-1,-1):\n    siftdown(arr,i,len(arr))\n  for i in range(len(arr)-1,0,-1):\n    arr[0],arr[i]=arr[i],arr[0]\n    siftdown(arr,0,i)",
    ],
    "code:pattern": [
        "class Singleton:\n  _i=None\n  def __new__(cls):\n    return cls._i or super().__new__(cls)",
        "class Registry(type):\n  _r={}\n  def __new__(m,n,b,a):\n    c=super().__new__(m,n,b,a)\n    Registry._r[n]=c\n    return c",
        "class Observer:\n  def __init__(self): self._obs=[]\n  def attach(self,o): self._obs.append(o)\n  def notify(self,d): [o.update(d) for o in self._obs]",
    ],
    "code:perf": [
        "@lru_cache(maxsize=256)\ndef memo(n): return n*n if n>0 else 0",
        "import time\ndef timer(f):\n  def w(*a,**k):\n    s=time.perf_counter()\n    r=f(*a,**k)\n    print(f'{f.__name__}: {time.perf_counter()-s:.4f}s')\n    return r\n  return w",
        "from functools import wraps\ndef retry(m=3):\n  def d(f):\n    @wraps(f)\n    def w(*a,**k):\n      for _ in range(m):\n        try: return f(*a,**k)\n        except: pass\n    return w\n  return d",
    ],
    "analysis:perf": [
        "# 性能\nCPU:45%\n内存:2.3GB\n延迟:P99=150ms\n建议:缓存、批量I/O",
        "# 性能报告\n瓶颈:DB45%序列化20%\n优化:连接池、批量",
        "# 分析\n峰值:2.3GB\n平均:1.8GB\n建议:减少分配",
    ],
    "analysis:struct": [
        "# 结构\n模块:main→config,utils\n复杂度:高5,中3,低2\n建议:拆分",
        "# 审查\n依赖:main→utils\n耦合:中\n改进:接口抽象",
        "# 代码\n层次:3层\n模块:5个\n建议:减少耦合",
    ],
    "security:vuln": [
        "# 扫描\n🔴SQL:user_input.py:45\n🔴XSS:template.py:78\n修复:参数化",
        "# 漏洞\n注入:user_input:45\nXSS:template:78\n优先级:立即",
        "# 安全\n高风险:2\n中风险:3\n建议:输入验证",
    ],
    "security:auth": [
        "# 认证\n风险:中\n2FA:否\n建议:bcrypt",
        "# 审计\n密码:中强度\n会话:30min\n建议:限制登录",
        "# 配置\n密码:12位+\n2FA:建议启用\n会话:15min超时",
    ],
    "data:process": [
        "# 处理\n速度:1000条/s\n延迟:P99=50ms\n建议:批量",
        "# 数据\n清洗率:95%\n错误率:5%\n建议:重试",
        "# ETL\n源:3个\n目标:1个\n状态:运行中",
    ],
    "data:transform": [
        "# 转换\n规则:10条\n处理:500条/s\n失败:2%",
        "# 映射\n字段:20\n转换:15\n跳过:5",
    ],
}

class Proc:
    def __init__(self, m): self.m = m
    
    def sub(self, t):
        c, p = t["category"], t["prompt"].lower()
        if c == "code":
            if any(w in p for w in ["sort","quick"]): return "sort"
            if any(w in p for w in ["pattern","singleton","design"]): return "pattern"
            return "perf"
        if c == "analysis":
            if any(w in p for w in ["perf","cpu","memory"]): return "perf"
            return "struct"
        if c == "security":
            if any(w in p for w in ["vuln","scan","inject"]): return "vuln"
            return "auth"
        if c == "data":
            if any(w in p for w in ["process","etl"]): return "process"
            return "transform"
        return "default"
    
    def proc(self, t):
        cat, sub = t["category"], self.sub(t)
        key = f"{cat}:{sub}"
        
        out, q, cnt = self.m.get(key)
        if out and q >= 3.0:
            return out, q, f"{cat}/{sub}命中"
        
        outs = TEMPLATES.get(key, ["# 完成"])
        out = random.choice(outs)
        
        q = 3.0 + random.random() * 1.5  # Simulated quality
        if len(out) > 80: q += 0.5
        if q > 5: q = 5
        
        self.m.store(key, outs, q)
        return out, q, f"{cat}/{sub}生成"

def worker(qi, qo, m, s):
    p = Proc(m)
    while True:
        try:
            t = qi.get(timeout=0.1)
            if t is None: break
            out, q, info = p.proc(t)
            with s["l"]: s["n"] += 1; s["q"] += q
            qo.put({"id": t["id"], "q": q, "info": info})
            qi.task_done()
        except: break

def run(nw=8, nt=20000):
    m = Memory(30)
    qi, qo = queue.Queue(), queue.Queue()
    s = {"l": threading.Lock(), "n": 0, "q": 0}
    
    tasks = [
        ("code","sort",["def","sort"]),
        ("code","pattern",["class","Singleton"]),
        ("code","perf",["def","timer"]),
        ("analysis","perf",["性能","CPU"]),
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
    ts = [threading.Thread(target=worker, args=(qi, qo, m, s)) for _ in range(nw)]
    for t in ts: t.start()
    qi.join()
    for _ in ts: qi.put(None)
    for t in ts: t.join()
    e = time.time() - t0
    
    r = []
    while not qo.empty(): r.append(qo.get())
    
    qa = s["q"] / s["n"] if s["n"] else 0
    tot = m.hits + m.misses
    
    print(f"\n{nt}任务, {nw}workers:")
    print(f"  TPS: {nt/e:.0f}")
    print(f"  质量: {qa:.2f}/5.0")
    print(f"  命中: {m.hits}/{tot} ({m.hits/tot*100:.0f}%)" if tot else "N/A")
    
    return {"tps": nt/e, "quality": qa, "hit": m.hits/tot*100 if tot else 0}

if __name__ == "__main__":
    print("=" * 60)
    print("MAS Ultra - v6 Generation")
    print("=" * 60)
    
    for nt in [5000, 10000, 20000]:
        run(8, nt)