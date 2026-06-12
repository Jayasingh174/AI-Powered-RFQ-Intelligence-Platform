import ezdxf
import subprocess
import os

# Path to ODA File Converter
ODA_PATH = r"C:\Jaya\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"

# -------------------------
# Step 1: DWG → DXF Conversion
# -------------------------
def convert_dwg_to_dxf(dwg_path: str, output_dir: str) -> str:
    """
    Convert DWG file to DXF using ODA File Converter.
    """
    if not os.path.exists(ODA_PATH):
        raise FileNotFoundError("ODA File Converter not found.")
    if not os.path.exists(dwg_path):
        raise FileNotFoundError("DWG file not found.")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    input_dir = os.path.dirname(dwg_path)
    base_name = os.path.splitext(os.path.basename(dwg_path))[0]
    dxf_path = os.path.join(output_dir, base_name + ".dxf")

    cmd = [
        ODA_PATH,
        input_dir,
        output_dir,
        "ACAD2018",  # Output DWG/DXF version
        "DXF",
        "0", "1", "*.DWG"
    ]

    print("Running ODA Converter:", cmd)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    if not os.path.exists(dxf_path):
        raise ValueError("DWG conversion failed - DXF not generated")

    return dxf_path


# -------------------------
# Step 2: Parse DXF Entities
# -------------------------
def parse_dxf(dxf_path: str):
    """
    Extract DXF entities as structured JSON.
    """
    try:
        doc = ezdxf.readfile(dxf_path)
    except IOError:
        return {"error": "Cannot read DXF file."}
    except ezdxf.DXFStructureError:
        return {"error": "Invalid DXF structure."}

    modelspace = doc.modelspace()
    entities = []
    blocks = []

    for entity in modelspace:
        info = {"type": entity.dxftype(), "layer": entity.dxf.layer}

        if entity.dxftype() == "LINE":
            info["start"] = tuple(entity.dxf.start)
            info["end"] = tuple(entity.dxf.end)

        elif entity.dxftype() == "CIRCLE":
            info["center"] = tuple(entity.dxf.center)
            info["radius"] = entity.dxf.radius

        elif entity.dxftype() == "ARC":
            info["center"] = tuple(entity.dxf.center)
            info["radius"] = entity.dxf.radius
            info["start_angle"] = entity.dxf.start_angle
            info["end_angle"] = entity.dxf.end_angle

        elif entity.dxftype() == "DIMENSION":
            info["text"] = entity.dxf.text if hasattr(entity.dxf, "text") else ""

        elif entity.dxftype() == "INSERT":
            info["block_name"] = entity.dxf.name
            info["insert_point"] = tuple(entity.dxf.insert)
            blocks.append(info)

        entities.append(info)

    return {
        "entities": entities,
        "blocks": blocks
    }


# -------------------------
# Step 3: Generate DWG Summary
# -------------------------
def summarize_dxf(parsed_data: dict) -> str:
    """
    Generate a human-readable summary for AI assistant.
    """
    if "error" in parsed_data:
        return parsed_data["error"]

    layers = set(e["layer"] for e in parsed_data["entities"])
    types = set(e["type"] for e in parsed_data["entities"])
    block_names = set(b["block_name"] for b in parsed_data.get("blocks", []))

    summary = f"DWG contains layers: {', '.join(layers)}; " \
              f"entity types: {', '.join(types)}."

    if block_names:
        summary += f" Blocks: {', '.join(block_names)}."

    return summary


# -------------------------
# Step 4: Full DWG Processing
# -------------------------
def extract_dwg(file_path: str, output_dir: str):
    """
    Full DWG pipeline: convert → parse → summarize
    """
    dxf_path = convert_dwg_to_dxf(file_path, output_dir)
    parsed_data = parse_dxf(dxf_path)
    summary = summarize_dxf(parsed_data)
    return {
        "parsed_entities": parsed_data,
        "summary": summary
    }