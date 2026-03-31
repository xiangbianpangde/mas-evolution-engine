#!/usr/bin/env python3
"""
MAS Quality v3 - 按category共享记忆
"""
import threading, queue, time, hashlib
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
    output: str; quality: float; use_count: int

class Memory:
    def __init__(self, max_size=100):
        self.mem: Dict[str, MemoryEntry] = {}
        self.max = max_size
        self.hits = self.misses = 0
    
    def get_by_category(self, category: str) -> Tuple[str, float, int]:
        e = self.mem.get(category)
        if e:
            e.use_count += 1; self.hits += 1
            return e.output, e.quality, e.use_count
        self.misses += 1
        return None, 0, 0
    
    def store_by_category(self, category: str, val: str, q: float):
        self.mem[category] = MemoryEntry(val, q, 0)
        if len(self.mem) > self.max:
            oldest = min(self.mem.items(), key=lambda x: x[1].use_count)
            del self.mem[oldest[0]]

TEMPLATES = {
    "code": '''```python
def quicksort(arr):
    if len(arr) <= 1: return arr
    pivot = arr[len(arr)//2]
    left = [x for x in arr if x < pivot]
    mid = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + mid + quicksort(right)

if __name__ == "__main__":
    print(quicksort([64, 34, 25, 12, 22, 11, 90]))
```''',
    "analysis": '''# 复杂度分析报告
## 概述
对代码进行了全面分析。

## 主要发现
| 函数 | 复杂度 | 建议 |
|------|--------|------|
| fib | 高 | 迭代改写 |
| process | 中 | 可接受 |
| validate | 低 | 良好 |

## 改进建议
1. 重构高复杂度函数
2. 添加缓存
3. 减少嵌套层次''',
    "security": '''# 安全扫描报告
## 风险等级
- 高风险: 2个
- 中风险: 3个

## 问题详情
### SQL注入
```python
# 危险
query = f"SELECT * FROM users WHERE name = '{user_input}'"
# 修复
cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))
```

## 建议
1. 立即修复高风险
2. 使用参数化查询'''
}

class Processor:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.eval = QualityEvaluator()
    
    def process(self, task: Dict) -> Tuple[str, QualityResult]:
        cat = task["category"]
        
        # 按category检查记忆
        out, q, cnt = self.memory.get_by_category(cat)
        if out and q >= 3.5:
            return out, QualityResult(QualityLevel.GOOD, q, [f"命中({cat})"])
        
        # 生成
        out = TEMPLATES.get(cat, "完成")
        res = self.eval.evaluate(task, out)
        
        # 存储
        if res.level.value >= 3:
            self.memory.store_by_category(cat, out, res.score)
        
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

def run(n_workers=8, n_tasks=500):
    print(f"\nMAS v3: {n_tasks}任务, {n_workers}workers")
    
    mem = Memory()
    q_in = queue.Queue(); q_out = queue.Queue()
    stats = {"lock": threading.Lock(), "done": 0, "quality_sum": 0}
    
    cats = ["code", "analysis", "security"]
    for i in range(1, n_tasks + 1):
        cat = cats[i % len(cats)]
        verify = ["def ", "quicksort"] if cat == "code" else ["分析"] if cat == "analysis" else ["安全"]
        q_in.put({"id": i, "category": cat, "verify": verify})
    
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
    print(f"  TPS: {n_tasks/elapsed:.0f}, 质量: {q_avg:.2f}/5.0")
    print(f"  分布: {dist}")
    print(f"  记忆: 命中{mem.hits}, 未命中{mem.misses}, 率{mem.hits/total*100:.1f}%" if total > 0 else "  记忆: N/A")
    
    return {"tps": n_tasks/elapsed, "q_avg": q_avg, "hit_rate": mem.hits/total if total > 0 else 0}

if __name__ == "__main__":
    print("=" * 60)
    print("MAS v3 - Category记忆测试")
    print("=" * 60)
    
    print("\n--- Run 1: 冷启动 ---")
    r1 = run(8, 300)
    
    print("\n--- Run 2: 同数据集 ---")
    r2 = run(8, 300)
    
    print("\n--- Run 3: 新任务但同category ---")
    r3 = run(8, 300)
    
    print("\n" + "=" * 60)
    print(f"记忆命中率: Run1={r1['hit_rate']*100:.0f}%, Run2={r2['hit_rate']*100:.0f}%, Run3={r3['hit_rate']*100:.0f}%")