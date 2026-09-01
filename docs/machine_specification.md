# Machine Specification

Recorded on 2026-08-31 before the frozen sweep.

| Component | Value |
|---|---|
| Host OS | Windows 11, build family 10.0.26200 |
| CPU | 13th Gen Intel Core i9-13900HX, 24 physical / 32 logical cores |
| RAM | 63.7 GiB |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, driver 592.82 |
| Python | 3.12.13 |
| PyTorch | 2.13.0+cpu; CUDA unavailable to the experiment process |
| SUMO | 1.27.1, Windows MSVC build |
| Git | 2.50.1.windows.1 |
| Shell | PowerShell 7.6.4 |

The IDQN training and all traffic simulations use CPU execution. API latency is
measured end to end from this host and includes the host's Internet path.
