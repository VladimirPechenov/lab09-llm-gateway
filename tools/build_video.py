"""110-second visual demonstration of saved, actually captured API responses."""

import json
from pathlib import Path

import imageio
import numpy as np
from build_artifacts import demo_frame

ROOT = Path(__file__).resolve().parents[1]


def main():
    demo = json.loads((ROOT / "results/demo.json").read_text(encoding="utf-8"))
    (ROOT / "videos").mkdir(exist_ok=True)
    with imageio.get_writer(
        str(ROOT / "videos/lab09_demo.mp4"), fps=2, codec="libx264", quality=8, macro_block_size=16
    ) as writer:
        for i, scene in enumerate(demo):
            for frame in range(20):
                writer.append_data(np.asarray(demo_frame(scene, i, (frame + 1) / 20)))
    (ROOT / "videos/chapters.json").write_text(
        json.dumps(
            [{"start_s": i * 10, "title": s["title"]} for i, s in enumerate(demo)], ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    demo_frame(demo[2], 2).save(ROOT / "docs/img/demo.png")
    demo_frame(demo[-1], 10).save(ROOT / "docs/img/demo-health.png")
    print("Video: 110 seconds, 11 scenarios, 1280x800, silent")


if __name__ == "__main__":
    main()
