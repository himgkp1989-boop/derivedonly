
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import xml.etree.ElementTree as ET
import tempfile
import os
from typing import Dict, List

app = FastAPI()

# --- Enable CORS for Angular frontend (localhost:4200) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # You can use ["*"] in dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Parse XML and build class map ---
def parse_class_map(root: ET.Element) -> Dict[str, ET.Element]:
    class_map = {}
    for class_elem in root.findall(".//class"):
        class_name = class_elem.attrib.get("name")
        if class_name:
            class_map[class_name] = class_elem
    return class_map

# --- Find the root class ---
def find_root_class(root: ET.Element) -> str:
    for class_elem in root.findall(".//class"):
        if class_elem.attrib.get("root") == "true":
            return class_elem.attrib.get("name")
    return None

# --- Recursive extraction of derived properties ---
def extract_all_derived_paths(class_name: str, class_map: Dict[str, ET.Element], prefix: str = "") -> List[str]:
    derived_paths = []
    class_elem = class_map.get(class_name)
    if class_elem is None:
        return []

    for prop in class_elem.findall("property"):
        # Case 1: Directly derived property
        if prop.attrib.get("derived") == "true":
            field_name = prop.attrib.get("name")
            if field_name:
                derived_paths.append(f"{prefix}{field_name}")

        # Case 2: Nested object property → recurse
        object_elem = prop.find("object")
        bind_elem = prop.find("bind")
        if object_elem is not None and bind_elem is not None:
            nested_class = object_elem.attrib.get("class")
            bind_name = bind_elem.attrib.get("name")
            if nested_class and bind_name:
                nested_prefix = f"{prefix}{bind_name}."
                derived_paths.extend(extract_all_derived_paths(nested_class, class_map, nested_prefix))

    return derived_paths

# --- FastAPI Endpoint ---
@app.post("/extract-derived-fields")  # <-- ✅ Updated to match Angular
async def extract_derived_properties_api(file: UploadFile = File(...)):
    try:
        # Save uploaded file to temp
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Parse XML
        tree = ET.parse(file_path)
        root = tree.getroot()

        class_map = parse_class_map(root)
        root_class_name = find_root_class(root)

        if not root_class_name:
            return JSONResponse({"error": "No root class found."}, status_code=400)

        result = extract_all_derived_paths(root_class_name, class_map, prefix=f"{root_class_name}.")

        # Clean up temp file
        os.remove(file_path)
        os.rmdir(temp_dir)

        return JSONResponse({
            "derived_fields": sorted(result),
            "count": len(result)
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
