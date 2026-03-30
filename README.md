# MAS Evolution Engine

Multi-Agent System Architecture Evolution Engine - Autonomous self-improving MAS framework.

## Overview

This repository contains an autonomous闭环测试循环系统 that continuously designs, tests, and optimizes Multi-Agent System (MAS) architectures.

## Core Principles

- **全自动、无人工干预**: Fully automated closed-loop testing cycle
- **永不停歇的 AI 科学家**: Perpetual AI scientist seeking optimal MAS architecture
- **收敛识别机制**: Convergence detection when连续10轮性能提升 < 1%

## Architecture

The system implements OODA-style evolution:
1. **基建** - Resource monitoring, Benchmark construction
2. **设计** - Architecture topology design
3. **沙盒** - Sandbox execution & monitoring
4. **评估** - Multi-dimensional radar evaluation
5. **风控** - Rollback on critical failures
6. **归档** - Git commit with evolution history

## Safety Constraints

- CPU ≤ 95%, Disk space ≥ 1GB
- 24-hour timeout per test instance
- No network penetration attempts
- No malicious code generation
