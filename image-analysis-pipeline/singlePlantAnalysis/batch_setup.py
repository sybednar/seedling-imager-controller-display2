"""Batch Analyze: confirm every plant's ROI and root origin on one plate
screen, then analyse each plant without further prompts.

Usage: python batch_setup.py --config <project_config.json>
"""
import argparse
import json
import os
import sys

from analysis.plantAnalysis import plantAnalysis
from analysis.utils.configPrep import prepare_conf
from analysis.utils.fileUtilities import getImages
from analysis.utils.getROIandSeed import getPlateROIsAndSeeds


def run_batch(conf, plants, analyse=plantAnalysis):
    """Analyse every plant with its own box and seed; return failed plant numbers.

    Each plant gets a fresh copy of conf so one plant's settings never leak
    into the next. A failure is recorded and the batch carries on.
    """
    failed = []
    for p in plants:
        plant_conf = dict(conf, plant=str(p['plant']))
        plant_conf['bounding box'] = p['bounding box']
        plant_conf['seed'] = p['seed']
        try:
            analyse(plant_conf, True)
        except Exception as e:
            print(f"Plant {p['plant']} failed: {e}", file=sys.stderr)
            failed.append(p['plant'])
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description='Batch analyse all plants on a plate')
    parser.add_argument('--config', type=str, required=True,
                        help='Path to the project configuration file')
    args = parser.parse_args(argv)

    with open(args.config) as f:
        conf = json.load(f)
    prepare_conf(conf)

    try:
        images, seg_files = getImages(conf)
        plants = getPlateROIsAndSeeds(conf, images, seg_files)
    except Exception as e:
        print(f"Batch setup failed before analysis: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if plants is None:
        print("Batch setup cancelled; nothing analysed.")
        return 0

    with open(os.path.join(conf['MainFolder'], 'batch_plants.json'), 'w') as f:
        json.dump(plants, f, indent=2)

    failed = run_batch(conf, plants, analyse=plantAnalysis)
    ok = len(plants) - len(failed)
    suffix = f" (plants {', '.join(str(n) for n in failed)})" if failed else ""
    print(f"Batch finished: {ok} succeeded, {len(failed)} failed{suffix}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
