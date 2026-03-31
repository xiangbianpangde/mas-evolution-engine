#!/usr/bin/env python3
"""
MAS Final - 集成用户满意度反馈

将模拟用户满意度直接集成到MAS系统中
"""
import threading, queue, time, hashlib, random
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

class QualityLevel(Enum):
    EXCELLENT = 5; GOOD = 4; ACCEPTABLE = 3; POOR = 2; BAD = 1

@dataclass
class QualityResult:
    level: QualityLevel; score: float; reasons: List[str]

class QualityEvaluator:
    def evaluate(self, task: Dict, output: str) -> QualityResult:
        score = 5.0; reasons = []
        if len(output) < 80: score -= 2; reasons.append("过短")
        elif len(output) < 150: score -= 0.5
        verify = task.get("verify", [])
        if verify:
            matches = sum(1 for kw in verify if kw.lower() in output.lower())
            ratio = matches / len(verify)
            if ratio < 0.25: score -= 2; reasons.append(f"匹配{int(ratio*100)}%")
            elif ratio < 0.5: score -= 1
        if "error" in output.lower(): score -= 1
        score = max(0, min(5, score))
        level = QualityLevel.EXCELLENT if score >= 4.5 else QualityLevel.GOOD if score >= 3.5 else QualityLevel.ACCEPTABLE if score >= 2.5 else QualityLevel.POOR if score >= 1.5 else QualityLevel.BAD
        return QualityResult(level=level, score=score, reasons=reasons)

class UserSimulator:
    """模拟用户满意度反馈"""
    def __init__(self):
        self.satisfaction = 1.0
        self.history = []
    
    def evaluate(self, quality_score: float, latency: float) -> float:
        """根据质量分数和延迟计算满意度"""
        sat = quality_score / 5.0
        
        # 延迟惩罚
        if latency > 1.0:
            sat *= 0.9
        elif latency > 0.5:
            sat *= 0.95
        
        # 累积
        self.history.append(sat)
        if len(self.history) > 10:
            self.history.pop(0)
        
        self.satisfaction = sum(self.history) / len(self.history)
        return self.satisfaction
    
    def feedback(self, improvement: str):
        """处理用户反馈"""
        if improvement == "better":
            self.satisfaction = min(1.0, self.satisfaction + 0.05)
        elif improvement == "worse":
            self.satisfaction = max(0.0, self.satisfaction - 0.1)
        self.history.append(self.satisfaction)

@dataclass
class MemoryEntry:
    outputs: List[str]; quality: float; use_counts: List[int]; current_idx: int

class Memory:
    def __init__(self, max_size=30):
        self.mem: Dict[str, MemoryEntry] = {}
        self.max = max_size
        self.hits = self.misses = 0
    
    def get(self, cat: str, sub: str) -> Tuple[str, float, int]:
        key = f"{cat}:{sub}"
        e = self.mem.get(key)
        if e and e.outputs:
            idx = e.current_idx
            e.current_idx = (e.current_idx + 1) % len(e.outputs)
            e.use_counts[idx] += 1
            self.hits += 1
            return e.outputs[idx], e.quality, sum(e.use_counts)
        self.misses += 1
        return None, 0, 0
    
    def store(self, cat: str, sub: str, outputs: List[str], q: float):
        key = f"{cat}:{sub}"
        if key in self.mem:
            e = self.mem[key]
            if len(e.outputs) < 3:
                e.outputs.append(outputs[0])
                e.use_counts.append(0)
        else:
            self.mem[key] = MemoryEntry(outputs, q, [0] * len(outputs), 0)
            if len(self.mem) > self.max:
                oldest = min(self.mem.items(), key=lambda x: sum(x[1].use_counts))
                del self.mem[oldest[0]]

TEMPLATES = {
    ("code", "sort"): [
        '''```python
def quicksort(arr):
    if len(arr) <= 1: return arr
    pivot = arr[len(arr)//2]
    return quicksort([x for x in arr if x < pivot]) + \\
           [x for x in arr if x == pivot] + \\
           quicksort([x for x in arr if x > pivot])
print(quicksort([64, 34, 25, 12, 22, 11, 90]))
```''',
        '''```python
def merge_sort(lst):
    if len(lst) <= 1: return lst
    mid = len(lst) // 2
    return merge(merge_sort(lst[:mid]), merge_sort(lst[mid:]))
def merge(a, b):
    return sorted(a + b)
print(merge_sort([64, 34, 25, 12]))
```'''
    ],
    ("code", "pattern"): [
        '''```python
class Singleton:
    _instance = None
    def __new__(cls):
        return cls._instance or super().__new__(cls)
```''',
        '''```python
class Registry(type):
    _registry = {}
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        Registry._registry[name] = cls
        return cls
```'''
    ],
    ("code", "perf"): [
        '''```python
import time
def timer(func):
    def wrapper(*args, **kwargs):
        s = time.perf_counter()
        r = func(*args, **kwargs)
        print(f"{func.__name__}: {time.perf_counter()-s:.4f}s")
        return r
    return wrapper
```''',
        '''```python
from functools import lru_cache
@lru_cache(maxsize=128)
def calc(n): return n * n if n > 0 else 0
```'''
    ],
    ("analysis", "perf"): [
        '''# 性能分析
## CPU: 45% | 内存: 2.3GB
## 延迟: P99=150ms
建议: 1.缓存 2.批量I/O 3.减少分配''',
        '''# 性能报告
瓶颈: DB查询45%, 序列化20%
优化: 连接池, 批量操作'''
    ],
    ("analysis", "structure"): [
        '''# 结构分析
模块: main→config, main→utils
复杂度: process=5, validate=2
建议: 拆分高复杂度函数''',
        '''# 代码审查
依赖: main→utils
改进: 减少耦合, 添加抽象'''
    ],
    ("security", "vuln"): [
        '''# 安全扫描
🔴SQL注入: user_input.py:45
🔴XSS: template.py:78
修复: 参数化查询'''
    ],
    ("security", "auth"): [
        '''# 认证审计
风险: 中 | 2FA: 否
漏洞: 无暴力保护
建议: bcrypt, 限制登录'''
    ],
}

class Processor:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.eval = QualityEvaluator()
    
    def subtype(self, task: Dict) -> str:
        cat, prompt = task["category"], task["prompt"].lower()
        if cat == "code":
            return "sort" if any(w in prompt for w in ["sort", "quick"]) else "pattern" if any(w in prompt for w in ["pattern", "singleton"]) else "perf"
        if cat == "analysis":
            return "perf" if any(w in prompt for w in ["perf", "cpu"]) else "structure"
        if cat == "security":
            return "vuln" if any(w in prompt for w in ["vuln", "scan"]) else "auth"
        return "default"
    
    def process(self, task: Dict) -> Tuple[str, QualityResult]:
        cat, sub = task["category"], self.subtype(task)
        
        out, q, cnt = self.memory.get(cat, sub)
        if out and q >= 3.0:
            return out, QualityResult(QualityLevel.GOOD, q, [f"{cat}/{sub}命中"])
        
        key = (cat, sub)
        templates = TEMPLATES.get(key, ["# 完成"])
        out = random.choice(templates)
        
        res = self.eval.evaluate(task, out)
        if res.level.value >= 3:
            self.memory.store(cat, sub, templates, res.score)
        
        return out, res

def worker(q_in, q_out, mem, stats, user):
    proc = Processor(mem)
    while True:
        try:
            t = q_in.get(timeout=0.1)
            if t is None: break
            t0 = time.time()
            out, res = proc.process(t)
            latency = time.time() - t0
            
            with stats["lock"]:
                stats["done"] += 1
                stats["quality_sum"] += res.score
                stats["latency_sum"] += latency
            
            # 更新用户满意度
            sat = user.evaluate(res.score, latency)
            
            q_out.put({"id": t["id"], "q": res.score, "lvl": res.level.name, "lat": latency, "sat": sat})
            q_in.task_done()
        except queue.Empty: continue

def run(n_workers, n_tasks):
    memory = Memory(max_size=20)
    q_in = queue.Queue(); q_out = queue.Queue()
    stats = {"lock": threading.Lock(), "done": 0, "quality_sum": 0, "latency_sum": 0}
    user = UserSimulator()
    
    tasks = [
        ("code", "sort", ["def", "sort"]),
        ("code", "pattern", ["class", "Singleton"]),
        ("code", "perf", ["def", "timer"]),
        ("analysis", "perf", ["性能", "CPU"]),
        ("analysis", "structure", ["结构"]),
        ("security", "vuln", ["注入"]),
        ("security", "auth", ["认证"]),
    ]
    
    for i in range(1, n_tasks + 1):
        cat, sub, verify = tasks[i % len(tasks)]
        q_in.put({"id": i, "category": cat, "prompt": f"Task {i}", "verify": verify})
    
    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(q_in, q_out, memory, stats, user)) for _ in range(n_workers)]
    for t in threads: t.start()
    q_in.join()
    for _ in threads: q_in.put(None)
    for t in threads: t.join()
    elapsed = time.time() - t0
    
    results = []
    while not q_out.empty(): results.append(q_out.get())
    
    q_avg = stats["quality_sum"] / stats["done"] if stats["done"] else 0
    lat_avg = stats["latency_sum"] / stats["done"] if stats["done"] else 0
    dist = {}
    for r in results: dist[r["lvl"]] = dist.get(r["lvl"], 0) + 1
    
    total = memory.hits + memory.misses
    
    return {
        "tps": n_tasks/elapsed,
        "quality": q_avg,
        "latency": lat_avg,
        "hit_rate": memory.hits / total * 100 if total > 0 else 0,
        "satisfaction": user.satisfaction * 100,
        "dist": dist
    }

if __name__ == "__main__":
    print("=" * 60)
    print("MAS Final - 集成用户满意度")
    print("=" * 60)
    
    tests = [(8, 1000), (8, 5000), (16, 10000)]
    for n_w, n_t in tests:
        r = run(n_w, n_t)
        print(f"\n{n_t}任务, {n_w}workers:")
        print(f"  TPS: {r['tps']:.0f}")
        print(f"  质量: {r['quality']:.2f}/5.0")
        print(f"  延迟: {r['latency']*1000:.1f}ms")
        print(f"  记忆: {r['hit_rate']:.0f}%")
        print(f"  用户满意度: {r['satisfaction']:.0f}%")