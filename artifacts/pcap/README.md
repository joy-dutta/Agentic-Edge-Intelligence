# Packet Captures

The optional Docker network harness writes `.pcap` files here while measuring the difference between edge and cloud communication paths. Packet captures are generated locally and ignored because they are binary, environment-specific measurement outputs.

Run the harness from the repository root with the commands in [`docs/network_harness.md`](../../docs/network_harness.md). Then reconcile captured transport bytes with application counters:

```bash
python scripts/reconcile_pcap.py --architecture edge
```

Repeat with `--architecture cloud`. The small released reconciliation summaries are kept in [`artifacts/tables`](../tables/README.md).
