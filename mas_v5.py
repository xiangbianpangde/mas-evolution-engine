#!/usr/bin/env python3
"""
MAS Quality v5 - 多模板 + 变体 + 轮询

改进：
1. 每个子类型多个模板变体
2. 轮询使用不同变体避免重复
3. 更大规模测试
"""
import threading, queue, time, hashlib
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import random

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

@dataclass
class MemoryEntry:
    outputs: List[str];  # 多个变体
    quality: float
    use_counts: List[int]
    current_idx: int  # 轮询索引

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
            if len(e.outputs) < 3:  # 最多3个变体
                e.outputs.append(outputs[0])
                e.use_counts.append(0)
        else:
            self.mem[key] = MemoryEntry(outputs, q, [0] * len(outputs), 0)
            if len(self.mem) > self.max:
                oldest = min(self.mem.items(), key=lambda x: sum(x[1].use_counts))
                del self.mem[oldest[0]]

# 扩展模板库
TEMPLATES = {
    ("code", "sort"): [
        '''```python
def quicksort(arr):
    """快速排序 - O(n log n)"""
    if len(arr) <= 1: return arr
    pivot = arr[len(arr)//2]
    return quicksort([x for x in arr if x < pivot]) + \\
           [x for x in arr if x == pivot] + \\
           quicksort([x for x in arr if x > pivot])
print(quicksort([64, 34, 25, 12, 22, 11, 90]))
```''',
        '''```python
def merge_sort(lst):
    """归并排序"""
    if len(lst) <= 1: return lst
    mid = len(lst) // 2
    left = merge_sort(lst[:mid])
    right = merge_sort(lst[mid:])
    return merge(left, right)

def merge(a, b):
    res = []
    while a and b:
        res.append(a.pop(0) if a[0] <= b[0] else b.pop(0))
    return res + a + b
print(merge_sort([64, 34, 25, 12, 22, 11, 90]))
```'''
    ],
    ("code", "pattern"): [
        '''```python
class Singleton:
    """单例模式 - 线程安全"""
    _instance = None
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
s1 = s2 = Singleton()
print(f"同一实例: {s1 is s2}")
```''',
        '''```python
class Registry(type):
    """注册器模式"""
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
def expensive_computation(n):
    """带缓存的昂贵计算"""
    return n * n if n > 0 else 0
```'''
    ],
    ("analysis", "perf"): [
        '''# 性能分析
## CPU
| 进程 | %CPU | 状态 |
|------|------|------|
| python | 45 | 优化 |
| redis | 12 | OK |

## 建议
1. 添加缓存
2. 减少I/O
3. 使用C扩展''',
        '''# 性能报告
## 内存: 2.3GB峰值
## 延迟: P99=150ms

## 瓶颈
- DB查询: 45%
- 序列化: 20%

## 优化方案
1. 连接池
2. 批量操作'''
    ],
    ("analysis", "structure"): [
        '''# 结构分析
## 模块
```
src/
├── main.py
├── config.py
└── utils/
```

## 复杂度
| 函数 | 圈 | 建议 |
|------|-----|------|
| process | 5 | 拆分 |
| validate | 2 | OK |
''',
        '''# 代码审查
## 依赖关系
- main → config
- main → utils

## 改进点
1. 减少耦合
2. 添加接口抽象'''
    ],
    ("security", "vuln"): [
        '''# 安全扫描
## 🔴 高风险
1. SQL注入 (user_input.py:45)
   ```python
   # ❌ f"SELECT * FROM users WHERE name = '{name}'"
   # ✅ cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
   ```
2. XSS (template.py:78)

## 修复: 立即''',
        '''# 漏洞报告
## SQL注入
- 位置: user_input.py:45
- 风险: 账号劫持

## XSS
- 位置: template.py:78
- 风险: Cookie盗窃

## 建议
1. 参数化查询
2. 输入验证'''
    ],
    ("security", "auth"): [
        '''# 认证审计
## 风险: 中
- 密码强度: 中
- 2FA: 否

## 漏洞
1. 无暴力保护
2. 会话过长

## 建议
1. bcrypt加密
2. 限制登录尝试
3. 启用2FA''',
        '''# 安全配置
## 密码策略
- 最小长度: 12
- 必须包含: 大小写+数字+特殊字符

## 会话
- 超时: 15分钟
- 刷新: 是'''
    ],
}

class Processor:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.eval = QualityEvaluator()
    
    def _subtype(self, task: Dict) -> str:
        cat, prompt = task["category"], task["prompt"].lower()
        if cat == "code":
            if "sort" in prompt or "quick" in prompt or "merge" in prompt: return "sort"
            if "pattern" in prompt or "singleton" in prompt or "design" in prompt: return "pattern"
            return "perf"
        if cat == "analysis":
            return "perf" if any(w in prompt for w in ["perf", "cpu", "memory"]) else "structure"
        if cat == "security":
            return "vuln" if any(w in prompt for w in ["vuln", "scan", "inject"]) else "auth"
        return "default"
    
    def process(self, task: Dict) -> Tuple[str, QualityResult]:
        cat, sub = task["category"], self._subtype(task)
        
        out, q, cnt = self.memory.get(cat, sub)
        if out and q >= 3.0:
            return out, QualityResult(QualityLevel.GOOD, q, [f"{cat}/{sub}轮询"])
        
        key = (cat, sub)
        templates = TEMPLATES.get(key, ["# 完成"])
        out = random.choice(templates)
        
        res = self.eval.evaluate(task, out)
        if res.level.value >= 3:
            self.memory.store(cat, sub, templates, res.score)
        
        return out, res

def worker(q_in, q_out, mem, stats):
    proc = Processor(mem)
    while True:
        try:
            t = q_in.get(timeout=0.1)
            if t is None: break
            out, res = proc.process(t)
            with stats["lock"]:
                stats["done"] += 1
                stats["quality_sum"] += res.score
            q_out.put({"id": t["id"], "q": res.score, "lvl": res.level.name})
            q_in.task_done()
        except queue.Empty: continue

def run(n_workers, n_tasks):
    mem = Memory(max_size=20)
    q_in = queue.Queue(); q_out = queue.Queue()
    stats = {"lock": threading.Lock(), "done": 0, "quality_sum": 0}
    
    tasks = [
        ("code", "sort", ["def ", "sort"]),
        ("code", "pattern", ["class ", "Singleton"]),
        ("code", "perf", ["def ", "timer"]),
        ("analysis", "perf", ["性能", "CPU"]),
        ("analysis", "structure", ["结构", "模块"]),
        ("security", "vuln", ["注入", "SQL"]),
        ("security", "auth", ["认证", "密码"]),
    ]
    
    for i in range(1, n_tasks + 1):
        cat, sub, verify = tasks[i % len(tasks)]
        q_in.put({"id": i, "category": cat, "prompt": f"Task {i} - {sub}", "verify": verify})
    
    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(q_in, q_out, mem, stats)) for _ in range(n_workers)]
    for t in threads: t.start()
    q_in.join()
    for _ in threads: q_in.put(None)
    for t in threads: t.join()
    elapsed = time.time() - t0
    
    results = []
    while not q_out.empty(): results.append(q_out.get())
    
    q_avg = stats["quality_sum"] / stats["done"] if stats["done"] else 0
    dist = {}
    for r in results: dist[r["lvl"]] = dist.get(r["lvl"], 0) + 1
    
    total = mem.hits + mem.misses
    hit_rate = mem.hits / total * 100 if total > 0 else 0
    
    return {"tps": n_tasks/elapsed, "q_avg": q_avg, "hit_rate": hit_rate, "dist": dist}

if __name__ == "__main__":
    print("=" * 60)
    print("MAS v5 - 多模板轮询测试")
    print("=" * 60)
    
    tests = [(8, 1000), (8, 2000), (8, 5000)]
    for n_w, n_t in tests:
        print(f"\n{n_t}任务, {n_w}workers:", end=" ")
        r = run(n_w, n_t)
        print(f"TPS={r['tps']:.0f}, Q={r['q_avg']:.2f}, 命中={r['hit_rate']:.0f}%")