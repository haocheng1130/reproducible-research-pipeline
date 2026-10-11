# Manually Created Data

Data that **cannot** be recreated by code goes here, and it is kept under
version control: hand-collected tables, one-off files from a provider, or
mappings you curated yourself. For each file, record:

| File | What it is | Where it came from (and when) | License / may it be shared? |
|---|---|---|---|

Everything that `doit` can rebuild belongs in `_data/` or `_output/` instead
(both gitignored). Use Git LFS for large files. Do not commit licensed vendor
data (CRSP, Compustat, TAQ, ...) here.
