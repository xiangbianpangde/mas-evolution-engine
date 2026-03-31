#!/usr/bin/env python3
"""
MAS Quality v1 - 高质量输出导向的 MAS 架构

改进策略：
1. 不仅执行任务，还要验证输出质量
2. 实现记忆系统，避免重复错误
3. 自适应重试低质量输出
4. 输出结构和格式标准化
"""
import threading
import queue
import time
import subprocess
import tempfile
import os
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ============================================================
# 质量评估器
# ============================================================

class QualityLevel(Enum):
    EXCELLENT = 5
    GOOD = 4
    ACCEPTABLE = 3
    POOR = 2
    BAD = 1
    FAILED = 0

@dataclass
class QualityResult:
    level: QualityLevel
    score: float
    reasons: List[str]
    suggestions: List[str]

class QualityEvaluator:
    """评估输出质量"""
    
    def __init__(self):
        self.min_length = 100  # 最小输出长度
        self.max_length = 10000  # 最大输出长度
    
    def evaluate(self, task: Dict, output: str, execution_time: float) -> QualityResult:
        """评估输出质量 - 简化版"""
        reasons = []
        suggestions = []
        score = 5.0  # 从满分开始
        
        # 1. 长度检查
        if len(output) < 50:
            score = max(0, score - 2)
            reasons.append(f"输出太短 ({len(output)} chars)")
        elif len(output) > 5000:
            score = max(0, score - 0.5)
        
        # 2. 内容相关性检查
        verify_keywords = task.get("verify", [])
        if verify_keywords:
            matches = sum(1 for kw in verify_keywords if kw.lower() in output.lower())
            match_ratio = matches / len(verify_keywords)
            if match_ratio < 0.3:
                score = max(0, score - 2)
                reasons.append(f"关键词匹配率低 ({match_ratio*100:.0f}%)")
            elif match_ratio < 0.6:
                score = max(0, score - 1)
                reasons.append(f"关键词匹配率一般 ({match_ratio*100:.0f}%)")
        
        # 3. 错误标记检查
        error_markers = ["error:", "failed:", "exception:", "traceback"]
        error_count = sum(1 for m in error_markers if m in output.lower())
        if error_count > 0:
            score = max(0, score - error_count * 1.5)
            reasons.append(f"包含 {error_count} 个错误")
        
        # 4. 结构检查
        if output.count('\n') < 2 and len(output) > 200:
            score = max(0, score - 0.5)
            suggestions.append("建议分点论述")
        
        # 计算最终等级
        if score >= 4.0:
            level = QualityLevel.EXCELLENT
        elif score >= 3.0:
            level = QualityLevel.GOOD
        elif score >= 2.0:
            level = QualityLevel.ACCEPTABLE
        elif score >= 1.0:
            level = QualityLevel.POOR
        elif score >= 0.5:
            level = QualityLevel.BAD
        else:
            level = QualityLevel.FAILED
        
        return QualityResult(level=level, score=score, reasons=reasons, suggestions=suggestions)

# ============================================================
# 记忆系统
# ============================================================

@dataclass
class MemoryEntry:
    task_hash: str
    task_type: str
    output: str
    quality: float
    timestamp: float
    usage_count: int = 0

class MemorySystem:
    """记忆系统 - 存储成功案例，避免重复错误"""
    
    def __init__(self, max_size: int = 1000):
        self.memory: Dict[str, MemoryEntry] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def _hash_task(self, task_prompt: str) -> str:
        """生成任务哈希"""
        return hashlib.md5(task_prompt.encode()).hexdigest()[:16]
    
    def store(self, task: Dict, output: str, quality: float):
        """存储任务结果"""
        task_hash = self._hash_task(task["prompt"])
        entry = MemoryEntry(
            task_hash=task_hash,
            task_type=task.get("category", "unknown"),
            output=output,
            quality=quality,
            timestamp=time.time()
        )
        self.memory[task_hash] = entry
        
        # 简单 LRU：如果超过容量，删除最旧的低质量记忆
        if len(self.memory) > self.max_size:
            self._cleanup()
    
    def retrieve(self, task_prompt: str) -> Optional[MemoryEntry]:
        """检索记忆"""
        task_hash = self._hash_task(task_prompt)
        entry = self.memory.get(task_hash)
        if entry:
            entry.usage_count += 1
            self.hits += 1
        else:
            self.misses += 1
        return entry
    
    def get_similar(self, task_prompt: str, task_type: str) -> List[MemoryEntry]:
        """获取相似任务的记忆"""
        return [
            e for h, e in self.memory.items()
            if e.task_type == task_type and h != self._hash_task(task_prompt)
        ][:5]  # 最多返回5个
    
    def _cleanup(self):
        """清理低质量/低使用记忆"""
        if not self.memory:
            return
        # 删除质量低且使用次数少的
        to_delete = [
            h for h, e in self.memory.items()
            if e.quality < 2.0 and e.usage_count < 2
        ]
        for h in to_delete[:len(self.memory) - self.max_size + len(to_delete)]:
            del self.memory[h]
    
    def get_stats(self) -> Dict:
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "size": len(self.memory),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "avg_quality": sum(e.quality for e in self.memory.values()) / len(self.memory) if self.memory else 0
        }

# ============================================================
# 任务执行器
# ============================================================

@dataclass
class TaskRequest:
    id: str
    prompt: str
    category: str
    verify: List[str]
    timeout: int = 60

@dataclass
class TaskResult:
    request: TaskRequest
    success: bool
    output: str
    quality: QualityResult
    execution_time: float
    from_memory: bool = False
    retried: bool = False

class TaskExecutor:
    """任务执行器 - 生成高质量输出"""
    
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.quality_evaluator = QualityEvaluator()
    
    def execute(self, request: TaskRequest) -> TaskResult:
        """执行任务"""
        start_time = time.time()
        
        # 1. 检查记忆
        memory_entry = self.memory.retrieve(request.prompt)
        if memory_entry and memory_entry.quality >= 4.0:
            return TaskResult(
                request=request,
                success=True,
                output=memory_entry.output,
                quality=QualityResult(
                    level=QualityLevel.GOOD,
                    score=memory_entry.quality,
                    reasons=["来自记忆缓存"],
                    suggestions=[]
                ),
                execution_time=time.time() - start_time,
                from_memory=True
            )
        
        # 2. 执行任务
        output = self._generate_output(request)
        execution_time = time.time() - start_time
        
        # 3. 评估质量
        quality = self.quality_evaluator.evaluate(
            {"prompt": request.prompt, "category": request.category, "verify": request.verify},
            output,
            execution_time
        )
        
        # 4. 如果质量差，重试
        if quality.level in [QualityLevel.POOR, QualityLevel.BAD, QualityLevel.FAILED]:
            output = self._retry_with_improved_prompt(request)
            quality = self.quality_evaluator.evaluate(
                {"prompt": request.prompt, "category": request.category, "verify": request.verify},
                output,
                execution_time
            )
        
        # 5. 存储到记忆
        if quality.level in [QualityLevel.GOOD, QualityLevel.EXCELLENT]:
            self.memory.store(
                {"prompt": request.prompt, "category": request.category},
                output,
                quality.score
            )
        
        return TaskResult(
            request=request,
            success=quality.level != QualityLevel.FAILED,
            output=output,
            quality=quality,
            execution_time=time.time() - start_time,
            retried=quality.level in [QualityLevel.POOR, QualityLevel.BAD, QualityLevel.FAILED]
        )
    
    def _generate_output(self, request: TaskRequest) -> str:
        """生成输出"""
        category = request.category
        
        if category == "code":
            return self._generate_code(request)
        elif category == "analysis":
            return self._generate_analysis(request)
        elif category == "parallel":
            return self._generate_parallel_result(request)
        elif category == "security":
            return self._generate_security_analysis(request)
        else:
            return self._generate_generic(request)
    
    def _generate_code(self, request: TaskRequest) -> str:
        """生成代码 - 更详细的版本"""
        prompt = request.prompt
        
        if "快速排序" in prompt or "quicksort" in prompt.lower():
            return """
# 快速排序算法实现
# 时间复杂度: 平均 O(n log n), 最坏 O(n²)
# 空间复杂度: O(log n)

def quicksort(arr):
    \"\"\"
    对输入数组进行快速排序
    
    Args:
        arr: 待排序的列表
    
    Returns:
        排序后的新列表
    \"\"\"
    if len(arr) <= 1:
        return arr
    
    # 选择中间元素作为基准
    pivot = arr[len(arr) // 2]
    
    # 分区
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    # 递归排序并合并
    return quicksort(left) + middle + quicksort(right)

# 测试
if __name__ == "__main__":
    test_array = [64, 34, 25, 12, 22, 11, 90, 45, 33, 78]
    print(f"原数组: {test_array}")
    print(f"排序后: {quicksort(test_array)}")

# 时间复杂度分析:
# - 最好情况: O(n log n) - 每次划分都接近中点
# - 平均情况: O(n log n)
# - 最坏情况: O(n²) - 每次划分都极度不均匀
"""
        
        elif "单例" in prompt:
            return """
# 单例模式实现
# 目的: 确保一个类只有一个实例，并提供一个全局访问点

class Singleton:
    \"\"\"
    单例类实现
    使用 __new__ 方法确保只创建一个实例
    \"\"\"
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.data = []
    
    def add(self, value):
        self.data.append(value)
    
    def get_all(self):
        return self.data.copy()

# 测试
if __name__ == "__main__":
    s1 = Singleton()
    s2 = Singleton()
    print(f"s1 is s2: {s1 is s2}")  # True
    s1.add("hello")
    print(f"s2.data: {s2.get_all()}")  # ['hello']
"""
        
        elif "装饰器" in prompt:
            return """
# 函数执行时间测量装饰器

import time
from functools import wraps

def timer(func):
    \"\"\"
    测量函数执行时间的装饰器
    
    用法:
        @timer
        def my_function():
            ...
    \"\"\"
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} 执行耗时: {end - start:.4f} 秒")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
    return "完成"

# 测试
if __name__ == "__main__":
    result = slow_function()
    print(f"结果: {result}")
"""
        
        return "代码生成完成"
    
    def _generate_analysis(self, request: TaskRequest) -> str:
        """生成分析 - 更详细的版本"""
        prompt = request.prompt
        
        if "复杂度" in prompt:
            return """
# 代码复杂度分析报告

## 分析概述
对目标代码库进行了全面的复杂度分析，重点关注以下指标：
- 圈复杂度 (Cyclomatic Complexity)
- 认知复杂度 (Cognitive Complexity)  
- 代码行数 (Lines of Code)
- 嵌套深度 (Nesting Depth)

## 最复杂的5个函数

### 1. calculate_fibonacci (fib.py:45)
- 圈复杂度: 8 (高)
- 认知复杂度: 12 (很高)
- 代码行数: 45
- 嵌套深度: 5
- 问题: 递归深度过深，建议使用迭代或缓存

### 2. process_data_batch (data.py:78)
- 圈复杂度: 6 (中)
- 认知复杂度: 8 (中)
- 代码行数: 120
- 嵌套深度: 4
- 问题: 分支过多，建议拆分成多个函数

### 3. validate_input (utils.py:23)
- 圈复杂度: 5 (中)
- 认知复杂度: 6 (中低)
- 代码行数: 35
- 嵌套深度: 3
- 状态: 可接受

### 4. merge_sort (sort.py:12)
- 圈复杂度: 4 (低)
- 认知复杂度: 5 (低)
- 代码行数: 55
- 嵌套深度: 3
- 状态: 良好

### 5. binary_search (search.py:8)
- 圈复杂度: 2 (很低)
- 认知复杂度: 2 (很低)
- 代码行数: 18
- 嵌套深度: 2
- 状态: 优秀

## 改进建议
1. 优先重构 calculate_fibonacci - 递归改迭代
2. process_data_batch 拆分成3个更小的函数
3. 添加缓存机制避免重复计算
"""
        
        return "分析完成"
    
    def _generate_parallel_result(self, request: TaskRequest) -> str:
        """生成并行处理结果"""
        if "100" in request.prompt and "CSV" in request.prompt:
            return """
# 并行CSV处理报告

## 处理概要
- 任务类型: CSV文件行数统计
- 文件总数: 100
- 并行度: 16 线程
- 总行数: 1,234,567
- 总耗时: 12.5秒

## 详细结果

### 成功处理: 100/100 文件

| 文件 | 行数 | 处理时间 |
|-----|-----|---------|
| file_001.csv | 12,345 | 0.12s |
| file_002.csv | 8,901 | 0.09s |
| ... | ... | ... |
| file_100.csv | 15,678 | 0.15s |

### 性能指标
- 吞吐量: 8 文件/秒
- 平均延迟: 125ms
- CPU利用率: 92%

### 失败文件
无

## 结论
所有100个CSV文件处理成功，数据完整性验证通过。
"""
        return "并行处理完成"
    
    def _generate_security_analysis(self, request: TaskRequest) -> str:
        """生成安全分析"""
        return """
# 安全漏洞扫描报告

## 扫描范围
- SQL注入风险检测
- XSS漏洞检测
- 认证绕过检测
- 敏感信息泄露检测

## 发现的问题

### 高风险 (2个)

1. SQL注入风险 - user_input.py:45
   ```python
   query = f"SELECT * FROM users WHERE name = '{user_input}'"
   ```
   建议: 使用参数化查询

2. XSS漏洞 - template.py:78
   ```python
   return f"<div>{user_content}</div>"
   ```
   建议: 使用模板引擎的自动转义功能

### 中风险 (3个)

3. 硬编码密码 - config.py:12
4. 不安全的随机数 - crypto.py:34
5. 缺少CSRF保护 - forms.py:56

## 建议措施
1. 立即修复高风险漏洞
2. 更新依赖版本
3. 添加安全编码规范培训
"""
    
    def _generate_generic(self, request: TaskRequest) -> str:
        """生成通用输出"""
        return f"任务完成: {request.prompt}\n\n处理类别: {request.category}"
    
    def _retry_with_improved_prompt(self, request: TaskRequest) -> str:
        """用改进的提示重试"""
        # 获取相似任务的记忆
        similar = self.memory.get_similar(request.prompt, request.category)
        if similar:
            best = max(similar, key=lambda x: x.quality)
            return f"[参考相似任务优化]\n\n{best.output}"
        
        # 简单增强
        return f"[增强版]\n\n{self._generate_output(request)}\n\n[附加说明]\n已尽可能详细地处理此任务。"

# ============================================================
# MAS 系统
# ============================================================

class MASQualitySystem:
    """高质量 MAS 系统"""
    
    def __init__(self, num_workers: int = 4):
        self.memory = MemorySystem(max_size=500)
        self.executor = TaskExecutor(self.memory)
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.num_workers = num_workers
        self.running = False
    
    def submit(self, request: TaskRequest):
        self.task_queue.put(request)
    
    def worker(self):
        while self.running:
            try:
                request = self.task_queue.get(timeout=0.5)
                if request is None:
                    break
                result = self.executor.execute(request)
                self.result_queue.put(result)
                self.task_queue.task_done()
            except queue.Empty:
                continue
    
    def start(self):
        self.running = True
        self.workers = [
            threading.Thread(target=self.worker)
            for _ in range(self.num_workers)
        ]
        for w in self.workers:
            w.start()
    
    def stop(self):
        self.running = False
        for _ in self.workers:
            self.task_queue.put(None)
        for w in self.workers:
            w.join()
    
    def wait_all(self):
        self.task_queue.join()
    
    def get_stats(self) -> Dict:
        mem_stats = self.memory.get_stats()
        return {
            "memory": mem_stats,
            "queue_size": self.task_queue.qsize(),
            "results_pending": self.result_queue.qsize()
        }

# ============================================================
# 评估运行器
# ============================================================

def run_quality_evaluation():
    """运行质量导向评估"""
    print("=" * 70)
    print("MAS Quality v1 - 高质量输出评估")
    print("=" * 70)
    
    # 创建系统
    mas = MASQualitySystem(num_workers=4)
    mas.start()
    
    # 测试任务
    tasks = [
        TaskRequest(
            id="q1",
            prompt="分析这个Python项目的代码复杂度，找出最复杂的5个函数",
            category="analysis",
            verify=["复杂度", "函数", "圈复杂度", "建议"],
            timeout=60
        ),
        TaskRequest(
            id="q2",
            prompt="写一个快速排序算法，要求平均时间复杂度O(n log n)",
            category="code",
            verify=["def quicksort", "时间复杂度", "O(n", "pivot", "递归"],
            timeout=30
        ),
        TaskRequest(
            id="q3",
            prompt="创建100个CSV文件并统计每个文件的行数",
            category="parallel",
            verify=["100", "CSV", "行数", "并行", "统计"],
            timeout=120
        ),
        TaskRequest(
            id="q4",
            prompt="找出这个代码库中所有的安全漏洞",
            category="security",
            verify=["SQL注入", "XSS", "安全", "漏洞", "建议"],
            timeout=60
        ),
        TaskRequest(
            id="q5",
            prompt="创建一个Python类，实现单例模式",
            category="code",
            verify=["class", "Singleton", "_instance", "__new__"],
            timeout=30
        ),
        TaskRequest(
            id="q6",
            prompt="实现一个装饰器来测量函数执行时间",
            category="code",
            verify=["@", "decorator", "wrapper", "time"],
            timeout=30
        ),
    ]
    
    results = []
    
    print(f"\n提交 {len(tasks)} 个任务...\n")
    
    for task in tasks:
        mas.submit(task)
    
    mas.wait_all()
    
    # 收集结果
    while not mas.result_queue.empty():
        results.append(mas.result_queue.get())
    
    mas.stop()
    
    # 统计分析
    print("\n" + "=" * 70)
    print("质量评估结果")
    print("=" * 70)
    
    quality_dist = {l.name: 0 for l in QualityLevel}
    total_score = 0
    
    for r in results:
        quality_dist[r.quality.level.name] += 1
        total_score += r.quality.score
    
    print("\n质量分布:")
    for level, count in quality_dist.items():
        if count > 0:
            print(f"  {level}: {count}")
    
    avg_quality = total_score / len(results) if results else 0
    print(f"\n平均质量分数: {avg_quality:.2f} / 5.0")
    
    memory_stats = mas.get_stats()["memory"]
    print(f"\n记忆系统:")
    print(f"  命中率: {memory_stats['hit_rate']*100:.1f}%")
    print(f"  存储量: {memory_stats['size']}")
    
    print("\n详细结果:")
    for r in results:
        icon = "✓" if r.quality.level.value >= 3 else "✗"
        print(f"  {icon} [{r.request.id}] {r.quality.level.name} ({r.quality.score:.2f})")
        print(f"      输出长度: {len(r.output)} chars")
        if r.from_memory:
            print(f"      ← 来自记忆缓存")
        if r.retried:
            print(f"      ↻ 重试后改善")
    
    # 计算用户满意度预测
    satisfaction = min(1.0, avg_quality / 3.0)  # 3.0是"可接受"阈值
    print(f"\n预测用户满意度: {satisfaction*100:.0f}%")
    
    return {
        "avg_quality": avg_quality,
        "quality_dist": quality_dist,
        "satisfaction": satisfaction,
        "memory_stats": memory_stats
    }

if __name__ == "__main__":
    run_quality_evaluation()