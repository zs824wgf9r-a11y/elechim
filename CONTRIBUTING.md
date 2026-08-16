# Contributing

Pull requests and issues are welcome, but be aware of two things:

1. **The project is tied to a specific two-machine setup** (Mac mini + PC with
   an NVIDIA GPU). There is no CI that can reproduce that hardware, so PRs from
   different setups will be reviewed carefully but cannot be fully tested here.
2. **The most useful reports contain numbers.** Logs, `nvidia-smi` output,
   timings, token counts, and before/after measurements are how every design
   decision in this project was made. "It feels slow" is hard to act on; "first
   turn went from 7s to 45s, prompt cache 0%" is not.

## What to avoid

- Do not include personal data, conversation excerpts, or document contents in
  issues or PRs. Numbers and logs are fine; contents are not.
- Do not add decorative badges for builds, coverage, or metrics that are not
  actually measured.

## Language

Internal documentation (`AGENTS.md`, `INCARICO-*.md`, `PIANO-DOCUMENTI.md`) stays
in Italian: it is working memory, not the showcase. The showcase files
(`README.md`, `CONTRIBUTING.md`) are in English so the project can be found and
read by the widest audience.
