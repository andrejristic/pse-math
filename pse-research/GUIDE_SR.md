# PSE Research — Vodič (SR)
### Komponente poređane od NAJBITNIJE → MANJE bitne

Ovo je izgrađeno na Surface-u (jedan kod, biran preko `Profile`; **bez forka**).
Sve je čist Python + SQLite (+ opciono Lean za C1, + PySide6 za GUI). Ceo suite:
`./run_tests.sh` → **105/105**.

Čitaj odozgo nadole: što je stavka više, to više ceo sistem zavisi od toga da je
ona tačna.

---

### 1. KAPIJA — `shared_lib.py` + `verifier.py` · ⭐ najbitnije
Jedina vlast. Samo `SHARED_LIB.validate_contribution` skladišti lemu, i to tek
kad prođu C1–C7. *Ako kapija curi, sve iznad je pesak.*
C1 parse/typecheck · C2 nema escape hatch-eva (`sorry`/`sorryAx`/`admit`/`axiom`,
`native_decide` samo na whitelist-i) · C3 nema ciklusa · C4 iskorišćenost
hipoteza · C5 ne-vakuoznost · C6 ne-dupliranje · C7 zatvorenost zavisnosti.
Test: `tests/test_gate_adversarial.py`, `tests/test_gate_hardening.py`.

### 2. APPEND-ONLY JOURNAL — `journal.py`
Jedini izvor istine. Svaki događaj, zauvek; UPDATE/DELETE zabranjeni DB
triger-ima. GUI, raporti i ceo audit izvedeni su iz njega.
Test: `test_gate_adversarial.py::test_journal_append_only_enforced`.

### 3. PROFILI — `config.py` + backendi (`verifier.py`, `model_backend.py`)
Split Surface/Dell kao CONFIG, ne fork. `Profile.surface()` = simbolički/goli
Lean, stub model, 2 jedinice, replay GUI. `Profile.dell()` = lake+mathlib, remote
model, pun roj, živi socket. Sve konstante iz spec-a su ovde, na jednom mestu.

### 4. RESEARCH UNIT — `unit.py` + `theta.py` (Faza 2)
Jedna jedinica = jedna grana. Core (nepromenljiva misija), Boundary (provizorni
kandidati), Registry (zarađena baza), Theta (merena, u Fazi 2 ne upravlja ničim).
**Absorpcija = UPOTREBA, ne istina**: lema ulazi u bazu samo ako je VERIFIED,
rezidentna, nosiva, relevantna za misiju, i NIJE orphan. Test:
`tests/test_phase2_unit.py`.

### 5. DETEKTORI PATOLOGIJA — `detectors.py`
Circle (re-izvodi sebe), Helix (thrashing), Closing Spiral (prerana konvergencija,
preko preklapanja baza), Opening Spiral (schizoid: verifikovana mašinerija koju
niko ne koristi — najopasniji, hvata se samo orphan-stopom + ravnom sigmom).
Test: `tests/test_detectors.py`.

### 6. GUARDIAN 2 — `guardian2.py`
Skeptik dokaza: jaz između teoreme koju si NAPISAO i one koju si MISLIO. Nema
vlast nad kapijom; proizvodi nalaze. Strukturne provere rade odmah (G3 inflacija,
G4 imenovanje, G5 alpha-rename punjenje, G2 švercovanje); G1 statement-drift i G6
regresija su model-hookovi. Self-check hvata „vuče vukove".
Test: `tests/test_guardian2.py`.

### 7. GAP_HYPOTHESIS — `gap.py` (addendum A3)
Guardian 2 okrenut NAPOLJE: „ima li rupe vredne napada?". Konjekturalno, nikad u
korpusu. Dedup + prover-skeptik filter pre nego što te košta pažnje; rangirano u
red; tvoja presuda hrani val(B). Pretvara Honest Null (F5) u barrier map.
Test: `tests/test_gap.py`.

### 8. LJUDSKI RED + RAPORT FAJLOVI — `queue.py` + `reports.py` (A5/A2)
Jedan red sa cap-om (12/dan); stavke se odlažu, ne bacaju; trajni overflow je i
sam patologija. Svaka odluka piše i git-diffabilan markdown raport (izveden iz
journala, nikad drugi izvor istine). Test: `tests/test_queue_reports.py`.

### 9. PROVER-SKEPTIK + SELDON — `prover_skeptic.py` + `seldon.py`
Adversarijalna forma (zajednička kazna na kasnu refutaciju) i strateški engine
(replicator nad metoda×oblik-problema; refutacije koštaju više od rejecta;
konzervativan ispod 20 opservacija). Izgrađeno + testirano na sintetici sad.
Test: `tests/test_pvp_seldon.py`.

### 10. KNOWLEDGE INGESTION — `ingestion.py` (addendum A1)
Scraper (mreža, Dell) + Curator (offline, lokalno). External store = **jeftin
signal, tvrd zid, nikad korpus**. Tri potrošača: RECON/dedup, Guardian 2 parovi,
Seldon prior. Test: `tests/test_ingestion.py`.

### 11. CHAT — `chat.py` (Sek. 11 / A5)
Read-only query-primitivi sa freshness stampom (R1), register separacijom (R2),
dostupnim „ne znam" (R3). Vodi pokretanje (kaže gde da klikneš), nikad ga ne
piše. Test: `tests/test_chat.py`.

### 12. DAEMON / KLIJENT — `daemon.py` (Sek. 13)
Unix-socket površina za upite; **read-only nametnut na socket-u**, ne
konvencijom (write operacije prosto nisu u tabeli operacija).
Test: `tests/test_daemon.py`.

### 13. GUI (REPLAY MOD) — `gui.py` (Faza 3) · najmanje kritično za tačnost
PySide6, čist klijent, čita snimljeni journal. Overview / Graph / Frontier /
Queue / Lean + theta strip + chat. **Status nosi OBLIK, ne boja** (verified pun,
contested deblji, refuted precrtan, orphan šupalj).
Pokretanje: `QT_QPA_PLATFORM=offscreen python3 -m pse_research.gui --db research.db`
(izbaci env var na pravom desktopu). Test: `tests/test_gui_smoke.py`.

---

## Šta NIJE ovde (Dell-klasa)
mathlib-formalizacija u punom obimu; dugi živi rojevi sa pravom generacijom; pun
Guardian 1. KOD za sve to radi na Surface-u na toy skali — Dell to samo pusti
veće, prebacivanjem profila.

## Brzi start
```sh
./run_tests.sh                                   # 105/105
python3 -m pse_research.cli --db r.db push examples/good.json
python3 -m pse_research.cli --db r.db --lean ./proj push cand.json   # pravi Lean
QT_QPA_PLATFORM=offscreen python3 -m pse_research.gui --db r.db
```
