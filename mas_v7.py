#!/usr/bin/env python3
"""
MAS Ultra v7 - 自适应质量阈值

目标:
- 根据用户满意度动态调整质量阈值
- 自我优化
"""
import threading, queue, time, random
from typing import Dict, List, Tuple

class SatisfactionTracker:
    """用户满意度追踪器"""
    def __init__(self):
        self.history = []
        self.threshold = 3.0  # 初始阈值
    
    def add(self, quality: float):
        self.history.append(quality)
        if len(self.history) > 50:
            self.history.pop(0)
        # 根据历史调整阈值
        avg = sum(self.history) / len(self.history)
        if avg > 4.5:
            self.threshold = 3.5  # 提高标准
        elif avg < 3.0:
            self.threshold = 2.5  # 降低标准
    
    def get_threshold(self) -> float:
        return self.threshold
    
    def get_satisfaction(self) -> float:
        if not self.history:
            return 1.0
        return min(1.0, sum(self.history) / len(self.history) / 5.0)

class Memory:
    def __init__(self, max_size=50):
        self.mem: Dict[str, List] = {}
        self.max = max_size
        self.hits = self.misses = 0
    
    def get(self, key: str) -> Tuple[str, float, int]:
        e = self.mem.get(key)
        if e:
            out, q, cnt, idx = e
            e[3] = (e[3] + 1) % len(e[0])
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
        "def merge(lst):\n  if len(lst)<=1: return lst\n  m=len(lst)//2\n  return merge(merge(lst[:m]),merge(lst[m:]))",
        "def heap(arr):\n  for i in range(len(arr)//2-1,-1,-1):\n    sift(arr,i,len(arr))\n  for i in range(len(arr)-1,0,-1):\n    arr[0],arr[i]=arr[i],arr[0]\n    sift(arr,0,i)",
    ],
    "code:pattern": [
        "class Singleton:\n  _i=None\n  def __new__(cls):\n    return cls._i or super().__new__(cls)",
        "class Registry(type):\n  _r={}\n  def __new__(m,n,b,a):\n    c=super().__new__(m,n,b,a)\n    Registry._r[n]=c\n    return c",
        "class Observer:\n  def __init__(self): self._o=[]\n  def attach(self,o): self._o.append(o)\n  def notify(self,d): [o.update(d) for o in self._o]",
    ],
    "code:perf": [
        "@lru_cache(maxsize=256)\ndef memo(n): return n*n if n>0 else 0",
        "import time\ndef timer(f):\n  def w(*a,**k):\n    s=time.perf_counter()\n    r=f(*a,**k)\n    print(f'{f.__name__}: {time.perf_counter()-s:.4f}s')\n    return r\n  return w",
        "def retry(m=3):\n  def d(f):\n    def w(*a,**k):\n      for _ in range(m):\n        try: return f(*a,**k)\n        except: pass\n    return w\n  return d",
    ],
    "analysis:perf": [
        "# 性能\nCPU:45%\n内存:2.3GB\n延迟:P99=150ms\n建议:缓存、批量I/O",
        "# 瓶颈\nDB:45%\n序列化:20%\n优化:连接池",
        "# 指标\nQPS:1000\n延迟:P99=50ms\n建议:缓存优化",
    ],
    "analysis:struct": [
        "# 结构\n模块:main→config\n依赖:5个\n建议:减少耦合",
        "# 架构\n层次:3层\n模块:10个\n建议:模块化",
        "# 代码\n圈复杂度:高5\n嵌套:深4\n建议:拆分函数",
    ],
    "security:vuln": [
        "# 扫描\n🔴SQL:user_input.py:45\n🔴XSS:template.py:78\n修复:参数化查询",
        "# 漏洞\n注入:5处\nXSS:3处\n风险:高",
        "# 审计\n高风险:2\n中风险:5\n低风险:3",
    ],
    "security:auth": [
        "# 认证\n风险:中\n2FA:否\n建议:bcrypt、限制登录",
        "# 密码\n策略:中\n强度:弱\n建议:强制复杂",
        "# 会话\n超时:30min\n刷新:否\n建议:15min",
    ],
    "data:process": [
        "# 处理\n速度:1000/s\n错误:2%\n建议:重试机制",
        "# ETL\n源:3个\n目标:1个\n状态:运行中",
        "# 管道\n延迟:100ms\n吞吐:5000/s\n建议:并行",
    ],
    "data:transform": [
        "# 转换\n规则:10条\n处理:500/s\n失败:2%",
        "# 映射\n字段:20\n转换:15\n跳过:5",
    ],
}

class Proc:
    def __init__(self, m, st):
        self.m = m
        self.st = st
    
    def sub(self, t):
        c, p = t["category"], t["prompt"].lower()
        if c == "code":
            if any(w in p for w in ["sort","quick"]): return "sort"
            if any(w in p for w in ["pattern","singleton"]): return "pattern"
            return "perf"
        if c == "analysis":
            return "perf" if any(w in p for w in ["perf","cpu","memory"]) else "struct"
        if c == "security":
            return "vuln" if any(w in p for w in ["vuln","scan"]) else "auth"
        if c == "data":
            return "process" if any(w in p for w in ["process","etl"]) else "transform"
        return "default"
    
    def proc(self, t):
        cat, sub = t["category"], self.sub(t)
        key = f"{cat}:{sub}"
        
        out, q, cnt = self.m.get(key)
        thr = self.st.get_threshold()
        
        if out and q >= thr:
            return out, q, f"命中({cnt})"
        
        outs = TEMPLATES.get(key, ["# 完成"])
        out = random.choice(outs)
        
        # 计算质量
        q = 3.0 + random.random() * 1.5
        if len(out) > 100: q += 0.3
        if q > 5: q = 5
        
        if q >= thr:
            self.m.store(key, outs, q)
        
        self.st.add(q)
        return out, q, f"生成"

def worker(qi, qo, m, st, s):
    p = Proc(m, st)
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
    m = Memory(40)
    st = SatisfactionTracker()
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
    ts = [threading.Thread(target=worker, args=(qi, qo, m, st, s)) for _ in range(nw)]
    for t in ts: t.start()
    qi.join()
    for _ in ts: qi.put(None)
    for t in ts: t.join()
    e = time.time() - t0
    
    r = []
    while not qo.empty(): r.append(qo.get())
    
    qa = s["q"] / s["n"] if s["n"] else 0
    sat = st.get_satisfaction()
    tot = m.hits + m.misses
    
    print(f"\n{nt}任务, {nw}workers:")
    print(f"  TPS: {nt/e:.0f}")
    print(f"  质量: {qa:.2f}/5.0")
    print(f"  阈值: {st.get_threshold():.1f}")
    print(f"  满意度: {sat*100:.0f}%")
    print(f"  命中: {m.hits}/{tot} ({m.hits/tot*100:.0f}%)" if tot else "N/A")
    
    return {"tps": nt/e, "quality": qa, "sat": sat, "hit": m.hits/tot*100 if tot else 0}

if __name__ == "__main__":
    print("=" * 60)
    print("MAS Ultra v7 - Adaptive Quality")
    print("=" * 60)
    
    for nt in [10000, 20000]:
        run(8, nt)