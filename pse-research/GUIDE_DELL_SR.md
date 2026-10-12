# PSE Research — Dell Vodič (SR)
### Šta radiš na Dell-u, redom

Surface je izgradio ceo deljeni engine (105/105). Dell je gde ide **Dell-klasa**:
mathlib u punom obimu, prava generacija kandidata, živi roj, i mrežno-izložena
odbrana. Ništa nije fork — prebaciš na `Profile.dell(...)` i isti kod radi veće.

Svaki korak ima ACCEPT kriterijum. Ne kreći sledeći dok prethodni ne prođe.
Legenda: 🔧 instalacija/config · 🧱 kod koji se piše+testira ovde · ✅ prihvatanje.

---

## 0. Prenesi projekat · 🔧
Kopiraj `~/Desktop/PSE/PSE Math/pse-research/` na Dell. Instaliraj Lean toolchain
(`elan`) isto kao na Surface-u, pa:
```sh
cd pse-research && ./run_tests.sh        # mora i dalje 105/105 na Dell-u
```
✅ 105/105 na Dell-u pre svega ostalog.

---

## 1. mathlib + Lake verifikator · 🔧
Ovo je onaj ~5–6 GB korak koji je Surface preskočio.
```sh
cd ~
lake new pse_corpus math                 # projekat sa zavisnošću od mathlib-a
cd pse_corpus
lake exe cache get                       # PREUZMI gotove oleane — NE kompajliraj
lake build                               # linkuje se na cache
```
Pa koristi Lake-mod verifikator (mathlib dostupan dokazima):
```python
from pse_research.verifier import LeanBackend
from pse_research.shared_lib import ResearchSharedLib
lib = ResearchSharedLib("research.db",
                        backend=LeanBackend("/home/<ti>/pse_corpus"))
# LeanBackend sam detektuje lakefile i pokreće `lake env lean`.
```
✅ Gurni kandidata koji `import Mathlib...` i koristi pravu mathlib lemu; prolazi
C1 protiv cache-a. Gurni lažnog; odbijen na C1.

---

## 2. Prebaci na Dell profil · 🔧
```python
from pse_research.config import Profile
prof = Profile.dell("/home/<ti>/pse_corpus")
# verifier=LEAN_LAKE, model=REMOTE, max_live_units=16, guardian1_enabled=True,
# ingestion_network_enabled=True, gui_live_socket=True
```
Sve nizvodno čita `prof`. To je cela „Dell verzija".

---

## 3. RemoteModelBackend — prava generacija kandidata · 🧱
`model_backend.py` isporučuje `RemoteModelBackend` kao glasni placeholder.
Implementiraj ga ovde (to je Dell akcija po spec-u: remote pozivi rezervisani za
tešku generaciju, i svaki poziv je KOŠTAN — za budžet).
- Implementiraj `generate_candidate(prompt, context) -> ModelResult(text, cost)`;
  vrati string Lean deklaracije koju kapija onda proverava.
- Drži frazu (`phrase`) laganu/lokalnu; samo generacija ide remote.
- **Budžet:** tretiraj svaki remote poziv kao koštan da `budget_report()` nešto
  znači (spec Sek. 13).
✅ Generisan kandidat teče generacija → kapija (C1–C7) → uskladišten, sa troškom
u journalu. Generisan dokaz sa `sorry` i dalje odbijen na C2.

---

## 4. Swarm runner — Faza 4 · 🧱 (najveći komad)
Poveži delove koje je Surface izgradio u živu petlju: više `ResearchUnit`-a,
Prover-Skeptik po kandidatu, SHARED_LIB-kontrolisani fazni prelazi
(RECON→ASSAULT→CONSOLIDATION), fisija, razmena kandidata na boundary-ju, i
**detekcija patologija sa pravim odgovorima** (forsiran RECON na Circle, budget
floor na Helix, forsirana divergencija na Closing Spiral, zamena na Opening
Spiral). Detektori i jedinica već postoje i testirani su; ti pišeš orkestraciju
koja ih pokreće svaki korak i deluje na presudu.
✅ (spec Faza 4) Namerno izazvan **Closing Spiral** (dve jedinice na istoj metodi)
detektovan preko basis-overlap-a i razdvojen; izazvan **Circle** (jedinica
hranjena samo svojim izlazom) detektovan i ugašen. *Ako detektori ne hvataju
greške koje si SAM posadio, neće ni prave.*

---

## 5. Guardian 2, pun — Faza 5 · 🧱🔧
Upali model-hookove i kontinuirani sweep.
- Ubaci pravi `drift_check` (preko `RemoteModelBackend`) u `Guardian2` da G1
  (statement drift) opali — najvrednija provera.
- Hrani ga curatorovim poravnatim (neformalno↔formalno) parovima (Sek. 7 dole)
  za kalibraciju G1.
- Pokreni kontinuirani corpus **sweep po blast radius-u** (re-review uskladištenih
  lema, ne samo novih) na praznom kapacitetu daemona; teške nalaze u red.
✅ G1 uhvati lemu koju si namerno pogrešno formalizovao; sweep ponovo iznese lošu
lemu uskladištenu ranije koja je u međuvremenu dobila zavisnike.

---

## 6. Seldon na pravim podacima — Faza 7 · 🔧
Pusti da se grane zatvaraju i beleže `BranchRecord`-e. Engine je izgrađen i
testiran; treba mu ≥ 20 zatvorenih grana po obliku problema pre nego što išta
kaže (konzervativnost je namerna — ne tuniraj na 3 tačke).
✅ Sa ≥ 20 zatvorenih grana, `top_method(shape)` se slaže sa tvojim sudom — ili je
neslaganje zanimljivo, a ne očigledno pogrešno.

---

## 7. Knowledge ingestion sa upaljenom mrežom — addendum A1 · 🧱🔧
Na Dell profilu `ingestion_network_enabled=True`, pa je `NetworkScraper` dozvoljen.
Implementiraj mu fetch (sandbox) u karantin; `Curator` i `ExternalStore` već
postoje. **Nikad ne izvršavaj scraped Lean** — to je tekst dok ga jedinica svesno
ne predloži kao kandidata.
✅ Scraped mathlib/nLab/errata slete u external store kao jeftini signali; RECON
dedup i Guardian 2 parovi ih čitaju; ništa scraped nikad ne uđe u korpus.

---

## 8. Guardian 1 — Faza 8 · 🧱
Tek kad je deployment izložen van lokalne mašine (remote pristup daemonu,
objavljen corpus endpoint, saradnici). Sandbox-uje scraper, validira unos,
rate-limit, i sleće threat-intel u ISTI journal i red kao Guardian 2 (jedan
inbox).
✅ Gradi kad je mrežno izložen; minimalna forma (scraper sandbox) već postoji iz
koraka 7.

---

## 9. Daemon kao servis + živi GUI · 🔧
```sh
# pse-researchd kao systemd USER servis (radi bez obzira da li je GUI otvoren)
systemctl --user enable --now pse-researchd
```
GUI se kači preko Unix socket-a (`gui_live_socket=True`) kao čist klijent — sme da
traži, nikad da menja. Na Dell-u imaš i živi mod, ne samo replay.
✅ GUI prikazuje žive grane, theta strip se ažurira, red se puni; gašenje GUI-ja ne
zaustavlja roj.

---

## 10. Pilot — bounded prime gaps · 🧱 (samo istraživanje)
Grane: **B1** admissible tuple pretraga · **B2** Maynard–Tao sieve-weight
optimizacija · **B3** formalizacija postojećeg lanca u Lean (najbolji *prvi*
realni posao; treba mathlib) · **B4** barrier mapping (najverovatniji prvi pravi
doprinos + izvor GAP_HYPOTHESIS-a).
⚠️ **PRVO KALIBRACIONI TEST:** sistem mora nezavisno re-izvesti POZNAT rezultat
end-to-end — kapija, Guardian 2, absorpcija, sve — pre nego što se ijedan nov
claim uzme ozbiljno. Ako ne može reprodukovati poznato, novina mu je šum.
✅ Poznat bounded-gaps rezultat reprodukovan end-to-end; tek onda hipoteze o
rupama iz B4 dobijaju težinu.

---

## Sažetak redosleda
0 testovi prolaze → 1 mathlib → 2 profil → 3 remote model → 4 roj (kapija na
posejanim greškama) → 5 Guardian 2 pun → 6 Seldon (≥20) → 7 ingestion mreža →
8 Guardian 1 → 9 servis+GUI → 10 pilot (prvo kalibracija).

Honest Null i dalje važi: ako pilot da samo formalizovano prepričavanje poznatog
plus barrier map potvrđenih rupa, to je realan, zapisiv ishod — ne neuspeh.
