"""Shared preparation of a project config before running plantAnalysis."""


def set_plant(conf, plant):
    """Point conf at one plant: plant number, plantField and sequenceLabel.

    Mutates and returns conf. Needs Experiment and Images already set.
    """
    conf['plant'] = conf['plantField'] = str(plant)
    conf['sequenceLabel'] = conf['Experiment'] + "_" + conf['Images'] + "_" + conf['plant']
    return conf


def prepare_conf(conf):
    """Fill derived keys (fileKey, Experiment, sequenceLabel, Plant, pixel_size).

    Mutates and returns conf. Shared by 1_analysis.py and batch_setup.py.
    """
    try:
        conf['fileKey'] = conf["Experiment"]
    except Exception:
        conf['fileKey'] = conf["identifierField"]
        conf['Experiment'] = conf["identifierField"]

    set_plant(conf, conf['plant'])
    conf['Plant'] = 'Arabidopsis thaliana'

    if not conf.get('videoHasQRbutton', False) and not conf.get('videoHasArucoButton', False):
        conf['pixel_size'] = float(conf['knownDistance']) / float(conf['pixelDistance'])

    return conf
