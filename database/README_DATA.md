# Local database data is not part of the distributed source

Keep `signals.db` on durable storage outside Git. It holds trade data and the
persistent order-intent journal. Before any upgrade take a consistent SQLite
backup including active WAL, then verify recovery on a separate copy.
Do not replace a running database with an archived development sample.
