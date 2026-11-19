"""Shared preparation of a project config before running plantAnalysis."""


def prepare_conf(conf):
    """Fill derived keys (fileKey, Experiment, sequenceLabel, Plant, pixel_size).

    Mutates and returns conf. Shared by 1_analysis.py and batch_setup.py.
    """
    try:
        conf['fileKey'] = conf["Experiment"]
    except Exception:
        conf['fileKey'] = conf["identifierField"]
        conf['Experiment'] = conf["identifierField"]

    conf['sequenceLabel'] = conf['Experiment'] + "_" + conf['Images'] + "_" + str(conf['plant'])
    conf['Plant'] = 'Arabidopsis thaliana'

    if not conf.get('videoHasQRbutton', False) and not conf.get('videoHasArucoButton', False):
        conf['pixel_size'] = float(conf['knownDistance']) / float(conf['pixelDistance'])

    return conf
