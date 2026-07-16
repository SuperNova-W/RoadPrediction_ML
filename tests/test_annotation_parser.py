from pathlib import Path

from src.datasets.annotation_parser import parse_annotation


xml_path = Path(
    "data/raw/RDD2022/Norway/train/"
    "annotations/xmls/Norway_001011.xml"
)

annotation = parse_annotation(xml_path)

print(annotation.filename)
print(annotation.width, annotation.height)

for damage_object in annotation.objects:
    print(damage_object.label)
    print(damage_object.class_index)
    print(damage_object.bounding_box)