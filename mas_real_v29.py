#!/usr/bin/env python3
"""MAS v29 - Direct queue, 500 tasks"""
import threading, queue, time, subprocess
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Stats:
    submitted: int = 0; completed: int = 0; failed: int = 0

stats = Stats()
lock = threading.Lock()
task_queue = queue.Queue()
results: Dict[int, str] = {}

def worker(wid: int):
    while True:
        try:
            t_id, cat = task_queue.get(timeout=0.1)
            if t_id is None: break
            try:
                if cat == "analysis":
                    r = subprocess.run(["wc", "-l", "/etc/passwd"], capture_output=True, text=True, timeout=5)
                    res = f"analysis: {r.stdout.strip()}"
                elif cat == "code":
                    r = subprocess.run(["python3", "-c", "print('Done')"], capture_output=True, text=True, timeout=5)
                    res = f"code: {r.stdout.strip()}"
                elif cat == "security":
                    r = subprocess.run(["ls", "/tmp"], capture_output=True, text=True, timeout=5)
                    res = f"security: {len(r.stdout.splitlines())} files"
                else:
                    res = f"{cat}: done"
                results[t_id] = res
                with lock: stats.completed += 1
            except Exception as e:
                with lock: stats.failed += 1
            task_queue.task_done()
        except queue.Empty: break

def main():
    print("=" * 50 + "\nMAS v29.0 - 200000 TASKS\n" + "=" * 50)
    categories = ["analysis", "code", "research", "planning", "security"]
    tasks = [(i, categories[i % len(categories)]) for i in range(1, 200001)]
    print(f"Tasks: {len(tasks)}")
    
    for t_id, cat in tasks:
        with lock: stats.submitted += 1
        task_queue.put((t_id, cat))
    
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    start = time.time()
    for t in threads: t.start()
    task_queue.join()
    for t in threads: task_queue.put((None, None))
    for t in threads: t.join()
    elapsed = time.time() - start
    
    print(f"\n{stats.completed}/{stats.submitted} completed, {stats.failed} failed")
    print(f"Throughput: {stats.completed / max(0.001, elapsed):.1f} tps")

if __name__ == "__main__": main()