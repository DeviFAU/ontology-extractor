"""
ontology_extractor_openai.py  (v7 - edge accuracy fixes from 6-example analysis)
==========================================================================
4-pass + Pass 0 pipeline: image -> structured JSON -> OWL (RDF/XML + Turtle)
Powered by OpenAI GPT-4o.

Fixes in v6 (over v5):
  PASS 0 (NEW):
    - Dedicated arrow inventory pass before full extraction
    - Explicitly identifies hollow-triangle (subClassOf) vs solid (objectProperty)
    - Feeds arrow type map into Pass 1 prompt for informed extraction

  PASS 1:
    - Explicitly instructs to capture BOTH schema-level AND instance-level edges
    - Two-layer diagram awareness (instance ovals + class rectangles)
    - Improved arrow style guide with visual fingerprints

  PASS 2:
    - Stricter: never change direction without explicit arrowhead evidence
    - Must describe COLOUR + POSITION of arrowhead to justify correction
    - Hard limit: max 5 missed edges to reduce hallucination

  PASS 3:
    - Only reclassify node if it has NO edges at all in the diagram
    - Individuals without visible rdf:type arrows stay as instances
    - Stronger guard against over-reclassification

  MERGE FIXES:
    - Block from==to self-loops added by Pass 4
    - Dedup normalises empty label vs "rdfs:subClassOf" as same edge
    - Remove isA/is-a from object_properties list
    - PROV-O type classes auto-declared as owl:Class

  SERIALISER FIXES:
    - local part of prefixed names cleaned of spaces (crash fix)
    - Already applied in hotfix

Usage:
  python ontology_extractor_openai.py <image_path> [output.owl] [base_uri]

Requirements:
  pip install openai rdflib
"""

import sys
import re
import json
import base64
from pathlib import Path

from openai import OpenAI
from rdflib import Graph, OWL, RDF, RDFS, Namespace, URIRef, Literal, BNode
from rdflib.namespace import XSD

client = OpenAI()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_NAMESPACES = {
    "owl":    "http://www.w3.org/2002/07/owl#",
    "rdf":    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs":   "http://www.w3.org/2000/01/rdf-schema#",
    "xsd":    "http://www.w3.org/2001/XMLSchema#",
    "foaf":   "http://xmlns.com/foaf/0.1/",
    "prov":   "http://www.w3.org/ns/prov#",
    "schema": "http://schema.org/",
    "dcterms":"http://purl.org/dc/terms/",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "skos":   "http://www.w3.org/2004/02/skos/core#",
    "qudt":   "http://qudt.org/schema/qudt/",
    "seas":   "https://w3id.org/seas/",
    "bpo":    "https://w3id.org/bpo#",
    "dbo":    "http://dbpedia.org/ontology/",
    "dbr":    "http://dbpedia.org/resource/",
    "geo":    "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "time":   "http://www.w3.org/2006/time#",
    "org":    "http://www.w3.org/ns/org#",
    "teo":    "http://www.ontologydesignpatterns.org/cp/owl/teo.owl#",
    "ro":     "http://purl.obolibrary.org/obo/",
}

# PROV-O type classes that should always be declared as owl:Class
PROV_CLASSES = {"prov:Entity", "prov:Activity", "prov:Agent",
                "prov:Collection", "prov:Bundle"}

DATATYPE_MAP = {
    "string":       XSD.string,
    "str":          XSD.string,
    "integer":      XSD.integer,
    "int":          XSD.integer,
    "float":        XSD.float,
    "double":       XSD.double,
    "boolean":      XSD.boolean,
    "bool":         XSD.boolean,
    "date":         XSD.date,
    "datetime":     XSD.dateTime,
    "xsd:datetime": XSD.dateTime,
    "xsd:date":     XSD.date,
    "xsd:string":   XSD.string,
    "xsd:integer":  XSD.integer,
    "xsd:int":      XSD.integer,
    "xsd:float":    XSD.float,
    "xsd:double":   XSD.double,
    "xsd:boolean":  XSD.boolean,
    "xsd:anyuri":   XSD.anyURI,
    "anyuri":       XSD.anyURI,
}

XSD_TYPE_NAMES = {
    "xsd:string", "xsd:integer", "xsd:int", "xsd:float", "xsd:double",
    "xsd:boolean", "xsd:date", "xsd:datetime", "xsd:dateTime",
    "xsd:anyuri", "xsd:anyURI", "xsd:decimal", "xsd:long", "xsd:short",
    "string", "integer", "float", "double", "boolean", "date", "datetime",
}

SUBCLASS_LABELS = {
    "is a", "is-a", "is_a", "isa", "subclassof", "rdfs:subclassof",
    "subclass", "sub-class", "sub_class", "a kind of", "kind of",
    "type of", "typeof",
}

# Labels that should NEVER be in object_properties
SUBCLASS_LABEL_SET = {"isa", "is_a", "is-a", "is a", "subclassof",
                      "rdfs:subclassof", "subclass"}

EDGE_TYPE_NORM = {
    "subclass":           "subClassOf",
    "subclassof":         "subClassOf",
    "rdfs:subclassof":    "subClassOf",
    "instanceof":         "instanceOf",
    "rdf:type":           "instanceOf",
    "typeof":             "instanceOf",
    "typedeclaration":    "typeDeclaration",
    "type_declaration":   "typeDeclaration",
    "equivalentclass":    "equivalentClass",
    "owl:equivalentclass":"equivalentClass",
    "disjointwith":       "disjointWith",
    "owl:disjointwith":   "disjointWith",
    "inverseof":          "inverseOf",
    "owl:inverseof":      "inverseOf",
    "objectproperty":     "objectProperty",
    "dataproperty":       "dataProperty",
    "datatypeproperty":   "dataProperty",
    "datatypeproperty":   "dataProperty",
}

META_URIS = {
    URIRef("http://www.w3.org/2002/07/owl#ObjectProperty"),
    URIRef("http://www.w3.org/2002/07/owl#DatatypeProperty"),
    URIRef("http://www.w3.org/2002/07/owl#Class"),
    URIRef("http://www.w3.org/2002/07/owl#NamedIndividual"),
    URIRef("http://www.w3.org/2002/07/owl#Thing"),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_namespace_hints(hint_str: str) -> dict:
    ns = dict(KNOWN_NAMESPACES)
    if not hint_str:
        return ns
    for part in re.split(r"[;,]", hint_str):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\w+)\s*:\s*(https?://\S+)$", part)
        if m:
            ns[m.group(1)] = m.group(2)
        else:
            bare = re.sub(r"[:\s]", "", part).lower()
            if bare in KNOWN_NAMESPACES:
                ns[bare] = KNOWN_NAMESPACES[bare]
    return ns


def resolve_name(name: str, ns_map: dict, base_uri: str) -> URIRef:
    name = name.strip()
    if name.startswith("http://") or name.startswith("https://"):
        return URIRef(name)
    if name.startswith("<") and name.endswith(">"):
        inner = name[1:-1]
        if inner.startswith("http"):
            return URIRef(inner)
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", inner)
        return URIRef(base_uri + clean)
    if name.lower().startswith("xsd:"):
        local = name[4:]
        local_clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", local)
        return URIRef(f"http://www.w3.org/2001/XMLSchema#{local_clean}")
    if ":" in name:
        prefix, local = name.split(":", 1)
        base = ns_map.get(prefix.lower()) or ns_map.get(prefix)
        if base:
            # Clean spaces and special chars in local part
            local_clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", local)
            return URIRef(base + local_clean)
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return URIRef(base_uri + clean)


def parse_typed_literal(value_str: str):
    value_str = value_str.strip()
    m = re.match(r'^"?(.*?)"?\^\^(.+)$', value_str)
    if m:
        val_part  = m.group(1).strip()
        type_part = m.group(2).strip().lower()
        dt = DATATYPE_MAP.get(type_part)
        if dt:
            try:
                if dt == XSD.integer:
                    return Literal(int(val_part), datatype=dt)
                elif dt in (XSD.float, XSD.double):
                    return Literal(float(val_part), datatype=dt)
                elif dt == XSD.boolean:
                    return Literal(val_part.lower() == "true", datatype=dt)
                else:
                    return Literal(val_part, datatype=dt)
            except ValueError:
                return Literal(val_part, datatype=dt)
    if value_str.startswith('"') or value_str.startswith("'"):
        return Literal(value_str.strip('"\''))
    return None


def normalize_edge_type(et: str) -> str:
    if not et:
        return "other"
    return EDGE_TYPE_NORM.get(et.lower().strip(), et)


def is_xsd_node(name: str) -> bool:
    return name.lower().strip() in XSD_TYPE_NAMES or \
           name.lower().startswith("xsd:")


def is_subclass_label(label: str) -> bool:
    return label.lower().strip() in SUBCLASS_LABELS


def _load_image(image_path: str):
    ext = Path(image_path).suffix.lower()
    media_types = {
        ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(ext, "image/png")
    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def _call_llm(image_data: str, media_type: str, prompt: str,
              max_tokens: int = 4096) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {
                "url": f"data:{media_type};base64,{image_data}",
                "detail": "high"}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return response.choices[0].message.content


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*",     "", raw)
    raw = re.sub(r"```$",        "", raw)
    return json.loads(raw.strip())


# ---------------------------------------------------------------------------
# Pass 0 – Arrow inventory (NEW in v6)
# ---------------------------------------------------------------------------

PASS0_PROMPT = """You are a visual analyst specialising in ontology diagrams.

Your ONLY job is to identify every arrow/line in this image and classify its
arrowhead style. This is a pre-processing step — do NOT extract semantics yet.

ARROW STYLE VISUAL FINGERPRINTS:

  HOLLOW/OPEN triangle  ──────▷  or  ──────△
    - The triangle outline is visible but the inside is EMPTY/WHITE
    - Often larger triangle than solid arrows
    - Used for: rdfs:subClassOf (inheritance)
    - In UML: open inheritance arrow
    - IMPORTANT: This means subClassOf ALWAYS, without exception

  SOLID/FILLED triangle  ──────►  or  ──────▶
    - The triangle is filled with colour (black/dark)
    - Used for: objectProperty or dataProperty

  SIMPLE CHEVRON  ──────>
    - Just a simple > shape, not a triangle
    - Used for: objectProperty or dataProperty

  DASHED line with arrowhead  - - - - ►  or  - - - - ▷
    - The LINE is dashed/dotted (not solid)
    - Used for: rdf:type (instanceOf) if dashed+solid head
    - Used for: subClassOf if dashed+hollow head

  DOUBLE-HEADED  ◄──────►
    - Arrows at both ends
    - Used for: owl:inverseOf or owl:equivalentClass

  NO arrowhead (plain line)
    - Just a connecting line with no arrow
    - Used for: associations without direction

For EACH arrow in the image list:
  - Source node (which node does the TAIL start at)
  - Target node (which node does the ARROWHEAD touch)
  - Line style: solid | dashed | dotted
  - Arrowhead style: hollow-triangle | solid-triangle | chevron | 
                     double-headed | none | other
  - Your conclusion: subClassOf | objectProperty | dataProperty | 
                     instanceOf | inverseOf | other

Return ONLY valid JSON:
{
  "arrows": [
    {
      "id": "a1",
      "from": "source node name",
      "to": "target node name",
      "line_style": "solid | dashed | dotted",
      "arrowhead_style": "hollow-triangle | solid-triangle | chevron | double-headed | none | other",
      "conclusion": "subClassOf | objectProperty | dataProperty | instanceOf | inverseOf | other",
      "label": "visible label on the arrow or empty string",
      "confidence": "high | medium | low"
    }
  ],
  "diagram_notes": "any observations about the overall diagram structure"
}"""


def pass0_arrow_inventory(image_data: str, media_type: str) -> dict:
    """Dedicated arrow type detection pass before full extraction."""
    raw = _call_llm(image_data, media_type, PASS0_PROMPT, max_tokens=3000)
    try:
        return _parse_json(raw)
    except Exception:
        return {"arrows": [], "diagram_notes": ""}


def _build_arrow_context(p0: dict) -> str:
    """Convert Pass 0 results into a context string for Pass 1 prompt.
    v7: Only pass high-confidence subClassOf arrows to avoid biasing
    Pass 1's direction detection for objectProperty arrows."""
    arrows = p0.get("arrows", [])
    subclass_arrows = [a for a in arrows
                       if a.get("conclusion") == "subClassOf"
                       and a.get("confidence") == "high"]
    if not subclass_arrows:
        return ""
    lines = ["PRE-DETECTED subClassOf ARROWS (hollow-triangle arrowheads):"]
    for a in subclass_arrows:
        lines.append(
            f"  - '{a['from']}' →◁ '{a['to']}' : HOLLOW TRIANGLE = subClassOf"
            f"  [label: '{a.get('label','')}']")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pass 1 – Full structural extraction
# ---------------------------------------------------------------------------

def build_pass1_prompt(arrow_context: str) -> str:
    arrow_section = f"""
━━━ PRE-DETECTED ARROW TYPES (from Pass 0) ━━━
{arrow_context if arrow_context else "No pre-detection available — use visual analysis."}
""" if arrow_context else ""

    return f"""You are an expert OWL ontology engineer. Analyse this diagram with extreme care.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ARROW DIRECTION — READ VISUALLY, NOT SEMANTICALLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For EACH arrow in the diagram:
  1. Find the ARROWHEAD (triangle or pointed tip)
  2. The node the arrowhead TOUCHES = "to" (TARGET)
  3. The other end (tail) = "from" (SOURCE)
  4. Set "arrowhead_at" to the SAME value as "to"

THE PROPERTY NAME DOES NOT TELL YOU THE DIRECTION.
  Example: An arrow labeled "wasGeneratedBy" with the arrowhead
  touching node X means "to" = X, regardless of what the name implies.
  DO NOT infer direction from semantics — only from the arrowhead.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{arrow_section}
━━━ STEP 0 - READ THE LEGEND ━━━
If a legend is present, use it to understand shape meanings.
Do NOT extract legend items as ontology elements.

Shape meanings:
  Oval/ellipse (solid border)   = owl:Class
  Oval/ellipse (dashed border)  = owl:NamedIndividual
  Solid rectangle               = owl:Class OR ObjectProperty node
  Dashed rectangle              = data attribute box (value example, NOT individual)
  HOLLOW triangle arrowhead ◁   = ALWAYS rdfs:subClassOf (NEVER objectProperty)
  SOLID triangle arrowhead ►    = objectProperty or dataProperty
  Dashed line arrow - - - ►     = rdf:type (instanceOf)
  Dotted line arrow . . . ▷     = rdfs:subClassOf in some styles
  Gray rounded rectangle        = owl:Restriction (some/only/and/or)
  Folded-corner box             = annotation / data assertion
  Pentagon shape                = prov:Agent
  Yellow oval                   = prov:Entity
  Blue rectangle                = prov:Activity
  xsd:* boxes                   = XSD DATATYPES only

━━━ TWO-LAYER DIAGRAM RULE ━━━
Many diagrams show TWO layers simultaneously:
  - INSTANCE layer: dashed ovals with specific names (alice, room102, buildingA)
  - SCHEMA layer: solid ovals/rectangles with class names (Building, Room, Sensor)

You MUST extract edges from BOTH layers. For each layer extract:
  Instance layer:
    (a) rdf:type edges:  instance --dashed--> Class
        DIRECTION RULE: "from" = INSTANCE, "to" = CLASS  (NEVER the reverse)
        Example: beatles --rdf:type--> Band  (NOT Band --rdf:type--> beatles)
    (b) instance→instance objectProperty edges (e.g. comeTogther --performedBy--> beatles)
        These are separate from schema-level edges and MUST be listed too.
  Schema layer: class→class edges (objectProperty domain/range declarations)

List BOTH the schema-level edge (Song --performedBy--> Artist) AND the
instance-level edge (comeTogther --performedBy--> beatles) as separate entries.

━━━ CRITICAL RULES ━━━

RULE A — XSD DATATYPES: xsd:* nodes are ALWAYS datatypes, never instances.
RULE B — "is a"/"is-a" between TWO CLASSES = ALWAYS subClassOf.
RULE C — Data property: edge → xsd:* or literal box = dataProperty only.
RULE D — Domain/Range: ONLY add "domain"/"range" edges if there is an explicit
          PROPERTY RECTANGLE node in the diagram. Plain arrows between ovals are
          NEVER "domain" or "range" — they are objectProperty edges.
RULE E — SELF-LOOPS: Only include if you physically see a curved arrow.
RULE F — Dashed rectangles = attribute value examples, NOT individuals.
RULE G — Individuals without rdf:type arrows: if they are clearly ovals
          connected to other individuals via property edges, keep them as
          instances even without an explicit rdf:type arrow.
RULE H — subClassOf: hollow/open triangle arrowhead ◁ = ALWAYS subClassOf.
          Check EVERY oval-to-oval edge for hollow vs solid arrowheads.
          Do NOT miss subClassOf edges in dense diagrams.

━━━ EDGES ━━━
Trace every line from TAIL to ARROWHEAD. Arrowhead = TARGET.
Extract ALL edges — do not skip any visible line.
For instanceOf edges: "from" is ALWAYS the instance, "to" is ALWAYS the class.

━━━ DATA ASSERTIONS ━━━
Scan for these patterns — they are ALL data assertions:
  1. Folded-corner annotation box with "property = value" or "property: value"
  2. A literal string or number (e.g. "Abbey Road", "1969", "101") visually
     attached to or near an instance node via a labelled dashed arrow
  3. Any value box (yellow rectangle) connected by a dashed arrow to an INSTANCE
     node (not a class node) — the arrow label is the property name
Extract ALL of these into "data_assertions".

━━━ OWL RESTRICTIONS ━━━
Gray boxes with "X some Y", "X only Y", "X and Y" = owl:Restriction axioms.

Return ONLY valid JSON — no markdown:

{{
  "diagram_type": "OWL diagram | UML class diagram | ER diagram | PROV-O | mind map | informal ontology | other",
  "classes": [
    {{"id": "c1", "name": "e:Person", "description": ""}}
  ],
  "object_properties": [
    {{"id": "op1", "name": "e:writes",
      "note": "ONLY include if range is a class, not a datatype or literal"}}
  ],
  "instances": [
    {{"id": "i1", "name": "e:eetu", "type_class": "e:Person"}}
  ],
  "attribute_values": [
    {{"id": "av1", "value": "War and Peace", "property": "hasTitle",
      "domain_class": "BOOK", "datatype": "string"}}
  ],
  "restriction_axioms": [
    {{"subject": "Decision", "property": "isAnswerFor",
      "restriction_type": "some", "filler": "Question", "cardinality": null}}
  ],
  "edges": [
    {{
      "id": "e1",
      "from": "source_name",
      "to": "target_name",
      "label": "edge label or empty string",
      "edge_type": "subClassOf | instanceOf | objectProperty | dataProperty | domain | range | inverseOf | equivalentClass | disjointWith | typeDeclaration | other",
      "arrowhead_at": "which node the arrowhead touches",
      "confidence": "high | medium | low"
    }}
  ],
  "data_properties": [
    {{"class": "BOOK", "property": "hasTitle", "datatype": "string"}}
  ],
  "data_assertions": [
    {{"individual": "derek", "property": "foaf:givenName",
      "value": "Derek", "datatype": "string"}}
  ],
  "cardinalities": [
    {{"edge_id": "e1", "min": 0, "max": -1}}
  ],
  "complex_axioms": [
    {{"subject": "ClassName", "axiom_type": "equivalentClass",
      "operator": "intersectionOf | unionOf | complementOf",
      "operands": ["ClassA", "ClassB"]}}
  ],
  "namespace_hints": "e: http://e.org/ont#; foaf: http://xmlns.com/foaf/0.1/",
  "ambiguities": ["list anything unclear"]
}}"""


def pass1_full_extraction(image_data: str, media_type: str,
                          arrow_context: str = "",
                          p0: dict = None) -> dict:
    prompt = build_pass1_prompt(arrow_context)
    raw = _call_llm(image_data, media_type, prompt, max_tokens=6000)
    result = _parse_json(raw)

    # v7: arrowhead_at consistency check — if arrowhead_at != to, swap
    for edge in result.get("edges", []):
        ah = edge.get("arrowhead_at", "")
        if ah and ah != edge.get("to", "") and ah == edge.get("from", ""):
            # arrowhead touches the "from" node — swap direction
            edge["from"], edge["to"] = edge["to"], edge["from"]
            edge["arrowhead_at"] = edge["to"]

    # v7.1: Cross-validate ALL edges against Pass 0
    # Pass 0 is a simpler task (just detect arrow shapes/directions),
    # so it's often more accurate on direction than Pass 1 which is
    # biased by property name semantics.
    if p0:
        # Build Pass 0 direction lookup: label -> (from, to)
        p0_directions = {}
        for a in p0.get("arrows", []):
            lbl = a.get("label", "").lower().strip()
            if lbl and a.get("confidence") == "high":
                p0_directions[lbl] = (a["from"], a["to"])

        for edge in result.get("edges", []):
            label = edge.get("label", "").lower().strip()
            if not label or label not in p0_directions:
                continue
            p0_from, p0_to = p0_directions[label]
            e_from, e_to = edge.get("from", ""), edge.get("to", "")

            # Case 1: Self-loop in Pass 0 but not in Pass 1
            if p0_from == p0_to and e_from != e_to:
                edge["from"] = p0_from
                edge["to"] = p0_to
                edge["arrowhead_at"] = p0_to

            # Case 2: Reversed direction (Pass 0 says A→B, Pass 1 says B→A)
            elif (e_from == p0_to and e_to == p0_from and
                  e_from != e_to):
                edge["from"] = p0_from
                edge["to"] = p0_to
                edge["arrowhead_at"] = p0_to

    return result


# ---------------------------------------------------------------------------
# Pass 2 – Edge direction verification (strict)
# ---------------------------------------------------------------------------

def pass2_edge_direction_verification(image_data: str, media_type: str,
                                       p1: dict) -> dict:
    edges_json = json.dumps(p1.get("edges", []), indent=2)
    prompt = f"""You are verifying arrow DIRECTIONS in an ontology diagram.

STRICT RULES:
  1. To CORRECT a direction: you must physically locate the arrowhead in the
     image and describe its COLOUR, SHAPE and which NODE it touches.
     Do NOT correct based on semantic reasoning alone.
  2. For missed_edges: MAXIMUM 5 new edges. Each needs visual_evidence
     describing the line's colour, position, and arrowhead location.
     Do NOT add edges because they "should" exist logically.
  3. NEVER add self-loops (from X to X) unless you see a curved arrow.
  4. NEVER add an edge that contradicts an existing edge (A→B and B→A
     cannot both be subClassOf for the same pair).

Direction rules:
  subClassOf  → HOLLOW triangle ◁ points TO superclass.  Dog →◁ Animal
  instanceOf  → dashed arrow from INSTANCE to CLASS.  beatles --rdf:type--> Band
               NEVER reverse this: Band --rdf:type--> beatles is WRONG
  domain      → property node → domain class
  range       → property node → range class/datatype
  inverseOf   → property ↔ property

Previously extracted edges:
{edges_json}

Return ONLY valid JSON:
{{
  "verified_edges": [
    {{
      "id": "original id",
      "from": "corrected source",
      "to": "corrected target",
      "label": "label",
      "edge_type": "corrected type",
      "direction_changed": true,
      "correction_note": "describe the arrowhead colour/position you see"
    }}
  ],
  "missed_edges": [
    {{
      "id": "me1",
      "from": "source",
      "to": "target",
      "label": "label",
      "edge_type": "type",
      "arrowhead_at": "node the arrowhead touches",
      "visual_evidence": "REQUIRED: colour + position + arrowhead description"
    }}
  ]
}}"""
    raw = _call_llm(image_data, media_type, prompt)
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# Pass 3 – Instance verification (conservative)
# ---------------------------------------------------------------------------

def pass3_instance_verification(image_data: str, media_type: str,
                                  p1: dict) -> dict:
    classes   = [c["name"] for c in p1.get("classes", [])]
    instances = p1.get("instances", [])
    av_list   = p1.get("attribute_values", [])
    all_edges = p1.get("edges", [])

    # Build set of node names that appear in edges
    nodes_with_edges = set()
    for e in all_edges:
        nodes_with_edges.add(e.get("from", ""))
        nodes_with_edges.add(e.get("to", ""))

    prompt = f"""You are verifying INSTANCES (owl:NamedIndividual) in this diagram.

Classes:        {classes}
Instances:      {json.dumps(instances)}
Attribute vals: {json.dumps(av_list)}
Nodes with edges: {sorted(nodes_with_edges)}

CONSERVATIVE RECLASSIFICATION RULES:

RULE 1 — XSD DATATYPES ARE NEVER INSTANCES:
  xsd:string, xsd:integer, xsd:float, xsd:double, xsd:boolean,
  xsd:date, xsd:dateTime — always datatypes, never reclassify.

RULE 2 — ONLY reclassify to attribute_value if ALL of these are true:
  (a) The node is a coloured rectangle (not an oval)
  (b) The node is connected ONLY via data property arrows (hasName, hasTitle)
  (c) The node has NO outgoing edges to other individuals or classes
  If any of these fails, KEEP as instance.

RULE 3 — DO NOT reclassify individuals just because they lack an rdf:type arrow.
  In ABox diagrams, many individuals have no visible rdf:type arrow but are
  clearly individuals (ovals connected to other individuals via properties).
  Keep them as instances.

RULE 4 — TRUE attribute_values:
  - Coloured (green/yellow/orange) rectangles with string values
  - Connected ONLY via data property arrows
  - Example: green box "War and Peace" connected via "hasTitle"

For each current instance: confirm or reject based on rules above.

Return ONLY valid JSON:
{{
  "confirmed_instances": [
    {{"name": "e:eetu", "type_class": "e:Person",
      "visual_cue": "oval with rdf:type arrow or connected via properties"}}
  ],
  "reclassified_nodes": [
    {{"name": "Rachel", "was": "instance", "now": "attribute_value",
      "property": "hasName", "domain_class": "PERSON",
      "datatype": "string",
      "reason": "green rectangle, only connected via hasName data property"}}
  ],
  "no_instances_present": false
}}"""
    raw = _call_llm(image_data, media_type, prompt)
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# Pass 4 – Completeness sweep
# ---------------------------------------------------------------------------

def pass4_completeness_check(image_data: str, media_type: str,
                               merged: dict) -> dict:
    prompt = f"""You are doing a FINAL COMPLETENESS CHECK.

Current extraction:
{json.dumps(merged, indent=2)}

Scan the image for anything missing:
  1. Any node NOT captured?
  2. Any arrow/line NOT captured?
  3. Any label missed?
  4. Any folded-corner annotation box with property=value lines?
  5. Any namespace prefix or IRI visible in the image?
  6. Any cardinality (1, *, 0..1, 1..*) missed?
  7. Any OWL restriction box (some/only/and) missed?
  8. DATA ASSERTIONS — scan carefully for:
       - Literal values (strings, numbers, dates) near instance nodes
       - Yellow/coloured value boxes connected by dashed arrows to instance nodes
       - Annotation boxes attached to instances
     For each: record individual name, property (arrow label), value, datatype.
  9. INSTANCE EDGES — for each instance node, check: are ALL its outgoing
     arrows captured? Instance→instance objectProperty edges are commonly missed
     in two-layer diagrams. Verify every dashed oval has its edges listed.

ANTI-HALLUCINATION RULES:
  - Only report what you PHYSICALLY SEE is missing
  - Do NOT add self-loops (from X to X) — these are almost never real
  - Do NOT add edges because they "should" exist semantically
  - Maximum 5 missing edges

Return ONLY valid JSON:
{{
  "missing_nodes": [{{"name": "...",
    "node_type": "class|instance|attribute_value|datatype|annotation"}}],
  "missing_edges": [{{"from": "...", "to": "...", "label": "...",
    "edge_type": "...", "visual_evidence": "describe what you see"}}],
  "missing_restrictions": [{{"subject": "...", "property": "...",
    "restriction_type": "some|only|min|max", "filler": "..."}}],
  "missing_data_assertions": [{{"individual": "...", "property": "...",
    "value": "...", "datatype": "string"}}],
  "annotations": ["floating text / legend items"],
  "namespace_info": "prefix: IRI pairs or empty",
  "overall_completeness": "complete | minor gaps | significant gaps",
  "notes": "anything unusual"
}}"""
    raw = _call_llm(image_data, media_type, prompt)
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def _normalize_label(label: str) -> str:
    """Normalize subClassOf label variants to empty string for dedup."""
    l = label.lower().strip()
    if l in ("rdfs:subclassof", "subclassof", "subclass", "is_a",
             "is-a", "is a", "isa", ""):
        return ""
    return label.strip()


def _dedup_edges(edges: list, class_names: set = None) -> list:
    """Remove duplicate edges. Treat empty label and rdfs:subClassOf as same.
    Also strips spurious domain/range edges that arise when the LLM misclassifies
    plain objectProperty arrows between class nodes as domain/range."""
    if class_names is None:
        class_names = set()
    seen   = set()
    result = []
    for e in edges:
        et    = normalize_edge_type(e.get("edge_type", "other"))
        label = _normalize_label(e.get("label", ""))

        # Auto-correct is-a labels to subClassOf
        if is_subclass_label(e.get("label", "")):
            et    = "subClassOf"
            label = ""

        # Auto-correct xsd:* targets to dataProperty
        if is_xsd_node(e.get("to", "")):
            et = "dataProperty"

        # Strip domain/range edges whose source is a plain class node
        # (real domain/range edges originate from a property-rectangle, not a class)
        if et in ("domain", "range"):
            src = e.get("from", "")
            # If the source looks like a class name (capitalized, no special chars)
            # and is in the known class set, demote to objectProperty
            if class_names and src in class_names:
                et = "objectProperty"
            elif not class_names and src and src[0].isupper():
                et = "objectProperty"

        key = (e.get("from", ""), e.get("to", ""), label, et)
        if key not in seen:
            seen.add(key)
            e["edge_type"] = et
            result.append(e)
    return result


def _clean_object_properties(obj_props: list, edges: list) -> list:
    """
    Remove from object_properties:
      1. Properties that only appear in dataProperty edges
      2. is-a / subClassOf labels
    """
    dp_only_props = set()
    prop_edge_types: dict = {}
    for e in edges:
        lbl = e.get("label", "")
        et  = normalize_edge_type(e.get("edge_type", ""))
        if lbl:
            prop_edge_types.setdefault(lbl, set()).add(et)
    for prop_name, types in prop_edge_types.items():
        if types == {"dataProperty"}:
            dp_only_props.add(prop_name)

    result = []
    for op in obj_props:
        name = op.get("name", "")
        # Skip if only used as dataProperty
        if name in dp_only_props:
            continue
        # Skip if name is a subClassOf variant
        if name.lower().strip() in SUBCLASS_LABEL_SET:
            continue
        result.append(op)
    return result


def merge_passes(p1: dict, p2: dict, p3: dict, p4: dict) -> dict:
    result = dict(p1)

    # ── v7 helpers ────────────────────────────────────────────────────────────
    VISUAL_KEYWORDS = {
        "black", "white", "grey", "gray", "dark", "filled", "hollow", "open",
        "solid", "dashed", "dotted", "triangle", "chevron", "arrow", "arrowhead",
        "top", "bottom", "left", "right", "above", "below", "touches", "points",
        "tip", "head", "tail", "colour", "color", "shape",
    }

    def _has_visual_evidence(note: str, min_kw: int = 2) -> bool:
        if not note:
            return False
        words = set(note.lower().split())
        return len(words & VISUAL_KEYWORDS) >= min_kw

    def _norm(name: str) -> str:
        n = name.lower().strip()
        return n.split(":", 1)[1] if ":" in n else n

    def _is_self_loop(e: dict) -> bool:
        f, t = e.get("from", ""), e.get("to", "")
        return f == t or _norm(f) == _norm(t)

    # Build sets for filtering
    av_names = {av.get("value", "") for av in p1.get("attribute_values", [])}
    dp_labels = {dp.get("property", "") for dp in p1.get("data_properties", [])}
    existing_edge_keys = set()
    for e in p1.get("edges", []):
        existing_edge_keys.add((_norm(e.get("from", "")),
                                _norm(e.get("to", "")),
                                _norm(e.get("label", ""))))

    # ── edges: apply pass-2 direction corrections (evidence-filtered) ─────
    verified_map = {e["id"]: e for e in p2.get("verified_edges", [])}
    corrected = []
    n_corrections = 0
    MAX_CORRECTIONS = 3

    for edge in p1.get("edges", []):
        v = verified_map.get(edge["id"])
        if v and v.get("direction_changed"):
            note = v.get("correction_note", "")
            if _has_visual_evidence(note) and n_corrections < MAX_CORRECTIONS:
                corrected.append({
                    "id":        edge["id"],
                    "from":      v["from"],
                    "to":        v["to"],
                    "label":     v["label"],
                    "edge_type": normalize_edge_type(v["edge_type"]),
                })
                n_corrections += 1
            else:
                # Reject correction — keep original
                corrected.append({
                    "id":        edge["id"],
                    "from":      edge["from"],
                    "to":        edge["to"],
                    "label":     edge.get("label", ""),
                    "edge_type": normalize_edge_type(
                                 edge.get("edge_type", "other")),
                })
        else:
            corrected.append({
                "id":        edge["id"],
                "from":      v["from"]      if v else edge["from"],
                "to":        v["to"]        if v else edge["to"],
                "label":     v["label"]     if v else edge.get("label", ""),
                "edge_type": normalize_edge_type(
                             v["edge_type"] if v else edge.get("edge_type", "other")),
            })

    # ── pass-2 missed edges (v7: strict filtering) ────────────────────────
    n_missed = 0
    MAX_MISSED = 2
    for me in p2.get("missed_edges", []):
        if n_missed >= MAX_MISSED:
            break
        # Block self-loops
        if _is_self_loop(me):
            continue
        me_label = me.get("label", "")
        me_to = me.get("to", "")
        me_from = me.get("from", "")
        # Block if target is an attribute value
        if me_to in av_names:
            continue
        # Block if label is a known data property AND target is not a class
        # (allows schema-level data prop edges like Class→xsd:type)
        if me_label in dp_labels and not is_xsd_node(me_to) and \
                me_to not in {c["name"] for c in p1.get("classes", [])}:
            continue
        # Block if this exact edge already exists
        key = (_norm(me_from), _norm(me_to), _norm(me_label))
        if key in existing_edge_keys:
            continue
        # v7.1: Block reverse duplicates — if B→A with same label exists
        rev_key = (_norm(me_to), _norm(me_from), _norm(me_label))
        if rev_key in existing_edge_keys:
            continue
        corrected.append({
            "id":        me["id"],
            "from":      me_from,
            "to":        me_to,
            "label":     me_label,
            "edge_type": normalize_edge_type(me.get("edge_type", "other")),
        })
        existing_edge_keys.add(key)
        n_missed += 1

    # ── instances: use pass-3 (conservative) ────────────────────────────────
    reclass_to_av    = {}
    reclass_to_class = {}
    for r in p3.get("reclassified_nodes", []):
        if is_xsd_node(r["name"]):
            continue
        if r["now"] == "attribute_value":
            reclass_to_av[r["name"]] = r
        elif r["now"] == "class":
            reclass_to_class[r["name"]] = r

    # v7: Protect nodes connected via objectProperty from reclassification
    obj_prop_connected = set()
    for e in p1.get("edges", []):
        et = normalize_edge_type(e.get("edge_type", "other"))
        if et == "objectProperty":
            obj_prop_connected.add(e.get("from", ""))
            obj_prop_connected.add(e.get("to", ""))
    reclass_to_av = {
        name: r for name, r in reclass_to_av.items()
        if name not in obj_prop_connected
    }

    if p3.get("no_instances_present"):
        result["instances"] = []
    else:
        result["instances"] = [
            {"name": i["name"], "type_class": i["type_class"]}
            for i in p3.get("confirmed_instances", [])
            if not is_xsd_node(i["name"])
        ]

    for name, r in reclass_to_class.items():
        if not any(c["name"] == name for c in result.get("classes", [])):
            result.setdefault("classes", []).append(
                {"id": name.lower(), "name": name, "description": ""})

    # Remove reclassified-to-av nodes from classes
    result["classes"] = [
        c for c in result.get("classes", [])
        if c["name"] not in reclass_to_av
    ]

    av_list = [
        av for av in result.get("attribute_values", [])
        if not is_xsd_node(av.get("value", ""))
    ]
    for name, r in reclass_to_av.items():
        if not any(av.get("value") == name for av in av_list):
            av_list.append({
                "value":        name,
                "property":     r.get("property", ""),
                "domain_class": r.get("domain_class", ""),
                "datatype":     r.get("datatype", "string"),
            })
    result["attribute_values"] = av_list

    # ── pass-4 additions ─────────────────────────────────────────────────────
    for node in p4.get("missing_nodes", []):
        nt = node["node_type"]
        if nt == "class" and not any(
                c["name"] == node["name"] for c in result["classes"]):
            result["classes"].append(
                {"id": node["name"].lower(), "name": node["name"],
                 "description": ""})
        elif nt == "instance" and not is_xsd_node(node["name"]) and not any(
                i["name"] == node["name"] for i in result["instances"]):
            result["instances"].append(
                {"name": node["name"], "type_class": "Unknown"})
        elif nt == "attribute_value" and not is_xsd_node(node["name"]) \
                and not any(av.get("value") == node["name"]
                            for av in result["attribute_values"]):
            result["attribute_values"].append(
                {"value": node["name"], "property": "",
                 "domain_class": "", "datatype": "string"})

    for edge in p4.get("missing_edges", []):
        # v7: Block self-loops (normalised)
        if _is_self_loop(edge):
            continue
        p4_from = edge.get("from", "")
        p4_to = edge.get("to", "")
        p4_label = edge.get("label", "")
        # v7: Block if this exact edge already exists
        fwd_key = (_norm(p4_from), _norm(p4_to), _norm(p4_label))
        if fwd_key in existing_edge_keys:
            continue
        # v7: Block reverse duplicates — if B→A with same label exists
        rev_key = (_norm(p4_to), _norm(p4_from), _norm(p4_label))
        if rev_key in existing_edge_keys:
            continue
        # v7: Block if any edge between these two nodes already exists
        #     (regardless of label) — prevents Pass 4 from adding
        #     direction-confused duplicates
        any_existing = any(
            (_norm(p4_from) == _norm(e.get("from", "")) and
             _norm(p4_to) == _norm(e.get("to", ""))) or
            (_norm(p4_from) == _norm(e.get("to", "")) and
             _norm(p4_to) == _norm(e.get("from", "")))
            for e in corrected
        )
        if any_existing:
            continue
        corrected.append({
            "id":        f"p4_{p4_from}_{p4_to}",
            "from":      p4_from,
            "to":        p4_to,
            "label":     p4_label,
            "edge_type": normalize_edge_type(edge.get("edge_type", "other")),
        })
        existing_edge_keys.add(fwd_key)

    # Restrictions
    restrictions = list(result.get("restriction_axioms", []))
    for r in p4.get("missing_restrictions", []):
        if not any(rx.get("subject") == r.get("subject") and
                   rx.get("property") == r.get("property") and
                   rx.get("filler") == r.get("filler")
                   for rx in restrictions):
            restrictions.append(r)
    result["restriction_axioms"] = restrictions

    # Data assertions
    assertions = list(result.get("data_assertions", []))
    for a in p4.get("missing_data_assertions", []):
        assertions.append(a)
    result["data_assertions"] = assertions

    # v7: Complex axioms (pass through from p1)
    result.setdefault("complex_axioms", [])

    # ── Auto-correct reversed instanceOf edges ───────────────────────────────
    # A correct instanceOf edge goes instance → class.
    # If the LLM reverses it (class → instance), swap it back.
    confirmed_instance_names = {
        i["name"] for i in p3.get("confirmed_instances", [])
        if not is_xsd_node(i["name"])
    }
    # Also collect instance names from pass1
    for inst in p1.get("instances", []):
        confirmed_instance_names.add(inst.get("name", ""))

    for edge in corrected:
        if normalize_edge_type(edge.get("edge_type", "")) == "instanceOf":
            frm, to = edge.get("from", ""), edge.get("to", "")
            # If "from" looks like a class and "to" looks like an instance, swap
            if (to in confirmed_instance_names and frm not in confirmed_instance_names
                    and frm not in confirmed_instance_names):
                edge["from"], edge["to"] = to, frm

    # Deduplicate edges (pass class names to filter spurious domain/range edges)
    known_classes = {c["name"] for c in result.get("classes", [])}
    result["edges"] = _dedup_edges(corrected, class_names=known_classes)

    # Clean object_properties
    result["object_properties"] = _clean_object_properties(
        result.get("object_properties", []), result["edges"])

    # Auto-declare PROV-O type classes
    prov_types_used = {i.get("type_class", "") for i in result.get("instances", [])}
    for pt in PROV_CLASSES:
        if pt in prov_types_used and not any(
                c["name"] == pt for c in result["classes"]):
            result["classes"].append(
                {"id": pt.replace(":", "_"), "name": pt, "description": ""})

    # Metadata
    if p4.get("namespace_info"):
        result["namespace_info"] = p4["namespace_info"]
    result["annotations"]             = p4.get("annotations", [])
    result["completeness_assessment"] = p4.get("overall_completeness", "unknown")
    result["completeness_notes"]      = p4.get("notes", "")
    return result


# ---------------------------------------------------------------------------
# OWL serialisation
# ---------------------------------------------------------------------------

def to_owl(extraction: dict,
           base_uri: str = "http://example.org/ontology#") -> Graph:
    g = Graph()

    hint_str = (extraction.get("namespace_hints") or
                extraction.get("namespace_info") or "")
    ns_map = parse_namespace_hints(hint_str)
    for prefix, iri in ns_map.items():
        try:
            g.bind(prefix, Namespace(iri))
        except Exception:
            pass

    def R(name: str) -> URIRef:
        return resolve_name(name, ns_map, base_uri)

    onto_uri = URIRef(base_uri.rstrip("#/"))
    g.add((onto_uri, RDF.type, OWL.Ontology))

    # ── Classes ──────────────────────────────────────────────────────────────
    for cls in extraction.get("classes", []):
        u = R(cls["name"])
        g.add((u, RDF.type,   OWL.Class))
        g.add((u, RDFS.label, Literal(cls["name"].split(":")[-1], lang="en")))
        if cls.get("description"):
            g.add((u, RDFS.comment, Literal(cls["description"], lang="en")))

    # ── Object Properties ────────────────────────────────────────────────────
    declared_obj_props: set = set()

    def ensure_obj_prop(name: str) -> URIRef:
        u = R(name)
        if u not in declared_obj_props:
            g.add((u, RDF.type,   OWL.ObjectProperty))
            g.add((u, RDFS.label, Literal(name.split(":")[-1], lang="en")))
            declared_obj_props.add(u)
        return u

    for op in extraction.get("object_properties", []):
        ensure_obj_prop(op["name"])

    # ── Data Properties ──────────────────────────────────────────────────────
    declared_data_props: dict = {}

    def ensure_data_prop(prop_name: str, domain_class: str = "",
                         datatype: str = "string") -> URIRef:
        u = R(prop_name)
        if prop_name not in declared_data_props:
            g.add((u, RDF.type,   OWL.DatatypeProperty))
            g.add((u, RDFS.label,
                   Literal(prop_name.split(":")[-1], lang="en")))
            declared_data_props[prop_name] = u
        if domain_class and not is_xsd_node(domain_class):
            g.add((u, RDFS.domain, R(domain_class)))
        dt = DATATYPE_MAP.get(datatype.lower(), XSD.string)
        g.add((u, RDFS.range, dt))
        return u

    for dp in extraction.get("data_properties", []):
        ensure_data_prop(dp["property"], dp.get("class", ""),
                         dp.get("datatype", "string"))

    # ── Attribute values ─────────────────────────────────────────────────────
    av_values: set = set()
    for av in extraction.get("attribute_values", []):
        if is_xsd_node(av.get("value", "")):
            continue
        av_values.add(av.get("value", ""))
        prop_name = av.get("property", "")
        if prop_name:
            u = ensure_data_prop(prop_name, av.get("domain_class", ""),
                                 av.get("datatype", "string"))
            if av.get("value"):
                g.add((u, RDFS.comment,
                       Literal(f"Example value: {av['value']}", lang="en")))

    dp_targets: set = {
        e["to"] for e in extraction.get("edges", [])
        if normalize_edge_type(e.get("edge_type", "")) == "dataProperty"
    }

    # ── Individuals ──────────────────────────────────────────────────────────
    for inst in extraction.get("instances", []):
        name = inst["name"]
        if name in av_values or name in dp_targets or is_xsd_node(name):
            continue
        u = R(name)
        g.add((u, RDF.type,   OWL.NamedIndividual))
        g.add((u, RDFS.label,
               Literal(name.split(":")[-1].strip("<>"), lang="en")))
        tc = inst.get("type_class", "Unknown")
        if tc and tc != "Unknown":
            g.add((u, RDF.type, R(tc)))

    # ── Data assertions ──────────────────────────────────────────────────────
    for da in extraction.get("data_assertions", []):
        ind_uri  = R(da["individual"])
        prop_uri = R(da["property"])
        g.add((prop_uri, RDF.type,   OWL.DatatypeProperty))
        g.add((prop_uri, RDFS.label,
               Literal(da["property"].split(":")[-1], lang="en")))
        dt  = DATATYPE_MAP.get(da.get("datatype", "string").lower(),
                               XSD.string)
        g.add((ind_uri, prop_uri, Literal(da["value"], datatype=dt)))

    # ── Edges ─────────────────────────────────────────────────────────────────
    for edge in extraction.get("edges", []):
        src_name = edge["from"]
        tgt_name = edge["to"]
        label    = edge.get("label", "").strip()
        src      = R(src_name)
        tgt      = R(tgt_name)

        etype = normalize_edge_type(edge.get("edge_type", "other"))
        if is_subclass_label(label):
            etype = "subClassOf"
        if is_xsd_node(tgt_name):
            etype = "dataProperty"

        if etype == "subClassOf" or label in ("rdfs:subClassOf", "subClassOf"):
            g.add((src, RDFS.subClassOf, tgt))

        elif etype == "instanceOf" or (
                label == "rdf:type" and tgt not in META_URIS and
                tgt_name not in av_values and not is_xsd_node(tgt_name)):
            g.add((src, RDF.type, tgt))

        elif etype == "typeDeclaration" or (
                label == "rdf:type" and tgt in META_URIS):
            tgt_str = tgt_name.lower()
            if "objectproperty" in tgt_str:
                ensure_obj_prop(src_name)
            elif "datatypeproperty" in tgt_str:
                ensure_data_prop(src_name)
            elif "class" in tgt_str:
                g.add((src, RDF.type, OWL.Class))

        elif etype == "domain" or label == "rdfs:domain":
            ensure_obj_prop(src_name)
            g.add((src, RDFS.domain, tgt))

        elif etype == "range" or label == "rdfs:range":
            ensure_obj_prop(src_name)
            xsd_t = DATATYPE_MAP.get(tgt_name.lower())
            g.add((src, RDFS.range, xsd_t if xsd_t else tgt))

        elif etype == "inverseOf" or label == "owl:inverseOf":
            ensure_obj_prop(src_name)
            ensure_obj_prop(tgt_name)
            g.add((src, OWL.inverseOf, tgt))

        elif etype == "equivalentClass":
            g.add((src, OWL.equivalentClass, tgt))

        elif etype == "disjointWith":
            g.add((src, OWL.disjointWith, tgt))

        elif etype == "objectProperty":
            prop_name = label if label else \
                f"{src_name}_relatedTo_{tgt_name}"
            prop = ensure_obj_prop(prop_name)
            src_is_ind = any(i["name"] == src_name
                             for i in extraction.get("instances", []))
            tgt_is_ind = any(i["name"] == tgt_name
                             for i in extraction.get("instances", []))
            if not src_is_ind:
                g.add((prop, RDFS.domain, src))
            if not tgt_is_ind and tgt_name not in av_values:
                g.add((prop, RDFS.range, tgt))

        elif etype == "dataProperty":
            prop_name = label if label else f"has_{tgt_name}"
            lit = parse_typed_literal(tgt_name)
            if lit is not None:
                prop_uri = R(prop_name)
                g.add((prop_uri, RDF.type,   OWL.DatatypeProperty))
                g.add((prop_uri, RDFS.label,
                       Literal(prop_name.split(":")[-1], lang="en")))
                g.add((src, prop_uri, lit))
            elif is_xsd_node(tgt_name):
                dtype = tgt_name.replace("xsd:", "")
                ensure_data_prop(prop_name, src_name, dtype)
            else:
                matched_av = next(
                    (av for av in extraction.get("attribute_values", [])
                     if av.get("value") == tgt_name), None)
                dtype = matched_av.get("datatype", "string") \
                    if matched_av else "string"
                ensure_data_prop(prop_name, src_name, dtype)

        else:
            if label and tgt not in META_URIS and tgt_name not in av_values:
                lit = parse_typed_literal(tgt_name)
                if lit is not None:
                    prop_uri = R(label)
                    g.add((prop_uri, RDF.type,  OWL.DatatypeProperty))
                    g.add((src, prop_uri, lit))
                elif not is_xsd_node(tgt_name):
                    prop = ensure_obj_prop(label)
                    g.add((prop, RDFS.domain, src))
                    g.add((prop, RDFS.range,  tgt))

    # ── OWL Restrictions ─────────────────────────────────────────────────────
    RESTRICTION_MAP = {
        "some":           OWL.someValuesFrom,
        "only":           OWL.allValuesFrom,
        "allvaluesfrom":  OWL.allValuesFrom,
        "somevaluesfrom": OWL.someValuesFrom,
        "min":            OWL.minCardinality,
        "max":            OWL.maxCardinality,
        "exactly":        OWL.cardinality,
        "value":          OWL.hasValue,
    }
    for rx in extraction.get("restriction_axioms", []):
        subject = rx.get("subject", "")
        prop_n  = rx.get("property", "")
        rtype   = rx.get("restriction_type", "some").lower()
        filler  = rx.get("filler", "")
        card    = rx.get("cardinality")
        if not subject or not prop_n:
            continue
        subj_uri = R(subject)
        prop_uri = ensure_obj_prop(prop_n)
        restr    = BNode()
        g.add((restr, RDF.type,       OWL.Restriction))
        g.add((restr, OWL.onProperty, prop_uri))
        owl_restr = RESTRICTION_MAP.get(rtype, OWL.someValuesFrom)
        if rtype in ("min", "max", "exactly") and card is not None:
            g.add((restr, owl_restr,
                   Literal(int(card), datatype=XSD.nonNegativeInteger)))
        elif filler:
            g.add((restr, owl_restr, R(filler)))
        g.add((subj_uri, RDFS.subClassOf, restr))

    # ── Cardinalities ─────────────────────────────────────────────────────────
    edge_map = {e["id"]: e for e in extraction.get("edges", [])}
    for card in extraction.get("cardinalities", []):
        edge = edge_map.get(card.get("edge_id"))
        if not edge or not edge.get("label"):
            continue
        prop = R(edge["label"])
        src  = R(edge["from"])
        mn, mx = card.get("min", 0), card.get("max", -1)
        restr = BNode()
        g.add((restr, RDF.type,       OWL.Restriction))
        g.add((restr, OWL.onProperty, prop))
        if mn == mx and mn >= 0:
            g.add((restr, OWL.cardinality,
                   Literal(mn, datatype=XSD.nonNegativeInteger)))
        else:
            if mn > 0:
                g.add((restr, OWL.minCardinality,
                       Literal(mn, datatype=XSD.nonNegativeInteger)))
            if mx >= 0:
                g.add((restr, OWL.maxCardinality,
                       Literal(mx, datatype=XSD.nonNegativeInteger)))
        g.add((src, RDFS.subClassOf, restr))

    return g


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def extract_ontology_to_owl(image_path: str, output_path=None,
                             base_uri: str = "http://example.org/ontology#"):
    stem = Path(image_path).stem
    if output_path is None:
        output_path = f"{stem}_ontology.owl"

    print(f"\n{'='*60}")
    print(f"  Ontology Extractor v7 (GPT-4o) - {image_path}")
    print(f"{'='*60}")

    image_data, media_type = _load_image(image_path)

    # ── Pass 0 ──────────────────────────────────────────────────────────────
    print("\n[Pass 0] Arrow inventory ...")
    p0 = pass0_arrow_inventory(image_data, media_type)
    n_arrows = len(p0.get("arrows", []))
    n_subclass = sum(1 for a in p0.get("arrows", [])
                     if a.get("conclusion") == "subClassOf")
    print(f"         arrows={n_arrows}  subClassOf_detected={n_subclass}")
    arrow_context = _build_arrow_context(p0)

    # ── Pass 1 ──────────────────────────────────────────────────────────────
    print("\n[Pass 1] Full structural extraction ...")
    p1 = pass1_full_extraction(image_data, media_type, arrow_context, p0=p0)
    print(f"         classes={len(p1.get('classes',[]))}  "
          f"obj_props={len(p1.get('object_properties',[]))}  "
          f"instances={len(p1.get('instances',[]))}  "
          f"attr_vals={len(p1.get('attribute_values',[]))}  "
          f"restrictions={len(p1.get('restriction_axioms',[]))}  "
          f"edges={len(p1.get('edges',[]))}")

    # ── Pass 2 ──────────────────────────────────────────────────────────────
    print("\n[Pass 2] Verifying edge directions ...")
    p2 = pass2_edge_direction_verification(image_data, media_type, p1)
    n_corrected = sum(1 for e in p2.get("verified_edges", [])
                      if e.get("direction_changed"))
    n_missed = len(p2.get("missed_edges", []))
    print(f"         corrections={n_corrected}  new edges={n_missed}")

    # ── Pass 3 ──────────────────────────────────────────────────────────────
    print("\n[Pass 3] Verifying instances ...")
    p3 = pass3_instance_verification(image_data, media_type, p1)
    print(f"         confirmed={len(p3.get('confirmed_instances',[]))}  "
          f"reclassified={len(p3.get('reclassified_nodes',[]))}")

    # ── Pass 4 ──────────────────────────────────────────────────────────────
    print("\n[Pass 4] Completeness sweep ...")
    temp_merged = merge_passes(p1, p2, p3,
                               {"missing_nodes": [], "missing_edges": [],
                                "missing_restrictions": [],
                                "missing_data_assertions": [],
                                "annotations": []})
    p4 = pass4_completeness_check(image_data, media_type, temp_merged)
    print(f"         missing_nodes={len(p4.get('missing_nodes',[]))}  "
          f"missing_edges={len(p4.get('missing_edges',[]))}  "
          f"completeness={p4.get('overall_completeness','?')}")

    # ── Merge ────────────────────────────────────────────────────────────────
    print("\n[Merge] Combining all passes ...")
    final = merge_passes(p1, p2, p3, p4)

    # ── OWL ──────────────────────────────────────────────────────────────────
    print("\n[OWL]  Serialising ...")
    g = to_owl(final, base_uri)
    g.serialize(destination=output_path,   format="xml")
    g.serialize(destination=f"{stem}.ttl", format="turtle")
    print(f"       -> {output_path}")
    print(f"       -> {stem}.ttl")

    json_path = f"{stem}_extraction.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({
            "pass0":              p0,
            "pass1":              p1,
            "pass2_corrections":  [e for e in p2.get("verified_edges", [])
                                   if e.get("direction_changed")],
            "pass2_missed_edges": p2.get("missed_edges", []),
            "pass3":              p3,
            "pass4":              p4,
            "final":              final,
        }, fh, indent=2, ensure_ascii=False)
    print(f"       -> {json_path}")

    report = {
        "total_classes":            len(final.get("classes",            [])),
        "total_object_properties":  len(final.get("object_properties",  [])),
        "total_instances":          len(final.get("instances",          [])),
        "total_attribute_values":   len(final.get("attribute_values",   [])),
        "total_restriction_axioms": len(final.get("restriction_axioms", [])),
        "total_edges":              len(final.get("edges",              [])),
        "pass0_arrows_detected":    n_arrows,
        "pass0_subclass_detected":  n_subclass,
        "edge_corrections":         n_corrected,
        "new_edges_pass2":          n_missed,
        "completeness":             p4.get("overall_completeness", "?"),
        "ambiguities":              final.get("ambiguities", []),
        "namespace_info":           final.get("namespace_hints", ""),
    }

    print("\n[Report]")
    for k, v in report.items():
        print(f"  {k}: {v}")

    return g, final, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ontology_extractor_openai.py "
              "<image_path> [output.owl] [base_uri]")
        sys.exit(1)
    img  = sys.argv[1]
    out  = sys.argv[2] if len(sys.argv) > 2 else None
    base = sys.argv[3] if len(sys.argv) > 3 else "http://example.org/ontology#"
    graph, extraction, summary = extract_ontology_to_owl(img, out, base)
