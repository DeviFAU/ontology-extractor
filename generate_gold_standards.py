"""
generate_gold_standards.py
==========================
Generates 15 synthetic gold-standard ontologies as JSON + OWL/TTL + Graphviz diagrams.

  - 5 Simple  (3-5 classes)   : basic features
  - 5 Medium  (6-10 classes)  : mixed features
  - 5 Complex (11-15 classes) : advanced OWL features + instances

Each gold JSON follows a strict schema that serves as ground truth for evaluation.

Usage:
  python generate_gold_standards.py --output F:\evaluation\gold
  python generate_gold_standards.py --output F:\evaluation\gold --only 1 3 7

Requirements:
  pip install rdflib graphviz
"""

import json
import argparse
from pathlib import Path

# ─── Gold JSON Schema ────────────────────────────────────────────────────────
# Every gold file follows this exact structure.
# The evaluation scorer compares extraction JSON against this.

GOLD_SCHEMA = {
    "id": "str — unique diagram identifier",
    "name": "str — human-readable name",
    "complexity": "simple | medium | complex",
    "diagram_type": "OWL | ER | PROV-O | mind-map | informal | mixed",
    "description": "str — what this diagram tests",
    "base_uri": "str — base namespace URI",
    "namespace_prefixes": {"prefix": "uri"},
    "classes": [{"name": "str", "description": "str (optional)"}],
    "object_properties": [
        {"name": "str", "domain": "str (class)", "range": "str (class)"}
    ],
    "data_properties": [
        {"name": "str", "domain": "str (class)", "range": "str (xsd type)", "datatype": "str"}
    ],
    "instances": [
        {"name": "str", "type_class": "str"}
    ],
    "attribute_values": [
        {"value": "str", "property": "str", "domain_class": "str", "datatype": "str"}
    ],
    "edges": [
        {"from": "str", "to": "str", "label": "str",
         "edge_type": "subClassOf | objectProperty | dataProperty | instanceOf | "
                      "inverseOf | equivalentClass | disjointWith | domain | range"}
    ],
    "restriction_axioms": [
        {"subject": "str", "property": "str",
         "restriction_type": "some | only | min | max | exactly",
         "filler": "str", "cardinality": "int | null"}
    ],
    "data_assertions": [
        {"individual": "str", "property": "str", "value": "str", "datatype": "str"}
    ],
}


# ─── 15 Gold Standard Definitions ────────────────────────────────────────────

def gold_01_simple_hierarchy():
    """Simple subClassOf hierarchy: Animal → Dog, Cat, Bird"""
    return {
        "id": "synth_01", "name": "Animal Hierarchy",
        "complexity": "simple", "diagram_type": "OWL",
        "description": "Tests subClassOf extraction with 3 subclass relationships",
        "base_uri": "http://example.org/animals#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Animal"}, {"name": "Dog"}, {"name": "Cat"}, {"name": "Bird"}
        ],
        "object_properties": [],
        "data_properties": [],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Dog", "to": "Animal", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Cat", "to": "Animal", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Bird", "to": "Animal", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_02_simple_er():
    """Simple ER diagram: Person with data properties"""
    return {
        "id": "synth_02", "name": "Person Attributes",
        "complexity": "simple", "diagram_type": "ER",
        "description": "Tests data property extraction from ER-style attribute boxes",
        "base_uri": "http://example.org/person#",
        "namespace_prefixes": {},
        "classes": [{"name": "Person"}, {"name": "Address"}],
        "object_properties": [
            {"name": "livesAt", "domain": "Person", "range": "Address"}
        ],
        "data_properties": [
            {"name": "hasName", "domain": "Person", "range": "xsd:string", "datatype": "string"},
            {"name": "hasAge", "domain": "Person", "range": "xsd:integer", "datatype": "integer"},
            {"name": "hasEmail", "domain": "Person", "range": "xsd:string", "datatype": "string"},
        ],
        "instances": [],
        "attribute_values": [
            {"value": "John", "property": "hasName", "domain_class": "Person", "datatype": "string"},
            {"value": "30", "property": "hasAge", "domain_class": "Person", "datatype": "integer"},
        ],
        "edges": [
            {"from": "Person", "to": "Address", "label": "livesAt", "edge_type": "objectProperty"},
            {"from": "Person", "to": "xsd:string", "label": "hasName", "edge_type": "dataProperty"},
            {"from": "Person", "to": "xsd:integer", "label": "hasAge", "edge_type": "dataProperty"},
            {"from": "Person", "to": "xsd:string", "label": "hasEmail", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_03_domain_range():
    """OWL diagram with explicit domain/range arrows"""
    return {
        "id": "synth_03", "name": "Domain Range OWL",
        "complexity": "simple", "diagram_type": "OWL",
        "description": "Tests domain/range edge type extraction",
        "base_uri": "http://example.org/domrange#",
        "namespace_prefixes": {},
        "classes": [{"name": "Author"}, {"name": "Book"}, {"name": "Publisher"}],
        "object_properties": [
            {"name": "writes", "domain": "Author", "range": "Book"},
            {"name": "publishes", "domain": "Publisher", "range": "Book"},
        ],
        "data_properties": [],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "writes", "to": "Author", "label": "rdfs:domain", "edge_type": "domain"},
            {"from": "writes", "to": "Book", "label": "rdfs:range", "edge_type": "range"},
            {"from": "publishes", "to": "Publisher", "label": "rdfs:domain", "edge_type": "domain"},
            {"from": "publishes", "to": "Book", "label": "rdfs:range", "edge_type": "range"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_04_simple_instances():
    """Classes with named individuals and rdf:type edges"""
    return {
        "id": "synth_04", "name": "Class Instances",
        "complexity": "simple", "diagram_type": "OWL",
        "description": "Tests instance extraction with rdf:type arrows",
        "base_uri": "http://example.org/instances#",
        "namespace_prefixes": {},
        "classes": [{"name": "City"}, {"name": "Country"}],
        "object_properties": [
            {"name": "locatedIn", "domain": "City", "range": "Country"}
        ],
        "data_properties": [],
        "instances": [
            {"name": "berlin", "type_class": "City"},
            {"name": "munich", "type_class": "City"},
            {"name": "germany", "type_class": "Country"},
        ],
        "attribute_values": [],
        "edges": [
            {"from": "berlin", "to": "City", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "munich", "to": "City", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "germany", "to": "Country", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "berlin", "to": "germany", "label": "locatedIn", "edge_type": "objectProperty"},
            {"from": "munich", "to": "germany", "label": "locatedIn", "edge_type": "objectProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_05_inverse_of():
    """Two properties that are owl:inverseOf each other"""
    return {
        "id": "synth_05", "name": "InverseOf Properties",
        "complexity": "simple", "diagram_type": "OWL",
        "description": "Tests owl:inverseOf extraction and type declarations",
        "base_uri": "http://example.org/inverse#",
        "namespace_prefixes": {},
        "classes": [{"name": "Parent"}, {"name": "Child"}],
        "object_properties": [
            {"name": "hasChild", "domain": "Parent", "range": "Child"},
            {"name": "hasParent", "domain": "Child", "range": "Parent"},
        ],
        "data_properties": [],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "hasChild", "to": "hasParent", "label": "owl:inverseOf", "edge_type": "inverseOf"},
            {"from": "hasChild", "to": "Parent", "label": "rdfs:domain", "edge_type": "domain"},
            {"from": "hasChild", "to": "Child", "label": "rdfs:range", "edge_type": "range"},
            {"from": "hasParent", "to": "Child", "label": "rdfs:domain", "edge_type": "domain"},
            {"from": "hasParent", "to": "Parent", "label": "rdfs:range", "edge_type": "range"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_06_university():
    """Medium complexity: University ontology"""
    return {
        "id": "synth_06", "name": "University Ontology",
        "complexity": "medium", "diagram_type": "OWL",
        "description": "Tests mixed subClassOf + objectProperty + dataProperty",
        "base_uri": "http://example.org/university#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Person"}, {"name": "Student"}, {"name": "Professor"},
            {"name": "Course"}, {"name": "Department"}, {"name": "University"},
        ],
        "object_properties": [
            {"name": "enrolledIn", "domain": "Student", "range": "Course"},
            {"name": "teaches", "domain": "Professor", "range": "Course"},
            {"name": "belongsTo", "domain": "Course", "range": "Department"},
            {"name": "partOf", "domain": "Department", "range": "University"},
        ],
        "data_properties": [
            {"name": "hasName", "domain": "Person", "range": "xsd:string", "datatype": "string"},
            {"name": "hasID", "domain": "Student", "range": "xsd:integer", "datatype": "integer"},
            {"name": "courseCode", "domain": "Course", "range": "xsd:string", "datatype": "string"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Student", "to": "Person", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Professor", "to": "Person", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Student", "to": "Course", "label": "enrolledIn", "edge_type": "objectProperty"},
            {"from": "Professor", "to": "Course", "label": "teaches", "edge_type": "objectProperty"},
            {"from": "Course", "to": "Department", "label": "belongsTo", "edge_type": "objectProperty"},
            {"from": "Department", "to": "University", "label": "partOf", "edge_type": "objectProperty"},
            {"from": "Person", "to": "xsd:string", "label": "hasName", "edge_type": "dataProperty"},
            {"from": "Student", "to": "xsd:integer", "label": "hasID", "edge_type": "dataProperty"},
            {"from": "Course", "to": "xsd:string", "label": "courseCode", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_07_ecommerce():
    """Medium: E-commerce with varied relationships"""
    return {
        "id": "synth_07", "name": "E-Commerce Ontology",
        "complexity": "medium", "diagram_type": "informal",
        "description": "Tests extraction from business domain with many objectProperties",
        "base_uri": "http://example.org/ecommerce#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Customer"}, {"name": "Order"}, {"name": "Product"},
            {"name": "Category"}, {"name": "Payment"}, {"name": "ShippingAddress"},
        ],
        "object_properties": [
            {"name": "places", "domain": "Customer", "range": "Order"},
            {"name": "contains", "domain": "Order", "range": "Product"},
            {"name": "belongsTo", "domain": "Product", "range": "Category"},
            {"name": "paidBy", "domain": "Order", "range": "Payment"},
            {"name": "shippedTo", "domain": "Order", "range": "ShippingAddress"},
            {"name": "hasAddress", "domain": "Customer", "range": "ShippingAddress"},
        ],
        "data_properties": [
            {"name": "orderDate", "domain": "Order", "range": "xsd:date", "datatype": "date"},
            {"name": "totalPrice", "domain": "Order", "range": "xsd:double", "datatype": "double"},
            {"name": "productName", "domain": "Product", "range": "xsd:string", "datatype": "string"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Customer", "to": "Order", "label": "places", "edge_type": "objectProperty"},
            {"from": "Order", "to": "Product", "label": "contains", "edge_type": "objectProperty"},
            {"from": "Product", "to": "Category", "label": "belongsTo", "edge_type": "objectProperty"},
            {"from": "Order", "to": "Payment", "label": "paidBy", "edge_type": "objectProperty"},
            {"from": "Order", "to": "ShippingAddress", "label": "shippedTo", "edge_type": "objectProperty"},
            {"from": "Customer", "to": "ShippingAddress", "label": "hasAddress", "edge_type": "objectProperty"},
            {"from": "Order", "to": "xsd:date", "label": "orderDate", "edge_type": "dataProperty"},
            {"from": "Order", "to": "xsd:double", "label": "totalPrice", "edge_type": "dataProperty"},
            {"from": "Product", "to": "xsd:string", "label": "productName", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_08_provenance():
    """Medium: PROV-O style with self-loops"""
    return {
        "id": "synth_08", "name": "Provenance Model",
        "complexity": "medium", "diagram_type": "PROV-O",
        "description": "Tests self-loops, data properties to xsd:dateTime, and PROV-O vocabulary",
        "base_uri": "http://example.org/prov#",
        "namespace_prefixes": {"prov": "http://www.w3.org/ns/prov#"},
        "classes": [
            {"name": "prov:Entity"}, {"name": "prov:Activity"},
            {"name": "prov:Agent"}, {"name": "prov:Plan"},
        ],
        "object_properties": [
            {"name": "prov:wasGeneratedBy", "domain": "prov:Entity", "range": "prov:Activity"},
            {"name": "prov:used", "domain": "prov:Activity", "range": "prov:Entity"},
            {"name": "prov:wasAssociatedWith", "domain": "prov:Activity", "range": "prov:Agent"},
            {"name": "prov:wasDerivedFrom", "domain": "prov:Entity", "range": "prov:Entity"},
            {"name": "prov:hadPlan", "domain": "prov:Agent", "range": "prov:Plan"},
        ],
        "data_properties": [
            {"name": "prov:startedAtTime", "domain": "prov:Activity", "range": "xsd:dateTime", "datatype": "dateTime"},
            {"name": "prov:endedAtTime", "domain": "prov:Activity", "range": "xsd:dateTime", "datatype": "dateTime"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "prov:Entity", "to": "prov:Activity", "label": "prov:wasGeneratedBy", "edge_type": "objectProperty"},
            {"from": "prov:Activity", "to": "prov:Entity", "label": "prov:used", "edge_type": "objectProperty"},
            {"from": "prov:Activity", "to": "prov:Agent", "label": "prov:wasAssociatedWith", "edge_type": "objectProperty"},
            {"from": "prov:Entity", "to": "prov:Entity", "label": "prov:wasDerivedFrom", "edge_type": "objectProperty"},
            {"from": "prov:Agent", "to": "prov:Plan", "label": "prov:hadPlan", "edge_type": "objectProperty"},
            {"from": "prov:Activity", "to": "xsd:dateTime", "label": "prov:startedAtTime", "edge_type": "dataProperty"},
            {"from": "prov:Activity", "to": "xsd:dateTime", "label": "prov:endedAtTime", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_09_library():
    """Medium: Library with inverseOf"""
    return {
        "id": "synth_09", "name": "Library System",
        "complexity": "medium", "diagram_type": "OWL",
        "description": "Tests inverseOf, multiple subClassOf, and data properties together",
        "base_uri": "http://example.org/library#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Work"}, {"name": "Book"}, {"name": "Article"},
            {"name": "Person"}, {"name": "Author"}, {"name": "Genre"},
            {"name": "Library"},
        ],
        "object_properties": [
            {"name": "writtenBy", "domain": "Work", "range": "Author"},
            {"name": "authored", "domain": "Author", "range": "Work"},
            {"name": "hasGenre", "domain": "Work", "range": "Genre"},
            {"name": "heldBy", "domain": "Work", "range": "Library"},
        ],
        "data_properties": [
            {"name": "title", "domain": "Work", "range": "xsd:string", "datatype": "string"},
            {"name": "isbn", "domain": "Book", "range": "xsd:string", "datatype": "string"},
            {"name": "yearPublished", "domain": "Work", "range": "xsd:integer", "datatype": "integer"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Book", "to": "Work", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Article", "to": "Work", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Author", "to": "Person", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "writtenBy", "to": "authored", "label": "owl:inverseOf", "edge_type": "inverseOf"},
            {"from": "Work", "to": "Author", "label": "writtenBy", "edge_type": "objectProperty"},
            {"from": "Work", "to": "Genre", "label": "hasGenre", "edge_type": "objectProperty"},
            {"from": "Work", "to": "Library", "label": "heldBy", "edge_type": "objectProperty"},
            {"from": "Work", "to": "xsd:string", "label": "title", "edge_type": "dataProperty"},
            {"from": "Book", "to": "xsd:string", "label": "isbn", "edge_type": "dataProperty"},
            {"from": "Work", "to": "xsd:integer", "label": "yearPublished", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_10_healthcare():
    """Medium: Healthcare with restrictions"""
    return {
        "id": "synth_10", "name": "Healthcare Ontology",
        "complexity": "medium", "diagram_type": "OWL",
        "description": "Tests OWL restriction axioms (some, only, min)",
        "base_uri": "http://example.org/health#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Patient"}, {"name": "Doctor"}, {"name": "Hospital"},
            {"name": "Diagnosis"}, {"name": "Treatment"}, {"name": "Medication"},
            {"name": "Allergy"},
        ],
        "object_properties": [
            {"name": "treatedBy", "domain": "Patient", "range": "Doctor"},
            {"name": "hasDiagnosis", "domain": "Patient", "range": "Diagnosis"},
            {"name": "hasTreatment", "domain": "Diagnosis", "range": "Treatment"},
            {"name": "prescribes", "domain": "Treatment", "range": "Medication"},
            {"name": "worksAt", "domain": "Doctor", "range": "Hospital"},
            {"name": "hasAllergy", "domain": "Patient", "range": "Allergy"},
        ],
        "data_properties": [
            {"name": "patientID", "domain": "Patient", "range": "xsd:string", "datatype": "string"},
            {"name": "dateOfBirth", "domain": "Patient", "range": "xsd:date", "datatype": "date"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Patient", "to": "Doctor", "label": "treatedBy", "edge_type": "objectProperty"},
            {"from": "Patient", "to": "Diagnosis", "label": "hasDiagnosis", "edge_type": "objectProperty"},
            {"from": "Diagnosis", "to": "Treatment", "label": "hasTreatment", "edge_type": "objectProperty"},
            {"from": "Treatment", "to": "Medication", "label": "prescribes", "edge_type": "objectProperty"},
            {"from": "Doctor", "to": "Hospital", "label": "worksAt", "edge_type": "objectProperty"},
            {"from": "Patient", "to": "Allergy", "label": "hasAllergy", "edge_type": "objectProperty"},
            {"from": "Patient", "to": "xsd:string", "label": "patientID", "edge_type": "dataProperty"},
            {"from": "Patient", "to": "xsd:date", "label": "dateOfBirth", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [
            {"subject": "Patient", "property": "treatedBy", "restriction_type": "some", "filler": "Doctor", "cardinality": None},
            {"subject": "Patient", "property": "hasDiagnosis", "restriction_type": "min", "filler": "Diagnosis", "cardinality": 1},
        ],
        "data_assertions": [],
    }


def gold_11_building_iot():
    """Complex: Building IoT with two layers (schema + instances)"""
    return {
        "id": "synth_11", "name": "Building IoT",
        "complexity": "complex", "diagram_type": "mixed",
        "description": "Tests two-layer extraction: schema classes + named instances",
        "base_uri": "http://example.org/building#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Building"}, {"name": "Floor"}, {"name": "Room"},
            {"name": "Sensor"}, {"name": "TemperatureSensor"}, {"name": "HumiditySensor"},
            {"name": "Actuator"}, {"name": "HVACUnit"}, {"name": "LightController"},
            {"name": "Zone"}, {"name": "OccupancyZone"},
        ],
        "object_properties": [
            {"name": "hasFloor", "domain": "Building", "range": "Floor"},
            {"name": "hasRoom", "domain": "Floor", "range": "Room"},
            {"name": "containsSensor", "domain": "Room", "range": "Sensor"},
            {"name": "controlledBy", "domain": "Room", "range": "Actuator"},
            {"name": "feedsDataTo", "domain": "Sensor", "range": "Actuator"},
            {"name": "inZone", "domain": "Room", "range": "Zone"},
        ],
        "data_properties": [
            {"name": "roomNumber", "domain": "Room", "range": "xsd:string", "datatype": "string"},
            {"name": "sensorValue", "domain": "Sensor", "range": "xsd:double", "datatype": "double"},
        ],
        "instances": [
            {"name": "buildingA", "type_class": "Building"},
            {"name": "floor1", "type_class": "Floor"},
            {"name": "room101", "type_class": "Room"},
            {"name": "tempSensor1", "type_class": "TemperatureSensor"},
            {"name": "hvac1", "type_class": "HVACUnit"},
        ],
        "attribute_values": [],
        "edges": [
            {"from": "TemperatureSensor", "to": "Sensor", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "HumiditySensor", "to": "Sensor", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "HVACUnit", "to": "Actuator", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "LightController", "to": "Actuator", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "OccupancyZone", "to": "Zone", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Building", "to": "Floor", "label": "hasFloor", "edge_type": "objectProperty"},
            {"from": "Floor", "to": "Room", "label": "hasRoom", "edge_type": "objectProperty"},
            {"from": "Room", "to": "Sensor", "label": "containsSensor", "edge_type": "objectProperty"},
            {"from": "Room", "to": "Actuator", "label": "controlledBy", "edge_type": "objectProperty"},
            {"from": "Sensor", "to": "Actuator", "label": "feedsDataTo", "edge_type": "objectProperty"},
            {"from": "Room", "to": "Zone", "label": "inZone", "edge_type": "objectProperty"},
            {"from": "Room", "to": "xsd:string", "label": "roomNumber", "edge_type": "dataProperty"},
            {"from": "Sensor", "to": "xsd:double", "label": "sensorValue", "edge_type": "dataProperty"},
            {"from": "buildingA", "to": "Building", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "floor1", "to": "Floor", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "room101", "to": "Room", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "tempSensor1", "to": "TemperatureSensor", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "hvac1", "to": "HVACUnit", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "buildingA", "to": "floor1", "label": "hasFloor", "edge_type": "objectProperty"},
            {"from": "floor1", "to": "room101", "label": "hasRoom", "edge_type": "objectProperty"},
            {"from": "room101", "to": "tempSensor1", "label": "containsSensor", "edge_type": "objectProperty"},
            {"from": "room101", "to": "hvac1", "label": "controlledBy", "edge_type": "objectProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [
            {"individual": "room101", "property": "roomNumber", "value": "101", "datatype": "string"},
        ],
    }


def gold_12_full_owl():
    """Complex: Full OWL features — restrictions, equivalentClass, disjointWith"""
    return {
        "id": "synth_12", "name": "Full OWL Features",
        "complexity": "complex", "diagram_type": "OWL",
        "description": "Tests complex OWL axioms: restrictions, equivalentClass, disjointWith",
        "base_uri": "http://example.org/fullowl#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Vehicle"}, {"name": "Car"}, {"name": "Truck"}, {"name": "Bicycle"},
            {"name": "ElectricVehicle"}, {"name": "Engine"}, {"name": "Battery"},
            {"name": "Wheel"}, {"name": "Manufacturer"}, {"name": "Driver"},
            {"name": "License"}, {"name": "Road"},
        ],
        "object_properties": [
            {"name": "hasEngine", "domain": "Vehicle", "range": "Engine"},
            {"name": "hasBattery", "domain": "ElectricVehicle", "range": "Battery"},
            {"name": "hasWheel", "domain": "Vehicle", "range": "Wheel"},
            {"name": "madeBy", "domain": "Vehicle", "range": "Manufacturer"},
            {"name": "drivenBy", "domain": "Vehicle", "range": "Driver"},
            {"name": "hasLicense", "domain": "Driver", "range": "License"},
            {"name": "drivesOn", "domain": "Vehicle", "range": "Road"},
        ],
        "data_properties": [
            {"name": "maxSpeed", "domain": "Vehicle", "range": "xsd:integer", "datatype": "integer"},
            {"name": "weight", "domain": "Vehicle", "range": "xsd:double", "datatype": "double"},
            {"name": "modelYear", "domain": "Vehicle", "range": "xsd:integer", "datatype": "integer"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Car", "to": "Vehicle", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Truck", "to": "Vehicle", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Bicycle", "to": "Vehicle", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "ElectricVehicle", "to": "Vehicle", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Car", "to": "Truck", "label": "owl:disjointWith", "edge_type": "disjointWith"},
            {"from": "Vehicle", "to": "Engine", "label": "hasEngine", "edge_type": "objectProperty"},
            {"from": "ElectricVehicle", "to": "Battery", "label": "hasBattery", "edge_type": "objectProperty"},
            {"from": "Vehicle", "to": "Wheel", "label": "hasWheel", "edge_type": "objectProperty"},
            {"from": "Vehicle", "to": "Manufacturer", "label": "madeBy", "edge_type": "objectProperty"},
            {"from": "Vehicle", "to": "Driver", "label": "drivenBy", "edge_type": "objectProperty"},
            {"from": "Driver", "to": "License", "label": "hasLicense", "edge_type": "objectProperty"},
            {"from": "Vehicle", "to": "Road", "label": "drivesOn", "edge_type": "objectProperty"},
            {"from": "Vehicle", "to": "xsd:integer", "label": "maxSpeed", "edge_type": "dataProperty"},
            {"from": "Vehicle", "to": "xsd:double", "label": "weight", "edge_type": "dataProperty"},
            {"from": "Vehicle", "to": "xsd:integer", "label": "modelYear", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [
            {"subject": "Car", "property": "hasWheel", "restriction_type": "exactly", "filler": "Wheel", "cardinality": 4},
            {"subject": "Bicycle", "property": "hasWheel", "restriction_type": "exactly", "filler": "Wheel", "cardinality": 2},
            {"subject": "ElectricVehicle", "property": "hasBattery", "restriction_type": "some", "filler": "Battery", "cardinality": None},
        ],
        "data_assertions": [],
    }


def gold_13_organization():
    """Complex: Large organizational ontology"""
    return {
        "id": "synth_13", "name": "Organization Structure",
        "complexity": "complex", "diagram_type": "informal",
        "description": "Tests large class count with deep hierarchy and cross-relationships",
        "base_uri": "http://example.org/org#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Organization"}, {"name": "Company"}, {"name": "Startup"},
            {"name": "Department"}, {"name": "Employee"}, {"name": "Manager"},
            {"name": "Engineer"}, {"name": "Project"}, {"name": "Skill"},
            {"name": "Technology"}, {"name": "Office"}, {"name": "Meeting"},
        ],
        "object_properties": [
            {"name": "hasDepartment", "domain": "Company", "range": "Department"},
            {"name": "employs", "domain": "Department", "range": "Employee"},
            {"name": "manages", "domain": "Manager", "range": "Department"},
            {"name": "worksOn", "domain": "Employee", "range": "Project"},
            {"name": "hasSkill", "domain": "Employee", "range": "Skill"},
            {"name": "uses", "domain": "Project", "range": "Technology"},
            {"name": "locatedAt", "domain": "Department", "range": "Office"},
            {"name": "attends", "domain": "Employee", "range": "Meeting"},
        ],
        "data_properties": [
            {"name": "employeeID", "domain": "Employee", "range": "xsd:string", "datatype": "string"},
            {"name": "salary", "domain": "Employee", "range": "xsd:double", "datatype": "double"},
            {"name": "projectName", "domain": "Project", "range": "xsd:string", "datatype": "string"},
            {"name": "startDate", "domain": "Project", "range": "xsd:date", "datatype": "date"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Company", "to": "Organization", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Startup", "to": "Company", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Manager", "to": "Employee", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Engineer", "to": "Employee", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Company", "to": "Department", "label": "hasDepartment", "edge_type": "objectProperty"},
            {"from": "Department", "to": "Employee", "label": "employs", "edge_type": "objectProperty"},
            {"from": "Manager", "to": "Department", "label": "manages", "edge_type": "objectProperty"},
            {"from": "Employee", "to": "Project", "label": "worksOn", "edge_type": "objectProperty"},
            {"from": "Employee", "to": "Skill", "label": "hasSkill", "edge_type": "objectProperty"},
            {"from": "Project", "to": "Technology", "label": "uses", "edge_type": "objectProperty"},
            {"from": "Department", "to": "Office", "label": "locatedAt", "edge_type": "objectProperty"},
            {"from": "Employee", "to": "Meeting", "label": "attends", "edge_type": "objectProperty"},
            {"from": "Employee", "to": "xsd:string", "label": "employeeID", "edge_type": "dataProperty"},
            {"from": "Employee", "to": "xsd:double", "label": "salary", "edge_type": "dataProperty"},
            {"from": "Project", "to": "xsd:string", "label": "projectName", "edge_type": "dataProperty"},
            {"from": "Project", "to": "xsd:date", "label": "startDate", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_14_experiment_hub():
    """Complex: Hub-and-spoke experiment diagram"""
    return {
        "id": "synth_14", "name": "Experiment Hub",
        "complexity": "complex", "diagram_type": "informal",
        "description": "Tests hub-and-spoke layout with one central node and many radiating edges",
        "base_uri": "http://example.org/experiment#",
        "namespace_prefixes": {"prov": "http://www.w3.org/ns/prov#"},
        "classes": [
            {"name": "Experiment"}, {"name": "Researcher"}, {"name": "Dataset"},
            {"name": "Protocol"}, {"name": "Instrument"}, {"name": "Sample"},
            {"name": "Result"}, {"name": "Publication"}, {"name": "Lab"},
            {"name": "FundingSource"}, {"name": "Software"}, {"name": "Parameter"},
        ],
        "object_properties": [
            {"name": "conductedBy", "domain": "Experiment", "range": "Researcher"},
            {"name": "usesDataset", "domain": "Experiment", "range": "Dataset"},
            {"name": "followsProtocol", "domain": "Experiment", "range": "Protocol"},
            {"name": "usesInstrument", "domain": "Experiment", "range": "Instrument"},
            {"name": "analysesSample", "domain": "Experiment", "range": "Sample"},
            {"name": "producesResult", "domain": "Experiment", "range": "Result"},
            {"name": "publishedIn", "domain": "Result", "range": "Publication"},
            {"name": "performedAt", "domain": "Experiment", "range": "Lab"},
            {"name": "fundedBy", "domain": "Experiment", "range": "FundingSource"},
            {"name": "usesSoftware", "domain": "Experiment", "range": "Software"},
            {"name": "hasParameter", "domain": "Experiment", "range": "Parameter"},
        ],
        "data_properties": [
            {"name": "experimentDate", "domain": "Experiment", "range": "xsd:date", "datatype": "date"},
            {"name": "experimentName", "domain": "Experiment", "range": "xsd:string", "datatype": "string"},
        ],
        "instances": [],
        "attribute_values": [],
        "edges": [
            {"from": "Experiment", "to": "Researcher", "label": "conductedBy", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Dataset", "label": "usesDataset", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Protocol", "label": "followsProtocol", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Instrument", "label": "usesInstrument", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Sample", "label": "analysesSample", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Result", "label": "producesResult", "edge_type": "objectProperty"},
            {"from": "Result", "to": "Publication", "label": "publishedIn", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Lab", "label": "performedAt", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "FundingSource", "label": "fundedBy", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Software", "label": "usesSoftware", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "Parameter", "label": "hasParameter", "edge_type": "objectProperty"},
            {"from": "Experiment", "to": "xsd:date", "label": "experimentDate", "edge_type": "dataProperty"},
            {"from": "Experiment", "to": "xsd:string", "label": "experimentName", "edge_type": "dataProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [],
    }


def gold_15_instances_abox():
    """Complex: ABox with many instances and data assertions"""
    return {
        "id": "synth_15", "name": "Music Collection ABox",
        "complexity": "complex", "diagram_type": "mixed",
        "description": "Tests rich instance extraction with data assertions and cross-references",
        "base_uri": "http://example.org/music#",
        "namespace_prefixes": {},
        "classes": [
            {"name": "Artist"}, {"name": "Album"}, {"name": "Song"},
            {"name": "Genre"}, {"name": "RecordLabel"}, {"name": "Instrument"},
            {"name": "Band"}, {"name": "SoloArtist"},
            {"name": "Studio"}, {"name": "Producer"}, {"name": "Award"},
        ],
        "object_properties": [
            {"name": "performedBy", "domain": "Song", "range": "Artist"},
            {"name": "onAlbum", "domain": "Song", "range": "Album"},
            {"name": "hasGenre", "domain": "Album", "range": "Genre"},
            {"name": "releasedBy", "domain": "Album", "range": "RecordLabel"},
            {"name": "plays", "domain": "Artist", "range": "Instrument"},
            {"name": "producedBy", "domain": "Album", "range": "Producer"},
            {"name": "recordedAt", "domain": "Album", "range": "Studio"},
            {"name": "wonAward", "domain": "Album", "range": "Award"},
        ],
        "data_properties": [
            {"name": "songTitle", "domain": "Song", "range": "xsd:string", "datatype": "string"},
            {"name": "albumTitle", "domain": "Album", "range": "xsd:string", "datatype": "string"},
            {"name": "releaseYear", "domain": "Album", "range": "xsd:integer", "datatype": "integer"},
            {"name": "duration", "domain": "Song", "range": "xsd:double", "datatype": "double"},
        ],
        "instances": [
            {"name": "beatles", "type_class": "Band"},
            {"name": "abbeyRoad", "type_class": "Album"},
            {"name": "comeTogther", "type_class": "Song"},
            {"name": "rock", "type_class": "Genre"},
            {"name": "emiRecords", "type_class": "RecordLabel"},
        ],
        "attribute_values": [],
        "edges": [
            {"from": "Band", "to": "Artist", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "SoloArtist", "to": "Artist", "label": "rdfs:subClassOf", "edge_type": "subClassOf"},
            {"from": "Song", "to": "Artist", "label": "performedBy", "edge_type": "objectProperty"},
            {"from": "Song", "to": "Album", "label": "onAlbum", "edge_type": "objectProperty"},
            {"from": "Album", "to": "Genre", "label": "hasGenre", "edge_type": "objectProperty"},
            {"from": "Album", "to": "RecordLabel", "label": "releasedBy", "edge_type": "objectProperty"},
            {"from": "Artist", "to": "Instrument", "label": "plays", "edge_type": "objectProperty"},
            {"from": "Album", "to": "Producer", "label": "producedBy", "edge_type": "objectProperty"},
            {"from": "Album", "to": "Studio", "label": "recordedAt", "edge_type": "objectProperty"},
            {"from": "Album", "to": "Award", "label": "wonAward", "edge_type": "objectProperty"},
            {"from": "Song", "to": "xsd:string", "label": "songTitle", "edge_type": "dataProperty"},
            {"from": "Album", "to": "xsd:string", "label": "albumTitle", "edge_type": "dataProperty"},
            {"from": "Album", "to": "xsd:integer", "label": "releaseYear", "edge_type": "dataProperty"},
            {"from": "Song", "to": "xsd:double", "label": "duration", "edge_type": "dataProperty"},
            {"from": "beatles", "to": "Band", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "abbeyRoad", "to": "Album", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "comeTogther", "to": "Song", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "rock", "to": "Genre", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "emiRecords", "to": "RecordLabel", "label": "rdf:type", "edge_type": "instanceOf"},
            {"from": "comeTogther", "to": "beatles", "label": "performedBy", "edge_type": "objectProperty"},
            {"from": "comeTogther", "to": "abbeyRoad", "label": "onAlbum", "edge_type": "objectProperty"},
            {"from": "abbeyRoad", "to": "rock", "label": "hasGenre", "edge_type": "objectProperty"},
            {"from": "abbeyRoad", "to": "emiRecords", "label": "releasedBy", "edge_type": "objectProperty"},
        ],
        "restriction_axioms": [],
        "data_assertions": [
            {"individual": "abbeyRoad", "property": "albumTitle", "value": "Abbey Road", "datatype": "string"},
            {"individual": "abbeyRoad", "property": "releaseYear", "value": "1969", "datatype": "integer"},
            {"individual": "comeTogther", "property": "songTitle", "value": "Come Together", "datatype": "string"},
        ],
    }


# ─── Registry ────────────────────────────────────────────────────────────────

ALL_GOLDS = {
    1:  gold_01_simple_hierarchy,
    2:  gold_02_simple_er,
    3:  gold_03_domain_range,
    4:  gold_04_simple_instances,
    5:  gold_05_inverse_of,
    6:  gold_06_university,
    7:  gold_07_ecommerce,
    8:  gold_08_provenance,
    9:  gold_09_library,
    10: gold_10_healthcare,
    11: gold_11_building_iot,
    12: gold_12_full_owl,
    13: gold_13_organization,
    14: gold_14_experiment_hub,
    15: gold_15_instances_abox,
}


# ─── Output ──────────────────────────────────────────────────────────────────

def generate_all(output_dir: str, only: list = None):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ids = only if only else list(ALL_GOLDS.keys())
    for i in ids:
        gold = ALL_GOLDS[i]()
        name = gold["id"]
        gold_path = out / f"{name}_gold.json"
        with open(gold_path, "w", encoding="utf-8") as f:
            json.dump(gold, f, indent=2, ensure_ascii=False)
        print(f"  [{i:>2}] {gold['name']:<30} "
              f"cls={len(gold['classes'])}  edges={len(gold['edges'])}  "
              f"inst={len(gold['instances'])}  -> {gold_path.name}")

    print(f"\nGenerated {len(ids)} gold standard JSON files in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate gold standard ontologies")
    parser.add_argument("--output", "-o", default="./gold_standards",
                        help="Output directory")
    parser.add_argument("--only", nargs="*", type=int,
                        help="Generate only specific IDs (1-15)")
    args = parser.parse_args()
    generate_all(args.output, args.only)
