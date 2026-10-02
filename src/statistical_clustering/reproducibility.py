"""Reproducibility metadata for statistical clustering."""

from dataclasses import asdict, dataclass
import platform

import numpy as np
import scipy
import sklearn


@dataclass(frozen=True)
class ClusteringEnvironment:
    python_version: str
    numpy_version: str
    scipy_version: str
    sklearn_version: str
    n_clusters: int
    random_state: int
    use_circular_hour: bool
    standardize_features: bool
    kmeans_n_init: str
    kmeans_init: str
    kmeans_algorithm: str


def get_clustering_environment(
    n_clusters: int = 2,
    random_state: int = 42,
) -> ClusteringEnvironment:
    """Record the environment and effective K-Means defaults."""

    model = sklearn.cluster.KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
    )

    return ClusteringEnvironment(
        python_version=platform.python_version(),
        numpy_version=np.__version__,
        scipy_version=scipy.__version__,
        sklearn_version=sklearn.__version__,
        n_clusters=n_clusters,
        random_state=random_state,
        use_circular_hour=True,
        standardize_features=True,
        kmeans_n_init=str(model.n_init),
        kmeans_init=str(model.init),
        kmeans_algorithm=str(model.algorithm),
    )


def environment_to_dict(
    environment: ClusteringEnvironment,
) -> dict:
    return asdict(environment)