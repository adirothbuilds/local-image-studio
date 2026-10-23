# Benchmarks

Measured on 2026-10-23: Apple M5 Pro, 64 GiB unified memory, macOS 27.0.1, arm64, Python 3.12.15, MFLUX 0.23.0, MLX 0.32.4. FLUX.2 Klein 4B at revision `e7b7dc27f91deacad38e78976d1f2b499d76a294`, 8-bit runtime quantization, 4 steps, no reference images or lettering.

| Preset | Pixels | Median wall time | Range (3 runs) | Peak MLX GPU allocation |
| --- | --- | --- | --- | --- |
| Quick draft | 512 × 512 | 4.968 s | 4.930–5.126 s | 12.05 GB |
| Portrait | 832 × 1184 | 11.002 s | 10.984–11.057 s | 12.90 GB |

Raw reports: [draft](benchmarks/m5-pro-64gb-draft.json), [portrait](benchmarks/m5-pro-64gb-portrait.json).

## Method

Each image gets a fresh Python worker process and loads the model again. Wall time includes worker startup/imports, loading/quantization, inference, original PNG/metadata, and A4 PNG/PDF export. The worker also reports its own narrower elapsed interval. Peak GPU memory is MLX allocation reported by `mlx.core.get_peak_memory`, in decimal GB; it is not whole-system RAM usage or total process RSS.

One warm-up (seed 42) precedes three measured runs (seeds 43, 44, 45). Warm-up results are recorded but excluded from the summary. All runs use the same generic prompt recorded in the reports. No personal images, paths, names or credentials are included. OS file caches and previously compiled kernels may already be warm; the warm-up is not a clean-reboot cold-start measurement. Runs are serial, with no concurrent image generation. Power state and unrelated system activity were not controlled. This small sample describes one machine, not a statistical guarantee or a minimum hardware specification.

## Reproduce on another Mac

Stop terminal/service mode, then run:

```bash
./studio.sh benchmark --runs 3 --preset draft
./studio.sh benchmark --runs 3 --preset portrait
```

Reports and generated benchmark images go into `logs/benchmark-<UTC timestamp>/`. Compare identical model revision, package lock, resolution and steps. Record your power mode, chip/RAM, OS, workload and whether the model/kernel caches were cold. Reference editing and larger images can change time and memory needs.

A first setup downloads about 15 GiB of weights plus the runtime. That is separate from these generation timings. Normal website startup has no model load; the model loads only when a job starts.
