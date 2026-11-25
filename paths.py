"""Paths of the inputs and outputs, read from one JSON file (default: cfg/paths.json).

Every script takes --paths FILE to read another one. Relative paths are taken from the directory of
this repository, so the default file works when the repository sits inside TupleAnalysis
(../output is the output/ of TupleAnalysis). $VARIABLES and ~ are expanded.

    import paths
    P = paths.load()                      # or paths.load(opts.paths)
    P.dataset("data")                     # -> ("/abs/path/without/.root", "data2024")
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(REPO, "cfg", "paths.json")

SAMPLE_TYPES = ("data2017", "data2018", "data2024", "mc2017", "mc2018", "mc2024", "ttbar2024")
MC_STACK = ("wjets", "ttbar", "ttbar_semilep", "qcd")
N_OVERLAYS = 3


class PathsError(Exception):
    pass


def resolve(p):
    """Absolute path: $VARIABLES and ~ expanded, relative paths taken from the repository."""
    p = os.path.expanduser(os.path.expandvars(p))
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(REPO, p))


def _strip_root(p):
    return p[:-5] if p.endswith(".root") else p


class Paths(object):
    def __init__(self, doc, source):
        self.source = source

        def need(key, kind):
            if key not in doc:
                raise PathsError("{}: '{}' missing".format(source, key))
            if not isinstance(doc[key], kind):
                raise PathsError("{}: '{}' must be a {}".format(source, key, kind.__name__))
            return doc[key]

        self.output_dir = resolve(need("output_dir", str))

        self.datasets = {}
        for name, d in need("datasets", dict).items():
            if not isinstance(d, dict) or "file" not in d or "sampleType" not in d:
                raise PathsError("{}: datasets.{} needs 'file' and 'sampleType'".format(source, name))
            if d["sampleType"] not in SAMPLE_TYPES:
                raise PathsError("{}: datasets.{}: sampleType '{}' is not one of {}".format(
                    source, name, d["sampleType"], ", ".join(SAMPLE_TYPES)))
            # BkgPrediction.C takes the path without .root; accept both forms
            self.datasets[name] = (_strip_root(resolve(d["file"])), d["sampleType"])

        self.launch = need("launch", list)
        self.default_dataset = need("dataset", str)
        for n in self.launch + [self.default_dataset]:
            self._check_dataset(n)

        self.signal_dir = resolve(need("signal_dir", str))

        stack = need("mc_stack", dict)
        missing = [k for k in MC_STACK if k not in stack]
        if missing:
            raise PathsError("{}: mc_stack needs {}".format(source, ", ".join(MC_STACK)))
        self.mc_stack = {k: resolve(stack[k]) for k in MC_STACK}

        overlays = need("signal_overlays", list)
        if len(overlays) != N_OVERLAYS or not all(isinstance(o, dict) and "file" in o and "label" in o
                                                   for o in overlays):
            raise PathsError("{}: signal_overlays must hold {} entries {{\"file\", \"label\"}}".format(
                source, N_OVERLAYS))
        self.signal_overlays = [(resolve(o["file"]), o["label"]) for o in overlays]

    def _check_dataset(self, name):
        if name not in self.datasets:
            raise PathsError("{}: no dataset '{}' (datasets: {})".format(
                self.source, name, ", ".join(sorted(self.datasets))))

    def dataset(self, name=None):
        """(path without .root, sample type) of a dataset; the 'dataset' of the file by default."""
        name = name or self.default_dataset
        try:
            self._check_dataset(name)
        except PathsError as e:
            sys.exit("paths: {}".format(e))
        return self.datasets[name]

    def signal(self, mass, weighted=True):
        """The step 1 file of a gluino mass point."""
        return os.path.join(self.signal_dir, "Gluino_Run3_MET_madgraph_{}{}.root".format(
            mass, "_weighted" if weighted else ""))


def load(path=None):
    """Read the paths file; exits with a message if it cannot be used."""
    path = path or os.environ.get("BKGPRED_PATHS") or DEFAULT
    try:
        with open(path) as f:
            doc = json.load(f)
        return Paths(doc, path)
    except (OSError, IOError, ValueError, PathsError) as e:
        sys.exit("paths: {}".format(e))
