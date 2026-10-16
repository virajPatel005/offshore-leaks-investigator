# QUERIES REGISTRY

Every Cypher query or graph algorithm the product depends on. This feeds the README section the hackathon requires.

## Template
### Q<number>: <name>
- Used by tool: 
- Purpose: 
- Why this shape (and why the hub filter sits inside the traversal): 
- Parameters: 
- Query:
- Measured latency and result size (with and without hub filter): 

## Import (Phase 1c, scripts/load_graph.py; graph `offshore`)
### Q1: index node_id per label
- Used by: loader. Purpose: indexed endpoint lookup during edge load.
- Why: FalkorDB indexes are per label, so one index per label (Address, Entity, Intermediary, Officer).
- Parameters: none (label is literal).
- Query: `CREATE INDEX FOR (n:Address) ON (n.node_id)` (repeated per label)
- Measured: <0.1s each on empty graph.
### Q2: load nodes from prepared CSV
- Used by: loader. Purpose: one file per label set; merged file gets both labels.
- Why: CREATE (not MERGE) on a fresh graph is the documented fast path; degrees cast with toInteger (LOAD CSV yields strings).
- Parameters: none (file path and label are literals).
- Query: `LOAD CSV WITH HEADERS FROM 'file://nodes_officer.csv' AS row CREATE (n:Officer {node_id: row.node_id, name: row.name, countries: row.countries, country_codes: row.country_codes, sourceID: row.sourceID, valid_until: row.valid_until, note: row.note, degree_core: toInteger(row.degree_core), degree_all: toInteger(row.degree_all)})` (same shape per label; merged: `CREATE (n:Intermediary:Officer {..., name_mismatch: row.name_mismatch = 'True', ...})`)
- Measured: 0.0–1.1s per file; 278,693 unique nodes total.
### Q3: load edges per rel_type with label-blind endpoint resolution
- Used by: loader. Purpose: one file per rel_type; raw link, role_category, status, dates, sourceID kept.
- Why this shape: edge rows carry no endpoint labels and indexes are per label, so each endpoint resolves via one indexed OPTIONAL MATCH per label plus coalesce (8 seeks/row). Type is literal per file (Cypher cannot parameterize it).
- Parameters: row map only.
- Query: `LOAD CSV WITH HEADERS FROM 'file://edges_officer_of.csv' AS row OPTIONAL MATCH (a1:Address {node_id: row.node_id_start}) OPTIONAL MATCH (a2:Entity {node_id: row.node_id_start}) OPTIONAL MATCH (a3:Intermediary {node_id: row.node_id_start}) OPTIONAL MATCH (a4:Officer {node_id: row.node_id_start}) OPTIONAL MATCH (b1:Address {node_id: row.node_id_end}) OPTIONAL MATCH (b2:Entity {node_id: row.node_id_end}) OPTIONAL MATCH (b3:Intermediary {node_id: row.node_id_end}) OPTIONAL MATCH (b4:Officer {node_id: row.node_id_end}) WITH row, coalesce(a1, a2, a3, a4) AS a, coalesce(b1, b2, b3, b4) AS b WHERE a IS NOT NULL AND b IS NOT NULL CREATE (a)-[r:officer_of {link: row.link, role_category: row.role_category, status: row.status, start_date: row.start_date, end_date: row.end_date, sourceID: row.sourceID}]->(b)`
- Measured: 0.0–4.4s per file; 562,700 edges total; full load ~14s.
### Q4: counts per label / type (verification)
- Used by: loader verify. Purpose: totals vs 278,693 nodes / 562,700 edges; label sums exceed unique by exactly the 1,139 D4 merged nodes.
- Query: `MATCH (n:Officer) RETURN count(n)`, `MATCH ()-[r:officer_of]->() RETURN count(r)`, `MATCH (n) RETURN count(n)`
### Q5: sample direction + hub-degree sanity (verification)
- Used by: loader verify. Purpose: confirm stored direction per type; Portcullis address core degree is 37,338 undirected distinct neighbors.
- Query: `MATCH (x)-[r:officer_of]->(y) RETURN labels(x), labels(y) LIMIT 1`; `MATCH (a:Address {node_id: $id})-[r:officer_of|intermediary_of|registered_address]-(n) RETURN count(DISTINCT n)`
- Measured: instant; degree check OK.
### Q6: strongest-connection candidates + reference (backend/graph/strongest_connection.py)
- Used by tool: strongest_connection. Purpose: shortest hub-respecting path between two node_ids, ranked by mean D3 rarity.
- Why this shape: undirected shortestPath() is unsupported and directed misses backward edges; WHERE all() on var-length patterns filters after expanding through hubs (60s timeout next to a 36k hub), so candidates use exact-depth chains with a hub predicate on every intermediate node (prunes during expansion) and iterative deepening 1..max_hops. Score = mean log((N+1)/(degree_core+1)) over intermediate nodes (mean, not sum, so padding hops cannot raise the score); endpoints are fixed and contribute nothing.
- Parameters: $s, $t node_ids; $hub threshold (integers inlined: depth bounds, LIMIT).
- Query (depth 2 shown): `MATCH (a {node_id: $s}), (b {node_id: $t}) MATCH (a)-[r1]-(m1)-[r2]-(b) WHERE m1.degree_core <= $hub RETURN [x IN [a, m1, b] | [x.node_id, x.name, labels(x), x.degree_core, x.sourceID]] AS nodes, [r IN [r1, r2] | [type(r), r.link, r.role_category]] AS edges LIMIT 5`
- Reference (unfiltered exact shortest, detects hub-changed results): `MATCH (x {node_id: $s}), (y {node_id: $t}) CALL algo.SPpaths({sourceNode: x, targetNode: y, relDirection: 'both', maxLen: 4, pathCount: 1}) YIELD path RETURN path`
- Measured: hub-respecting 2-hop 15ms-scale per depth; SPpaths reference 30–95ms; hub-blocked and no-path cases return in ms with excluded hubs listed.
### Q7: name search via full-text index (backend/graph/search_entity.py)
- Used by tool: search_entity. Purpose: find Entity/Officer/Intermediary nodes by name; exact matches first.
- Why this shape: MATCH+CONTAINS cannot use the index (known FalkorDB limitation), so search goes through the procedure; a single WHERE with an empty-string country comparison filtered out every row (no short-circuit on missing properties), hence the country predicate is a separate query shape built in Python.
- Parameters: $q search text; $country code or omitted (LIMIT inlined).
- Index: `CREATE FULLTEXT INDEX FOR (n:Entity) ON (n.name)` (once per label; error "already indexed" means done)
- Query: `CALL db.idx.fulltext.queryNodes('Entity', $q) YIELD node, score RETURN node.node_id, node.name, labels(node), node.country_codes, node.degree_core, node.sourceID, score LIMIT 10`
- Measured: instant on 278k nodes; 'Portcullis' returns ranked candidates.
### Q8: shared neighbors with hub filter (backend/graph/shared_neighbors.py)
- Used by tool: shared_neighbors. Purpose: common neighbors of two nodes for "shared officer and non-hub address" questions; caller filters by label.
- Why this shape: the hub predicate sits on the shared node inside the pattern; hubs among common neighbors come from a second query so they are listed, never silently dropped. Endpoints exempt (n <> endpoints guards loops).
- Parameters: $x, $y node_ids; $hub threshold (LIMIT inlined).
- Query: `MATCH (a {node_id: $x}), (b {node_id: $y}) MATCH (a)-[r1]-(n)-[r2]-(b) WHERE n.degree_core <= $hub AND n.node_id <> $x AND n.node_id <> $y RETURN n.node_id, n.name, labels(n), n.degree_core, n.sourceID, type(r1), r1.link, r1.role_category, type(r2), r2.link, r2.role_category LIMIT 20`
- Measured: instant on tested pairs.
