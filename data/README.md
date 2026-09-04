# Released Data

This folder contains compact data that is useful immediately after cloning the repository.

The [`processed/`](processed/README.md) folder holds the run-level analysis frames used to verify the released statistics. Raw run folders are generated under [`artifacts/raw`](../artifacts/raw/README.md), not here. Keeping a single raw-output location avoids ambiguity about which files the analysis scripts read.

The processed files are derived evidence, not hidden inputs: their source format, generation command, and field meanings are documented, and the repository includes checks that recompute the published tables from them.
