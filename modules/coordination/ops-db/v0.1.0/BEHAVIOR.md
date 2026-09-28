# BEHAVIOR — ops-db
## MUST
- Remain standalone under `modules/coordination/ops-db/v<semver>/`.
- One shared SQLite; partitioned streams with **per-partition** FIFO/size caps.
- Fossil append-only: `occurred_at` + `recorded_at`; as-of = recorded_at prefix replay.
- Keep pins/claim SoT snaps off the short tool-call FIFO.
- Document: lasting proof = git + GitHub issues + benchmarks only.
## MUST NOT
- Global single FIFO that deletes pins when tool spam fills the DB.
- Self-learning forever store / unbounded growth.
- Embed on JEV hot path.
- Store secrets; redact before write.
