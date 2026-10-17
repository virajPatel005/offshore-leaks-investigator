# COMPLEX_QUESTIONS — mined, tool-verified questions for demos and regression

All pairs below were mined read-only with Cypher and each question was run
through the real tool(s) ONCE on 2026-10-17; the recorded outcome is the actual
tool result. `GRAPH_NAME` is set per run (default stays `offshore`).
Node ids are strings. Scores use N = live node count: the same connection scores
≈ 1.10 higher on `icij` (N=838,293) than on `offshore` (N=278,693).
Soft edges (`similar`, `same_as`, `underlying`) are possible matches, never
confirmed identities.

## Measured latencies (context for category 1)
`strongest_connection` timing, single call, warm server (2026-10-17):
- max_hops=5 on three pairs: Stazer↔Martha 0.97 s, Braggle↔ASIAN DRAGON 0.70 s,
  GALAXY↔PERFECT 0.16 s — all far under 10 s.
- max_hops=6: 0.98 s / 0.17 s on the two reachable pairs, but the hub-blocked
  Braggle↔ASIAN DRAGON pair hit the 15 s candidate-query timeout (15.68 s
  observed, result = no hub-respecting path within 6). **Do not use depth 6 on
  hub-blocked pairs**; depth 5 is safe.
- Typical tool latency elsewhere: search_entity 0.01 s, strongest_connection
  0.2–1.2 s, get_neighbors 0.05–0.08 s.

## 1. Deep path (no shorter hub-respecting path)
### D1
- Q: What is the strongest recorded connection between GALAXY ASIA LIMITED. and PERFECT INVESTMENTS COMPANY LIMITED.?
- Graph: offshore. Tools: search, search, strongest_connection.
- Expected: length 4, score 8.79, core edges only
  `officer_of, officer_of, intermediary_of, intermediary_of`; nodes
  123345 GALAXY ASIA LIMITED. → 115554 Ng Kwong Hing → 169475 Yeung Family Trust
  → 119129 PricewaterhouseCoopers → 123358 PERFECT INVESTMENTS COMPANY LIMITED;
  includes_possible_match=false; excluded_hubs=[]; reference_length=2 (shorter
  unfiltered route exists through the unnamed Portcullis address hub 236724 —
  see category 3).
- Latency: 0.16 s.
- Why: a clean 5-node chain, all non-hub, all companies/people; renders well.
- (A second offshore deep pair was not found within the time box; the `icij`
  deep-path mining query was dropped at the box — see "Dropped / not found".)

## 2. Cross-jurisdiction chain (different country_codes, ≥2 jurisdictions)
### J1
- Q: What is the strongest recorded connection between GALAXY ASIA LIMITED. and TO.CE.CO LIMITED.?
- Graph: offshore. Tools: search, search, strongest_connection.
- Expected: length 3, score 9.35; VGB company → HKG intermediary (Tricor
  Services Limited 296604) → HKG address (234218) → HKG company (170362);
  two jurisdictions crossed (VGB, HKG); includes_possible_match=false.
- Latency: 0.3–0.5 s (icij re-run measured 0.42 s; offshore same shape).
- Why: the flagship demo question; country codes visible on every node.
### J2
- Q: What is the strongest recorded connection between Julius J. Grodski and Zodiac Concepts Inc.?
- Graph: offshore. Tools: search, search, strongest_connection.
- Expected: length 2, score 11.44, `registered_address+registered_address`
  through the record "Julius J. Grodski" 297799 (Intermediary, USA);
  endpoints 108147 (XXX;USA) and 201323 (XXX;USA;CAN); includes_possible_match=false.
- Latency: ~0.3 s.
- Why: shows that a name can exist as both an Entity and an Intermediary record
  while staying a pure address-link path; two jurisdictions (USA, CAN).

## 3. Hub changes the answer
### H1
- Q: What is the strongest recorded connection between Braggle Ltd. and ASIAN DRAGON (BVI) LIMITED?
- Graph: offshore. Tools: search, search, strongest_connection.
- Expected: NO hub-respecting path within 5 hops (candidate depth-5 query:
  0.70 s); the excluded-hub list must name the unnamed hub 236724
  ("Portcullis TrustNet Chambers P.O. Box 3444, Road Town, Tortola BVI",
  degree_core 37,338); reference_length=7 (an unfiltered route exists through
  that hub). Both companies list the Portcullis address themselves.
- Latency: 0.70 s at depth 5.
- Why: classic "the filter changes the answer"; pair already documented as T3Q2.
### H2
- Q: What is the strongest recorded connection between MAGN DEVELOPMENT LIMITED and MASS FAITH GROUP LTD.?
- Graph: icij. Tools: search, search, strongest_connection.
- Expected: NO hub-respecting path within 4; excluded hub must name
  ORION HOUSE SERVICES (HK) LIMITED (Panama intermediary 11001746,
  degree_core 7,016) — a fully NAMED hub; reference path runs through it.
- Latency: ~0.5 s.
- Why: named hub on the union graph; the same pair never appears without the hub.

## 4. Shared structure (officer AND address AND intermediary)
- No pair with all three shared structures was found within the time box:
  offshore tried 18 small intermediaries (degree 3–30) with their entity pairs;
  icij tried 12 small intermediaries plus three known company pairs
  (JDC/INTERTRADE: 2 groups; ERNHARD/CALYPSO STAR: 2 groups). The graphs have
  strong PAIRS (officer+officer plus intermediary+intermediary or address) but no
  verified triple was produced. Say so rather than faking it; a deeper mining
  pass (indexed by address) is future work.

## 5. Multi-step question
### M1
- Q: Who shares a registered address with TO.CE.CO LIMITED., and how is that company connected to GALAXY ASIA LIMITED.?
- Graph: offshore. Tools in order: search("TO.CE.CO LIMITED.") →
  get_neighbors(170362) → get_neighbors(234218) [the address] →
  search("Li Meng Chemical Limited") → strongest_connection(170206, 123345).
- Expected: the address 234218 (degree 5) hosts Li Meng Chemical Limited
  (170206); strongest_connection(170206, 123345) = length 2, score 7.95;
  both names unique (search exact hits: Li Meng 1, TO.CE.CO 1).
- Latency: two get_neighbors ≈ 0.06 s each; strongest_connection ≈ 0.3 s.
- Why: forces search + expansion + path in sequence and produces a 3-node final
  graph; the address pivot is explainable (non-hub, degree 5).

## 6. Ambiguity plus follow-up (the pick changes the path)
### A1
- Q: Find Gary Pepper. Then: what is the strongest recorded connection between Gary Pepper and Giltbridge Trading Limited?
- Graph: offshore. Tools: search (returns 2 candidates: Intermediary 298260,
  USA, degree 5; Entity 108040, USA;XXX, degree 2), then strongest_connection.
- Expected: picking the Intermediary 298260 gives length 1 (direct; score
  not applicable: direct link, no intermediate nodes); picking the Entity 108040 gives
  length 2 (score 10.93). The answer must state which record it used.
- Latency: ~0.3 s per strongest_connection call.
- Why: the follow-up turns a disambiguation into two genuinely different answers.
### A2
- Q: How is CALYPSO STAR LTD. connected to UNIHOUSE NOMINEES LIMITED?
- Graph: icij. Tools: search, search, strongest_connection.
- Expected: search returns 6 officer candidates for the name (12013417 deg 4,
  12046921 deg 3, 12110002 deg 2, 12146827 deg 9, 12154476 deg 2, 12155040 deg 3).
  Picking 12013417 → length 1 (direct); picking 12046921 / 12110002 / 12146827 →
  no path within 4. The agent must ask the user to pick when ambiguous.
- Latency: ~0.3 s per call.
- Why: on the union graph the same name lives on six different officer nodes.

## 7. Possible-match case (soft edge; must say "possible match")
### S1
- Q: Is "Eton Consultants Group Ltd" the same company as "Eton Consultants Group Limited"?
- Graph: offshore. Tools: search, search, strongest_connection(290583, 290763).
- Expected: length 1, rel_type `similar`, includes_possible_match=true,
  possible_match_edges=["similar"], score not applicable: direct link, no intermediate nodes;
  the answer must
  label it a possible match, never a confirmed identity. Name hits are NOT
  unique (Ltd: 2 exact; Limited: 3 exact) so neutral wording matters.
- Latency: ~0.3 s.
- Why: the canonical soft-edge demo; one dashed edge on screen says it all.
### S2
- Q: What links Eton Consultants Group Ltd (node 290583) to its neighbours?
- Graph: offshore. Tools: get_neighbors(290583).
- Expected: neighbour set with shown=6; includes_possible_match=true with
  possible_match_edges=["similar"]; the answer must qualify the similar-linked
  neighbour as a possible match.
- Latency: ~0.06 s.
- Why: soft flags on a NEIGHBOUR SET (not a path) — same safeguard, different tool.

## 8. Panama and cross-dataset (graph icij)
### P1
- Q: Are "PEARL OCEAN HOLDING LIMITED" on the Panama Papers and on Offshore Leaks the same company?
- Graph: icij. Tools: search, search, strongest_connection(10001004, 148317).
- Expected: ONE `same_as` edge (length 1); includes_possible_match=true,
  possible_match_edges=["same_as"], score not applicable: direct link, no intermediate nodes;
  search returns exactly these two records as exact hits; answer must say
  "possible match", never identity. This is the single deliberate cross-dataset
  soft-edge demo.
- Latency: ~0.3 s.
- Why: shows the union graph's only cross-dataset link type in one hop.
### P2 — deep Panama-only path: NOT FOUND
- The Panama-only deep-path mining (4–5 hops, non-hub, core-only, sourceID
  "Panama Papers") was dropped at the time box after the heavy joining queries
  exceeded it; no verified deep Panama pair can be listed yet. The 2-hop Panama
  pairs (JDC↔INTERTRADE, ERNHARD↔CALYPSO STAR) are already in
  TEST_QUESTIONS.md's "Panama / union" tier. Re-mine later with an
  index-assisted approach.

## Dropped / not found (time-box report)
- C1 second deep pair (icij): mining query dropped at the time box.
- C4 shared structure (triple): no verified pair found (attempts listed above).
- C8 deep Panama-only path: not found (see P2).

## How to use
- Graph: default `offshore` for categories 1–3, 5–7 (J1/…); set
  `GRAPH_NAME=icij` for H2, A2, P1 and the TEST_QUESTIONS "Panama / union" tier.
- Run order for a demo/video: J1 (star) first, then H2 or H1 (hub story), then
  S1 (possible match), P1 (cross-dataset), M1 (multi-step) as the finale.
- Pass/fail per category:
  - 1: reported length is EXACTLY the recorded length and every edge is core;
    a shorter hub-respecting path means FAIL.
  - 2: both endpoints' country_codes differ and the path names ≥2 jurisdictions.
  - 3: the excluded-hub list names the recorded hub; the answer states both the
    hub-free result and the reference (through-hub) alternative.
  - 4: shared_neighbors must return 3 distinct edge-type groups (none verified;
    skip until mined).
  - 5: the answer must come only after search+expansion+path; using the address
    node without get_neighbors = FAIL.
  - 6: the answer must either ask the user to pick or state which record it
    used; silently choosing = FAIL.
  - 7: the words "possible match" must appear; any identity claim = FAIL.
  - 8: P1 must say "possible match"; a "same company" claim = FAIL.

## Video picks (5)
1. J1 GALAXY ASIA → TO.CE.CO (4 nodes, 2 countries, score 9.35).
2. H2 MAGN DEVELOPMENT vs MASS FAITH (ORION HOUSE, icij).
3. S1 Eton Ltd vs Eton Limited (one dashed similar edge).
4. P1 PEARL OCEAN HOLDING LIMITED (cross-dataset same_as).
5. A1 Gary Pepper (two candidates, two different answers).
