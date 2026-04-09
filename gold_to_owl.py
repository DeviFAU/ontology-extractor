"""
gold_to_owl.py
==============
Converts gold-standard JSON files to valid OWL (RDF/XML + Turtle).

Usage:
  python gold_to_owl.py --input gold_standards/ --output owl_gold/
  python gold_to_owl.py --file gold_standards/synth_01_gold.json

Requirements:
  pip install rdflib
"""

import json
import argparse
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, OWL, RDF, RDFS, Namespace, URIRef, Literal, BNode
from rdflib.namespace import XSD

KNOWN_NS = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "prov": "http://www.w3.org/ns/prov#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "schema": "http://schema.org/",
}

XSD_MAP = {
    "string": XSD.string, "str": XSD.string,
    "integer": XSD.integer, "int": XSD.integer,
    "float": XSD.float, "double": XSD.double,
    "boolean": XSD.boolean, "date": XSD.date,
    "dateTime": XSD.dateTime, "datetime": XSD.dateTime,
}


def resolve(name: str, ns_map: dict, base: str) -> URIRef:
    if name.startswith("http://") or name.startswith("https://"):
        # Clean up spaces in full URIs (URL-encode them)
        # Find the last # or / to identify the fragment/path boundary
        if "#" in name:
            prefix, fragment = name.rsplit("#", 1)
            clean_fragment = quote(fragment, safe="")
            return URIRef(prefix + "#" + clean_fragment)
        elif "/" in name:
            # For paths, encode spaces in the last component
            parts = name.rsplit("/", 1)
            if len(parts) == 2:
                clean_last = quote(parts[1], safe="")
                return URIRef(parts[0] + "/" + clean_last)
        return URIRef(name)
    if name.startswith("xsd:"):
        local = name[4:]
        clean_local = quote(local, safe="")
        return URIRef(f"http://www.w3.org/2001/XMLSchema#{clean_local}")
    if ":" in name:
        prefix, local = name.split(":", 1)
        base_uri = ns_map.get(prefix.lower(), ns_map.get(prefix))
        if base_uri:
            clean_local = quote(local, safe="")
            return URIRef(base_uri + clean_local)
    clean = quote(name, safe="")
    return URIRef(base + clean)


def gold_to_owl(gold: dict) -> Graph:
    g = Graph()
    base = gold.get("base_uri", "http://example.org/ontology#")

    ns_map = dict(KNOWN_NS)
    ns_map.update(gold.get("namespace_prefixes", {}))
    for prefix, uri in ns_map.items():
        try:
            g.bind(prefix, Namespace(uri))
        except Exception:
            pass

    R = lambda name: resolve(name, ns_map, base)

    # Ontology declaration
    onto = URIRef(base.rstrip("#/"))
    g.add((onto, RDF.type, OWL.Ontology))

    # Classes
    for cls in gold.get("classes", []):
        u = R(cls["name"])
        g.add((u, RDF.type, OWL.Class))
        g.add((u, RDFS.label, Literal(cls["name"].split(":")[-1], lang="en")))

    # Object Properties
    for op in gold.get("object_properties", []):
        u = R(op["name"])
        g.add((u, RDF.type, OWL.ObjectProperty))
        g.add((u, RDFS.label, Literal(op["name"].split(":")[-1], lang="en")))
        if op.get("domain"):
            g.add((u, RDFS.domain, R(op["domain"])))
        if op.get("range"):
            g.add((u, RDFS.range, R(op["range"])))

    # Data Properties
    for dp in gold.get("data_properties", []):
        u = R(dp["name"])
        g.add((u, RDF.type, OWL.DatatypeProperty))
        g.add((u, RDFS.label, Literal(dp["name"].split(":")[-1], lang="en")))
        if dp.get("domain"):
            g.add((u, RDFS.domain, R(dp["domain"])))
        dt = XSD_MAP.get(dp.get("datatype", "string"), XSD.string)
        g.add((u, RDFS.range, dt))

    # Individuals
    for inst in gold.get("instances", []):
        u = R(inst["name"])
        g.add((u, RDF.type, OWL.NamedIndividual))
        g.add((u, RDFS.label, Literal(inst["name"].split(":")[-1], lang="en")))
        if inst.get("type_class"):
            g.add((u, RDF.type, R(inst["type_class"])))

    # Edges
    for edge in gold.get("edges", []):
        src = R(edge["from"])
        tgt = R(edge["to"])
        etype = edge.get("edge_type", "other")

        if etype == "subClassOf":
            g.add((src, RDFS.subClassOf, tgt))
        elif etype == "instanceOf":
            g.add((src, RDF.type, tgt))
        elif etype == "inverseOf":
            g.add((src, OWL.inverseOf, tgt))
        elif etype == "equivalentClass":
            g.add((src, OWL.equivalentClass, tgt))
        elif etype == "disjointWith":
            g.add((src, OWL.disjointWith, tgt))
        elif etype == "domain":
            g.add((src, RDFS.domain, tgt))
        elif etype == "range":
            xsd_t = XSD_MAP.get(edge["to"].replace("xsd:", "").lower())
            g.add((src, RDFS.range, xsd_t if xsd_t else tgt))

    # Restriction axioms
    for rx in gold.get("restriction_axioms", []):
        subj = R(rx["subject"])
        prop = R(rx["property"])
        rtype = rx.get("restriction_type", "some")
        restr = BNode()
        g.add((restr, RDF.type, OWL.Restriction))
        g.add((restr, OWL.onProperty, prop))
        if rtype in ("min", "max", "exactly") and rx.get("cardinality") is not None:
            owl_pred = {"min": OWL.minCardinality, "max": OWL.maxCardinality,
                        "exactly": OWL.cardinality}[rtype]
            g.add((restr, owl_pred,
                   Literal(int(rx["cardinality"]), datatype=XSD.nonNegativeInteger)))
        elif rx.get("filler"):
            owl_pred = {"some": OWL.someValuesFrom, "only": OWL.allValuesFrom
                        }.get(rtype, OWL.someValuesFrom)
            g.add((restr, owl_pred, R(rx["filler"])))
        g.add((subj, RDFS.subClassOf, restr))

    # Data assertions
    for da in gold.get("data_assertions", []):
        ind = R(da["individual"])
        prop = R(da["property"])
        dt = XSD_MAP.get(da.get("datatype", "string"), XSD.string)
        g.add((ind, prop, Literal(da["value"], datatype=dt)))

    return g


def convert_all(input_dir: str, output_dir: str):
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    gold_files = sorted(in_path.glob("*_gold.json"))
    if not gold_files:
        print(f"[!] No *_gold.json files found in {input_dir}")
        return

    print(f"\nConverting {len(gold_files)} gold files to OWL...")
    for gf in gold_files:
        with open(gf) as f:
            gold = json.load(f)
        stem = gf.stem.replace("_gold", "")
        g = gold_to_owl(gold)

        owl_path = out_path / f"{stem}_gold.owl"
        ttl_path = out_path / f"{stem}_gold.ttl"
        g.serialize(destination=str(owl_path), format="xml")
        g.serialize(destination=str(ttl_path), format="turtle")
        print(f"  {stem:<20} triples={len(g):>4}  -> {owl_path.name}, {ttl_path.name}")

    print(f"\nConverted {len(gold_files)} files to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert gold JSON to OWL/TTL")
    parser.add_argument("--input", "-i", help="Directory with *_gold.json files")
    parser.add_argument("--output", "-o", default="./owl_gold", help="Output directory")
    parser.add_argument("--file", "-f", help="Single gold JSON file")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            gold = json.load(f)
        g = gold_to_owl(gold)
        stem = Path(args.file).stem.replace("_gold", "")
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        g.serialize(destination=str(out / f"{stem}_gold.owl"), format="xml")
        g.serialize(destination=str(out / f"{stem}_gold.ttl"), format="turtle")
        print(f"Converted: {stem} ({len(g)} triples)")
    elif args.input:
        convert_all(args.input, args.output)
    else:
        parser.print_help()
