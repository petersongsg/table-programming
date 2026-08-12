# Table Programming

> A table-driven programming framework for robots and automation devices. All business logic lives in a JSON rule table; hardware I/O runs in an isolated background thread with thread-safe snapshot synchronization. Say goodbye to if-else mountains, state machine nesting, and hardware-blocked business loops.

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org) [![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Architecture: 4 files](https://img.shields.io/badge/architecture-4%20files-orange.svg)](#core-architecture)

[中文版 →](README.md) | [Guideline →](docs/GUIDELINE_EN.md) | [开发纲领 →](docs/GUIDELINE.md)

## What is this

In traditional robotics / industrial control projects, business logic is scattered across the codebase, state machines nest dozens of layers, I/O blocks the main loop, and multi-threading synchronization is a footgun. This framework provides a **fixed 4-file architecture + flat rule table + background I/O thread + snapshot synchronization** that turns the code into a fixed carrier and pushes all business logic into configuration — change the config, not the code.

Ideal for: mobile robot chassis, AGVs, automation equipment control logic, sensor interlock, workflow orchestration, low-code rule configuration.

## Quick Start

```bash
git clone https://github.com/yourname/table-programming.git
cd table-programming

# 1) Debug the hardware layer (no business rules run)
python io_debug.py
# → Prints a sensor snapshot every 200ms; verify IO + lock sync

# 2) Run the full business loop
python main.py
# → Background I/O thread + main rule loop, rules in rules.json
```

## Core Architecture

```
table-programming/
├── main.py               # Universal fixed kernel (rule dispatch + locks + background IO)
├── source_plugins.py     # Sensor collection plugins (pure hardware reads, out-of-lock)
├── action_plugins.py     # Action plugins (hardware execution + state transitions, main thread only)
├── rules.json            # Flat business rule table (single business-logic entry point)
├── io_debug.py           # Standalone IO debug script (hardware layer verification)
├── examples/             # Additional examples
│   └── demo_chassis.json # Chassis pick-and-drop scenario rules
├── tests/                # Unit tests
├── docs/                 # Full guideline (中文 + EN)
├── README.md             # This file
└── LICENSE               # MIT
```

## Core Features

| Feature | Description |
|---------|-------------|
| **4-file flat architecture** | Fixed structure, no layering, no grouping, no nesting. Newcomers understand the codebase in 5 minutes. |
| **Business as config** | All business lives in `rules.json`; even non-developers can change workflows. |
| **Priority-preemption dispatch** | Rule order = priority. Only the first hit executes per cycle — actions are naturally mutex. |
| **IO in background thread** | Hardware reads (serial, CAN) are out-of-lock in a background thread; the main loop never blocks. |
| **Thread-safe snapshot** | Main thread takes a full ctx snapshot under lock every cycle; rule checks run on the snapshot — no torn reads. |
| **Layered debugging** | `io_debug.py` for hardware, `main.py` for business. Problems localized cleanly. |
| **Soft state machine** | Workflows/states live in `ctx.task_stage`; rule conditions filter them. No hard-coded FSM. |

## rules.json Format

```json
[
  {
    "name": "Global emergency stop",
    "src":  ["plugin_read_emergency_btn"],
    "cond": "emergency_btn",
    "act":  "action_full_stop"
  },
  {
    "name": "Move to pick point",
    "src":  ["plugin_read_front_lidar", "plugin_read_pos"],
    "cond": "task_stage=='go_pick' and pos_error>0.15 and front_dist>=0.6",
    "act":  "action_move_forward"
  }
]
```

Fields:
- `name`: rule name (for readability and debug trace)
- `src`: sensor dependencies (documentation only, not executed)
- `cond`: condition expression (native Python syntax; `ctx` fields + `time.time()` allowed)
- `act`: action plugin name (string-mapped, see `action_plugins.py`)

## Use Cases

| ✅ Good fit | ❌ Bad fit |
|------------|-----------|
| Mobile robot chassis (AGV / patrol) | CPU-bound compute (GIL-limited) |
| Industrial automation (arm / conveyor) | High-frequency control (>1 kHz) |
| Sensor interlock + workflow orchestration | Massive rule tables (>1000; full-scan has cost) |
| Low-code business iteration | Complex temporal logic (FSM is better) |
| Rapid prototyping | Web services / multi-tenant (eval risk; see below) |

## ⚠️ Security Warning (read this)

**The `cond` field in `rules.json` is parsed via `eval()`.**

- **Project intent**: `rules.json` is a trusted local config written by engineers — **not** user-submitted input.
- **Do not** load `rules.json` from network / untrusted sources — arbitrary code execution risk.
- **Do not** use this framework in web services or multi-tenant scenarios.
- If you need to expose it externally, replace `eval` with `pyparsing` / `simpleeval` first (left as TODO).

See [GUIDELINE_EN.md §3.2 Forbidden Threading Patterns](docs/GUIDELINE_EN.md)

## Development Workflow

1. **Hardware adaptation** → add `plugin_read_xxx()` in `source_plugins.py`, register in `io_task_all_sensors()`, add field to `RobotContext` in `main.py`.
2. **Action adaptation** → write `action_xxx(ctx)` in `action_plugins.py`, register in `ACTION_PLUGIN_REGISTRY`.
3. **Business config** → edit `rules.json`; rule order = priority.
4. **Layered debug** → first `io_debug.py` for hardware, then `main.py` for business.

Full guideline: [docs/GUIDELINE_EN.md](docs/GUIDELINE_EN.md)

## Run Output Example

```
✅ Background IO thread started: hardware polled independently, lock-protected sync
----- Control cycle 1 -----
state: idle | speed:0.00 | front_dist:1.00
----- Control cycle 2 -----
state: idle | speed:0.00 | front_dist:1.00
...
(assume start button pressed, start_btn=True)
----- Control cycle 5 -----
state: idle | speed:0.00 | front_dist:1.00
[hit rule] Standby, waiting for start
 >> state: go_pick
----- Control cycle 6 -----
state: go_pick | speed:0.00 | front_dist:1.00
[hit rule] Move to pick point
 >> action: forward
...
```

## Testing

```bash
cd tests
python -m unittest test_rule_engine.py -v
```

## Performance & Limits

- Cycle scan: 100 rules ≈ 0.5 ms (Python `eval` overhead)
- IO thread poll: 50 ms interval (tunable)
- Memory: ~10 MB (depends on sensor count)
- GIL: best for IO-bound; CPU-bound needs multi-process

## Roadmap (TODO)

- [ ] Expression sandbox (replace `eval` with `pyparsing` / `simpleeval`)
- [ ] Web visual rule editor
- [ ] Hot-reload of rules (file watcher, no downtime)
- [ ] Sensor debounce (condition must hold N cycles)
- [ ] Logging (per-cycle rule match + state dump)
- [ ] Embedded C++ port (based on exprtk; see `docs/`)

## Contributing

PRs and issues welcome. **Architecture invariants** (see GUIDELINE §7) are not negotiable:
- 4-file structure
- flat rule table (no nesting, no grouping)
- main thread owns all action execution
- business logic lives only in `rules.json`

## License

[MIT](LICENSE) — permissive; commercial use allowed.
