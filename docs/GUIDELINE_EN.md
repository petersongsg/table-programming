# Table Programming — Complete Development Guideline

> This document is the **sole authoritative guideline** for the entire framework. All project iterations, feature additions, bug fixes, and team handovers must strictly follow this document.
> **Core principle**: code is a fixed carrier; all business logic lives in configuration. Reading the rule table alone should be enough to understand the entire program.

---

## 0. About this document

This document unifies all architectural ideas, file conventions, threading models, read/write discipline, debugging methods, and engineering constraints. **No new architectural paradigms, no private layering, no custom patterns.**

## 1. Overall Architecture (core idea, non-negotiable)

### 1.1 Definition
**Four-file absolute flat architecture** — no layering, no grouping, no nesting, no scene submodules, no state machine code, no hard-coded business if-else.

All device control logic, interlocks, timing, priorities, and workflow switches are carried by a single flat `rules.json` table.

### 1.2 The four fixed files (permanent project structure)

```
project/
├── main.py               # Universal fixed main kernel
├── source_plugins.py     # Sensor collection plugin set
├── action_plugins.py     # Action plugin set
└── rules.json            # Flat business rule table
```

**Do not add architecture files. Do not remove core files.**

### 1.3 Core execution mechanism (conflict-avoidance basis)

- Rule top-to-bottom order = priority high to low
- **Only the first hit rule executes per control cycle**
- Hitting a higher-priority rule short-circuits the rest of the cycle — naturally prevents action conflicts
- Safety / protection / emergency-stop rules are always at the top with the highest preemption right

### 1.4 Complex task solution (no grouping, no sub-rules)

All complex timing, multi-step workflows, multi-mode operation, and state transitions are handled **without grouping, layering, or sub-rules**.

The single unified approach: **context state variables + rule condition filters** to implement a soft FSM.

Workflow stages and operation modes live in `ctx.task_stage`-style business state variables; rule `cond` expressions filter which rules are active right now.

## 2. Global Context Design Rules (thread safety, variable isolation)

### 2.1 Strict variable dichotomy (architecture iron rule)

Context variables are forever split into two classes with strict read/write isolation. Crossing classes is forbidden.

| Class | Writer | Reader | Notes |
|-------|--------|--------|-------|
| **External sensor vars** (distance/speed/button/position/temperature) | background IO thread only | main thread (snapshot read-only) | business code and action plugins must not modify |
| **Internal business state vars** (task_stage / mission flags / workflow state) | main thread action plugins only | all threads read-only | IO thread and sensor plugins must not modify |

### 2.2 Timestamp variable rule

Always keep a `ts_io` variable, refreshed every frame by the IO thread. Use it in rule conditions for:
- sensor timeout detection
- hardware drop-out protection
- data freshness checks
- time-delay logic

**Never use `time.sleep` for business delays**; always derive delay from a timestamp difference inside a rule expression.

## 3. Multi-thread Synchronization Rules (mandatory)

### 3.1 Two-thread fixed model

- **Background IO thread**: independent infinite loop, pure hardware collection, fully decoupled from the rule engine
- **Main thread**: rule dispatch, condition evaluation, action execution, state transitions

### 3.2 Standard thread-safe flow (only legal synchronization)

**Background IO thread (IO out of lock, assignment in lock)**:
1. Perform all hardware reads, blocking I/O, serial reads, CAN parsing **outside the lock**
2. Store results in a local dict (never touch the shared `ctx`)
3. Acquire the lock; perform an extremely short critical section that batch-assigns into `ctx`
4. Release the lock, `sleep` until next frame

**Main thread (snapshot isolation, no torn reads)**:
1. At the start of each cycle, acquire the lock and copy a full `ctx` snapshot
2. Release the lock; all rule checks use the snapshot
3. Only when an action fires, modify the original `ctx` business-state variables

### 3.3 Forbidden threading patterns (red lines)

- No I/O, `sleep`, or long computation inside the lock
- No direct reads of the original `ctx` for rule checks
- No IO thread modification of business state variables
- No action plugin modification of sensor variables
- No business if-else logic hard-coded inside any plugin
- Do not load `rules.json` from network / untrusted sources (eval injection risk)

## 4. Detailed File-level Conventions

### 4.1 main.py — main kernel (permanent; do not modify for business)

**Position**: the universal scheduling framework. Once finalized, never add business logic.

**Fixed responsibilities**:
- Load `rules.json`
- Start the independent background IO thread
- Thread lock, snapshot copy, data sync
- Single-cycle priority-preemption dispatch, conflict avoidance
- Rule expression evaluation, exception capture

**Constraint**: never modify `main.py` to add new business / modes / interlocks.

### 4.2 source_plugins.py — sensor collection set

**Position**: pure hardware read layer. No business, no state, no logic.

**Conventions**:
- Each collection function only reads hardware; never writes state or makes decisions
- All return local values; the IO thread batch-flushes into `ctx`
- Adding a sensor: write a new function → add to `io_task_all_sensors()` → add a field in `RobotContext`
- Never modify `task_stage` or any business state
- No `sleep`, no delays, no blocking of the main framework

### 4.3 action_plugins.py — action execution set

**Position**: hardware execution + business state transitions.

**Two action types, strictly distinct**:
- Hardware execution: brake, move, gripper, alarm, GPIO output
- State transition: only modifies `task_stage`, no hardware output, used for workflow transitions

**Iron rule**: all business judgment, condition filtering, and timing logic MUST NOT be coded inside action functions. They go into the rule table.

**Adding an action**: write the function → register in `ACTION_PLUGIN_REGISTRY`.

### 4.4 rules.json — rule table (the only business entry point)

**Position**: the single carrier of all business logic, interlocks, timing, and priorities.

**Fixed compact fields (forever — no extension, no nesting, no grouping)**:
- `name`: rule name (readability, debug trace)
- `src`: sensor dependencies (documentation only, **not executed**)
- `cond`: condition expression (native Python syntax, supports sensor + state + timestamp)
- `act`: action plugin name to execute when the condition hits

**Format rules**:
- Single-line compact format, flat ordering
- Priority decreases from top to bottom
- **Protection rules at the top, business rules below**

## 5. Standard Development Workflow

For every new feature, follow this order strictly. **No reverse order, no skipping**:

1. **Hardware adaptation** — add sensor read function in `source_plugins.py` + register in the batch entry
2. **Action adaptation** — add execution/state-transition function in `action_plugins.py` + register
3. **Configure business logic** — edit `rules.json`; adjust order = adjust priority
4. **Layered debug** — `io_debug.py` for hardware first, then `main.py` for business

## 6. Debugging System (layer-isolated)

### 6.1 Two strictly-isolated layers

- **Hardware layer debug**: `io_debug.py` standalone. Tests IO collection, threading, data sync. No business.
- **Business layer debug**: `main.py`. Tests rule logic, state flow, action execution.

**Advantage**: hardware and logic problems are fully decoupled, precise localization, no cross-interference.

### 6.2 Fault-finding priority

When something is wrong, **check the rule table first**, then the ctx snapshot, **then the plugin code**:

- 90% of business bugs: rule order, condition expression, priority
- 9% hardware bugs: sensor faults, thread desync
- 1% code bugs: plugin written incorrectly

## 7. Permanent Architecture Prohibitions (red lines)

These behaviors are **permanently forbidden** — no iteration may break them:

- No rule grouping, layering, sub-rules, scene nesting
- No business logic / judgment / modes inside `main.py`
- No business if-else inside any plugin
- No concurrent action execution (single-rule-per-cycle is permanent mutex)
- No `sleep` for business delays
- No cross-thread variable writes
- No abandoning the flat structure to revert to hard-coded flows
- No loading `rules.json` from network / untrusted sources (eval injection)

## 8. Core Architectural Advantages (design intent)

- **Extreme readability**: read `rules.json` and you understand the whole machine
- **Extreme maintainability**: change business by changing config, not code
- **Zero conflicts**: natural priority preemption; no action mutex bugs
- **Hardware/software decoupling**: hardware in its own thread; business pure config
- **Zero-code business iteration**: pair with a visual editor; field debugging without code
- **Standardization & transferability**: fixed 4 files, fixed workflow, fixed debug procedure; team-wide consistency

## 9. Final Verdict

This Table Programming architecture delivers, through:

> **fixed 4 files + thread-safe hardware/business separation + flat single-layer rules + state-variable workflow + priority-preemption conflict avoidance**

a new-generation automation programming paradigm: **stable kernel, fully configurable business, transparent logic, layered debugging, conflict-free system**.

All future projects must follow this guideline. **No new architecture, no new patterns.**
