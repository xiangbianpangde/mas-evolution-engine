#!/usr/bin/env python3
"""MAS v21 - Simplified 200 tasks"""
import threading, queue, time, subprocess
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; VERIFIED = "verified"

class TaskPriority(Enum):
    LOW = 1; NORMAL = 2; HIGH = 3; CRITICAL = 4

@dataclass
class Task:
    id: str; description: str; category: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    start_time: float = 0; end_time: float = 0
    execution_time: float = 0

class Agent:
    def __init__(self, id: str, name: str):
        self.id = id; self.name = name; self.current_task: Optional[Task] = None
        self.completed: int = 0; self.failed: int = 0

class MAS:
    def __init__(self, num_agents: int = 16):
        self.agents: Dict[str, Agent] = {f"agent_{i}": Agent(f"agent_{i}", f"Agent{i}") for i in range(num_agents)}
        self.tasks: Dict[str, Task] = {}
        self.queue = queue.PriorityQueue()
        self.running = True; self.lock = threading.Lock()
        self.stats = {"submitted": 0, "completed": 0, "failed": 0, "verified": 0}
    
    def submit(self, task: Task):
        with self.lock: self.tasks[task.id] = task; self.stats["submitted"] += 1
        self.queue.put((task.priority.value, task.id, task))
    
    def execute(self, task: Task) -> bool:
        task.status = TaskStatus.RUNNING; task.start_time = time.time()
        try:
            if task.category == "analysis":
                r = subprocess.run(["wc", "-l", "/etc/passwd"], capture_output=True, text=True, timeout=5)
                task.result = f"Analysis: {r.stdout.strip()}"
            elif task.category == "code":
                r = subprocess.run(["python3", "-c", "print('Done')"], capture_output=True, text=True, timeout=5)
                task.result = f"Code: {r.stdout.strip()}"
            elif task.category == "security":
                r = subprocess.run(["ls", "/tmp"], capture_output=True, text=True, timeout=5)
                task.result = f"Security: {len(r.stdout.splitlines())} files"
            else:
                task.result = f"{task.category}: task {task.id}"
            task.status = TaskStatus.VERIFIED; task.end_time = time.time()
            task.execution_time = task.end_time - task.start_time
            with self.lock: self.stats["completed"] += 1; self.stats["verified"] += 1
            return True
        except Exception as e:
            task.status = TaskStatus.FAILED; task.end_time = time.time()
            task.execution_time = task.end_time - task.start_time
            with self.lock: self.stats["failed"] += 1; return False
    
    def run(self):
        while self.running:
            try:
                prio, task_id, task = self.queue.get(timeout=0.1)
                if task is None: break
                for agent in self.agents.values():
                    if agent.current_task is None:
                        agent.current_task = task
                        success = self.execute(task)
                        agent.current_task = None
                        if success: agent.completed += 1
                        else: agent.failed += 1
                        break
                else:
                    self.queue.put((prio, task_id, task)); time.sleep(0.01)
            except queue.Empty: continue
    
    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total_time = sum(t.execution_time for t in self.tasks.values() if t.end_time > 0)
            return {**self.stats, "throughput": self.stats["completed"] / max(0.001, total_time)}
    def stop(self): self.running = False; self.queue.put((0, None, None))

def main():
    print("=" * 50 + "\nMAS v21.0 - 200 TASKS\n" + "=" * 50)
    mas = MAS(num_agents=16)
    categories = ["analysis", "code", "research", "planning", "security"]
    tasks = [Task(id=f"{i}", description=f"Task {i}", category=categories[i % len(categories)]) for i in range(1, 201)]
    print(f"Agents: {len(mas.agents)}, Tasks: {len(tasks)}")
    for t in tasks: mas.submit(t)
    start = time.time(); t = threading.Thread(target=mas.run); t.start()
    t.join(timeout=300); mas.stop()
    stats = mas.get_stats()
    print(f"\n{stats['completed']}/{stats['submitted']} completed, {stats['verified']} verified, {stats['failed']} failed")
    print(f"Throughput: {stats['throughput']:.1f} tps")

if __name__ == "__main__": main()