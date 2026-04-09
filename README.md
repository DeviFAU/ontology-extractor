# Ontology Extractor — Automatic OWL Extraction from Diagram Images

Thesis project by **Devi** | Supervisors: Simon & Jessica

This system takes an ontology diagram image (PNG) and automatically extracts a valid OWL ontology using a multi-pass GPT-4o pipeline. It produces an OWL/Turtle file, an intermediate extraction JSON, and evaluation metrics against a gold standard.

---

## Folder Structure

```
project/
│
├── diagrams/                   # Input diagram images (.png)
│   └── synth_01.png ... synth_15.png
│
├── gold_standards/             # Gold standard files for evaluation
│   ├── synth_01_gold.json      # Gold standard extraction JSON
│   ├── synth_01_gold.ttl       # Gold standard Turtle OWL file
│   └── ...
│
├── results/                    # Outputs from evaluate.py (JSON-level evaluation)
│   ├── synth_01_extraction.json
│   ├── synth_01_eval_report.json
│   └── ...
│
├── results_diagrams/           # Outputs from ontology_extractor_openai.py
│   ├── synth_01_ontology.owl
│   ├── synth_01.ttl
│   ├── synth_01_extraction.json
│   └── ...
│
├── ontology_extractor_openai.py    # Main pipeline — image → OWL
├── evaluate.py                     # JSON-level evaluator
├── owl_compare.py                  # OWL file-level evaluator
├── generate_gold_standards.py      # Script to generate synthetic gold standards
├── gold_to_[...].py                # Gold standard conversion utilities
├── run_all_examples.py             # Batch runner for all examples
│
├── evaluation_results_diagrams.xlsx  # Batch evaluation results (Excel)
├── owl_batch_comparison.xlsx         # Batch OWL comparison results (Excel)
│
└── README.md
```

---

## Scripts

### `ontology_extractor_openai.py` — Main Pipeline
Takes a diagram image and runs it through a 5-pass GPT-4o pipeline to extract an OWL ontology.

**Passes:**
| Pass | Name | What it does |
|------|------|-------------|
| Pass 0 | Arrow inventory | Classifies every arrowhead style before semantic extraction |
| Pass 1 | Full extraction | Extracts classes, properties, instances, edges, restrictions, data assertions |
| Pass 2 | Edge verification | Verifies and corrects edge directions with visual evidence |
| Pass 3 | Instance verification | Confirms or rejects each instance node |
| Pass 4 | Completeness sweep | Hunts for any missed nodes, edges, or data assertions |
| Merge | Merge & serialise | Combines all passes, auto-derives missing properties, serialises to OWL |

**Usage:**
```bash
python ontology_extractor_openai.py <image.png> [output.owl] [base_uri]

# Example
python ontology_extractor_openai.py diagrams/synth_01.png results_diagrams/synth_01_ontology.owl
```

**Outputs:**
- `*_ontology.owl` — RDF/XML OWL file
- `*.ttl` — Turtle serialisation
- `*_extraction.json` — Full intermediate extraction JSON (all pass outputs + final)

**Requirements:**
```bash
pip install openai rdflib
export OPENAI_API_KEY="your-key-here"
```

---

### `evaluate.py` — JSON-Level Evaluator
Compares an extraction JSON against a gold standard JSON. Computes precision, recall, F1, and Edge Direction Accuracy (EDA) for every element type.

**Metrics computed:**
- Precision, Recall, F1 per: classes, object properties, data properties, instances, edges, restriction axioms, data assertions
- Edge Direction Accuracy (EDA) — fraction of correctly directed edges
- Overall micro-averaged F1 (includes restriction axioms)

**Usage:**
```bash
# Single diagram
python evaluate.py --extraction results/synth_01_extraction.json \
                   --gold gold_standards/synth_01_gold.json

# With JSON output
python evaluate.py -e results/synth_01_extraction.json \
                   -g gold_standards/synth_01_gold.json \
                   -o results/synth_01_eval_report.json

# With Excel output
python evaluate.py -e results/synth_01_extraction.json \
                   -g gold_standards/synth_01_gold.json \
                   --output-excel results/synth_01_eval_report.xlsx

# Batch (whole folders)
python evaluate.py --batch-extraction results/ \
                   --batch-gold gold_standards/ \
                   --output results/batch_report.json
```

**Outputs:**
- Console report with per-element table
- `*_eval_report.json` — machine-readable results
- `*_eval_report.xlsx` — Excel with Summary, Edge Direction Accuracy, Mismatch Notes sheets

---

### `owl_compare.py` — OWL File Comparator
Compares two OWL files directly using rdflib. Parses classes, object/data properties, and restriction axioms from both files and computes F1 at the OWL level.

**Usage:**
```bash
python owl_compare.py <extracted.owl> <gold.owl> [output_dir]

# Example
python owl_compare.py results_diagrams/synth_01_ontology.owl \
                      gold_standards/synth_01_gold.ttl \
                      results/synth_01_owl_comparison/
```

**Outputs (in output_dir):**
- `comparison_report.json` — full comparison with per-element metrics
- `comparison_report.txt` — human-readable text report
- `differences.csv` — all FP/FN items with explanations
- `comparison_report.xlsx` — Excel with Summary, Mismatch Notes, per-element sheets

---

### `generate_gold_standards.py` — Gold Standard Generator
Generates synthetic ontology diagrams together with their gold standard JSON and OWL files. Used to create the 15 synthetic test cases.

**Usage:**
```bash
python generate_gold_standards.py
```

---

### `run_all_examples.py` — Batch Runner
Runs the full extraction pipeline on all images in the `diagrams/` folder and saves results to `results_diagrams/`.

**Usage:**
```bash
python run_all_examples.py
```

---

## Gold Standard Format

Each gold standard JSON follows this schema:

```json
{
  "id": "synth_01",
  "name": "Human-readable name",
  "complexity": "simple | medium | complex",
  "diagram_type": "OWL | PROV-O | mixed | informal",
  "classes":            [{ "name": "ClassName" }],
  "object_properties":  [{ "name": "propName", "domain": "...", "range": "..." }],
  "data_properties":    [{ "name": "propName", "domain": "...", "range": "xsd:string", "datatype": "string" }],
  "instances":          [{ "name": "instanceName", "type_class": "ClassName" }],
  "edges": [
    { "from": "A", "to": "B", "label": "propName", "edge_type": "objectProperty | subClassOf | instanceOf | dataProperty" }
  ],
  "restriction_axioms": [{ "subject": "Class", "property": "prop", "restriction_type": "some | min | max", "filler": "Class", "cardinality": null }],
  "data_assertions":    [{ "individual": "inst", "property": "prop", "value": "val", "datatype": "string" }]
}
```

---

## Evaluation Results (Synthetic — 5 of 15)

| Diagram | Type | Complexity | Overall F1 | EDA |
|---------|------|------------|-----------|-----|
| synth_08 | PROV-O | Medium | 94.1% | 100% |
| synth_10 | OWL | Medium | 95.8%* | 100% |
| synth_11 | Mixed | Complex | 81.4% | 80% |
| synth_13 | Informal | Complex | 89.7% | 100% |
| synth_15 | Mixed ABox | Complex | 76.8% | 100% |
| **Mean** | | | **87.6%** | **96.0%** |

*synth_10: 100% on all visible elements; 95.8% true overall due to 2 restriction axioms invisible in diagram (structural limitation).

**Known limitation:** OWL restriction axioms (owl:someValuesFrom, minCardinality etc.) are encoded as blank nodes in OWL files and are not visible in diagrams — these are always missed by visual extraction and are annotated as a structural limitation rather than an extraction failure.

---

## Requirements

```
openai
rdflib
openpyxl
```

Install:
```bash
pip install openai rdflib openpyxl
```

Set your OpenAI API key:
```bash
export OPENAI_API_KEY="sk-..."   # Linux/Mac
set OPENAI_API_KEY=sk-...        # Windows
```

---

## Next Steps

- [ ] Collect real ontology diagram images (from papers, documentation, hand-drawn)
- [ ] Manually create gold standard JSONs for real diagrams
- [ ] Run extraction pipeline on real diagrams
- [ ] Compare synthetic vs real performance
- [ ] Supervisor review of evaluation methodology and scope
