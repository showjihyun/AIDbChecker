---
name: db-adapter
description: Generate a database adapter plugin for the NeuralDB monitoring system. Creates collector, analyzer, and query translator implementations for PostgreSQL, MySQL, or MS-SQL following the plugin architecture from the architecture spec.
argument-hint: "[db-type: postgresql|mysql|mssql] [feature: collector|analyzer|ash|all]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate Database Adapter

You are generating a DB adapter plugin for the **NeuralDB** system.

## Arguments
- Database type: $0
- Feature scope: $1 (default: all)

## Architecture Reference
Read `ai-db-monitor-architecture-spec-v3.md` for:
- Plugin-based DB adapter architecture
- Collector interface contracts
- ASH implementation per DB type

## Adapter Structure
```
engine/app/adapters/{db_type}/
├── __init__.py
├── adapter.py              # Main adapter class (implements BaseAdapter)
├── collector.py            # Metric collector (1s granularity)
├── ash_collector.py        # Active Session History collector
├── wait_event_mapper.py    # Wait event classification
├── query_analyzer.py       # Query plan analysis
├── schema_tracker.py       # DDL change detection
├── config.py               # DB-specific configuration
├── queries/                # SQL query templates
│   ├── metrics.sql         # System metrics queries
│   ├── ash.sql             # ASH sampling queries
│   ├── locks.sql           # Lock detection queries
│   ├── replication.sql     # Replication status queries
│   └── schema.sql          # Schema introspection queries
└── tests/
    ├── test_collector.py
    ├── test_ash.py
    └── conftest.py          # DB-specific fixtures
```

## Base Adapter Interface
```python
class BaseAdapter(ABC):
    @abstractmethod
    async def connect(self, config: DBConfig) -> None: ...

    @abstractmethod
    async def collect_metrics(self) -> MetricSample: ...

    @abstractmethod
    async def collect_ash(self) -> list[ActiveSession]: ...

    @abstractmethod
    async def get_wait_events(self) -> list[WaitEvent]: ...

    @abstractmethod
    async def get_locks(self) -> list[LockInfo]: ...

    @abstractmethod
    async def analyze_query(self, sql: str) -> QueryPlan: ...

    @abstractmethod
    async def get_schema_changes(self, since: datetime) -> list[SchemaChange]: ...

    @abstractmethod
    async def execute_remediation(self, action: RemediationAction) -> RemediationResult: ...
```

## DB-Specific Implementation Notes

### PostgreSQL
- Use `pg_stat_activity` for ASH sampling
- Use `pg_stat_statements` for query statistics
- Use `pg_locks` for lock detection
- Use `pg_stat_replication` for replication monitoring
- Use event triggers for DDL change tracking
- Connection via asyncpg (MIT)

### MySQL
- Use `performance_schema.threads` for ASH
- Use `performance_schema.events_statements_summary` for query stats
- Use `information_schema.INNODB_LOCKS` for lock detection
- Use `SHOW SLAVE STATUS` for replication
- Use `information_schema.TABLES` for schema tracking
- Connection via aiomysql (MIT)

### MS-SQL
- Use `sys.dm_exec_requests` for ASH
- Use `sys.dm_exec_query_stats` for query statistics
- Use `sys.dm_tran_locks` for lock detection
- Use `sys.dm_exec_sql_text` for query text
- Use DDL triggers for schema tracking
- Connection via aioodbc (Apache 2.0)

## Rules
- All I/O operations must be async
- Use connection pooling
- Handle connection failures gracefully with retry logic
- Normalize wait events to a common taxonomy
- 1-second collection interval must not overload the monitored DB
- Read-only connections by default (remediation uses separate write connection)
