# Macroeconomic Simulator

**On econvitals.org:** the [Macroeconomic Simulator](https://econvitals.org/lab/frbus-simulator/): policy and economic shocks run through the Federal Reserve Board’s own FRB/US model, with the Fed’s response, the duration and the way expectations are formed chosen by the reader.

**Where the code is.** The Simulator has its own replication package, built from the same engine that produced every run the page shows: [macro-simulator-replication.zip](https://econvitals.org/lab/frbus-simulator/replication/macro-simulator-replication.zip) (about 31 MB), linked in the last paragraph of the page. It is kept beside the page rather than here because it carries the Board’s model and its baseline data exactly as the runs were made, and it is rebuilt whenever the engine changes.

**What is in it.** The engine’s code; the Board’s `pyfrbus` package and the LONGBASE baseline the stored runs were solved from (both public domain, from the Federal Reserve Board); CSV copies of every input typed into the engine; a README, a method note and a list of sources; pinned Python requirements; the page’s own stored runs as `expected/`; and `verify.py`, which reruns the model and compares.

**Run it.** Unzip, create a Python 3.14 environment with the package’s `requirements.txt`, and run `python verify.py`. It needs no network and no keys. Before each release of the package, Econvitals runs exactly that in a fresh environment with the network blocked: a sample of 238 stored runs (two from every stored file) rebuilds to the last digit in about 22 minutes.

**How close.** Exact. The stored runs are what the page interpolates between; the package rebuilds them digit for digit.

**Why it is not in the nightly check.** Rebuilding the sample takes the better part of an hour of model solving, and the stored runs change only when the engine does, at which point the package is rebuilt and verified before it is published.

**License.** The package carries its own MIT license; everything else in this repository is CC0.
