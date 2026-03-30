#!/usr/bin/env python3
"""
MAS Evolution Engine - Generation 1
Multi-Agent System Architecture for Complex Task Solving

Architecture: Hierarchical Orchestrator with Parallel Workers
- Orchestrator: Task decomposition and delegation
- Workers: Parallel task execution with tool usage
- Evaluator: Quality assessment and routing decisions
- Memory: Shared context management
"""

import asyncio
import json
import time
import os
import psutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import traceback

# ============ CONFIGURATION ============
MODEL = "minimax-portal/MiniMax-M2.7"
OUTPUT_DIR = "/root/.openclaw/workspace/mas_gen1_output"
LOG_FILE = f"{OUTPUT_DIR}/test_log.json"
BENCHMARK_RESULTS = f"{OUTPUT_DIR}/benchmark_results.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============ RESOURCE MONITORING ============
@dataclass
class ResourceSnapshot:
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    disk_free_gb: float

class ResourceMonitor:
    def __init__(self, max_cpu=95, max_mem=95, min_disk_gb=1):
        self.max_cpu = max_cpu
        self.max_mem = max_mem
        self.min_disk_gb = min_disk_gb
        self.snapshots: List[ResourceSnapshot] = []
    
    def check(self) -> ResourceSnapshot:
        snap = ResourceSnapshot(
            timestamp=time.time(),
            cpu_percent=psutil.cpu_percent(),
            memory_percent=psutil.virtual_memory().percent,
            memory_used_gb=psutil.virtual_memory().used / (1024**3),
            disk_free_gb=psutil.disk_usage('/').free / (1024**3)
        )
        self.snapshots.append(snap)
        return snap
    
    def is_safe(self) -> bool:
        snap = self.check()
        if snap.cpu_percent > self.max_cpu:
            print(f"⚠️ CPU critical: {snap.cpu_percent}%")
            return False
        if snap.memory_percent > self.max_mem:
            print(f"⚠️ Memory critical: {snap.memory_percent}%")
            return False
        if snap.disk_free_gb < self.min_disk_gb:
            print(f"⚠️ Disk critical: {snap.disk_free_gb}GB")
            return False
        return True
    
    def emergency_gc(self):
        """Emergency garbage collection when resources are low"""
        print("🚨 EMERGENCY GC TRIGGERED")
        import gc
        gc.collect()
        # Clean up any temporary files
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith('.tmp'):
                os.remove(f"{OUTPUT_DIR}/{f}")

# ============ AGENT DEFINITIONS ============
class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    EVALUATOR = "evaluator"

@dataclass
class AgentMessage:
    role: AgentRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class TaskResult:
    task_id: str
    success: bool
    output: str
    tokens_used: int
    duration_seconds: float
    error: Optional[str] = None

# ============ SIMPLE LLM CALL ============
async def call_llm(prompt: str, model: str = MODEL) -> tuple[str, int]:
    """Call the LLM API and return response + token count estimate"""
    # This is a placeholder - in real implementation, use OpenAI API or similar
    # For now, simulate response based on task complexity
    start = time.time()
    
    # Simulate thinking time based on prompt length
    await asyncio.sleep(min(len(prompt) / 1000, 2.0))
    
    # Generate simulated response
    response = f"[MAS-Gen1 Response to: {prompt[:50]}...]"
    tokens = len(prompt) + len(response)
    
    return response, tokens

# ============ ORCHESTRATOR AGENT ============
class Orchestrator:
    def __init__(self, resource_monitor: ResourceMonitor):
        self.resource_monitor = resource_monitor
        self.task_queue: List[Dict] = []
        self.results: Dict[str, TaskResult] = {}
    
    async def decompose_task(self, task: str) -> List[Dict[str, Any]]:
        """Break down complex task into subtasks"""
        prompt = f"""Decompose the following task into parallelizable subtasks.
Task: {task}

Respond with JSON array of subtasks, each with 'id', 'description', 'type'.
Types: 'reasoning', 'tool_use', 'code', 'analysis'
"""
        response, _ = await call_llm(prompt)
        
        # Parse subtasks (simplified)
        subtasks = []
        if "reasoning" in task.lower():
            subtasks.append({"id": "sub1", "description": "Logical analysis", "type": "reasoning"})
        if "code" in task.lower() or "implement" in task.lower():
            subtasks.append({"id": "sub2", "description": "Code generation", "type": "code"})
        if "search" in task.lower() or "find" in task.lower():
            subtasks.append({"id": "sub3", "description": "Information retrieval", "type": "tool_use"})
        if not subtasks:
            subtasks.append({"id": "sub1", "description": "General analysis", "type": "reasoning"})
        
        return subtasks
    
    async def delegate_to_worker(self, subtask: Dict, context: str) -> TaskResult:
        """Delegate subtask to worker agent"""
        task_id = subtask["id"]
        start = time.time()
        
        prompt = f"""Context: {context}
Task: {subtask['description']}
Type: {subtask['type']}

Execute this task and provide a structured result."""
        
        try:
            output, tokens = await call_llm(prompt)
            return TaskResult(
                task_id=task_id,
                success=True,
                output=output,
                tokens_used=tokens,
                duration_seconds=time.time() - start
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                success=False,
                output="",
                tokens_used=0,
                duration_seconds=time.time() - start,
                error=str(e)
            )
    
    async def synthesize_results(self, subtask_results: List[TaskResult], original_task: str) -> str:
        """Combine subtask results into final answer"""
        prompt = f"""Original task: {original_task}

Subtask results:
{json.dumps([{"id": r.task_id, "success": r.success, "output": r.output} for r in subtask_results], indent=2)}

Synthesize these results into a coherent final answer."""
        
        response, _ = await call_llm(prompt)
        return response

# ============ EVALUATOR AGENT ============
class Evaluator:
    def __init__(self):
        self.criteria = ["accuracy", "completeness", "coherence"]
    
    async def assess_quality(self, output: str, task: str) -> Dict[str, float]:
        """Assess output quality across multiple dimensions"""
        prompt = f"""Task: {task}
Output: {output}

Rate the output quality (0-1) for:
- accuracy: How factually correct
- completeness: How fully it addresses the task
- coherence: How logically consistent

Respond with JSON: {{"accuracy": 0.X, "completeness": 0.X, "coherence": 0.X}}"""
        
        # Simulated assessment
        score = {
            "accuracy": 0.7 + (hash(output) % 30) / 100,
            "completeness": 0.6 + (hash(output[::-1]) % 40) / 100,
            "coherence": 0.75 + (len(output) % 25) / 100
        }
        return score
    
    def decide_next_action(self, quality: Dict[str, float], threshold: float = 0.6) -> str:
        """Decide if result needs improvement"""
        avg_quality = sum(quality.values()) / len(quality)
        if avg_quality >= threshold:
            return "accept"
        else:
            return "retry_with_feedback"

# ============ MAS SYSTEM ============
class MASGeneration1:
    def __init__(self):
        self.resource_monitor = ResourceMonitor()
        self.orchestrator = Orchestrator(self.resource_monitor)
        self.evaluator = Evaluator()
        self.generation = 1
        self.start_time = time.time()
    
    async def execute_task(self, task: str, max_retries: int = 1) -> Dict[str, Any]:
        """Execute a task through the MAS pipeline"""
        task_id = f"gen{self.generation}_{int(time.time())}"
        print(f"🎯 [{task_id}] Executing task: {task[:80]}...")
        
        # Check resources before starting
        if not self.resource_monitor.is_safe():
            self.resource_monitor.emergency_gc()
        
        start = time.time()
        
        # Step 1: Decompose
        subtasks = await self.orchestrator.decompose_task(task)
        print(f"   📦 Decomposed into {len(subtasks)} subtasks")
        
        # Step 2: Execute in parallel
        workers = [self.orchestrator.delegate_to_worker(st, task) for st in subtasks]
        results = await asyncio.gather(*workers, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for r in results:
            if isinstance(r, Exception):
                processed_results.append(TaskResult(
                    task_id="err",
                    success=False,
                    output="",
                    tokens_used=0,
                    duration_seconds=0,
                    error=str(r)
                ))
            else:
                processed_results.append(r)
        
        # Step 3: Evaluate
        final_output = await self.orchestrator.synthesize_results(processed_results, task)
        quality = await self.evaluator.assess_quality(final_output, task)
        
        # Step 4: Check if retry needed
        action = self.evaluator.decide_next_action(quality)
        if action == "retry_with_feedback" and max_retries > 0:
            print(f"   🔄 Quality below threshold, retrying with feedback...")
            feedback = f"Previous attempt scored {quality}. Improve: {task}"
            return await self.execute_task(feedback, max_retries - 1)
        
        duration = time.time() - start
        total_tokens = sum(r.tokens_used for r in processed_results)
        
        result = {
            "task_id": task_id,
            "task": task,
            "success": True,
            "output": final_output,
            "quality": quality,
            "avg_quality": sum(quality.values()) / len(quality),
            "subtasks_executed": len(processed_results),
            "tokens_used": total_tokens,
            "duration_seconds": duration,
            "action": action
        }
        
        print(f"   ✅ Completed: quality={result['avg_quality']:.2f}, tokens={total_tokens}, duration={duration:.1f}s")
        return result

# ============ BENCHMARK TASKS ============
BENCHMARK_TASKS = [
    {
        "id": "bench_1",
        "task": "Write a Python function to find the longest palindromic substring in a given string. Include error handling and unit tests.",
        "expected_types": ["code", "reasoning"]
    },
    {
        "id": "bench_2", 
        "task": "Analyze the pros and cons of microservices vs monolithic architecture. Provide a decision matrix.",
        "expected_types": ["analysis", "reasoning"]
    },
    {
        "id": "bench_3",
        "task": "Research and summarize the latest developments in quantum computing (simulate by searching web for 'quantum computing 2024 breakthroughs').",
        "expected_types": ["tool_use", "analysis"]
    },
    {
        "id": "bench_4",
        "task": "Design a distributed rate limiter system. Include architecture diagram description, API spec, and implementation strategy.",
        "expected_types": ["reasoning", "code"]
    },
    {
        "id": "bench_5",
        "task": "Explain the technical challenges and solutions for implementing a multi-region active-active database.",
        "expected_types": ["analysis", "reasoning"]
    }
]

# ============ MAIN BENCHMARK RUNNER ============
async def run_benchmark():
    """Run the complete benchmark suite"""
    print("=" * 60)
    print("🧬 MAS EVOLUTION ENGINE - GENERATION 1 BENCHMARK")
    print("=" * 60)
    
    mas = MASGeneration1()
    results = []
    all_resource_snapshots = []
    
    for i, bench_task in enumerate(BENCHMARK_TASKS):
        print(f"\n📊 Benchmark {i+1}/{len(BENCHMARK_TASKS)}: {bench_task['id']}")
        
        # Check resources before each task
        snap = mas.resource_monitor.check()
        all_resource_snapshots.append(snap)
        print(f"   Resources: CPU={snap.cpu_percent:.1f}% Mem={snap.memory_percent:.1f}% Disk={snap.disk_free_gb:.1f}GB")
        
        # Execute task
        result = await mas.execute_task(bench_task["task"])
        results.append(result)
        
        # Save intermediate results
        with open(LOG_FILE, 'w') as f:
            json.dump({
                "generation": 1,
                "timestamp": datetime.now().isoformat(),
                "completed": i + 1,
                "total": len(BENCHMARK_TASKS),
                "results": results
            }, f, indent=2)
        
        # Small delay between tasks
        await asyncio.sleep(1)
    
    # Calculate aggregate metrics
    success_rate = sum(1 for r in results if r["success"]) / len(results)
    avg_quality = sum(r["avg_quality"] for r in results) / len(results)
    avg_tokens = sum(r["tokens_used"] for r in results) / len(results)
    avg_duration = sum(r["duration_seconds"] for r in results) / len(results)
    total_tokens = sum(r["tokens_used"] for r in results)
    total_duration = sum(r["duration_seconds"] for r in results)
    
    # Resource stats
    avg_cpu = sum(s.cpu_percent for s in all_resource_snapshots) / len(all_resource_snapshots)
    avg_mem = sum(s.memory_percent for s in all_resource_snapshots) / len(all_resource_snapshots)
    
    benchmark_result = {
        "generation": 1,
        "timestamp": datetime.now().isoformat(),
        "benchmark_tasks": len(BENCHMARK_TASKS),
        "success_rate": success_rate,
        "avg_quality": avg_quality,
        "avg_tokens_per_task": avg_tokens,
        "avg_duration_per_task": avg_duration,
        "total_tokens": total_tokens,
        "total_duration": total_duration,
        "resource_usage": {
            "avg_cpu_percent": avg_cpu,
            "avg_memory_percent": avg_mem,
            "peak_disk_free_gb": min(s.disk_free_gb for s in all_resource_snapshots)
        },
        "individual_results": results
    }
    
    # Save final results
    with open(BENCHMARK_RESULTS, 'w') as f:
        json.dump(benchmark_result, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📈 BENCHMARK RESULTS - GENERATION 1")
    print("=" * 60)
    print(f"  Success Rate:    {success_rate*100:.1f}%")
    print(f"  Avg Quality:     {avg_quality:.3f}")
    print(f"  Avg Tokens/Task: {avg_tokens:.0f}")
    print(f"  Avg Duration:    {avg_duration:.1f}s")
    print(f"  Total Tokens:    {total_tokens}")
    print(f"  Total Duration:  {total_duration:.1f}s")
    print(f"  Avg CPU:         {avg_cpu:.1f}%")
    print(f"  Avg Memory:      {avg_mem:.1f}%")
    print("=" * 60)
    
    return benchmark_result

# ============ ENTRY POINT ============
if __name__ == "__main__":
    result = asyncio.run(run_benchmark())
    print("\n🏁 Benchmark complete. Results saved to:", BENCHMARK_RESULTS)
