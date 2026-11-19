"""Check a blobs run independently of Fiji.

Counts 8-connected particles in the saved mask, keeps those of at least 50
pixels that do not touch the image edge (the settings the run passed to
Fiji's ParticleAnalyzer), and compares their areas with Fiji's Results table.
Needs only numpy and Pillow.
"""

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def particle_areas(mask: np.ndarray, min_area: int = 50) -> list[int]:
    seen = np.zeros(mask.shape, dtype=bool)
    rows, cols = mask.shape
    areas = []
    for start in zip(*np.nonzero(mask), strict=True):
        if seen[start]:
            continue
        seen[start] = True
        queue, area, edge = deque([start]), 0, False
        while queue:
            r, c = queue.popleft()
            area += 1
            edge |= r in (0, rows - 1) or c in (0, cols - 1)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if (
                        0 <= rr < rows
                        and 0 <= cc < cols
                        and mask[rr, cc]
                        and not seen[rr, cc]
                    ):
                        seen[rr, cc] = True
                        queue.append((rr, cc))
        if area >= min_area and not edge:
            areas.append(area)
    return sorted(areas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run", type=Path, help="Folder with mask.tiff and measurements.json"
    )
    run = parser.parse_args().run
    mask = np.asarray(Image.open(run / "mask.tiff")) > 0
    results = json.loads((run / "measurements.json").read_text())
    fiji = sorted(int(row[results["columns"].index("Area")]) for row in results["rows"])
    ours = particle_areas(mask)
    check = {
        "particles_fiji": len(fiji),
        "particles_independent": len(ours),
        "areas_match": fiji == ours,
        "area_range_px2": [ours[0], ours[-1]] if ours else None,
        "image_shape": list(mask.shape),
    }
    (run / "validation.json").write_text(json.dumps(check, indent=2) + "\n")
    print(json.dumps(check))
    if not check["areas_match"]:
        raise SystemExit("Particle areas differ from Fiji's Results.")


if __name__ == "__main__":
    main()
