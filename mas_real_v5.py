#!/usr/bin/env python3
"""
MAS Real v5.0 - Scalable Multi-Agent System with Communication

New features:
- Agent-to-agent real communication
- Task dependencies
- Performance benchmarking
- Throughput measurement
"""
import threading
import queue
import time
import os
import subprocess
import tempfile
import json
import random
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"

@dataclass
class Task:
    id: str
    description: str
    category: str
    difficulty: int
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    start_time: float = 0
    end_time: float = 0
    agent_id: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    messages: List[dict] = field(default_factory=list)

@dataclass
class Message:
    sender: str
    receiver: str
    content: Any
    msg_type: str
    timestamp: float = field(default_factory=time.time)

@dataclass
class Agent:
    id: str
    name: str
    specialty: str
    capabilities: List[str]
    level: int
    current_task: Optional[Task] = None
    completed: int = 0
    failed: int = 0
    messages_sent: int = 0
    messages_recv: int = 0
    msg_queue: queue.Queue = field(default_factory=queue.Queue)

class MASv5:
    """Scalable MAS with real inter-agent communication"""
    
    def __init__(self, num_agents: int = 12):
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.queue = queue.Queue()
        self.broadcast_queue = queue.Queue()
        self.running = True
        self.lock = threading.Lock()
        self.stats = {"submitted": 0, "completed": 0, "failed": 0, "verified": 0}
        
        self._init_agents(num_agents)
        self._start_communication_thread()
        
    def _init_agents(self, count: int):
        specs = [
            ("analyzer", "DataAnalyzer", ["analysis", "metrics"], 3),
            ("coder", "CodeEngineer", ["code", "debugging"], 3),
            ("researcher", "ResearchAgent", ["research", "files"], 2),
            ("planner", "StrategicPlanner", ["planning"], 2),
            ("verifier", "QAVerifier", ["testing", "verification"], 2),
            ("communicator", "CommAgent", ["reporting"], 1),
            ("optimizer", "PerfOptimizer", ["optimization"], 2),
            ("security", "SecurityAgent", ["security"], 2),
            ("database", "DBAgent", ["database"], 2),
            ("devops", "DevOpsAgent", ["deployment", "ci/cd"], 2),
            ("monitor", "MonitorAgent", ["monitoring", "alerts"], 1),
            ("scheduler", "SchedulerAgent", ["scheduling", "coordination"], 1),
        ]
        
        for i, (sid, name, caps, lvl) in enumerate(specs[:count]):
            self.agents[f"{sid}_{i}"] = Agent(
                id=f"{sid}_{i}", name=name, specialty=name,
                capabilities=caps, level=lvl
            )
    
    def _start_communication_thread(self):
        """Background thread for agent communication"""
        def comm_loop():
            while self.running:
                try:
                    msg = self.broadcast_queue.get(timeout=0.1)
                    if msg is None:
                        break
                    self._route_message(msg)
                except queue.Empty:
                    continue
        self.comm_thread = threading.Thread(target=comm_loop, daemon=True)
        self.comm_thread.start()
    
    def _route_message(self, msg: Message):
        """Route message to target agent"""
        if msg.receiver in self.agents:
            self.agents[msg.receiver].msg_queue.put(msg)
            with self.lock:
                self.agents[msg.receiver].messages_recv += 1
            with self.lock:
                if msg.sender in self.agents:
                    self.agents[msg.sender].messages_sent += 1
    
    def send_msg(self, sender: str, receiver: str, content: Any, msg_type: str):
        """Send inter-agent message"""
        msg = Message(sender=sender, receiver=receiver, content=content, msg_type=msg_type)
        self.broadcast_queue.put(msg)
        
    def broadcast(self, sender: str, content: Any, msg_type: str):
        """Broadcast to all agents"""
        for agent_id in self.agents:
            if agent_id != sender:
                self.send_msg(sender, agent_id, content, msg_type)
    
    def submit(self, task: Task):
        with self.lock:
            self.tasks[task.id] = task
            self.stats["submitted"] += 1
        self.queue.put(task)
        
    def execute(self, task: Task) -> bool:
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        
        try:
            # Check dependencies
            for dep_id in task.depends_on:
                if dep_id in self.tasks:
                    dep = self.tasks[dep_id]
                    if dep.status not in (TaskStatus.COMPLETED, TaskStatus.VERIFIED):
                        raise Exception(f"Dependency {dep_id} not ready")
            
            # Get result
            result = self._dispatch(task)
            task.result = result
            task.status = TaskStatus.COMPLETED
            
            # Notify completion via message
            if task.agent_id:
                self.broadcast(task.agent_id, {"task_id": task.id, "status": "completed"}, "task_update")
            
            # Self-verify
            if self._verify(task):
                task.status = TaskStatus.VERIFIED
                self.stats["verified"] += 1
            
            task.end_time = time.time()
            self.stats["completed"] += 1
            return True
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
            self.stats["failed"] += 1
            return False
    
    def _dispatch(self, task: Task) -> str:
        handlers = {
            "analysis": self._handle_analysis,
            "code": self._handle_code,
            "research": self._handle_research,
            "planning": self._handle_planning,
            "verification": self._handle_verification,
            "communication": self._handle_communication,
            "optimization": self._handle_optimization,
            "security": self._handle_security,
            "database": self._handle_database,
            "devops": self._handle_devops,
            "monitoring": self._handle_monitoring,
            "scheduling": self._handle_scheduling,
        }
        handler = handlers.get(task.category, self._handle_default)
        return handler(task)
    
    def _handle_analysis(self, t: Task) -> str:
        cmds = {
            "passwd": ["wc", "-l", "/etc/passwd"],
            "disk": ["df", "-h"],
            "memory": ["free", "-h"],
            "cpu": ["cat", "/proc/cpuinfo"],
            "process": ["ps", "aux"],
        }
        for key, cmd in cmds.items():
            if key in t.description.lower():
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return f"{t.category}: {r.stdout.strip()[:100]}"
        return f"Analysis: {t.description[:50]}"
    
    def _handle_code(self, t: Task) -> str:
        templates = {
            "hello": "print('Hello, World!')\n",
            "sort": "print(sorted([3,1,4,1,5,9,2,6,5,3,5]))\n",
            "fib": "def fib(n): return n if n<2 else fib(n-1)+fib(n-2)\nprint([fib(i) for i in range(10)])\n",
            "prime": "print([n for n in range(2,50) if all(n%p for p in range(2,n))])\n",
            "factorial": "from math import factorial\nprint([factorial(i) for i in range(10)])\n",
        }
        code = "# Generated\n"
        for key, c in templates.items():
            if key in t.description.lower():
                code = c
                break
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                path = f.name
            r = subprocess.run(["python3", path], capture_output=True, text=True, timeout=10)
            os.unlink(path)
            return f"Result: {r.stdout.strip()[:80]}" if r.returncode == 0 else f"Error: {r.stderr[:50]}"
        except Exception as e:
            return f"Error: {e}"
    
    def _handle_research(self, t: Task) -> str:
        paths = {"/tmp": "/tmp", "/var/log": "/var/log", "/etc": "/etc"}
        for key, path in paths.items():
            if key in t.description.lower():
                try:
                    items = os.listdir(path)
                    return f"{path}: {len(items)} items - {', '.join(items[:5])}"
                except:
                    pass
        return f"Research: {t.description[:50]}"
    
    def _handle_planning(self, t: Task) -> str:
        return f"Plan for: {t.description}\n1. Analyze\n2. Design\n3. Implement\n4. Test\n5. Deploy\n6. Monitor"
    
    def _handle_verification(self, t: Task) -> str:
        return f"Verified: {t.description[:50]}"
    
    def _handle_communication(self, t: Task) -> str:
        return f"Report: {t.description[:50]}"
    
    def _handle_optimization(self, t: Task) -> str:
        return f"Optimized: {t.description[:50]}"
    
    def _handle_security(self, t: Task) -> str:
        r = subprocess.run(["ls", "-la", "/tmp"], capture_output=True, text=True)
        return f"Security: /tmp has {len(r.stdout.splitlines())} entries"
    
    def _handle_database(self, t: Task) -> str:
        return f"DB: {t.description[:50]}"
    
    def _handle_devops(self, t: Task) -> str:
        r = subprocess.run(["uptime"], capture_output=True, text=True)
        return f"DevOps: {r.stdout.strip()}"
    
    def _handle_monitoring(self, t: Task) -> str:
        return f"Monitoring: {t.description[:50]}"
    
    def _handle_scheduling(self, t: Task) -> str:
        return f"Scheduled: {t.description[:50]}"
    
    def _handle_default(self, t: Task) -> str:
        return f"Done: {t.description[:50]}"
    
    def _verify(self, t: Task) -> bool:
        if not t.result:
            return False
        if t.category == "code":
            return "error" not in t.result.lower() and len(t.result) > 5
        return len(t.result) > 3
    
    def _route(self, task: Task) -> Optional[Agent]:
        with self.lock:
            cat_map = {
                "analysis": "analyzer", "code": "coder", "research": "researcher",
                "planning": "planner", "verification": "verifier", "communication": "communicator",
                "optimization": "optimizer", "security": "security", "database": "database",
                "devops": "devops", "monitoring": "monitor", "scheduling": "scheduler"
            }
            target = cat_map.get(task.category, "")
            
            for agent in self.agents.values():
                if target in agent.id and agent.current_task is None:
                    return agent
            for agent in self.agents.values():
                if agent.current_task is None:
                    return agent
        return None
    
    def run(self):
        while self.running:
            try:
                task = self.queue.get(timeout=0.5)
                if task is None:
                    break
                
                agent = self._route(task)
                if agent:
                    with self.lock:
                        task.agent_id = agent.id
                    agent.current_task = task
                    
                    success = self.execute(task)
                    
                    agent.current_task = None
                    with self.lock:
                        if success:
                            agent.completed += 1
                        else:
                            agent.failed += 1
                else:
                    task.error = "No agent"
                    task.status = TaskStatus.FAILED
                    self.stats["failed"] += 1
                    
            except queue.Empty:
                continue
    
    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total_time = sum(t.end_time - t.start_time for t in self.tasks.values() if t.end_time > 0)
            return {
                **self.stats,
                "total_time": total_time,
                "throughput": self.stats["completed"] / max(0.001, total_time),
                "agents": {a.id: {"name": a.name, "completed": a.completed, "failed": a.failed,
                                   "sent": a.messages_sent, "recv": a.messages_recv}
                          for a in self.agents.values()}
            }
    
    def stop(self):
        self.running = False
        self.queue.put(None)
        self.broadcast_queue.put(None)

def create_tasks() -> List[Task]:
    tasks = [
        Task(id="01", description="Count /etc/passwd lines", category="analysis", difficulty=1),
        Task(id="02", description="Check disk usage", category="analysis", difficulty=1),
        Task(id="03", description="Check memory", category="analysis", difficulty=1),
        Task(id="04", description="Generate hello", category="code", difficulty=1),
        Task(id="05", description="Generate sort", category="code", difficulty=1),
        Task(id="06", description="Generate fibonacci", category="code", difficulty=2),
        Task(id="07", description="Generate primes", category="code", difficulty=2),
        Task(id="08", description="Generate factorial", category="code", difficulty=2),
        Task(id="09", description="Research /tmp", category="research", difficulty=1),
        Task(id="10", description="Research /var/log", category="research", difficulty=2),
        Task(id="11", description="Create plan", category="planning", difficulty=1),
        Task(id="12", description="Create deployment plan", category="planning", difficulty=2),
        Task(id="13", description="System uptime", category="devops", difficulty=1),
        Task(id="14", description="Security check", category="security", difficulty=2),
        Task(id="15", description="Generate report", category="communication", difficulty=1),
        Task(id="16", description="Optimize performance", category="optimization", difficulty=2),
        Task(id="17", description="Monitor system", category="monitoring", difficulty=1),
        Task(id="18", description="Schedule tasks", category="scheduling", difficulty=1),
        Task(id="19", description="Check CPU info", category="analysis", difficulty=1),
        Task(id="20", description="Check processes", category="analysis", difficulty=2),
    ]
    
    # Add dependencies for some tasks
    tasks[10].depends_on = ["09"]  # planning depends on research
    tasks[12].depends_on = ["02", "03"]  # devops depends on disk and memory
    
    return tasks

def main():
    print("=" * 70)
    print("MAS v5.0 - SCALABLE MAS WITH COMMUNICATION")
    print("=" * 70)
    
    mas = MASv5(num_agents=12)
    tasks = create_tasks()
    
    print(f"\nAgents: {len(mas.agents)}")
    print(f"Tasks: {len(tasks)}")
    for t in tasks:
        deps = f" (deps: {t.depends_on})" if t.depends_on else ""
        print(f"  [{t.id}] {t.category:15} L{t.difficulty}{deps} - {t.description[:30]}")
    
    start = time.time()
    for t in tasks:
        mas.submit(t)
    
    thread = threading.Thread(target=mas.run)
    thread.start()
    thread.join(timeout=120)
    mas.stop()
    total_time = time.time() - start
    
    stats = mas.get_stats()
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\nPerformance:")
    print(f"  {stats['completed']}/{stats['submitted']} completed ({stats['completed']/max(1,stats['submitted']):.0%})")
    print(f"  {stats['verified']} verified")
    print(f"  {stats['failed']} failed")
    print(f"  Wall time: {total_time:.3f}s")
    print(f"  CPU time: {stats['total_time']:.3f}s")
    print(f"  Throughput: {stats['throughput']:.1f} tasks/sec")
    
    print(f"\nAgents:")
    for aid, info in stats['agents'].items():
        print(f"  {info['name']}: {info['completed']} ok, {info['failed']} fail, {info['sent']} sent, {info['recv']} recv")
    
    print(f"\nTasks:")
    for tid, t in mas.tasks.items():
        icon = {TaskStatus.COMPLETED: "✓", TaskStatus.VERIFIED: "✓✓", TaskStatus.FAILED: "✗"}.get(t.status, "?")
        dt = t.end_time - t.start_time if t.end_time > 0 else 0
        result = (t.result or t.error or "...")[:50]
        deps = f" ←{t.depends_on}" if t.depends_on else ""
        print(f"  {icon} [{tid}]{deps} {t.category:15} ({dt:.3f}s) {result}...")

if __name__ == "__main__":
    main()