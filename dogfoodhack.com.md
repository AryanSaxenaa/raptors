\[ UNIT / DF-01 \]51.5310°N 0.0500°EREV 2.6SYS READY · REGISTRATION OPEN

# DOGFOODDOGFOODDOGFOODDOGFOOD

## Build the platform  that will judge you.

September 25-28, 2026 · Online

Free · $2,500 in prizes

[\[ Go to Discord \]](https://discord.gg/xfYPDZYqeh)

\[ BRIEF / 00 \]

Thirty-five hackathons in, across 85 countries, we know exactly what a submission and judging platform should do. So does every organizer who has ever run one. What none of us has is a modern, open, self-hostable platform that does it. This is the hackathon where you build it. The winning project is the one we run.

/// SCROLLHACKATHON RAPTORS ™

01\[ 01 / BY THE NUMBERS \]

UNIT / N-01 +

35

hackathons Hackathon Raptors has run since 2023, across 85+ countries. The spec for this event comes out of that.[\[15\]](https://dogfoodhack.com/#ref-15)

UNIT / N-02 +

0

major hackathon platforms publish an official public API. The whole ecosystem runs on scrapers and CSV export.[\[14\]](https://dogfoodhack.com/#ref-14)

UNIT / N-03 +

5 hours

for one judge to score 30 projects, by the largest platform's own estimate.[\[1\]](https://dogfoodhack.com/#ref-1)

UNIT / N-04 · COUNTDOWN

72h

to build the thing that replaces all of it.

02\[ 02 / THE PROBLEM \]

## Running a hackathon is a data problem wearing a party hat.

FIG. 01 — EVENT PIPELINE / 10 STAGESFAILURE SURFACE: STAGE 07

01Registration

02Teams

03Submissions

04Eligibility

05Assignment

06Scoring

07Normalization

08Results

09Certificates

10Archive

Registration, teams, submissions, eligibility, judge assignment, scoring, normalization, results, certificates, and an archive somebody can query two years later. Ten stages, each with its own state, each feeding the next. Get one wrong and the part that suffers is the judging, which is the part participants actually came for.

Hackathon Raptors has run thirty-five events on this pipeline since 2023, across 85 countries and roughly a dozen a year. That is where the specification for this hackathon comes from. We know which stage breaks first, which one nobody budgets for, and which one every organizer ends up doing by hand on the Sunday night. We have opinions earned the expensive way.

The obvious question is why nobody just uses the platforms that already exist. We studied them closely, and the answer is more interesting than "they cost money."

The incumbents converged. Devpost, Devfolio, TAIKAI, DoraHacks, HackerEarth and Unstop all ship the same nine things: an event microsite, registration, team formation, project submission, a public gallery, judge scoring, community voting, an organizer dashboard, and a CSV export.[\[2\]](https://dogfoodhack.com/#ref-2) [\[6\]](https://dogfoodhack.com/#ref-6) [\[9\]](https://dogfoodhack.com/#ref-9) [\[11\]](https://dogfoodhack.com/#ref-11) That list is not exotic. It is a weekend of work for a team that knows what it is doing.

Then they stopped. The largest platform in the category **cannot weight its judging criteria differently**. Its own documentation tells organizers who need weighted criteria to judge offline in a spreadsheet.[\[1\]](https://dogfoodhack.com/#ref-1) Devfolio advertises "automatic score normalization" as a headline feature and, like everyone else, **publishes nothing about how it works**.[\[6\]](https://dogfoodhack.com/#ref-6) [\[7\]](https://dogfoodhack.com/#ref-7) Community voting is universally conceded to be gameable: the standard advice is to keep the prize small and hide results until you have manually reviewed the votes.[\[1\]](https://dogfoodhack.com/#ref-1) And **not one of them has an official public API**, so the integration layer of an entire industry is unofficial scrapers and downloaded spreadsheets.[\[14\]](https://dogfoodhack.com/#ref-14)

> Build the platform that will judge you.
>
> \[ PULL QUOTE / DEGRADED · 1-BIT \]

Meanwhile the open-source tier proves the appetite is real. Gavel came out of HackMIT with a genuine idea inside it: stop asking judges for absolute scores and ask them which of two projects is better, then recover a global ranking with a Bradley-Terry estimator.[\[12\]](https://dogfoodhack.com/#ref-12) JunctionApp, Dribdat, Quill and Hibiscus all exist and are all self-hostable.[\[13\]](https://dogfoodhack.com/#ref-13) What nobody has assembled is a modern, self-hostable, API-first whole that a working organizer can run on Monday.

That is the gap. It is real, it is narrow, and it fits in 72 hours.

Dogfood is a 72-hour hackathon with one product in it. Everyone builds the same thing against the same spec: a submission and judging portal. We publish the spec, a real anonymised dataset, and an acceptance suite you run against your own build. You ship it open source. We take the winner, self-host it, and run our events on it.

We are not asking you to build a demo of a platform. We are asking you to build ours.

03\[ 03 / DOSSIER · WHAT HAPPENS TO THE WINNER \]

CLASSIFICATION / OPENFILE DF-2026-WSHEET 1 OF 1REV 2.6

## What happens to the winner

The part every other hackathon leaves vague, stated plainly.

01 / You keep your work.

Ship under MIT or Apache-2.0. The repo is yours. We do not ask for an assignment, a transfer, a CLA, or an exclusivity clause. There is nothing to sign.

02 / We fork it and run it.

The winning project gets forked, self-hosted, and put into production for Hackathon Raptors events. That is the prize behind the prize.

03 / You get credited where it counts.

Not a thank-you tweet. A credit line on every event page the platform powers, for as long as it powers them.

04 / We upstream back.

Every fix, hardening pass and feature we add on top gets sent back to your repository as a pull request. If you want them, take them. If you have moved on, the fork carries on and the credit stays.

05 / This is not a maybe.

We run roughly a dozen events a year and we intend to run the next decade of them on whatever wins. We are not shopping for inspiration. We are commissioning software, in the open, and paying for it.

/// One honest caveat, because you deserve it before you spend a weekend: if the top entries are close, we may adopt one and borrow ideas from another, with credit to both. We will say so publicly and in detail. What we will not do is quietly take your architecture and call it ours.

04\[ 04 / THE TIER LADDER \]

## The Tier Ladder

No tracks. One product, four tiers. Every team builds against the same published spec, and your score is how far up the ladder you climbed and how cleanly you did it.

T1Core

\[ LOCKED \]

**Required.** A submission that does not clear T1 is not judged. This is the floor, not the target.

- →Authentication and sessions
- →A real role model: visitor, participant, judge, organizer, admin
- →Event creation with configurable dates, tracks and prizes
- →Team formation by invite link
- →Project submission with draft-and-edit until the deadline
- →Deadline enforcement that actually holds
- →Public gallery with search and filter

**Reference:** the submission field set is stable across every platform we studied. Name, tagline, long description, thumbnail, image gallery, hosted demo video URL, repository URL, live link, tech tags, track, plus organizer-defined custom questions.[\[4\]](https://dogfoodhack.com/#ref-4) [\[5\]](https://dogfoodhack.com/#ref-5)

T2Judging

\[ LOCKED \]

Where the real engineering starts.

- →Judge invitation and assignment, by batch or algorithmically
- →Scoring against a **weighted**, organizer-configurable rubric. The market leader cannot weight criteria at all[\[1\]](https://dogfoodhack.com/#ref-1), and its closest rival ships one fixed five-criterion rubric that every event on the platform shares[\[8\]](https://dogfoodhack.com/#ref-8)
- →**Role isolation, enforced in the backend.** A judge must never see another judge's scores. A track judge must never see another track. If this only works because the UI hides a button, it does not work.
- →Live progress dashboard so an organizer can see who has not started
- →**Cross-judge normalization**, with your method documented and defended
- →CSV export at every stage

T3Public

\[ LOCKED \]

- →Community voting with configurable access: open link, email-gated, or authenticated[\[3\]](https://dogfoodhack.com/#ref-3)
- →Or something better than one-person-one-vote, if you can defend it. Quadratic voting, where casting n votes on one project costs the square root of n in influence, is the most credible attempt anyone has shipped at stopping a loud minority from deciding the outcome[\[10\]](https://dogfoodhack.com/#ref-10)
- →Comments on gallery projects
- →Results hidden from everyone but organizers during the voting window[\[1\]](https://dogfoodhack.com/#ref-1)
- →Randomised project ordering on ballots, to kill position bias[\[3\]](https://dogfoodhack.com/#ref-3)
- →Anti-abuse that means something: rate limits, duplicate detection, and an audit trail an organizer can read without a database client

T4Stretch

\[ LOCKED \]

- →A REST API and webhooks covering every action the UI can take
- →Certificate and record generation
- →Signed, publicly verifiable judge participation records
- →An embeddable gallery widget
- →Bulk import and export, so an organizer can leave as easily as they arrived

FIG. 04 — JUDGE ASSIGNMENT / BATCHED, DISJOINTNO JUDGE SEES A PEER'S BALLOTJUDGESPROJECTSJ-01J-02J-03J-04P-118P-204P-391BATCH 03 / 40 PROJECTS · 30 JUDGES · 3 REVIEWS PER PROJECTFIG. 02 — ROLE ISOLATION MATRIX / BACKEND-ENFORCED● EXPECTED

| Actor | Own scores | Peer scores | Other track | Aggregate | Audit log |
| --- | --- | --- | --- | --- | --- |
| VISITOR | ✗ | ✗ | ✗ | ✗ | ✗ |
| PARTICIPANT | ✗ | ✗ | ✗ | ✗ | ✗ |
| JUDGE | + | ✗ | ✗ | ✗ | ✗ |
| ORGANIZER | + | + | + | + | + |
| ADMIN | + | + | + | + | + |

\+ PERMITTED  ·  ✗ DENIED AT THE API, NOT IN THE UI  ·  VERIFIED BY ACCEPTANCE SUITE T2.03

**Climb honestly.** A clean, correct T2 scores above a broken T4 every time. Judges are reading for what works, not what is listed in your README.

05\[ 05 / WHAT COUNTS AS DONE \]

## What counts as done

The one rule that makes this judgeable, and it is verifiable in about a minute.

`docker compose up` **produces a working portal.** On localhost. Seeded with the fixture data we publish at kickoff. No cloud account, no API key, no external service, no signup.

**The acceptance suite runs against your build** and prints a tier-by-tier pass report. Publish that output in your repository. A judge should be able to confirm which tier you reached without reading a line of your code.

\[ CLOSED LOOPHOLES, NAMED UP FRONT \]

- →A hosted database service is a dependency on someone else's uptime and someone else's invoice. It must run locally.
- →Authentication-as-a-service is the same problem wearing a nicer hat. Build it or use something self-hosted.
- →A staging URL is not a submission. We need to run it, not visit it.
- →"Works on my machine" has never once been true.

If it does not come up on a laptop with the network off, we cannot adopt it, and adoption is the entire point of the event.

06\[ 06 / DELIVERABLES \]

## Deliverables

After 72 hours we want software an organizer could run. Not a design system. Not a slide deck.

**A working portal.** It starts with one command, seeds itself, and takes a project from submission through judging to published results.

**An acceptance report.** The output of our suite against your build, committed to the repository. This is your tier claim and your receipt at the same time.

**Honest documentation.**  `ARCHITECTURE.md` for how it fits together, `DATA-MODEL.md` for the schema and how an organizer gets data in and out, `JUDGING.md` for your scoring maths. These are read by judges and they carry weight.

You'll submit:

- →Public GitHub repo under an OSI-approved license
- →`docker compose up` to a seeded, working portal
- →`acceptance-report.txt`: the suite output, tier by tier
- →`README.md`: what it does, how to run it, what it does not do yet
- →`ARCHITECTURE.md`: the shape of the system and why
- →`DATA-MODEL.md`: schema, plus import and export paths
- →`JUDGING.md`: assignment strategy, scoring maths, normalization method, defended
- →5-minute demo video walking one full event lifecycle: create, submit, judge, publish

\[ ANATOMY OF A SUBMISSION \]

What a serious submission looks like on disk.

```
 your-portal/
 ├── README.md              ← what it does, how to run, honest limits
 ├── ARCHITECTURE.md        ← the shape of the system and why
 ├── DATA-MODEL.md          ← schema, import and export paths
 ├── JUDGING.md             ← assignment, scoring maths, normalization
 ├── docker-compose.yml     ← one command to a seeded, running portal
 ├── src/                   ← your code, all of it written this weekend
 ├── tests/                 ← your own tests, beyond the acceptance suite
 ├── acceptance-report.txt  ← our suite's output, tier by tier
 ├── LICENSE                ← MIT or Apache-2.0
 └── .dogfood.toml          ← tiers claimed, one-line pitch
```

**One command runs it.**  `docker compose up`, seeded, working. If a judge has to read your CI config to figure out how to start it, you have failed this rule.

**The acceptance report is the receipt.** Claim T3 in your README and pass T2 in the report, and you score T2 with a note about the gap.

**JUDGING.md counts.** It feeds straight into Judging Integrity (25%). "We averaged the scores" is an answer, and it is a weak one. Tell us what you did about the judge who marks everything a 3.

**Honest tier claims beat inflated ones.** A team that says "we reached T2, here is the T3 work we started and did not finish" scores above a team claiming T4 with three broken endpoints.

Layout is advisory. Judges read what you actually ship.

07\[ 07 / SCORING \]

## Scoring

Each project is rated on a 5-point scale across four weighted criteria. Final ranking is the weighted average across all judges who evaluated the project.

### Tier Completion & Correctness

40%

How far up the ladder you got, verified by the acceptance suite rather than by your README. T1 is a gate, not a score. Above that, correctness beats breadth: a clean T2 outranks a T4 with three features that half-work. Honest gap reporting is rewarded, inflated claims are penalised here.

### Judging Integrity

25%

The hard part, weighted like it. Is role isolation enforced in the backend or painted on the frontend? Is your normalization method documented and defensible, or did you average the scores and hope? Is there an audit trail an organizer can actually read? Did you think about vote abuse before a judge asked?

### Adoptability & Operability

20%

Could we run this on Monday? One command to running. Seeded with real data. Documentation a stranger can follow without asking you a question. A migration path in and out, because a platform you cannot leave is a trap. A clean license with no surprises.

### Code Quality & Innovation

15%

Does it read as idiomatic to a senior reviewer in your stack? Is the schema one a database person would defend? And the part we cannot specify in advance: the decision that made a judge stop and say they would steal it.

FIG. 03 — WEIGHT DISTRIBUTION / FINAL SCOREΣ = 100 · SCALE 1–5

40 TIER

25 INTEGRITY

20 ADOPT

15 CODE

RAW JUDGE SPREAD / 5 JUDGES

σ = 0.94 · UNCALIBRATED

NORMALIZED / SAME 5 JUDGES

σ = 0.31 · METHOD DOCUMENTED

RANK MOVEMENT

▲ 4  PROJECT 17▲ 1  PROJECT 04▼ 3  PROJECT 22▼ 6  PROJECT 09

FIXTURE SET · 40 PROJECTS

\[ BONUS CHALLENGES \]

Optional. Pick one and nail it. Do not half-do all four.

| Challenge | Difficulty | Points |
| --- | --- | --- |
| Normalization Proof | Hard | +5 |
| Pairwise Mode | Hard | +5 |
| Threat Model | Medium | +3 |
| API First | Medium | +3 |

+16MAXIMUM IF YOU TOOK ALL FOUR. NOBODY SHOULD.BONUSES BREAK TIES. THEY DO NOT CHANGE YOUR SCORE.

1DONE PROPERLY BEATS FOUR STARTED.

Normalization Proof+5 · Hard

Implement cross-judge score normalization and prove it works on the fixture data. Show the raw scores, the normalized scores, and the ranking change. Document the method well enough that a statistician would not wince. Every commercial platform claims to do this and none of them will tell you how.[\[6\]](https://dogfoodhack.com/#ref-6) [\[7\]](https://dogfoodhack.com/#ref-7)

Pairwise Mode+5 · Hard

Ship pairwise comparison as an alternative judging mode: show a judge two projects, ask which is better, recover a global ranking with a Bradley-Terry style estimator. This is the Gavel approach, and it sidesteps cross-judge calibration entirely by never asking for an absolute score.[\[12\]](https://dogfoodhack.com/#ref-12) Hard to get right, extremely satisfying when it works.

Threat Model+3 · Medium

A written, defensible threat model for voting and submission abuse. Sybil votes, ballot stuffing, submission scraping, judge collusion, deadline gaming. Name the attacks you stopped, and name the ones you did not. The honest list is worth more than the heroic one.

API First+3 · Medium

Every action available in the UI is available through a documented API, with a published OpenAPI spec. Nobody else in this category has one.[\[14\]](https://dogfoodhack.com/#ref-14) Be the first.

08\[ 08 / OUT OF SCOPE \]

## Out of Scope

Save yourself the trouble. These will not score well.

09WAYS TO SCORE NOTHING

1TEST THEY ALL FAIL

We are not against using a framework. We are against handing us something we cannot run.

- 01✗Design mockups, Figma files, or a frontend with hardcoded data behind it
- 02✗Anything that needs a cloud account, a hosted database, or an auth provider to start
- 03✗An authentication demo that stops at the login screen
- 04✗A gallery with no judging, or judging with no gallery, this is one product
- 05✗Role checks that live only in the frontend, if I can curl another judge's scores it is not isolation
- 06✗LLM dumps with no architecture document and nobody able to defend the schema in writing
- 07✗Closed source, or a license that is not OSI-approved
- 08✗Anything requiring custom hardware, GUI toolchains, or proprietary services, keep it laptop-friendly
- 09✗A rewrite of an existing open-source platform with the name changed

09\[ 09 / TIMELINE · ALL TIMES UTC · 2026 \]

## Timeline

FIG. 05 — THE 72-HOUR WINDOWT-0 = 25.09.2026 / 18:00 UTCT-0 KICKOFF+24H+48H+72H FREEZESCHEMA / AUTH / SUBMISSIONJUDGING / NORMALIZATIONACCEPTANCE / DOCS / VIDEO

\[ PRE-EVENT \]

AUG 24, 2026

Registration opens. Join the [Discord](https://discord.gg/xfYPDZYqeh), start sketching your schema.

SEP 04, 2026

Judging panel announced.

SEP 21, 2026

Team formation. 1-4 people per team. Solo welcome.

SEP 23, 2026

Raptors Conference, online and free. Unrelated event, same community, worth your afternoon.

SEP 24, 2026

`spec.md` published. Read it before the clock starts. No code yet.

[Read the spec >>>](https://dogfoodhack.com/spec)

\[ HACKATHON · 72H \]

SEP 25, 2026 @ 18:00 UTC

Kickoff. `fixtures.json` and the acceptance suite released. Hacking begins.

SEP 28, 2026 @ 18:00 UTC

Code freeze. Submissions due. Acceptance reports verified.

\[ POST-EVENT \]

SEP 28 → OCT 08, 2026

Judging window. Each project reviewed independently by multiple judges on structured forms across the window. Weighted scores and written feedback to every team.

OCT 05, 2026 @ 18:00 UTC

The Write Up Quest closes.

OCT 09, 2026

Winners announced. Adoption decision announced with them.

10\[ 10 / PRIZES \]

## $2,500 total prize pool.

FIG. 06 — POOL ALLOCATION / USD 2,500

1ST — GRAND PRIZE$80032%

2ND — RUNNER-UP$50020%

3RD PLACE$35014%

4TH PLACE$2008%

5TH PLACE$1506%

BEST JUDGING ENGINE$1004%

WRITE UP QUEST — $100 × 4$40016%

COMPARTMENT / P-01

$800

1st Place

**Grand Prize, and the one we run.** The portal that cleared the ladder honestly, enforced its own rules in the backend, started with one command, and read like software somebody intends to maintain. This is the project Hackathon Raptors forks and puts into production.

2

COMPARTMENT / P-02

$500

2nd Place

**Runner-Up.** Exceptional work across the board. Strong tier completion, defensible judging maths, documentation that respects the reader. Close enough that we will be reading it for ideas.

213

COMPARTMENT / P-03

$350

3rd Place

**Third Place.** A standout, either for how far it climbed in 72 hours or for one decision nobody else made.

4

COMPARTMENT / P-04

$200

4th Place

**Fourth Place.** Finished the climb and left something behind worth reading. Solid tier completion, honest scope, no shortcuts hiding in the backend.

5

COMPARTMENT / P-05

$150

5th Place

**Fifth Place.** Made the top five out of everyone who started. Something in this build works better than it had any right to after 72 hours.

COMPARTMENT / P-06

$100

Best Judging Engine

**For the team whose judging layer was the most defensible.** Assignment strategy, normalization method, role isolation, audit trail. The category prize for the problem the whole industry quietly avoids.

COMPARTMENT / P-07 · SIDE QUEST

$400

Write Up Quest

**Side quest. $100 x 4.**

Building a platform in 72 hours is hard. Explaining what actually happened is rarer, and more useful to everyone else. So we are paying for it.

What it is.Publish a write-up of your build. The schema you would redo. The normalization maths that fought you and won. The role-isolation bug you found at hour 60. The feature you cut and do not regret. The part where you realised the spec was harder than it looked.

How they are judged.On insight, not follower count. We are reading for technical substance: the debugging story, the benchmark that disappointed you, the design you abandoned and why. A 200-follower account writing something genuinely useful beats a viral thread that says nothing. Small accounts, this one is winnable.

Where.X, LinkedIn, Dev.to, your own blog, any developer-focused platform. Your call. Tag Hackathon Raptors.

Prize.Top 4 write-ups, $100 each.

When.Write any time from kickoff. Submissions close October 5, 18:00 UTC. Winners announced October 9 with the main results.

Optional. Does not affect your main score.

11\[ 11 / RULES \]

## Rules

What counts as a valid submission.

CHECKLIST · 09 ITEMS

01Open Source, OSI-Approved

02One Command To Running

03Clear T1 Or You Are Not Judged

04New Code Only

05No Hosted-Service Dependency

06Claim Your Tiers Honestly

07Team Size

08Source Code Public

09AI Tools Are Expected

If we cannot run it, we cannot adopt it. Every rule below is downstream of that one.

01 Open Source, OSI-Approved

MIT or Apache-2.0 preferred. Public at submission. You keep ownership of your repository. We do not ask for an assignment, a transfer, or a CLA.

02 One Command To Running

`docker compose up` brings up a working, seeded portal on a laptop. No cloud account, no hosted service, no external API. If we cannot run it, we cannot adopt it.

03 Clear T1 Or You Are Not Judged

T1 is the floor. Auth, roles, event, submission, gallery. A project that does not reach it is not scored, however good the parts are.

04 New Code Only

All project code written during the 72-hour window. Frameworks, libraries, boilerplate generators and AI assistance are all fair game. A pre-existing project of yours, or an existing open-source platform with the name changed, is not.

05 No Hosted-Service Dependency

It runs offline on a laptop. This is not an aesthetic preference, it is the condition for the winner being adoptable at all.

06 Claim Your Tiers Honestly

Declare the tiers you reached in `.dogfood.toml`. The acceptance report is the receipt. Overclaiming costs more than the tier was worth.

07 Team Size

1-4 people. Solo entries welcome, though this brief rewards a pair. Find teammates on the [Hackathon Raptors Discord](https://discord.gg/xfYPDZYqeh) before or during the event.

08 Source Code Public

GitHub repository, public at submission. Anonymous-username submissions accepted, but the team must be reachable for written follow-up by judges during the evaluation window.

09 AI Tools Are Expected

Claude Code, Cursor, Aider, Copilot, local models, bring whatever you have. We do not gatekeep on whether you used AI. We gatekeep on whether the thing holds up and whether somebody on the team can defend the schema in writing. The acceptance report, `ARCHITECTURE.md` and `JUDGING.md` are the receipts.

12\[ 12 / WHO THIS IS FOR \]

## If you have ever filled in a hackathon submission form and thought "I could build this, and better", here is your invitation to prove it.

Full-Stack Builders

This is a whole product in a weekend: auth, roles, forms, gallery, dashboards, exports. If you like shipping the entire thing yourself, the tier ladder is built for you.

Start at: T1 → T2

Backend & API Engineers

The interesting problems are all yours: role isolation that survives a curl, assignment algorithms, an export path that does not lose data, an API nobody else in this category bothered to build.

Start at: T2 → T4

Frontend & Design-System People

The judge console and the public gallery are the product. Thirty projects to score in five hours is a UX problem before it is anything else.[\[1\]](https://dogfoodhack.com/#ref-1) Make that not miserable and you have done something the incumbents have not.

Start at: T1 → T3

Data & Algorithms People

Cross-judge normalization and pairwise ranking are the genuinely hard parts, and the two Hard bonuses live here. Bradley-Terry, Crowd-BT, or something better you can defend.[\[12\]](https://dogfoodhack.com/#ref-12)

Start at: T2 + bonuses

Security Engineers

Role isolation, vote abuse, sybil resistance, audit trails. Every platform in this space treats community voting as a known-gameable feature they mitigate with policy rather than engineering.[\[1\]](https://dogfoodhack.com/#ref-1) Do better.

Start at: T2 → T3 + Threat Model

DevOps & Self-Hosting Folks

"One command to running" is not a nice-to-have here, it is 20% of the score and the reason the winner gets adopted. If you have opinions about how software should ship, this brief is downstream of all of them.

Start at: T1 → adoptability

13\[ 13 / JUDGES \]

## Judges

3REVIEWS PER PROJECT

36PANEL SEATS

11dEVALUATION WINDOW

_The panel is seated and assignments are issued. Reach out at [hello@raptors.dev](mailto:hello@raptors.dev) to nominate someone for a future event, or to be nominated._

Senior engineers, architects and technical leaders who have built and operated evaluation systems, run production software at scale, and sat on the other side of a judging form knowing it could have been better.

→Every project is reviewed independently, on structured forms, across the window.

→Judges never see one another's ballots. The platform you build has to hold that line too.

→Weighted scores and written feedback go to every team, placed or not.

PANEL · 36 · SEATEDEVALUATION 29.09 – 08.10.2026

- ![Anuj Kapoor](https://dogfoodhack.com/img/judges/anuj-kapoor.jpg)



### Anuj Kapoor



Microsoft · United States



Senior Software Engineer at Microsoft and an IEEE Senior Member, with 16 years building AI and cloud platforms at Microsoft, Amazon and Priceline. Agentic AI, multi-agent systems, enterprise automation and distributed systems, plus published research behind products serving millions of users.

[LinkedIn](https://www.linkedin.com/in/anuj-kapoor-38b6a899/)

- ![Smit Nitinkumar Shah](https://dogfoodhack.com/img/judges/smit-nitinkumar-shah.jpg)



### Smit Nitinkumar Shah



Microsoft · United States



Senior Software Engineer at Microsoft working on large-scale cloud platforms, distributed systems, Kubernetes and confidential computing. He has led platform work across Azure security, compliance, reliability and workflow orchestration, and has judged and mentored at hackathons before this one.

[LinkedIn](https://www.linkedin.com/in/smit-shah-a7060b1a)

- ![Rupesh Kumar Prasad](https://dogfoodhack.com/img/judges/rupesh-kumar-prasad.jpg)



### Rupesh Kumar Prasad



Analog Devices · United States



Principal architect with 18 years designing secure, scalable enterprise platforms across Azure, AWS and the Microsoft stack. Cloud architecture, identity and security, APIs, DevOps and data platforms, with an IEEE Senior Member's habit of reading a design for what breaks under load rather than what demos well.

[LinkedIn](https://www.linkedin.com/in/rupeshprasad/)

- ![Narasimha Reddy Annapareddy](https://dogfoodhack.com/img/judges/narasimha-reddy-annapareddy.jpg)



### Narasimha Reddy Annapareddy



ChargePoint, Inc. · USA



Software Engineering Manager for NetSuite Business Systems at ChargePoint, with 14 years in enterprise software and engineering leadership. His work is integrations across finance and supply chain operations, which is where data models either hold or quietly lose records.

[LinkedIn](https://linkedin.com/in/narasimha-annapareddy)

- ![Hari Krishna Bethanaboina](https://dogfoodhack.com/img/judges/hari-krishna-bethanaboina.jpg)



### Hari Krishna Bethanaboina



Martin Marietta Materials · USA



Lead Solutions Architect at Martin Marietta Materials, where he runs enterprise transformation programmes across ERP modernization, AI-driven asset maintenance and cloud migration. Twenty three years of delivery across the US, Europe, the Middle East, Asia and Africa, on systems governing $8B in assets across 400 sites. IEEE Senior Member, Oracle ACE Associate, and a peer reviewer for IEEE, Elsevier and Springer Nature.

[LinkedIn](https://www.linkedin.com/in/haribethanaboina)

- ![Igor Malovytsia](https://dogfoodhack.com/img/judges/igor-malovytsia.jpg)



### Igor Malovytsia



GuardSpine · United States



CTO at GuardSpine, co-founder and mentor at the Ukrainian Rust Community, currently researching AI governance. Deep Rust background, which shows up in how he reads ownership of state and error paths in someone else's codebase.

[LinkedIn](https://www.linkedin.com/in/igor-malovitsa/)

- ![Rushikesh Hayatnagarkar](https://dogfoodhack.com/img/judges/rushikesh-hayatnagarkar.jpg)



### Rushikesh Hayatnagarkar



United States



Senior Product Manager and hands-on AI builder working on technical infrastructure, autonomous multi-agent systems and large-scale platforms. He scores architectural depth and code integrity alongside whether the thing survives contact with real operations, and writes feedback aimed at what a team should do after the hackathon.

[LinkedIn](https://www.linkedin.com/in/rushikeshhayatnagarkar/)

- ![Konstantin Mishukov](https://dogfoodhack.com/img/judges/konstantin-mishukov.jpg)



### Konstantin Mishukov



United States



Lead iOS Engineer with more than ten years on production mobile systems. At Yandex Market he owned iOS work across search, backend-driven UI and payments serving millions of customers, and at Sberbank he was a key engineer on an award-winning business intelligence platform. Mobile architecture, code quality and data visualization, judged for production readiness.

[LinkedIn](https://www.linkedin.com/in/kmishukov/)

- ![Nail Iarmukhametov](https://dogfoodhack.com/img/judges/nail-iarmukhametov.jpg)



### Nail Iarmukhametov



Bulgaria



Cloud Infrastructure and DevOps Lead with ten years operating production systems on Kubernetes, AWS and Azure. Infrastructure as code, CI/CD, cloud security and reliability, which is the exact ground the one command to running requirement stands on.

[LinkedIn](https://www.linkedin.com/in/restaq)


// the rest of the panel

[![Sourav Sinha](https://dogfoodhack.com/img/judges/sourav-sinha.jpg)Sourav SinhaAmazon Web Services · United States Of America](https://www.linkedin.com/in/sourav-s-36a7a225) [![Nikolai Sidiropulo](https://dogfoodhack.com/img/judges/nikolai-sidiropulo.jpg)Nikolai SidiropuloMeta · United States](https://www.linkedin.com/in/nsidiropulo) [![Anton Musatov](https://dogfoodhack.com/img/judges/anton-musatov.jpg)Anton MusatovDigitail Inc. · Spain](https://www.linkedin.com/in/ayacaste/) [![Arun Kumar Kaliamoorthy](https://dogfoodhack.com/img/judges/arun-kumar-kaliamoorthy.jpg)Arun Kumar KaliamoorthyGoDaddy · United States Of America](https://www.linkedin.com/in/arunkumarspk) [![Dmitriy Fedoryshchev](https://dogfoodhack.com/img/judges/dmitriy-fedoryshchev.jpg)Dmitriy FedoryshchevEverCommerce · United Kingdom](https://www.linkedin.com/in/dife/) [![Dmitry Gusev](https://dogfoodhack.com/img/judges/dmitry-gusev.jpg)Dmitry GusevAvito · Georgia](https://www.linkedin.com/in/sw1tch3roo/) [![Dmitry Kuznetsov](https://dogfoodhack.com/img/judges/dmitry-kuznetsov.jpg)Dmitry KuznetsovFunnelFox · Serbia](https://www.linkedin.com/in/dmitry-kuznetsov-685b72194/) [![Gautam Siddhartha](https://dogfoodhack.com/img/judges/gautam-siddhartha.jpg)Gautam SiddharthaWalmart · USA](https://www.linkedin.com/in/gautam-siddhartha/) [![Ivan Antropov](https://dogfoodhack.com/img/judges/ivan-antropov.jpg)Ivan AntropovT-Bank · Russia](https://www.linkedin.com/in/ivan-antropov-9505a969/) [![Jose Galarza](https://dogfoodhack.com/img/judges/jose-galarza.jpg)Jose GalarzaWise · Singapore](https://www.linkedin.com/in/igalarzab/) [![Kadharmoideen Fadurudeen](https://dogfoodhack.com/img/judges/kadharmoideen-fadurudeen.jpg)Kadharmoideen FadurudeenAdobe Inc · United States of America](https://www.linkedin.com/in/kadharmoideen-fadurudeen-b50216174) [![Nikolay Dolgov](https://dogfoodhack.com/img/judges/nikolay-dolgov.jpg)Nikolay DolgovThe Lightning Group · UK](https://www.linkedin.com/in/niko-dolgo/) [![Pavani Totli Kuruba](https://dogfoodhack.com/img/judges/pavani-totli-kuruba.jpg)Pavani Totli KurubaLululemon · United States](https://linkedin.com/in/pavani-totli-kuruba) [![Shon Thomas](https://dogfoodhack.com/img/judges/shon-thomas.jpg)Shon ThomasYahoo · USA](http://lnkd.in/bC3Wsz9) [![Shriniwas Phalke](https://dogfoodhack.com/img/judges/shriniwas-phalke.jpg)Shriniwas PhalkeWalmart Global tech · USA](https://www.linkedin.com/in/shriniwas-phalke-2978b147/) [![Soumyajit Mukherjee](https://dogfoodhack.com/img/judges/soumyajit-mukherjee.jpg)Soumyajit MukherjeeShutterfly Inc · United States](https://www.linkedin.com/in/soumyajit-mukherjee-97a56070/) [![Stanislav Korolev](https://dogfoodhack.com/img/judges/stanislav-korolev.jpg)Stanislav KorolevAvito · Russia](https://www.linkedin.com/in/krus210/) [![Tomasz Kubiak](https://dogfoodhack.com/img/judges/tomasz-kubiak.jpg)Tomasz KubiakWelltech · Poland](https://www.linkedin.com/in/t-kubiak/) [![Kursad Alsan](https://dogfoodhack.com/img/judges/kursad-alsan.jpg)Kursad AlsanThailand](https://www.linkedin.com/in/kursadalsan/) [![Manish Gupta](https://dogfoodhack.com/img/judges/manish-gupta.jpg)Manish GuptaUSA](https://www.linkedin.com/in/manish-gupta-9a871a10/) [![Manpreet Kaur](https://dogfoodhack.com/img/judges/manpreet-kaur.jpg)Manpreet KaurUnited States](https://www.linkedin.com/in/manpreet-aneja-2a446b60/) [![Pramodini Girish Mahendrakar](https://dogfoodhack.com/img/judges/pramodini-girish-mahendrakar.jpg)Pramodini Girish MahendrakarUnited States](https://www.linkedin.com/in/pramodini-mahendrakar-88799515/?lipi=urn%3Ali%3Apage%3Ad_flagship3_profile_view_base_contact_details%3BGqoEp%2BIfTBm2sPCRsH6a9A%3D%3D) [![Pritesh Gehlot](https://dogfoodhack.com/img/judges/pritesh-gehlot.jpg)Pritesh GehlotUNITED STATES](https://www.linkedin.com/in/pritesh-gehlot-7999b428) [![Rajasree Pachuveetil](https://dogfoodhack.com/img/judges/rajasree-pachuveetil.jpg)Rajasree PachuveetilUnited States](https://www.linkedin.com/in/sree4all/) [![Reeshav Kumar](https://dogfoodhack.com/img/judges/reeshav-kumar.jpg)Reeshav KumarUSA](https://www.linkedin.com/in/reeshavkumar) [![Shashank Shekhar](https://dogfoodhack.com/img/judges/shashank-shekhar.jpg)Shashank ShekharUnited States](https://www.linkedin.com/in/shashankshekhar32) [![Sonali Priya](https://dogfoodhack.com/img/judges/sonali-priya.jpg)Sonali PriyaUnited States](https://www.linkedin.com/in/priyasonali/) [![Sourav Sinha](https://dogfoodhack.com/img/judges/sourav-sinha.jpg)Sourav SinhaAmazon Web Services · United States Of America](https://www.linkedin.com/in/sourav-s-36a7a225) [![Nikolai Sidiropulo](https://dogfoodhack.com/img/judges/nikolai-sidiropulo.jpg)Nikolai SidiropuloMeta · United States](https://www.linkedin.com/in/nsidiropulo) [![Anton Musatov](https://dogfoodhack.com/img/judges/anton-musatov.jpg)Anton MusatovDigitail Inc. · Spain](https://www.linkedin.com/in/ayacaste/) [![Arun Kumar Kaliamoorthy](https://dogfoodhack.com/img/judges/arun-kumar-kaliamoorthy.jpg)Arun Kumar KaliamoorthyGoDaddy · United States Of America](https://www.linkedin.com/in/arunkumarspk) [![Dmitriy Fedoryshchev](https://dogfoodhack.com/img/judges/dmitriy-fedoryshchev.jpg)Dmitriy FedoryshchevEverCommerce · United Kingdom](https://www.linkedin.com/in/dife/) [![Dmitry Gusev](https://dogfoodhack.com/img/judges/dmitry-gusev.jpg)Dmitry GusevAvito · Georgia](https://www.linkedin.com/in/sw1tch3roo/) [![Dmitry Kuznetsov](https://dogfoodhack.com/img/judges/dmitry-kuznetsov.jpg)Dmitry KuznetsovFunnelFox · Serbia](https://www.linkedin.com/in/dmitry-kuznetsov-685b72194/) [![Gautam Siddhartha](https://dogfoodhack.com/img/judges/gautam-siddhartha.jpg)Gautam SiddharthaWalmart · USA](https://www.linkedin.com/in/gautam-siddhartha/) [![Ivan Antropov](https://dogfoodhack.com/img/judges/ivan-antropov.jpg)Ivan AntropovT-Bank · Russia](https://www.linkedin.com/in/ivan-antropov-9505a969/) [![Jose Galarza](https://dogfoodhack.com/img/judges/jose-galarza.jpg)Jose GalarzaWise · Singapore](https://www.linkedin.com/in/igalarzab/) [![Kadharmoideen Fadurudeen](https://dogfoodhack.com/img/judges/kadharmoideen-fadurudeen.jpg)Kadharmoideen FadurudeenAdobe Inc · United States of America](https://www.linkedin.com/in/kadharmoideen-fadurudeen-b50216174) [![Nikolay Dolgov](https://dogfoodhack.com/img/judges/nikolay-dolgov.jpg)Nikolay DolgovThe Lightning Group · UK](https://www.linkedin.com/in/niko-dolgo/) [![Pavani Totli Kuruba](https://dogfoodhack.com/img/judges/pavani-totli-kuruba.jpg)Pavani Totli KurubaLululemon · United States](https://linkedin.com/in/pavani-totli-kuruba) [![Shon Thomas](https://dogfoodhack.com/img/judges/shon-thomas.jpg)Shon ThomasYahoo · USA](http://lnkd.in/bC3Wsz9) [![Shriniwas Phalke](https://dogfoodhack.com/img/judges/shriniwas-phalke.jpg)Shriniwas PhalkeWalmart Global tech · USA](https://www.linkedin.com/in/shriniwas-phalke-2978b147/) [![Soumyajit Mukherjee](https://dogfoodhack.com/img/judges/soumyajit-mukherjee.jpg)Soumyajit MukherjeeShutterfly Inc · United States](https://www.linkedin.com/in/soumyajit-mukherjee-97a56070/) [![Stanislav Korolev](https://dogfoodhack.com/img/judges/stanislav-korolev.jpg)Stanislav KorolevAvito · Russia](https://www.linkedin.com/in/krus210/) [![Tomasz Kubiak](https://dogfoodhack.com/img/judges/tomasz-kubiak.jpg)Tomasz KubiakWelltech · Poland](https://www.linkedin.com/in/t-kubiak/) [![Kursad Alsan](https://dogfoodhack.com/img/judges/kursad-alsan.jpg)Kursad AlsanThailand](https://www.linkedin.com/in/kursadalsan/) [![Manish Gupta](https://dogfoodhack.com/img/judges/manish-gupta.jpg)Manish GuptaUSA](https://www.linkedin.com/in/manish-gupta-9a871a10/) [![Manpreet Kaur](https://dogfoodhack.com/img/judges/manpreet-kaur.jpg)Manpreet KaurUnited States](https://www.linkedin.com/in/manpreet-aneja-2a446b60/) [![Pramodini Girish Mahendrakar](https://dogfoodhack.com/img/judges/pramodini-girish-mahendrakar.jpg)Pramodini Girish MahendrakarUnited States](https://www.linkedin.com/in/pramodini-mahendrakar-88799515/?lipi=urn%3Ali%3Apage%3Ad_flagship3_profile_view_base_contact_details%3BGqoEp%2BIfTBm2sPCRsH6a9A%3D%3D) [![Pritesh Gehlot](https://dogfoodhack.com/img/judges/pritesh-gehlot.jpg)Pritesh GehlotUNITED STATES](https://www.linkedin.com/in/pritesh-gehlot-7999b428) [![Rajasree Pachuveetil](https://dogfoodhack.com/img/judges/rajasree-pachuveetil.jpg)Rajasree PachuveetilUnited States](https://www.linkedin.com/in/sree4all/) [![Reeshav Kumar](https://dogfoodhack.com/img/judges/reeshav-kumar.jpg)Reeshav KumarUSA](https://www.linkedin.com/in/reeshavkumar) [![Shashank Shekhar](https://dogfoodhack.com/img/judges/shashank-shekhar.jpg)Shashank ShekharUnited States](https://www.linkedin.com/in/shashankshekhar32) [![Sonali Priya](https://dogfoodhack.com/img/judges/sonali-priya.jpg)Sonali PriyaUnited States](https://www.linkedin.com/in/priyasonali/)

14\[ 14 / FAQ \]

## FAQ

What's the team size limit?>>>

1-4 people. Solo welcome. For this brief we would recommend 2-3, since the tier ladder splits cleanly across a frontend and a backend.

Can I use AI code generation?>>>

Yes, and you should. Claude Code, Cursor, Aider, Copilot, all expected. We do not score whether you used AI. We score whether the portal runs, whether role isolation survives a curl, and whether somebody can explain the schema. The acceptance report and your docs are the receipts.

Can I use a framework, an ORM, a boilerplate generator?>>>

Yes. All of it. Rails, Django, Laravel, Next.js, Phoenix, whatever gets you to a working product fastest. The constraint here is one-command self-hosting, not dependency count. That was a different hackathon.

What if I only reach T2?>>>

Then you are scored on T2 and you can absolutely still win. Tier Completion is 40% and correctness beats breadth inside it. A clean, correct, well-documented T2 has beaten a broken T4 every time we have modelled this.

Does design count?>>>

Yes, inside Code Quality and inside Adoptability. A judge console that makes 30 reviews bearable is a real contribution. But a beautiful frontend over hardcoded data scores zero on Tier Completion, which is 40%.

What exactly is in the fixture data?>>>

A synthetic dataset built to the shape of a real Raptors event: roughly 40 projects, 30 judges, 8 tracks, and a full set of scores. No real names, no real submissions. It is deliberately built with the edge cases every evaluation system has to survive, including a reviewer who rates everything the same, an incomplete batch, and a duplicate entry. If your portal only works on tidy input, you will find out on Friday rather than on Monday.

What is the acceptance suite?>>>

A test suite we publish at kickoff that runs against your running portal and reports pass or fail per tier requirement. You run it yourself, as often as you like, and commit the output. Judges run the same suite. Nobody is guessing.

Can I start coding before September 25?>>>

No project code. Planning, sketching schemas, reading the spec, choosing your stack, tuning prompts, all fine and encouraged. Any project code committed before kickoff disqualifies the submission.

Do I have to use Docker specifically?>>>

`docker compose up` is the default and the safest choice. If your stack has a genuinely equivalent single command that needs nothing but a laptop, use it and say so clearly in your README. The test is whether a stranger gets a running portal from one command, not which tool printed the logs.

What license do I have to use?>>>

Any OSI-approved license. MIT or Apache-2.0 preferred, because those are the ones we can adopt without a legal conversation. Copyleft is allowed and will not cost you points.

What does Raptors actually do with the winner?>>>

Fork it, self-host it, and run our events on it. Credit your team on every event page it powers. Send our changes back to you as pull requests. See What happens to the winner for the full statement.

Do I keep ownership?>>>

Yes, entirely. No assignment, no transfer, no CLA, nothing to sign. You are licensing your work to the world under an open license, and we are one of the people using it.

What if two entries are both worth adopting?>>>

Then we will say so publicly, adopt one, and credit both, describing exactly what we took from where. We will not quietly merge someone's architecture without naming them.

15\[ 15 / WHY NOW \]

## Why Now

Every hackathon platform in the world converged on the same nine features, and then stopped moving.

The category leader still cannot weight judging criteria and tells organizers to use a spreadsheet instead.[\[1\]](https://dogfoodhack.com/#ref-1) Score normalization, the one genuinely hard statistical problem in the whole domain, is advertised as a feature by multiple platforms and documented by none of them.[\[6\]](https://dogfoodhack.com/#ref-6) [\[7\]](https://dogfoodhack.com/#ref-7) Community voting is treated as an unsolvable abuse surface to be managed with small prizes and hidden results rather than fixed with engineering.[\[1\]](https://dogfoodhack.com/#ref-1) Pricing is sales-gated across the board, so a volunteer organizer running a free event cannot even find out what it costs. And after fifteen years and millions of developers, not one of them ships a public API, leaving an entire industry to integrate through screen scrapers and downloaded spreadsheets.[\[14\]](https://dogfoodhack.com/#ref-14)

The open-source alternatives are better than their reputation. Gavel brought a real idea from mathematical psychology into judging and has been quietly producing fairer rankings at HackMIT for years.[\[12\]](https://dogfoodhack.com/#ref-12) JunctionApp, Dribdat, Quill and Hibiscus are all real and all self-hostable.[\[13\]](https://dogfoodhack.com/#ref-13) What is missing is a modern one, assembled as a whole, that a working organizer can deploy without becoming its maintainer.

We are not writing this as analysts. We are writing it as operators, from thirty-five events of knowing precisely which stage of the pipeline the tooling abandons you at.

Generating a CRUD app is trivial now. Building an evaluation system that is fair, that enforces its own rules, that an organizer can actually operate, and that you can hand to someone else without a handover call, is the part that still takes engineers.

That is the hackathon. 72 hours. One product. We run the winner.

> Build the platform that will judge you.

[\[ Go to Discord \] >>>](https://discord.gg/xfYPDZYqeh)

\[ REFERENCES \]

01. [\[1\] Devpost, "Judging & public voting" (equally-weighted criteria only, offline judging required for weights; ~5 hours to score 30 projects; public-vote fraud guidance). help.devpost.com](https://help.devpost.com/article/64-judging-public-voting)
02. [\[2\] Devpost, "7 key features to consider when choosing your hackathon platform provider". info.devpost.com](https://info.devpost.com/blog/key-hackathon-platform-features)
03. [\[3\] Devpost for Teams, "New voting, guest access, and setup features". info.devpost.com](https://info.devpost.com/blog/devpost-for-teams-releases-q1-2025)
04. [\[4\] Devpost, "Know your submission steps" (the full submission field set). help.devpost.com](https://help.devpost.com/article/126-know-your-submission-steps)
05. [\[5\] MLH Organizer Guide, "Using Devpost". guide.mlh.com](https://guide.mlh.com/general-information/judging-and-submissions/hackathon-submission-portal/using-devpost)
06. [\[6\] Devfolio, "Devfolio's stack of features". devfolio.co](https://devfolio.co/blog/devfolios-stack-of-features/)
07. [\[7\] Devfolio, "Organizer judging". guide.devfolio.co](https://guide.devfolio.co/docs/guide/organizer-judging)
08. [\[8\] Devfolio, "Judging" (the fixed five-criterion rubric). guide.devfolio.co](https://guide.devfolio.co/docs/guide/judging)
09. [\[9\] DoraHacks (700+ hackathons, 32,000+ projects, BUIDL AI automated review and AI judging). dorahacks.io](https://dorahacks.io/)
10. [\[10\] DoraHacks, "Building effective on-chain governance mechanisms". dorahacks.io](https://dorahacks.io/blog/news/qf-retrospective/)
11. [\[11\] HackerEarth, "11 best hackathon platforms for enterprise in 2026". hackerearth.com](https://www.hackerearth.com/blog/hackathon-platforms)
12. [\[12\] Gavel, HackMIT's pairwise-comparison judging system (Crowd-BT / Bradley-Terry estimator). github.com/anishathalye/gavel](https://github.com/anishathalye/gavel)
13. [\[13\] awesome-hackathon, curated list of open-source, self-hostable hackathon platforms and tools. github.com/dribdat/awesome-hackathon](https://github.com/dribdat/awesome-hackathon)
14. [\[14\] Unofficial Devpost API, a scraper-based community project standing in for the API that does not exist. github.com/ViRb3/devpost-api](https://github.com/ViRb3/devpost-api)
15. [\[15\] Hackathon Raptors event archive, 35 events from September 2023 to July 2026. raptors.dev](https://raptors.dev/)

72 HOURSONE PRODUCTWE RUN THE WINNER+72 HOURSONE PRODUCTWE RUN THE WINNER+

72 HOURSONE PRODUCTWE RUN THE WINNER+72 HOURSONE PRODUCTWE RUN THE WINNER+