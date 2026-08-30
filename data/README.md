# Datasets

None of these are committed. They are large and separately licensed. The
simulator and detector run without them; only the fidelity harness
(`scripts/run_fidelity.py`) needs real data, because a noise floor requires a
real reference corpus.

## Required for F4

**IEEE-CIS Fraud Detection** — 590,540 real card-not-present transactions
contributed by Vesta Corporation. Kaggle competition `ieee-fraud-detection`.
You must join the competition from your account before the API will serve it.

    data/train_transaction.csv
    data/train_identity.csv

Used as the real-data noise floor. Note it has no entity identifier, so the
partition is reconstructed — see `chakra/fidelity/loaders.py` for the three
partitions we report and why the choice moves the answer.

## Optional cross-check

**Sparkov** — Kaggle `kartik2112/fraud-detection`. Carries a true entity id
(`cc_num`) and a realistic 0.58% fraud rate, so it validates the IEEE-CIS UID
reconstruction.

    data/fraudTrain.csv

Used only as a reference **corpus**, never as a real-data floor. Sparkov is
simulator output; its split-half floor is up to 21x tighter than IEEE-CIS's
because its halves come from one stationary process. Scoring against it would
inflate every degradation ratio by roughly an order of magnitude.
