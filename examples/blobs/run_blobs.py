"""Run the blobs evaluation through this repository's stdio MCP server.

The steps an assistant would take are scripted: open ImageJ's blobs sample,
threshold it with Otsu, measure the particles, and save before, mask, and
comparison images. Set FIJI_PATH to a local Fiji root. Outputs go to a new
folder given by --output, so an earlier run is never overwritten. Check the
result with check_blobs.py.
"""

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[2]
BLOBS_URL = "https://imagej.net/ij/images/blobs.gif"

THRESHOLD = """setAutoThreshold("Otsu");
setOption("BlackBackground", true);
run("Convert to Mask");"""

MEASURE = """#@output Integer count
import ij.WindowManager
import ij.measure.Measurements
import ij.measure.ResultsTable
import ij.plugin.filter.Analyzer
import ij.plugin.filter.ParticleAnalyzer

def image = WindowManager.getCurrentImage()
image.getProcessor().setThreshold(255, 255, 0)
def table = new ResultsTable()
Analyzer.setResultsTable(table)
def options = ParticleAnalyzer.CLEAR_WORKSHEET | ParticleAnalyzer.EXCLUDE_EDGE_PARTICLES
def measurements = Measurements.AREA | Measurements.CENTROID | Measurements.PERIMETER
def analyzer = new ParticleAnalyzer(options, measurements, table, 50, Double.POSITIVE_INFINITY)
if (!analyzer.analyze(image)) throw new IllegalStateException("Particle analysis failed")
count = table.size()
"""


async def main(output: Path) -> None:
    if not os.environ.get("FIJI_PATH"):
        raise SystemExit(
            "Set FIJI_PATH to the directory containing jars/ and plugins/."
        )
    output.mkdir(parents=True, exist_ok=False)
    blobs = output / "blobs.gif"
    urllib.request.urlretrieve(BLOBS_URL, blobs)
    env = dict(os.environ, FIJI_MODE="headless", PYTHONPATH=str(ROOT / "src"))
    transport = StdioTransport(
        command=sys.executable,
        # Current SciJava defaults to downloading Java even with a local Fiji.
        # Use the caller's installed Java; still launch the supported entrypoint.
        args=[
            "-c",
            (
                "import scyjava.config; "
                "scyjava.config.set_java_constraints(fetch='auto'); "
                "import runpy; runpy.run_module('fiji_mcp', run_name='__main__')"
            ),
        ],
        cwd=str(ROOT),
        env=env,
        log_file=output / "server.log",
        keep_alive=False,
    )
    records = []
    async with Client(transport, init_timeout=300, timeout=300) as client:

        async def call(name: str, arguments: dict):
            result = await client.call_tool(name, arguments)
            data = (
                result.structured_content
                if isinstance(result.structured_content, dict)
                else result.data
            )
            records.append({"tool": name, "arguments": arguments, "result": data})
            (output / "tool_calls.json").write_text(json.dumps(records, indent=2))
            print(name, "complete", flush=True)
            return data

        await call("open_image", {"path": str(blobs)})
        await call("get_state", {})
        await call(
            "screenshot",
            {"target": "active_image", "save_path": str(output / "before.png")},
        )
        await call("run_script", {"language": "ijm", "code": THRESHOLD})
        await call(
            "screenshot",
            {"target": "active_image", "save_path": str(output / "mask.png")},
        )
        await call("run_script", {"language": "groovy", "code": MEASURE})
        results = await call("get_results", {"offset": 0, "limit": 500})
        (output / "measurements.json").write_text(json.dumps(results, indent=2))
        await call(
            "screenshot",
            {"target": "results", "save_path": str(output / "results.png")},
        )
        await call(
            "compare_screenshots",
            {
                "before_path": str(output / "before.png"),
                "after_path": str(output / "mask.png"),
                "save_path": str(output / "comparison.png"),
            },
        )
        await call("save_image", {"path": str(output / "mask.tiff")})
        print(
            json.dumps(
                {"objects": results["total_rows"], "columns": results["columns"]}
            ),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.output.resolve()))
