# Third-party dataset notices

This directory contains third-party data with its upstream licensing notices.
Keep these notices, attribution, provenance and license texts with redistributed
copies. The corpus is not relicensed as original NormLab data.

## RCB records (EXT-RCB-001 through EXT-RCB-024)

- Dataset: Russian Commitment Bank, Russian SuperGLUE / RussianNLP contributors.
- Source: <https://huggingface.co/datasets/RussianNLP/russian_super_glue>.
- Task: <https://russiansuperglue.com/tasks/task_info/RCB>.
- License declaration: <https://russiansuperglue.com/faq/> (MIT for the Russian datasets).
- [Unmodified upstream MIT notice](licenses/RCB-MIT.txt), including its
  `Copyright (c) 2020 New York University` line, from the RussianSuperGLUE repository.
- [Unmodified dataset card](upstream/rcb-card.md) retains the authors' references.
- Text fields and candidate labels are unchanged; NormLab selected a subset,
  renamed input fields, separated labels and added provenance metadata.

## Judicial records (EXT-SUD-001 through EXT-SUD-012)

- Dataset publisher: lawful-good-project.
- Source: <https://huggingface.co/datasets/lawful-good-project/sud-resh-benchmark>.
- Upstream declares `license: gpl-3.0`; preserved verbatim in the
  [dataset card](upstream/court-card.md). No later-version grant is inferred.
- [GNU GPL version 3 text](licenses/SUD-GPL-3.0.txt), downloaded from the pinned
  SPDX license-list-data release recorded in `upstream-sources.json`.
- The dataset card credits a Yandex OpenSource compute grant.
- Full selected `source` fields are unchanged. NormLab selected a subset, grouped
  related upstream task rows, renamed input fields and added provenance metadata.
- The upstream card is the license/attribution evidence available from the
  publisher; individual primary judgment publication URLs are not supplied.

The combined `inputs.jsonl` includes both subsets: retain the notices for both.
Per-record provenance identifies the upstream license. The readable files under
`texts/` provide the same text without an application-specific binary format.
