"""
gold_to_diagram.py
==================
Renders gold-standard JSON files as ontology diagram images using Graphviz.
Mimics common ontology diagram styles (OWL, ER, PROV-O).

Usage:
  python gold_to_diagram.py --input gold_standards/ --output diagrams/
  python gold_to_diagram.py --file gold_standards/synth_01_gold.json

Requirements:
  pip install graphviz
  (also needs `dot` command — install graphviz system package)
"""

import json
import argparse
import random
from pathlib import Path
import graphviz


# ─── Style Configuration ────────────────────────────────────────────────────

STYLES = {
    "OWL": {
        "class_shape": "ellipse", "class_color": "#F5F5F5", "class_border": "#333333",
        "instance_shape": "ellipse", "instance_style": "dashed", "instance_color": "#E8E8E8",
        "xsd_shape": "rectangle", "xsd_color": "#FFFFCC",
        "attr_shape": "rectangle", "attr_color": "#D5F5D5",
        "prop_shape": "rectangle", "prop_color": "#D5E8F0", "prop_border": "#4477AA",
        "subclass_style": "solid", "subclass_arrow": "empty",
        "objprop_style": "solid", "objprop_arrow": "normal",
        "dataprop_style": "dashed", "dataprop_arrow": "normal",
        "instance_edge_style": "dashed", "instance_arrow": "normal",
    },
    "ER": {
        "class_shape": "ellipse", "class_color": "#FDDCAA", "class_border": "#CC8833",
        "instance_shape": "ellipse", "instance_style": "dashed", "instance_color": "#E8E8E8",
        "xsd_shape": "rectangle", "xsd_color": "#FFFFCC",
        "attr_shape": "rectangle", "attr_color": "#C5E8C5", "attr_border": "#66AA66",
        "prop_shape": "diamond", "prop_color": "#F5F5F5", "prop_border": "#333333",
        "subclass_style": "solid", "subclass_arrow": "empty",
        "objprop_style": "solid", "objprop_arrow": "normal",
        "dataprop_style": "solid", "dataprop_arrow": "normal",
        "instance_edge_style": "dashed", "instance_arrow": "normal",
    },
    "PROV-O": {
        "class_shape": "ellipse", "class_color": "#FFFACD", "class_border": "#DAA520",
        "instance_shape": "ellipse", "instance_style": "dashed", "instance_color": "#E8E8E8",
        "xsd_shape": "rectangle", "xsd_color": "#FFFFCC",
        "attr_shape": "rectangle", "attr_color": "#D5F5D5",
        "prop_shape": "rectangle", "prop_color": "#D5E8F0",
        "subclass_style": "solid", "subclass_arrow": "empty",
        "objprop_style": "solid", "objprop_arrow": "vee",
        "dataprop_style": "dashed", "dataprop_arrow": "vee",
        "instance_edge_style": "dashed", "instance_arrow": "vee",
    },
}

DEFAULT_STYLE = STYLES["OWL"]


def get_style(diagram_type: str) -> dict:
    for key in STYLES:
        if key.lower() in diagram_type.lower():
            return STYLES[key]
    return DEFAULT_STYLE


# ─── Renderer ────────────────────────────────────────────────────────────────

def _gv_id(name: str) -> str:
    """Escape colons in node names for Graphviz (colons = port syntax)."""
    return name.replace(":", "__")


def render_diagram(gold: dict, output_path: str, fmt: str = "png") -> str:
    """Render a gold JSON as a Graphviz diagram image."""
    style = get_style(gold.get("diagram_type", "OWL"))

    dot = graphviz.Digraph(
        name=gold.get("id", "ontology"),
        format=fmt,
        engine="dot",
        graph_attr={
            "rankdir": "TB",
            "fontname": "Arial",
            "fontsize": "11",
            "bgcolor": "white",
            "pad": "0.5",
            "nodesep": "0.6",
            "ranksep": "0.8",
            "dpi": "150",
        },
        node_attr={"fontname": "Arial", "fontsize": "11"},
        edge_attr={"fontname": "Arial", "fontsize": "9"},
    )

    # Track which nodes are property nodes (for domain/range diagrams)
    class_names = {c["name"] for c in gold.get("classes", [])}
    instance_names = {i["name"] for i in gold.get("instances", [])}
    xsd_nodes = set()
    prop_nodes = set()
    attr_nodes = set()

    # Identify XSD and property nodes from edges
    for edge in gold.get("edges", []):
        if edge["to"].startswith("xsd:"):
            xsd_nodes.add(edge["to"])
        if edge["edge_type"] in ("domain", "range"):
            prop_nodes.add(edge["from"])

    for av in gold.get("attribute_values", []):
        attr_nodes.add(av["value"])

    # ── Add class nodes ──────────────────────────────────────────────────
    for cls in gold.get("classes", []):
        name = cls["name"]
        dot.node(_gv_id(name), label=name,
                 shape=style["class_shape"],
                 style="filled",
                 fillcolor=style["class_color"],
                 color=style.get("class_border", "#333333"),
                 penwidth="1.5")

    # ── Add instance nodes ───────────────────────────────────────────────
    for inst in gold.get("instances", []):
        name = inst["name"]
        dot.node(_gv_id(name), label=name,
                 shape=style.get("instance_shape", "ellipse"),
                 style=f"filled,{style.get('instance_style', 'dashed')}",
                 fillcolor=style.get("instance_color", "#E8E8E8"),
                 penwidth="1.0")

    # ── Add XSD type nodes ───────────────────────────────────────────────
    for xsd in xsd_nodes:
        dot.node(_gv_id(xsd), label=xsd,
                 shape=style["xsd_shape"],
                 style="filled",
                 fillcolor=style["xsd_color"],
                 fontsize="10")

    # ── Add property nodes (for domain/range diagrams) ───────────────────
    for prop in prop_nodes:
        if prop not in class_names and prop not in instance_names:
            dot.node(_gv_id(prop), label=prop,
                     shape=style.get("prop_shape", "rectangle"),
                     style="filled",
                     fillcolor=style.get("prop_color", "#D5E8F0"),
                     color=style.get("prop_border", "#4477AA"),
                     fontsize="10")

    # ── Add attribute value nodes ────────────────────────────────────────
    for av in gold.get("attribute_values", []):
        val = av["value"]
        if val not in class_names and val not in instance_names:
            dot.node(_gv_id(val), label=val,
                     shape=style.get("attr_shape", "rectangle"),
                     style="filled",
                     fillcolor=style.get("attr_color", "#D5F5D5"),
                     fontsize="10")

    # ── Add edges ────────────────────────────────────────────────────────
    for edge in gold.get("edges", []):
        src = edge["from"]
        tgt = edge["to"]
        label = edge.get("label", "")
        etype = edge.get("edge_type", "other")

        edge_attrs = {"label": f"  {label}  " if label else ""}

        if etype == "subClassOf":
            edge_attrs.update({
                "style": style["subclass_style"],
                "arrowhead": style["subclass_arrow"],
                "color": "#333333",
                "penwidth": "1.2",
            })
        elif etype == "instanceOf":
            edge_attrs.update({
                "style": style["instance_edge_style"],
                "arrowhead": style.get("instance_arrow", "normal"),
                "color": "#666666",
                "penwidth": "1.0",
            })
        elif etype == "dataProperty":
            edge_attrs.update({
                "style": style["dataprop_style"],
                "arrowhead": style["dataprop_arrow"],
                "color": "#555555",
                "penwidth": "1.0",
            })
        elif etype == "inverseOf":
            edge_attrs.update({
                "style": "solid",
                "dir": "both",
                "arrowhead": "normal",
                "arrowtail": "normal",
                "color": "#CC4444",
                "penwidth": "1.2",
            })
        elif etype == "equivalentClass":
            edge_attrs.update({
                "style": "solid",
                "dir": "both",
                "arrowhead": "empty",
                "arrowtail": "empty",
                "color": "#4444CC",
                "penwidth": "1.2",
            })
        elif etype == "disjointWith":
            edge_attrs.update({
                "style": "dashed",
                "arrowhead": "none",
                "color": "#CC4444",
                "penwidth": "1.2",
                "label": f"  {label or 'disjointWith'}  ",
            })
        elif etype in ("domain", "range"):
            edge_attrs.update({
                "style": "solid",
                "arrowhead": "normal",
                "color": "#4477AA",
                "penwidth": "1.0",
            })
        else:
            edge_attrs.update({
                "style": style["objprop_style"],
                "arrowhead": style["objprop_arrow"],
                "color": "#333333",
                "penwidth": "1.0",
            })

        dot.edge(_gv_id(src), _gv_id(tgt), **edge_attrs)

    # ── Render ───────────────────────────────────────────────────────────
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = str(out.with_suffix(""))
    dot.render(stem, cleanup=True)
    return f"{stem}.{fmt}"


# ─── Batch Renderer ──────────────────────────────────────────────────────────

def render_all(input_dir: str, output_dir: str, fmt: str = "png"):
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    gold_files = sorted(in_path.glob("*_gold.json"))
    if not gold_files:
        print(f"[!] No *_gold.json files found in {input_dir}")
        return

    print(f"\nRendering {len(gold_files)} diagrams...")
    for gf in gold_files:
        with open(gf) as f:
            gold = json.load(f)
        stem = gf.stem.replace("_gold", "")
        out_file = out_path / f"{stem}.{fmt}"
        result = render_diagram(gold, str(out_file), fmt)
        print(f"  {gold['id']:<20} {gold['name']:<30} -> {Path(result).name}")

    print(f"\nRendered {len(gold_files)} diagrams to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render gold JSON as diagram images")
    parser.add_argument("--input", "-i", help="Directory with *_gold.json files")
    parser.add_argument("--output", "-o", default="./diagrams", help="Output directory")
    parser.add_argument("--file", "-f", help="Single gold JSON file to render")
    parser.add_argument("--format", default="png", choices=["png", "svg", "pdf"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            gold = json.load(f)
        out = Path(args.output) / f"{gold['id']}.{args.format}"
        render_diagram(gold, str(out), args.format)
        print(f"Rendered: {out}")
    elif args.input:
        render_all(args.input, args.output, args.format)
    else:
        parser.print_help()
