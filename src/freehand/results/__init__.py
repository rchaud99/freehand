"""Where results go and in what format (docs/results_format.md): the run tree, manifests, the global index."""

from freehand.results.layout import condition, episode_dir, iter_episode_dirs, make_run_id, run_dir
from freehand.results.writer import EpisodeWriter, RunWriter, write_json_atomic

__all__ = [
    "EpisodeWriter",
    "RunWriter",
    "condition",
    "episode_dir",
    "iter_episode_dirs",
    "make_run_id",
    "run_dir",
    "write_json_atomic",
]
