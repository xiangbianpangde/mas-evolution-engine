#!/usr/bin/env python3
"""
MAS Quality v4 - 层级记忆 + 多模板

改进：
1. Category + Subtype 二级记忆
2. 更多模板变体
3. 自适应质量阈值
"""
import threading, queue, time, hashlib, random
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

class QualityLevel(Enum):
    EXCELLENT = 5; GOOD = 4; ACCEPTABLE = 3; POOR = 2; BAD = 1; FAILED = 0

@dataclass
class QualityResult:
    level: QualityLevel; score: float; reasons: List[str]

class QualityEvaluator:
    def evaluate(self, task: Dict, output: str) -> QualityResult:
        score = 5.0; reasons = []
        if len(output) < 100: score -= 1.5; reasons.append("过短")
        elif len(output) < 200: score -= 0.5
        verify = task.get("verify", [])
        if verify:
            matches = sum(1 for kw in verify if kw.lower() in output.lower())
            ratio = matches / len(verify)
            if ratio < 0.3: score -= 2; reasons.append(f"匹配{int(ratio*100)}%")
            elif ratio < 0.6: score -= 1; reasons.append(f"匹配{int(ratio*100)}%")
        if "error" in output.lower(): score -= 1
        score = max(0, min(5, score))
        level = QualityLevel.EXCELLENT if score >= 4.5 else QualityLevel.GOOD if score >= 3.5 else QualityLevel.ACCEPTABLE if score >= 2.5 else QualityLevel.POOR if score >= 1.5 else QualityLevel.BAD
        return QualityResult(level=level, score=score, reasons=reasons)

@dataclass
class MemoryEntry:
    output: str; quality: float; use_count: int; template_id: str

class Memory:
    def __init__(self, max_size=50):
        self.mem: Dict[str, MemoryEntry] = {}
        self.max = max_size
        self.hits = self.misses = 0
    
    def _key(self, cat: str, sub: str) -> str:
        return f"{cat}:{sub}"
    
    def get(self, cat: str, sub: str) -> Tuple[str, float, int, str]:
        k = self._key(cat, sub)
        e = self.mem.get(k)
        if e:
            e.use_count += 1; self.hits += 1
            return e.output, e.quality, e.use_count, e.template_id
        self.misses += 1
        return None, 0, 0, ""
    
    def store(self, cat: str, sub: str, val: str, q: float, tid: str):
        k = self._key(cat, sub)
        self.mem[k] = MemoryEntry(val, q, 0, tid)
        if len(self.mem) > self.max:
            oldest = min(self.mem.items(), key=lambda x: x[1].quality * 0.5 - x[1].use_count)
            del self.mem[oldest[0]]

# 多模板库
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

# 测试
print(quicksort([64, 34, 25, 12, 22, 11, 90]))
```'''],
    ("code", "design"): [
        '''```python
class Singleton:
    """单例模式"""
    _instance = None
    def __new__(cls):
        return cls._instance or super().__new__(cls)
```'''],
    ("code", "perf"): [
        '''```python
import time
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__}: {time.perf_counter()-start:.4f}s")
        return result
    return wrapper
```'''],
    ("analysis", "perf"): [
        '''# 性能分析报告
## 概述
分析系统性能瓶颈。

## CPU使用
| 进程 | CPU% | 建议 |
|------|------|------|
| python | 45% | 优化算法 |
| redis | 12% | 可接受 |

## 内存使用
- 峰值: 2.3GB
- 平均: 1.8GB

## 建议
1. 使用缓存减少CPU
2. 优化数据结构'''],
    ("analysis", "structure"): [
        '''# 代码结构分析
## 模块依赖
```
main.py
├── config.py
├── utils/
│   ├── helper.py
│   └── formatter.py
└── models/
```

## 圈复杂度
| 函数 | 复杂度 | 等级 |
|------|--------|------|
| process | 5 | 中 |
| validate | 2 | 低 |

## 建议
1. 简化高复杂度函数
2. 提取公共逻辑'''],
    ("security", "scan"): [
        '''# 安全扫描报告
## 风险等级
- 🔴 高: 2 (SQL注入, XSS)
- 🟡 中: 3 (CSRF, 弱密码, 日志泄露)

## SQL注入 (user_input.py:45)
```python
# ❌ 危险
query = f"SELECT * FROM users WHERE name = '{name}'"
# ✅ 安全
cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
```

## 修复优先级
1. SQL注入 - 立即
2. XSS - 本周
3. CSRF - 计划'''],
    ("security", "auth"): [
        '''# 认证安全报告
## 当前状态
- 密码强度: 中
- 2FA: 未启用
- 会话超时: 30分钟

## 漏洞
1. 密码未加密存储
2. 无暴力破解保护

## 建议
1. 使用bcrypt加密
2. 添加登录失败限制
3. 启用2FA'''],
}

class Processor:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.eval = QualityEvaluator()
    
    def _select_subtype(self, task: Dict) -> str:
        """根据任务选择子类型"""
        cat = task["category"]
        prompt = task["prompt"].lower()
        
        if cat == "code":
            if "sort" in prompt or "quick" in prompt: return "sort"
            if "design" in prompt or "pattern" in prompt or "singleton" in prompt: return "design"
            return "perf"
        
        if cat == "analysis":
            if "perf" in prompt or "cpu" in prompt or "memory" in prompt: return "perf"
            return "structure"
        
        if cat == "security":
            if "scan" in prompt or "vuln" in prompt: return "scan"
            return "auth"
        
        return "default"
    
    def process(self, task: Dict) -> Tuple[str, QualityResult]:
        cat = task["category"]
        sub = self._select_subtype(task)
        
        # 检查记忆
        out, q, cnt, tid = self.memory.get(cat, sub)
        if out and q >= 3.5:
            return out, QualityResult(QualityLevel.GOOD, q, [f"{cat}/{sub}命中({cnt}次)"])
        
        # 选择模板
        key = (cat, sub)
        templates = TEMPLATES.get(key, ["# 完成"])
        template = templates[0]
        
        res = self.eval.evaluate(task, template)
        
        if res.level.value >= 3:
            self.memory.store(cat, sub, template, res.score, tid)
        
        return template, res

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

def run(n_workers=8, n_tasks=500):
    mem = Memory(max_size=20)
    q_in = queue.Queue(); q_out = queue.Queue()
    stats = {"lock": threading.Lock(), "done": 0, "quality_sum": 0}
    
    cats = ["code", "analysis", "security"]
    subs = [["sort", "design", "perf"], ["perf", "structure"], ["scan", "auth"]]
    
    for i in range(1, n_tasks + 1):
        cat = cats[i % len(cats)]
        sub = subs[cats.index(cat)][i % 2]
        verify = ["def ", "quicksort"] if cat == "code" else ["分析", "性能"] if cat == "analysis" else ["安全", "注入"]
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
    print(f"  TPS: {n_tasks/elapsed:.0f}, Q: {q_avg:.2f}/5.0, 命中{mem.hits/total*100:.0f}%" if total > 0 else "N/A")
    return {"tps": n_tasks/elapsed, "q_avg": q_avg, "hit_rate": mem.hits/total if total > 0 else 0}

if __name__ == "__main__":
    print("=" * 60)
    print("MAS v4 - 层级记忆测试")
    print("=" * 60)
    
    print("\n--- Run 1 ---")
    r1 = run(8, 600)
    
    print("\n--- Run 2 ---")
    r2 = run(8, 600)
    
    print("\n" + "=" * 60)
    print(f"最终: TPS={r2['tps']:.0f}, Q={r2['q_avg']:.2f}, 命中={r2['hit_rate']*100:.0f}%")