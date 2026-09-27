# INTEL.md — forensic reading of the four given files

Sources: `dogfoodhack.com.md` (the brief), `spec.md` (the contract), `run.py` (the grader),
`fixtures.json` (the dataset). Written before any implementation code.

---

## 1. What the organisation actually wants

This is not a "build a CRUD app" hackathon with a scoring rubric bolted on. The brief says it
in plain text three separate times: **they are commissioning software they intend to run in
production for the next decade of their events.** "We are not shopping for inspiration. We are
commissioning software, in the open, and paying for it."

Consequences that change engineering decisions:

- **Adoptability is a first-class feature, not polish.** 20% of the score, and the brief's
  framing is "could we run this on Monday?" A stranger must go from clone to running portal with
  one command and no questions asked.
- **They already know what the product is.** Thirty-five events of experience. They are not
  evaluating product imagination; they are evaluating whether you got the boring parts right.
  "Build the boring parts well" is the literal last line of `spec.md`.
- **They have named the industry's failure and will check whether you repeated it.** Every
  incumbent ships the same nine features and then stops: no weighted rubric, no documented
  normalization, gameable voting, no public API. Those four gaps are the four bonus challenges.
  The gaps *are* the brief.
- **Honesty is scored, and dishonesty is the only thing explicitly penalised.** "Saying you got
  further than you did is the one thing that actually costs you points." Repeated on the website
  as "Overclaiming costs more than the tier was worth."
- **Tone.** Terse, operator-voice, allergic to marketing. Documentation written in that register
  will read as native. Documentation written as LLM filler will read as exactly what the brief
  calls out in Out of Scope item 06: "LLM dumps with no architecture document and nobody able to
  defend the schema in writing."

### Score weights, and what actually moves them

| Criterion | Weight | What it's really measuring | Where it is won |
| --- | --- | --- | --- |
| Tier Completion & Correctness | 40% | `run.py` output + honest claims | 7 checks passing, no overclaim note |
| Judging Integrity | 25% | backend role isolation, normalization maths, audit trail, abuse thinking | `JUDGING.md`, the 403s, the audit log |
| Adoptability & Operability | 20% | one command, seeded, docs a stranger can follow, migration in *and out* | `docker compose up`, `DATA-MODEL.md` |
| Code Quality & Innovation | 15% | idiomatic code, a schema a DB person would defend, "the decision a judge would steal" | the schema, the normalization engine |

**Structural insight:** `run.py` only verifies T1 and T2 (seven checks). 40% of the score is
gated on seven HTTP requests, and **65% of the total score (Integrity + Adoptability + Code) is
decided by documents and code a human reads.** Most teams will optimise for the seven checks.
The seven checks are the *entry fee*, not the prize.

**Second structural insight:** the bonus challenges do not add to the score. They break ties and
they decide the Best Judging Engine prize. So a bonus is only worth doing if it is done to a
standard that survives a statistician reading it — "Do not half-do all four."

---

## 2. Requirement checklist

Tagged `HARD` (explicit rule / grader-checked), `IMPLIED` (stated as behaviour or example but not
as a rule, or logically forced by something else), `BONUS` (optional, tie-break only).

### Submission validity — fail any of these and nothing else matters

1. **HARD** — `docker compose up` brings up a working, seeded portal with the network off.
   No cloud account, no hosted DB, no external API, no signup. (`spec.md` §"five things"; website
   Rule 02, and four explicitly "closed loopholes".)
2. **HARD** — OSI-approved licence in the repo. MIT or Apache-2.0 preferred.
3. **HARD** — all project code written inside the 72-hour window.
4. **HARD** — `.dogfood.toml` at repo root with honest tier claims.
5. **HARD** — `acceptance-report.txt` committed, whatever it says.
6. **HARD** — public repo, T1 cleared (a submission that does not clear T1 is not judged).
7. **HARD** — docs present: `README.md`, `ARCHITECTURE.md`, `DATA-MODEL.md`, `JUDGING.md`, demo video.
8. **IMPLIED** — `tests/` directory. Listed in "anatomy of a serious submission" as "your own
   tests, beyond the acceptance suite", and Out of Scope 06 punishes undefendable work. Not checked
   by `run.py`; visible to a human in five seconds.

### T1 core

9.  **HARD** — authentication and sessions.
10. **HARD** — five-role model: visitor, participant, judge, organizer, admin. (Website names all
    five; the role-isolation matrix has a row for each.)
11. **HARD** — event creation with configurable dates, tracks and prizes.
12. **HARD** — team formation *by invite link* (the mechanism is specified, not just "teams").
13. **HARD** — project submission with draft-and-edit until the deadline.
14. **HARD** — deadline enforcement that actually holds. **Grader check T1.03.**
15. **HARD** — public gallery with search and filter. **Grader checks T1.01, T1.02.**
16. **IMPLIED** — the submission field set, given as a "Reference" and stable across every platform
    they studied: name, tagline, long description, thumbnail, image gallery, hosted demo video URL,
    repository URL, live link, tech tags, track, **plus organizer-defined custom questions**.
    Phrased as a reference rather than a rule — so most teams will ship `title` + `summary` +
    `repo_url` (the three fields `fixtures.json` happens to contain) and silently miss eight fields
    and the custom-question mechanism.
17. **IMPLIED** — the gallery must be **server-rendered**, or at least return fixture titles in the
    raw response body. See §3: the grader substring-matches the response bytes. A client-rendered
    SPA fails T1.02 while looking perfect in a browser. This is the highest-probability silent
    failure in the whole suite.

### T2 judging

18. **HARD** — judge invitation and assignment, "by batch or algorithmically".
19. **HARD** — scoring against a **weighted**, organizer-configurable rubric. (Called out twice as
    the market leader's headline failure — this is a graded opinion, not a feature request.)
20. **HARD** — role isolation enforced in the backend. A judge must never see another judge's
    scores. **Grader check T2.02, called "the one that matters most".**
21. **HARD** — *a track judge must never see another track.* Same bullet as 20, second sentence.
    **Not covered by any grader check.** See §5 — this is a hidden requirement.
22. **HARD** — live progress dashboard so an organizer can see who has not started.
23. **HARD** — cross-judge normalization, with the method documented and defended.
24. **HARD** — CSV export **at every stage** (not one endpoint). **Grader check T2.04** tests one.
25. **HARD** — judge can read their own scores. **Grader check T2.01.**
26. **HARD** — participant is not a judge. **Grader check T2.03.**
27. **IMPLIED** — the portal must survive uneven review coverage: "Your portal should not fall over
    when a project has two reviews and its neighbour has five." Stated as a soft "should"; the
    fixtures make it unavoidable (8 projects with 2 reviews, 4 with 5).
28. **IMPLIED** — "a documented way to even out judges who score harshly or generously" (T2 one-line
    summary). Note this is a *different* sentence from 23, and it names the two failure modes the
    fixtures actually contain.
29. **IMPLIED** — "Tell us what you did about the judge who marks everything a 3." The website
    escalates this from a feature to a question you will be asked. `fixtures.json` contains that
    judge (see §4).
30. **IMPLIED** — an audit trail "an organizer can read without a database client". Listed under T3
    anti-abuse, but Judging Integrity (25%) asks for it as a T2-level question.

### T3 public

31. Community voting with configurable access: open link, email-gated, or authenticated.
32. Comments on gallery projects.
33. Results hidden from everyone but organizers during the voting window.
34. Randomised project ordering on ballots, to kill position bias.
35. Anti-abuse: rate limits, duplicate detection, readable audit trail.
36. **IMPLIED** — "or something better than one-person-one-vote, if you can defend it" (quadratic
    voting named as the most credible attempt). Optional alternative, rewarded if defended.

### T4 stretch

37. REST API and webhooks covering every action the UI can take.
38. Certificate and record generation.
39. Signed, publicly verifiable judge participation records.
40. Embeddable gallery widget.
41. Bulk import and export ("so an organizer can leave as easily as they arrived" — echoed in
    Adoptability: "a platform you cannot leave is a trap").

### Bonuses (tie-break only, do not change the score)

42. **BONUS +5 Hard** — Normalization Proof: implement it, prove it on the fixture data, show raw
    scores, normalized scores, **and the ranking change**, documented so a statistician would not
    wince.
43. **BONUS +5 Hard** — Pairwise Mode: Bradley-Terry / Crowd-BT style estimator.
44. **BONUS +3 Medium** — Threat Model: sybil votes, ballot stuffing, submission scraping, judge
    collusion, deadline gaming. "The honest list is worth more than the heroic one."
45. **BONUS +3 Medium** — API First: every UI action available through a documented API with a
    published OpenAPI spec.

---

## 3. `run.py` forensics

It is 269 lines. Read as an adversary, it has seven assertions and about a dozen exploitable or
dangerous details.

### Execution order (matters — later checks reuse earlier state)

| # | Tier | Label | Request | Pass condition |
| --- | --- | --- | --- | --- |
| 1 | T1 | gallery is public | `GET base+routes.gallery`, **no auth header** | `status == 200` |
| 2 | T1 | project from fixtures shown | *reuses body from check 1* | any of first 3 fixture titles, lowercased, appears as a substring of the lowercased body |
| 3 | T1 | closed event refuses submissions | `POST base+routes.submit` as `auth.participant`, JSON body `{"title":"dogfood-late-submission-probe","summary":"probe"}` | `400 <= status < 500` |
| 4 | T2 | judge sees own scores | `GET base+routes.judge_scores` as `auth.judge_a` | `status == 200` |
| 5 | T2 | judge cannot see peer scores | `GET base+routes.peer_scores` as `auth.judge_b` | `status in (401, 403)` |
| 6 | T2 | participant blocked | `GET base+routes.judge_scores` as `auth.participant` | `status in (401, 403)` |
| 7 | T2 | csv export works | `GET base+routes.csv_export` as `auth.organizer` | `status == 200` **and** `","` in the first line of the body |

Check 2 does **not** issue its own request. If check 1 times out, `gallery_body` is the exception
string and check 2 fails too. One slow gallery response loses two checks and, via the tier gate,
the entire report.

### Comparison logic

- Everything is **status-code equality**, except check 2 (case-insensitive substring on raw response
  bytes) and check 7 (`"," in body.splitlines()[0]`).
- **No tolerance, no fuzzy matching, no structural JSON comparison anywhere.** There is nothing to
  approximately satisfy. Either the number is right or it is not.
- Check 2 greps the *raw body*. HTML entities matter: if a title contained `&`, template escaping
  would turn it into `&amp;` and break the match. The first three fixture titles are
  `Glass Signal`, `Small Meadow`, `Deep Compass` — plain ASCII, no escaping hazard. Lucky, not safe:
  a hidden fixture set could contain one.
- Check 7 needs a comma **on line one**. A single-column CSV fails. A leading comment line or a
  UTF-8 BOM before the header fails.

### The transport, precisely

```python
req = urllib.request.Request(url, method=method)
if header:
    name, _, value = header.partition(":")
    req.add_header(name.strip(), value.strip())
```

- **Exactly one header is attached.** Auth must fit in one header. `partition(":")` splits on the
  *first* colon, so `Cookie: session=abc` and `Authorization: Bearer abc` both work.
- `TIMEOUT = 10` seconds, per request. Cold-start lazy work (building an index, computing
  normalization for 41 projects on first hit) must not land inside a graded request.
- `except Exception: return 0, ...` — connection refused, DNS failure, timeout and TLS errors all
  collapse to status `0`, which fails every comparison. **A portal that is still booting scores
  zero across the board**, so the container must not report ready before it can serve.
- `urlopen` follows redirects. On a 301/302/303 urllib **rewrites POST to GET**. So if
  `routes.submit` 302s to a login page or to a canonical slash-suffixed path, check 3 turns into a
  GET that returns 200 and the check fails. **No redirects on any graded route.**
- No `Accept` header is sent, and `Accept-Encoding: identity`. Content negotiation cannot be relied
  on: the graded gallery route must return its fixture-title-bearing representation by default.

### Config parsing — two parsers, and they disagree

`load_config` uses `tomllib` on Python ≥3.11 and falls back to the hand-rolled `parse_toml` below
that. **macOS ships Python 3.9.** The brief says "Any Python 3, including the one already on your
Mac", so the fallback is a live code path for at least some judges, and it is not TOML:

```python
line = raw.split("#")[0].strip()
```

- **A `#` anywhere in a value truncates it**, inside quotes or not. Real TOML would keep it.
  A `pitch` with a `#`, or a token containing `#`, parses differently for a judge on 3.9 than for
  me on 3.11. → **Constraint: no `#` character anywhere in `.dogfood.toml` values.**
- Arrays are parsed by `re.findall(r'"([^"]*)"', value)` — **double quotes only**. Single-quoted
  array items silently become an empty list, which empties `claimed`.
- Keys before the first `[section]` are silently dropped (`if not sep or section is None: continue`).
- No multi-line values, no inline tables, no nested keys.
- → **Constraint: `.dogfood.toml` must be written in the intersection of both parsers.** Single-line
  double-quoted values, every key under a section header, no `#`, no cleverness.

### `routes` lookups and the fallback landmine

```python
def url(key, suffix=""):
    return base + routes.get(key, "")
...
probe = base + routes.get("peer_scores", routes.get("judge_scores", ""))
```

- A missing route key becomes the empty string, so the request silently goes to `base_url` itself.
  A typo'd key name does not error — it tests the wrong URL.
- **If `peer_scores` is omitted it falls back to `judge_scores`**, which judge B legitimately gets a
  200 on (their own scores), so check 5 fails with "the backend returned another judge's scores"
  when nothing is actually wrong. Omitting the key looks like a security bug in the report.
- `base_url` is `.rstrip("/")`-ed; route values are concatenated raw. Routes must start with `/`.

### The tier gate

```python
verified = [t for t in TIERS if any(c.tier == t for c in checks)
            and all(c.ok for c in checks if c.tier == t)]
solid = []
for t in TIERS:
    if t in verified: solid.append(t)
    else: break
```

- A tier counts only if **every** check in it passes, and only if every tier below it also passed.
  One T1 failure zeroes T2 as well, even if all four T2 checks pass. **The seven checks are one
  atomic unit, not seven independent points.**
- There are **no T3 or T4 checks**, so `verified` can never contain T3 or T4. `solid` is capped at
  `["T1","T2"]` **for every team in the hackathon.**
- Therefore `claimed = ["T1","T2","T3"]` *always* prints
  `note: claimed but not verified: T3` — mechanically indistinguishable from overclaiming, which is
  the one penalised act. See §5 for the judgement call this forces.
- `claimed` is filtered against `TIERS`, so junk values are dropped silently; `claimed` has **no
  effect on `solid`**. It only affects the two closing lines.
- Exit code is always `0`. The report is the artefact; the exit status is meaningless. CI that
  gates on `$?` is gating on nothing.

### Fixture discovery

```python
candidates = ["fixtures.json",
              os.path.join(here, "fixtures.json"),            # beside run.py
              os.path.join(beside_config, "fixtures.json"),   # beside .dogfood.toml
              os.path.join(beside_config, "data", "fixtures.json")]
```

First hit wins, starting with **CWD-relative** `fixtures.json`. If the fixture file is missing,
`fixture_titles` returns `[]`, `any([])` is `False`, and check 2 fails with "no fixture file was
loaded". → **Commit `fixtures.json` at the repo root, next to both `run.py` and `.dogfood.toml`,
so all four candidate paths resolve.**

### Code paths never exercised by a well-formed run

| Path | When it fires | Why it matters |
| --- | --- | --- |
| `parse_toml` | judge on Python < 3.11 | different semantics; see the `#` rule above |
| `fixture is None` branch | fixture file missing | prints a note and dooms check 2 |
| `status == 0` | portal not up, or >10 s | every check fails; boot ordering is a graded concern |
| `status == 200` note in check 5 | the isolation bug | the one line they want to print about you |
| CSV `else` branch | 200 with no comma | silent formatting trap |
| `suffix` parameter of `url()` | never | dead code — no hidden probe is assembled from it |
| non-`fixture['projects']` keys | never read | the grader reads **only** `event.submissions_close` (for a message) and the first three project titles |

That last row is the most useful single finding in this section: **`run.py` never looks at judges,
teams, tracks, scores, or projects 4–41.** Everything else in `fixtures.json` is there for the
*human* judges and for the shape of your data model. Which means the fixtures are not grader input
— they are a specification of the awkward cases you are expected to survive, delivered as data.

### What `run.py` explicitly defends against (i.e. what not to break)

- Never raising on an HTTP error status — it *wants* to see your 4xx, so error responses must be
  real HTTP statuses, not 200-with-an-error-body.
- Accepting both 401 and 403 — it does not care whether you distinguish "unauthenticated" from
  "forbidden", so both are safe, but a 404 on a peer-scores probe **fails**. Hiding the resource is
  not accepted as refusing it; you must affirmatively deny.
- Reading `resp.read()` on both success and error paths — a 4xx with an empty body is fine.
- Searching four plausible fixture locations — they expect you to move the file and do not punish it.
- Tolerating a missing `auth` table entirely (`cfg.get("auth", {})`) — so an unauthenticated POST to
  `submit` returning 401 would pass check 3 **for the wrong reason**. A deliberate trap for anyone
  who "fixes" a failing check by removing config.

---

## 4. `fixtures.json` forensics

41 projects (not 40), 40 teams, 30 judges, 8 tracks, 126 scores, 1 event. Every id is a string,
every timestamp is ISO-8601 Z. Project fields present: `id, team, track, title, summary, repo_url,
submitted_at` — seven of the ~twelve fields requirement 16 lists, so the fixture is a *subset* of
the specified submission model, not a definition of it.

### Referential integrity: clean

No duplicate ids, no orphan references, no unknown tracks, no `(judge, project)` score collisions,
no team-member email appearing twice, no judge who is also a participant, no non-ASCII anywhere.
So the file does **not** test malformed-input handling. Every planted case is a *semantic* edge
case, not a parsing one. That is a deliberate choice and it tells you where the difficulty is meant
to be: in the judging maths and the data model, not in the ingest.

### The planted cases, and what each one is for

| Fixture evidence | Category | What it tests | Named in `spec.md`? |
| --- | --- | --- | --- |
| `prj_41` duplicates `prj_07`: same team `tm_07`, same title `Dry Harbour`, same `repo_url`, submitted 13.5 h later at `17:57` — 3 minutes before the `18:00` close | duplicate / deadline gaming | do you detect it, and does the leaderboard double-count one team? | "A duplicate submission" |
| `jdg_07` Iva Petrova: 3 reviews, **every single criterion = 4**, σ = 0 | degenerate scorer | **z-score normalization divides by zero here.** Does your maths produce `NaN`, or handle it? | "A judge who gave every single project the same score" |
| `jdg_01` Tomas Varga: **1 review**, mean 2.00 — the harshest scorer in the set | unfinished batch + harsh judge, confounded | with n=1 you *cannot* separate judge bias from project quality. Does your method pretend it can? | "Two review batches that were never finished" |
| `jdg_23` Anya Sokolova: **1 review**, empty comment | unfinished batch | the second never-finished batch | as above |
| `jdg_02` mean 4.22 vs `jdg_01` mean 2.00 — a **2.22-point spread on a 5-point scale** between judges | generous vs harsh | the entire reason normalization is 25% of the score | "even out judges who score harshly or generously" |
| Review counts per project: **8 projects with 2, 26 with 3, 3 with 4, 4 with 5** | uneven coverage | ranking projects whose scores have very different standard errors | "two reviews and its neighbour has five" |
| Judge load: 1 to **11** reviews (`jdg_24` has 11, `jdg_26` 10, `jdg_29` 9) | unbalanced design | per-judge statistics are wildly unequal in reliability; naive per-judge standardisation is invalid here | no |
| 51 of 126 comments are empty strings (40%) | optional fields | empty-vs-null handling in export, UI and CSV | "Text, sometimes empty." |
| All criteria values are in **2..5** — nobody ever scored a 1 | scale range | a rubric hardcoded to the observed range is wrong; the scale is 1–5 | no |
| Track load: `trk_04` has 8 judges / 5 projects, `trk_01` and `trk_08` have 3 judges / 6 projects | assignment fairness | an assignment algorithm that ignores track capacity will starve two tracks | no |
| **Zero** track mismatches in 126 scores — every judge only ever scored inside their assigned tracks | invariant | the fixture demonstrates the T2 rule "a track judge must never see another track". Your assignment algorithm must preserve it | implied by requirement 21 |
| `prj_07`/`prj_41`: `jdg_19`, `jdg_21` and `jdg_26` each scored **both** copies | duplicate × assignment | one team consumed 9 of the 126 review slots. Naive dedup at read time still leaves the wasted budget and the double-counted judges | no |
| Every project has ≥ 2 reviews; **no project has 0** | gap in coverage | the zero-review case is *not* in the fixtures but is guaranteed in a real event — and division by `len(scores)` crashes there | no |
| `submissions_close` = `2026-03-01T18:00:00Z`, i.e. **in the past** | deadline | seeded honestly, the portal is already closed — which is exactly what grader check 3 requires | yes, explicitly |
| Latest submission `2026-03-01T17:57:00Z` — 3 minutes inside the deadline | boundary | off-by-one on the close comparison (`<` vs `<=`) changes whether the last project is valid | no |
| 13 solo teams, 12 pairs, 6 triples, 9 quads | team shapes | team model must not assume ≥2 members | no |

### Categories

- **Happy path:** 26 projects with exactly 3 reviews, in-range scores, clean references.
- **Boundary:** the 17:57 submission vs the 18:00 close; criteria never hitting 1 on a 1–5 scale;
  solo teams; 40% empty comments.
- **Semantic corruption:** the duplicate submission pair and its shared reviewers.
- **Statistical pathology:** σ = 0 judge; n = 1 judges; 2.22-point harsh/generous spread;
  review counts from 2 to 5; judge loads from 1 to 11.
- **Fairness / capacity:** track-level judge-to-project imbalance.
- **Malformed input:** **absent.** Nothing here tests your parser. If a hidden fixture set exists,
  this is where it will differ — see §6.
- **Performance stress:** **absent.** 41 projects, 126 scores, 30 judges. Nothing needs an index to
  be fast, and no algorithmic choice can be justified on the fixture sizes alone. Anything O(n²) in
  projects is still free here; the constraint is the 10-second grader timeout, not the data volume.

### Fixture → requirement mapping

| Requirement | Fixture evidence that forces it |
| --- | --- |
| 14 deadline holds | `submissions_close` in the past; grader check 3 |
| 15/17 gallery shows fixtures | first three titles: `Glass Signal`, `Small Meadow`, `Deep Compass` |
| 21 track isolation | zero cross-track scores in 126 observations |
| 22 progress dashboard | `jdg_01` and `jdg_23` with 1 review each; 8 under-reviewed projects |
| 23/28/29 normalization | σ = 0 judge, n = 1 judges, 2.22 mean spread |
| 24 CSV export | 40% empty comments and 2-to-5 review counts make row shape non-obvious |
| 27 uneven coverage | review-count distribution 2/3/4/5 |
| 35 duplicate detection | `prj_07` / `prj_41` |
| 12 teams | 13 solo teams |
| 18 assignment | track capacity imbalance; judge loads 1–11 |

---

## 5. Cross-reference: contradictions, gaps, and things unexplained

**(a) `run.py` reads almost none of `fixtures.json`.** It touches `event.submissions_close` (only to
print it in a failure message) and the titles of the first three projects. The other 2,200 lines of
the file are not grader input. They are the human-judging surface. Teams that treat `fixtures.json`
as "the thing the tests check" will under-build; teams that treat it as a specification of required
behaviours will over-deliver on the 25% and 15% criteria.

**(b) The grader cannot see requirement 21 (track isolation).** "A track judge must never see
another track" sits in the same bullet as the peer-scores rule that `run.py` does check, and the
role-isolation matrix on the website has a dedicated "Other track" column marked
"✗ DENIED AT THE API, NOT IN THE UI". There is no automated check for it. A human reading for
Judging Integrity (25%) will look, because the matrix is their own artefact. **Hidden requirement.**

**(c) The role-isolation matrix contains four columns and `run.py` checks one.** Columns: Own
scores, Peer scores, Other track, Aggregate, Audit log — across five actor rows. That is 25 cells.
`run.py` verifies three of them (judge→own = permitted, judge→peer = denied, participant→own =
denied). The matrix is a published, machine-shaped spec that nobody is machine-checking. Implementing
all 25 cells and *testing them myself* converts an unverifiable claim into evidence.

**(d) `spec.md` and the website disagree in emphasis about tier claims.** The website says: "Claim
T3 in your README and pass T2 in the report, and you score T2 with a note about the gap" — which
reads as permission to claim ahead of the report. `spec.md` says overclaiming "is the one thing that
actually costs you points". And §3 shows `run.py` *cannot ever* verify T3 or T4 for anybody.
**This needs a human decision** (see §7).

**(e) "CSV export at every stage" vs one checked endpoint.** The grader tests one CSV route. T2
requires export at every stage, and Adoptability requires "a migration path in and out". One CSV
endpoint satisfies the grader and fails both human criteria.

**(f) `spec.md` says "Almost nothing here is a restriction" and means it.** Route names, schema,
stack, layout are all explicitly unchecked. Every constraint that actually exists is in `run.py`'s
transport behaviour, not in the prose. That asymmetry is the whole reason for this document.

**(g) The website's own figure is a spec for the normalization bonus.** FIG. 03 shows
"RAW JUDGE SPREAD / 5 JUDGES σ = 0.94 · UNCALIBRATED" → "NORMALIZED / SAME 5 JUDGES σ = 0.31 ·
METHOD DOCUMENTED" and then "RANK MOVEMENT ▲4 PROJECT 17, ▲1 PROJECT 04, ▼3 PROJECT 22, ▼6 PROJECT
09 / FIXTURE SET · 40 PROJECTS". They have already drawn the deliverable: a before/after σ and a
rank-movement table computed on these exact fixtures. Producing that artefact matches their own
mental model of a correct answer.

**(h) Nothing in either document explains the `suffix` parameter of `url()`.** It is dead code.
Most plausibly a vestige of an earlier draft that probed `gallery + "?q=..."` for the search
requirement. Cheap insurance: make the gallery route tolerate arbitrary query strings without
changing its status code or dropping fixture titles from the body.

---

## 6. Where hidden tests would most plausibly differ

The fixtures contain no malformed input and no scale. If the panel runs anything beyond `run.py`,
these are the gaps it would probe, ranked by likelihood:

1. A project with **zero** reviews (guaranteed in a real event, absent here) — anything dividing by
   review count crashes or shows `NaN`.
2. A **1** or a **0** or a `null` in a criteria value; a criteria key the rubric does not define.
3. A title with `&`, `<`, a quote, or non-ASCII — breaks the grader's raw-body substring match if
   escaped, breaks the CSV if unquoted (a title containing a comma is the classic).
4. An event whose deadline is in the **future**, exercising the draft-and-edit path the fixture
   event's past deadline makes unreachable.
5. A judge assigned to zero tracks; a track with zero judges.
6. A second event, testing whether anything is accidentally global instead of event-scoped.
7. Volume: 400 projects instead of 41, to catch an O(n²) gallery or an un-indexed join.

---

## 7. Ranked: what separates passing from dominant

**Passing** is seven HTTP checks and five committed files. It is a weekend of unremarkable work and
it will be achieved by most of the field. Ranked by marginal score per unit of effort:

1. **Do not fail a check for a transport reason.** Server-rendered gallery containing fixture titles
   (requirement 17), no redirects on graded routes, boot-before-ready ordering, sub-10-second
   responses, both-parsers-safe `.dogfood.toml`, `peer_scores` present. §3 says every one of these
   fails silently and takes the *whole* report with it via the tier gate. This is pure downside
   protection and it is where most of the field will lose 40%.
2. **Make role isolation real and then make it visible.** 25% of the score, and the brief tells you
   it is "the most common way a good looking project loses points". The differentiator is not
   passing check 5 — everyone who reads `run.py` passes check 5. It is implementing all 25 cells of
   the published role matrix, and shipping a test file that asserts each one, so a human does not
   have to take it on faith.
3. **Ship the normalization proof as an artefact, not a paragraph.** The fixtures contain a σ=0
   judge and two n=1 judges specifically to break naive z-scoring. A method that handles those
   *by construction* — and a reproducible before/after rank-movement table on the fixture data,
   matching FIG. 03 — is simultaneously requirement 23, bonus 42, most of Judging Integrity, and the
   Best Judging Engine prize. Highest-leverage single deliverable in the event.
4. **Detect the duplicate and say what you did about it.** `prj_07`/`prj_41` is a planted trap with a
   second-order effect nobody will notice: three judges scored both copies, so one team consumed 9
   of 126 review slots. Flagging it, excluding it from the ranking while *keeping* its observations
   for judge calibration, and logging the decision, is the "decision that made a judge stop and say
   they would steal it" that Code Quality & Innovation explicitly asks for.
5. **An audit trail that logs the denials.** The 403 that check 5 provokes should appear as a
   readable audit entry. It turns an invisible security property into something a judge can watch
   happen. Cheap; nobody else will do it.
6. **Honest, quantified gap reporting.** Explicitly rewarded twice. A README that names what is not
   built, with the report to match, outscores a claim of completeness.
7. **One command, genuinely.** 20% of the score. Seeded, offline, no post-start manual steps, and a
   documented way out (bulk export), because "a platform you cannot leave is a trap".
8. **A schema a database person would defend.** Explicit DDL with constraints and indexes beats
   ORM-generated tables when `DATA-MODEL.md` has to quote it.

### The one thing I need a human decision on

**Tier claim.** `run.py` structurally cannot verify T3 or T4 for any team (§3, §5d). So any claim
beyond T2 prints `note: claimed but not verified: …` in the committed report, which looks identical
to the one penalised act. Options: claim exactly `["T1","T2"]` and describe further work in the
README as explicitly unverified, or claim what was built and accept the note. Recommendation and
rationale in `PLAN.md` → DECISION 01.
