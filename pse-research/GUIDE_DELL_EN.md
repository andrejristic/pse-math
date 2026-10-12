# PSE Research — Dell Guide (EN)
### What you do on the Dell, in order

The Surface built the whole shared engine (105/105). The Dell is where the
**Dell-class** work runs: mathlib at scale, real candidate generation, the live
swarm, and network-exposed defence. Nothing here is a fork — you switch to
`Profile.dell(...)` and the same code runs bigger.

Each step has an ACCEPT gate. Do not start a step before the previous one passes.
Legend: 🔧 install/config · 🧱 code to write+test here · ✅ acceptance.

---

## 0. Bring the project across · 🔧
Copy `~/Desktop/PSE/PSE Math/pse-research/` to the Dell. Install the Lean
toolchain (`elan`) exactly as on the Surface, then:
```sh
cd pse-research && ./run_tests.sh        # must still be 105/105 on the Dell
```
✅ 105/105 on the Dell before anything else.

---

## 1. mathlib + the Lake verifier · 🔧
This is the ~5–6 GB step the Surface skipped.
```sh
cd ~
lake new pse_corpus math                 # project depending on mathlib
cd pse_corpus
lake exe cache get                       # DOWNLOAD prebuilt oleans — do NOT compile
lake build                               # links against the cache
```
Then use the Lake-mode verifier (mathlib available to proofs):
```python
from pse_research.verifier import LeanBackend
from pse_research.shared_lib import ResearchSharedLib
lib = ResearchSharedLib("research.db",
                        backend=LeanBackend("/home/<you>/pse_corpus"))
# LeanBackend auto-detects the lakefile and runs `lake env lean`.
```
✅ Push a candidate that `import Mathlib...` and uses a real mathlib lemma; it
passes C1 against the cache. Push a false one; it is rejected at C1.

---

## 2. Switch to the Dell profile · 🔧
```python
from pse_research.config import Profile
prof = Profile.dell("/home/<you>/pse_corpus")
# verifier=LEAN_LAKE, model=REMOTE, max_live_units=16, guardian1_enabled=True,
# ingestion_network_enabled=True, gui_live_socket=True
```
Everything downstream reads `prof`. This is the entire "Dell version".

---

## 3. RemoteModelBackend — real candidate generation · 🧱
`model_backend.py` ships `RemoteModelBackend` as a loud placeholder. Implement it
here (this is a Dell action per the spec: remote calls are reserved for heavy
generation, and every call is a COSTED action for the budget).
- Implement `generate_candidate(prompt, context) -> ModelResult(text, cost)`;
  return a Lean declaration string that the gate will then check.
- Keep phrasing (`phrase`) light/local; only generation goes remote.
- **Budget:** treat each remote call as a costed action so `budget_report()`
  means something (build spec Sec 13).
✅ A generated candidate flows generation → gate (C1–C7) → stored, with its cost
journalled. A generated proof with `sorry` is still rejected by C2.

---

## 4. The swarm runner — Phase 4 · 🧱 (the big one)
Wire the pieces the Surface built into a live loop: multiple `ResearchUnit`s,
Prover-Skeptic per candidate, SHARED_LIB-controlled phase transitions
(RECON→ASSAULT→CONSOLIDATION), fission, sibling-candidate exchange at the
boundary, and **pathology detection with real responses** (forced RECON on
Circle, budget floor on Helix, forced divergence on Closing Spiral, replacement
on Opening Spiral). The detectors and unit already exist and are tested; you are
writing the orchestration that drives them each step and acts on the verdict.
✅ (build spec Phase 4) A deliberately induced **Closing Spiral** (two units
seeded on the same method) is detected by basis-overlap and forcibly diverged;
an induced **Circle** (a unit fed only its own output) is detected and
terminated. *If the detectors cannot catch failures you PLANTED, they will not
catch the ones you did not.*

---

## 5. Guardian 2, full — Phase 5 · 🧱🔧
Turn on the model-backed checks and the continuous sweep.
- Inject a real `drift_check` (via `RemoteModelBackend`) into `Guardian2` so G1
  (statement drift) fires — the highest-value check.
- Feed the curator's aligned (informal↔formal) pairs (Section 10 below) to
  calibrate G1.
- Run the continuous corpus **sweep ordered by blast radius** (re-review stored
  lemmas, not just new arrivals) on idle daemon capacity; push severe findings to
  the queue.
✅ G1 catches a lemma you deliberately mis-formalized; the sweep re-surfaces a
bad lemma stored earlier that has since acquired dependents.

---

## 6. Seldon on real data — Phase 7 · 🔧
Let branches close and record `BranchRecord`s. The engine is built and tested;
it just needs ≥ 20 closed branches per problem shape before it says anything
(conservatism is deliberate — do not tune on 3 points).
✅ With ≥ 20 closed branches, `top_method(shape)` matches your judgement — or the
disagreement is interesting rather than obviously wrong.

---

## 7. Knowledge ingestion with the network on — addendum A1 · 🧱🔧
On the Dell profile `ingestion_network_enabled=True`, so `NetworkScraper` is
allowed. Implement its fetch (sandboxed) into quarantine; the `Curator` and
`ExternalStore` already exist. **Never execute scraped Lean** — it is text until
a unit knowingly proposes it as a candidate.
✅ Scraped mathlib/nLab/errata land in the external store as cheap signals; RECON
dedup and Guardian 2 pairs read them; nothing scraped ever enters the corpus.

---

## 8. Guardian 1 — Phase 8 · 🧱
Only once the deployment is exposed beyond the local machine (remote daemon
access, published corpus endpoint, collaborators). It sandboxes the scraper,
validates inputs, rate-limits, and lands its threat-intel in the SAME journal and
queue as Guardian 2 (one inbox).
✅ Build when network-exposed; its minimal form (scraper sandbox) already exists
from step 7.

---

## 9. Daemon as a service + live GUI · 🔧
```sh
# pse-researchd as a systemd USER service (runs whether or not the GUI is open)
systemctl --user enable --now pse-researchd
```
The GUI attaches over the Unix socket (`gui_live_socket=True`) as a pure client —
it may request, never mutate. On the Dell you also get live mode, not only replay.
✅ The GUI shows live branches, theta strips update, the queue populates; killing
the GUI does not stop the swarm.

---

## 10. The pilot — bounded prime gaps · 🧱 (the actual research)
Branches: **B1** admissible tuple search · **B2** Maynard–Tao sieve-weight
optimization · **B3** formalize the existing chain in Lean (best *first* real
work; needs mathlib) · **B4** barrier mapping (most likely first real
contribution + the source of GAP_HYPOTHESIS).
⚠️ **CALIBRATION TEST FIRST:** the system must independently re-derive a KNOWN
result end to end — gate, Guardian 2, absorption, the lot — before any novel
claim is taken seriously. If it cannot reproduce what is known, its novelty is
noise.
✅ A known bounded-gaps result is reproduced end to end; only then do B4's gap
hypotheses get weight.

---

## Order summary
0 tests pass → 1 mathlib → 2 profile → 3 remote model → 4 swarm (planted-failure
gate) → 5 Guardian 2 full → 6 Seldon (≥20) → 7 ingestion network → 8 Guardian 1
→ 9 service+GUI → 10 pilot (calibration first).

Honest Null still holds: if the pilot yields only a formalized restatement of
known work plus a barrier map of confirmed gaps, that is a real, recordable
outcome — not a failure.
