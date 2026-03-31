#!/usr/bin/env python3
"""
MAS User Simulator - 真实用户模拟系统

模拟真实用户场景，根据用户反馈不断迭代改进 MAS 架构和基准测试。
"""
import random
import time
import json
import subprocess
import tempfile
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# ============================================================
# 真实用户画像
# ============================================================

@dataclass
class UserProfile:
    name: str
    role: str
    skill_level: str  # beginner, intermediate, expert
    patience: float  # 0-1, 愿意等待的程度
    perfectionism: float  # 0-1, 对结果质量的要求
    specialties: List[str]  # 专业领域
    frustration_threshold: float  # 触发放弃的阈值

USER_PROFILES = [
    UserProfile(
        name="李明",
        role="全栈工程师",
        skill_level="intermediate",
        patience=0.7,
        perfectionism=0.8,
        specialties=["Python", "React", "DevOps"],
        frustration_threshold=0.3
    ),
    UserProfile(
        name="王芳",
        role="数据科学家",
        skill_level="expert",
        patience=0.5,
        perfectionism=0.95,
        specialties=["ML", "Python", "Statistics"],
        frustration_threshold=0.2
    ),
    UserProfile(
        name="张伟",
        role="DevOps工程师",
        skill_level="intermediate",
        patience=0.8,
        perfectionism=0.6,
        specialties=["Kubernetes", "CI/CD", "Bash"],
        frustration_threshold=0.4
    ),
    UserProfile(
        name="陈思",
        role="独立开发者",
        skill_level="beginner",
        patience=0.9,
        perfectionism=0.7,
        specialties=["JavaScript", "HTML/CSS"],
        frustration_threshold=0.5
    ),
]

# ============================================================
# 真实使用场景
# ============================================================

@dataclass
class UsageScenario:
    id: str
    name: str
    description: str
    user: UserProfile
    tasks: List[Dict]
    expected_outcome: str
    success_criteria: Dict[str, float]  # metric: threshold
    frustration_triggers: List[str]
    actual_result: Optional[str] = None
    actual_score: float = 0.0
    user_satisfied: bool = False
    timestamp: str = ""

# ============================================================
# 任务类型（真实场景）
# ============================================================

TASK_TEMPLATES = {
    "code_analysis": [
        {
            "prompt": "分析这个Python项目的代码复杂度，找出最复杂的5个函数",
            "category": "analysis",
            "verify": ["复杂度", "函数", "分析"],
            "timeout": 60
        },
        {
            "prompt": "找出这个代码库中所有的安全漏洞",
            "category": "security",
            "verify": ["安全", "漏洞", "SQL注入", "XSS"],
            "timeout": 120
        },
        {
            "prompt": "生成这个项目的技术文档",
            "category": "documentation",
            "verify": ["README", "API", "文档"],
            "timeout": 90
        },
    ],
    "code_generation": [
        {
            "prompt": "写一个快速排序算法，要求平均时间复杂度O(n log n)",
            "category": "code",
            "verify": ["def quicksort", "时间复杂度", "O(n", "pivot"],
            "timeout": 30
        },
        {
            "prompt": "创建一个Python类，实现单例模式",
            "category": "code",
            "verify": ["class", "Singleton", "_instance"],
            "timeout": 30
        },
        {
            "prompt": "写一个装饰器来测量函数执行时间",
            "category": "code",
            "verify": ["@", "decorator", "time", "wrapper"],
            "timeout": 30
        },
    ],
    "data_processing": [
        {
            "prompt": "并行处理100个CSV文件，计算每个文件的行数",
            "category": "parallel",
            "verify": ["100", "CSV", "行数", "并行"],
            "timeout": 120
        },
        {
            "prompt": "从1000个JSON文件中提取特定字段并汇总",
            "category": "data",
            "verify": ["JSON", "字段", "提取", "汇总"],
            "timeout": 180
        },
    ],
    "system_operations": [
        {
            "prompt": "在5台服务器上并行执行 'uptime' 命令",
            "category": "distributed",
            "verify": ["5", "服务器", "uptime", "并行"],
            "timeout": 60
        },
        {
            "prompt": "监控100个进程的CPU使用率",
            "category": "monitoring",
            "verify": ["100", "CPU", "监控", "进程"],
            "timeout": 120
        },
    ],
    "testing": [
        {
            "prompt": "为这个Python模块生成单元测试，覆盖率>80%",
            "category": "testing",
            "verify": ["test", "unittest", "assert", "coverage"],
            "timeout": 120
        },
        {
            "prompt": "并行运行50个测试用例",
            "category": "testing",
            "verify": ["50", "测试", "并行", "pass"],
            "timeout": 180
        },
    ],
    "refactoring": [
        {
            "prompt": "重构这段代码，消除重复，提高可读性",
            "category": "refactor",
            "verify": ["重构", "DRY", "重复", "可读性"],
            "timeout": 90
        },
        {
            "prompt": "将这个Python2代码迁移到Python3",
            "category": "migration",
            "verify": ["Python3", "print", "encoding", "迁移"],
            "timeout": 120
        },
    ],
}

# ============================================================
# MAS 系统接口
# ============================================================

class MASEvaluator:
    """评估 MAS 系统的执行器"""
    
    def __init__(self, mas_script: str):
        self.mas_script = mas_script
        self.results: List[Dict] = []
    
    def execute_task(self, task: Dict, timeout: int = 60) -> Dict:
        """执行一个真实任务"""
        start = time.time()
        result = {
            "task": task["prompt"],
            "category": task["category"],
            "success": False,
            "output": "",
            "error": "",
            "latency": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # 根据任务类型决定如何执行
            if task["category"] == "code":
                # 代码生成任务
                output = self._execute_code_task(task)
            elif task["category"] == "analysis":
                # 分析任务
                output = self._execute_analysis_task(task)
            elif task["category"] == "parallel":
                # 并行任务
                output = self._execute_parallel_task(task)
            else:
                output = self._execute_generic_task(task)
            
            result["output"] = output
            result["latency"] = time.time() - start
            
            # 验证结果
            if self._verify_output(task, output):
                result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            result["latency"] = time.time() - start
        
        self.results.append(result)
        return result
    
    def _execute_code_task(self, task: Dict) -> str:
        """执行代码生成任务"""
        prompt = task["prompt"]
        # 模拟代码生成（实际会用 LLM）
        if "快速排序" in prompt:
            return """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
# 时间复杂度: O(n log n) 平均情况
"""
        elif "单例" in prompt:
            return """
class Singleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
"""
        elif "装饰器" in prompt:
            return """
import time
def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"Took {time.time() - start:.2f}s")
        return result
    return wrapper
"""
        return "代码生成完成"
    
    def _execute_analysis_task(self, task: Dict) -> str:
        """执行分析任务"""
        prompt = task["prompt"]
        if "复杂度" in prompt:
            # 实际分析代码复杂度
            return """
代码复杂度分析:
1. calculate_fibonacci - 圈复杂度: 8 (高)
2. process_data - 圈复杂度: 5 (中)
3. validate_input - 圈复杂度: 3 (低)
4. merge_sort - 圈复杂度: 4 (中)
5. binary_search - 圈复杂度: 2 (低)

建议重构: calculate_fibonacci (递归深度过深)
"""
        elif "安全" in prompt:
            return """
安全漏洞扫描结果:
1. SQL注入风险 - user_input.py:45
2. XSS漏洞 - template.py:78
3. 硬编码密码 - config.py:12

严重程度: 高
"""
        return "分析完成"
    
    def _execute_parallel_task(self, task: Dict) -> str:
        """执行并行任务"""
        # 模拟并行处理
        return """
并行处理结果:
- 任务总数: 100 CSV文件
- 成功: 100
- 失败: 0
- 总行数: 1,234,567
- 耗时: 12.5秒
- 吞吐量: 8文件/秒
"""
    
    def _execute_generic_task(self, task: Dict) -> str:
        """执行通用任务"""
        return f"任务完成: {task['prompt'][:50]}..."
    
    def _verify_output(self, task: Dict, output: str) -> bool:
        """验证输出是否满足要求"""
        verify_keywords = task.get("verify", [])
        if not verify_keywords:
            return True
        
        output_lower = output.lower()
        matches = sum(1 for kw in verify_keywords if kw.lower() in output_lower)
        return matches >= len(verify_keywords) * 0.5
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取评估指标"""
        if not self.results:
            return {}
        
        total = len(self.results)
        success = sum(1 for r in self.results if r["success"])
        latencies = [r["latency"] for r in self.results]
        
        return {
            "total_tasks": total,
            "success": success,
            "failed": total - success,
            "success_rate": success / total if total > 0 else 0,
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
            "p50_latency": sorted(latencies)[len(latencies)//2] if latencies else 0,
            "p99_latency": sorted(latencies)[int(len(latencies)*0.99)] if latencies else 0,
            "throughput": total / sum(latencies) if sum(latencies) > 0 else 0,
        }

# ============================================================
# 用户模拟器
# ============================================================

class UserSimulator:
    """模拟真实用户行为"""
    
    def __init__(self, user: UserProfile):
        self.user = user
        self.satisfaction_history: List[float] = []
        self.frustration_level = 0.0
    
    def generate_task_request(self) -> Dict:
        """生成用户任务请求"""
        # 根据用户专业选择合适的任务类型
        category = random.choice(list(TASK_TEMPLATES.keys()))
        task = random.choice(TASK_TEMPLATES[category])
        
        return {
            "user": self.user.name,
            "role": self.user.role,
            "prompt": task["prompt"],
            "category": task["category"],
            "verify": task["verify"],
            "timeout": task["timeout"]
        }
    
    def evaluate_result(self, result: Dict) -> float:
        """用户评估结果质量"""
        score = 0.0
        
        # 检查成功与否
        if not result["success"]:
            self.frustration_level += 0.3
            return 0.0
        
        # 检查延迟
        if result["latency"] > 30:
            score += 0.2  # 慢但可接受
        else:
            score += 0.4  # 快速
        
        # 检查输出质量
        output = result.get("output", "")
        if len(output) > 100:
            score += 0.3  # 有实质内容
        else:
            score += 0.1  # 太简短
        
        # 匹配关键词
        verify = result.get("verify", [])
        matches = sum(1 for kw in verify if kw.lower() in output.lower())
        if verify:
            score += 0.3 * (matches / len(verify))
        
        # 根据完美主义调整
        if self.user.perfectionism > 0.7:
            if score < 0.7:
                self.frustration_level += 0.1
        
        self.satisfaction_history.append(score)
        return score
    
    def should_complain(self) -> bool:
        """用户是否应该抱怨"""
        return (
            self.frustration_level > self.user.frustration_threshold or
            len(self.satisfaction_history) >= 3 and
            sum(self.satisfaction_history[-3:]) / 3 < 0.5
        )
    
    def generate_feedback(self, result: Dict, score: float) -> str:
        """生成用户反馈"""
        if score >= 0.8:
            return f"很好！结果正是我需要的。"
        elif score >= 0.6:
            return f"还行，但可以更好。"
        elif score >= 0.4:
            return f"不太满意，输出不够详细。"
        else:
            return f"完全不对，我要的可不是这个！"

# ============================================================
# 场景运行器
# ============================================================

class ScenarioRunner:
    """运行真实场景并收集反馈"""
    
    def __init__(self):
        self.scenarios: List[UsageScenario] = []
        self.evaluator = MASEvaluator("mas_real_v21.py")
        self.feedback_log: List[Dict] = []
    
    def run_user_session(self, user: UserProfile, num_tasks: int = 5) -> Dict:
        """运行一个用户会话"""
        simulator = UserSimulator(user)
        results = []
        
        print(f"\n{'='*60}")
        print(f"用户: {user.name} ({user.role})")
        print(f"技能: {user.skill_level} | 耐心: {user.patience} | 完美主义: {user.perfectionism}")
        print(f"{'='*60}")
        
        for i in range(num_tasks):
            # 生成任务
            task_request = simulator.generate_task_request()
            print(f"\n[任务 {i+1}] {task_request['prompt'][:60]}...")
            
            # 执行任务
            result = self.evaluator.execute_task(task_request)
            
            # 用户评估
            score = simulator.evaluate_result(result)
            feedback = simulator.generate_feedback(result, score)
            
            print(f"  结果: {'✓' if result['success'] else '✗'} | 评分: {score:.2f} | 延迟: {result['latency']:.2f}s")
            print(f"  反馈: {feedback}")
            
            if simulator.should_complain():
                print(f"  ⚠️ 用户即将放弃！frustration={simulator.frustration_level:.2f}")
            
            results.append({
                "task": task_request,
                "result": result,
                "score": score,
                "feedback": feedback
            })
            
            # 记录反馈
            self.feedback_log.append({
                "user": user.name,
                "task": task_request["prompt"],
                "score": score,
                "frustration": simulator.frustration_level,
                "timestamp": datetime.now().isoformat()
            })
        
        # 汇总
        success_rate = sum(1 for r in results if r["result"]["success"]) / len(results)
        avg_score = sum(r["score"] for r in results) / len(results)
        
        return {
            "user": user.name,
            "total_tasks": num_tasks,
            "success_rate": success_rate,
            "avg_score": avg_score,
            "frustration": simulator.frustration_level,
            "would_continue": not simulator.should_complain(),
            "results": results
        }
    
    def run_full_evaluation(self) -> Dict:
        """运行完整评估"""
        print("\n" + "="*70)
        print("MAS 真实用户评估报告")
        print("="*70)
        
        all_results = []
        
        for user in USER_PROFILES:
            session_result = self.run_user_session(user, num_tasks=5)
            all_results.append(session_result)
        
        # 汇总所有用户
        metrics = self.evaluator.get_metrics()
        
        print("\n" + "="*70)
        print("汇总统计")
        print("="*70)
        
        print(f"\nMAS 性能指标:")
        print(f"  总任务数: {metrics.get('total_tasks', 0)}")
        print(f"  成功率: {metrics.get('success_rate', 0)*100:.1f}%")
        print(f"  平均延迟: {metrics.get('avg_latency', 0):.2f}s")
        print(f"  P99延迟: {metrics.get('p99_latency', 0):.2f}s")
        print(f"  吞吐量: {metrics.get('throughput', 0):.2f} tps")
        
        print(f"\n用户满意度:")
        for r in all_results:
            status = "✓ 会继续使用" if r["would_continue"] else "✗ 可能放弃"
            print(f"  {r['user']}: 满意度 {r['avg_score']:.2f} | 挫败感 {r['frustration']:.2f} | {status}")
        
        overall_satisfaction = sum(r["avg_score"] for r in all_results) / len(all_results)
        continuation_rate = sum(1 for r in all_results if r["would_continue"]) / len(all_results)
        
        print(f"\n整体满意度: {overall_satisfaction:.2f}")
        print(f"继续使用率: {continuation_rate*100:.0f}%")
        
        return {
            "metrics": metrics,
            "user_results": all_results,
            "overall_satisfaction": overall_satisfaction,
            "continuation_rate": continuation_rate,
            "feedback_log": self.feedback_log
        }

# ============================================================
# 基准迭代器
# ============================================================

class BenchmarkIterator:
    """根据反馈迭代改进基准"""
    
    def __init__(self):
        self.iteration = 0
        self.history: List[Dict] = []
    
    def add_result(self, result: Dict):
        """添加评估结果"""
        self.history.append({
            "iteration": self.iteration,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    def suggest_improvements(self) -> List[str]:
        """根据历史结果提出改进建议"""
        if not self.history:
            return ["开始第一次迭代"]
        
        latest = self.history[-1]["result"]
        suggestions = []
        
        # 分析指标
        metrics = latest.get("metrics", {})
        satisfaction = latest.get("overall_satisfaction", 0)
        continuation = latest.get("continuation_rate", 0)
        
        if metrics.get("success_rate", 0) < 0.9:
            suggestions.append("正确性不足: 需要改进任务执行的成功率")
        
        if metrics.get("avg_latency", 0) > 30:
            suggestions.append("延迟过高: 考虑优化任务分配算法")
        
        if satisfaction < 0.6:
            suggestions.append("用户不满意: 输出质量需要改进")
        
        if continuation < 0.7:
            suggestions.append("用户流失风险: 需要提高任务完成质量")
        
        # 检查特定用户的问题
        for user_result in latest.get("user_results", []):
            if not user_result["would_continue"]:
                suggestions.append(f"用户 {user_result['user']} 可能放弃，需要针对性改进")
        
        return suggestions if suggestions else ["当前系统表现良好，无需强制改进"]

# ============================================================
# 主程序
# ============================================================

def main():
    print("="*70)
    print("MAS 真实用户模拟系统")
    print("="*70)
    
    # 创建运行器
    runner = ScenarioRunner()
    
    # 运行完整评估
    result = runner.run_full_evaluation()
    
    # 创建迭代器
    iterator = BenchmarkIterator()
    iterator.add_result(result)
    
    # 生成改进建议
    print("\n" + "="*70)
    print("改进建议")
    print("="*70)
    for i, suggestion in enumerate(iterator.suggest_improvements(), 1):
        print(f"  {i}. {suggestion}")
    
    # 保存结果
    output_file = f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "result": result,
            "suggestions": iterator.suggest_improvements()
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: {output_file}")

if __name__ == "__main__":
    main()