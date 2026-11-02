# Results Directory

This directory stores trial results, model outputs, and evaluation reports.

## Structure

```
results/
├── trials/          # Individual trial records (gitignored)
│   └── {task}/{variant}/{model}/{trial_id}/
│       ├── metadata.json
│       ├── candidate.py
│       ├── grader_output.txt
│       └── transcript.txt
├── reports/         # Generated analysis reports (gitignored)
└── README.md        # This file
```

Trial data and reports are excluded from version control via `.gitignore` to keep the repository lightweight. They should be archived separately for reproducibility.
