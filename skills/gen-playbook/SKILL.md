---
name: gen-playbook
description: Generate Playbook-as-Code YAML definitions for automated DB incident response. Creates trigger conditions, action sequences, rollback procedures, and escalation rules based on common DB failure patterns.
argument-hint: "[playbook-name] [db-type: postgresql|mysql|mssql]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate Playbook-as-Code

You are generating a YAML playbook for the **NeuralDB** self-healing system.

## Arguments
- Playbook name: $0
- Target DB type: $1 (default: postgresql)

## Reference
- Read `ai-db-monitor-architecture-spec-v3.md` for playbook schema
- Read `docs/screen2_selfhealing.html` for Playbook UI reference

## Playbook Schema

```yaml
# playbook-name.yaml
name: "{playbook-name}"
version: "1.0"
description: "Brief description of what this playbook remediates"
agent: "autonomy-l{level}"
min_autonomy_level: 3
db_type: [postgresql, mysql, mssql]

trigger:
  type: metric_threshold | anomaly_detection | schema_change | manual
  metric: "{metric_name}"
  condition: "> | < | == | != | between"
  threshold: "{value}"
  duration: "{time_window}"
  cooldown: "{min_interval_between_triggers}"

preconditions:
  - check: "{validation_query_or_command}"
    expect: "{expected_result}"
    fail_action: skip | alert | escalate

actions:
  - name: "{step_name}"
    type: sql | command | api_call | agent_invoke
    command: "{sql_or_command}"
    timeout: "{max_duration}"
    retry: {count: 3, backoff: exponential}
    validate:
      query: "{validation_query}"
      expect: "{expected_result}"
    on_failure: continue | halt | rollback | escalate

rollback:
  - name: "{rollback_step}"
    command: "{undo_command}"

escalation:
  on_failure: page_sre_team | create_incident | notify_slack
  channel: "{notification_channel}"
  severity: critical | warning | info

metadata:
  author: "ai-agent | human"
  tags: [performance, lock, replication, schema, security]
  last_tested: "{date}"
  success_rate: "{percentage}"
```

## Common Playbook Templates

| Playbook | Trigger | Key Actions |
|----------|---------|-------------|
| lock_remediation | lock_wait_timeout > 5000ms | detect_blocking → profile_plan → kill_or_rewrite |
| index_optimization | sequential_scan_ratio > 80% | identify_missing_index → simulate → create_concurrent |
| replication_lag | replication_lag > 5s | check_wal_sender → adjust_params → alert |
| connection_pool | active_connections > 80% | identify_idle → terminate_idle → adjust_pool |
| memory_pressure | shared_buffers_hit_ratio < 95% | analyze_cache → adjust_params → restart_if_needed |
| vacuum_maintenance | dead_tuples > threshold | analyze_bloat → run_vacuum → reindex |
| query_timeout | query_duration > 30s | identify_query → check_plan → suggest_optimization |

## Output Location
```
engine/app/playbooks/{playbook-name}.yaml
```

## Rules
- All actions must be idempotent
- Include rollback for every destructive action
- Validate before and after each step
- Respect autonomy level (don't auto-execute if level < min_autonomy_level)
- Log every action to remediation_log
