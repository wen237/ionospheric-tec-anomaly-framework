import numpy as np
from validation.legacy.statistical_clustering.OneSampleTest_latest import OneSampleTest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def encode_hour_sin_cos(hours: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Encode hour (0-23) to circular sin-cos representation.
    """
    hour_rad = 2 * np.pi * hours / 24.0
    sin_hour = np.sin(hour_rad)
    cos_hour = np.cos(hour_rad)

    return sin_hour, cos_hour


def decode_hour_from_sin_cos(sin_hour: np.ndarray, cos_hour: np.ndarray) -> np.ndarray:
    """
    Decode hour from sin-cos, return integer hours in [0, 23].
    """
    hour = np.arctan2(sin_hour, cos_hour) * 24.0 / (2 * np.pi)
    hour = np.mod(hour, 24.0)

    return np.round(hour).astype(int)


def data_preprocessing(mask_arr:np.ndarray, obs_days:int) -> tuple[np.ndarray, np.ndarray]:
    """
    Process One Sample Test data into input dataset.

    Returns:
        resized_mask (np.ndarray): Remove post-earthquake data and flip it.
        X (np.ndarray): Form a dataset with hours, days, and polarity characteristics.
    """
    resized_mask = np.flipud(mask_arr[:obs_days+1])
    pos_rows, pos_cols = np.where(resized_mask == 1)
    neg_rows, neg_cols = np.where(resized_mask == -1)

    X = np.zeros((len(pos_rows)+len(neg_rows), 3), dtype=int)
    X[:, 0] = np.concatenate((pos_cols, neg_cols), axis=0)      # hour 0–23
    X[:, 1] = np.concatenate((-pos_rows, -neg_rows), axis=0)    # day -1,-2,...
    X[:len(pos_rows), 2], X[len(pos_rows):, 2] = 1, -1          # polarity ±1

    return resized_mask, X


class DataStandardization:
    def __init__(self) -> None:
        self.scaler = StandardScaler()

    def standardize(self, X:np.ndarray) -> np.ndarray:
        return self.scaler.fit_transform(X)
    
    def inversely_standardize(self, X_standardized:np.ndarray) -> np.ndarray:
        return self.scaler.inverse_transform(X_standardized)


class ApplyKmeans(DataStandardization):
    def __init__(self, input_data:np.ndarray, obs_days:int, t_format:int, num_clusters:int, random_state:int, standardize_X:bool, use_circular_hour:bool=True) -> None:
        super().__init__()
        self.X_raw = input_data
        self.X = None
        self.obs_days = obs_days
        self.t_format = t_format
        self.n_clusters = num_clusters
        self.random_seed = random_state
        self.standardization = standardize_X
        self.use_circular_hour = use_circular_hour

    def _prepare_features(self) -> None:
        """
        Transform X_raw into the feature space to be fed into k-means:
        if use_circular_hour=True → [sin_hour, cos_hour, day, polarity]
        else → [hour, day, polarity]
        """
        hours = self.X_raw[:, 0].astype(float)
        days = self.X_raw[:, 1].astype(float)
        polarity = self.X_raw[:, 2].astype(float)

        if self.use_circular_hour:
            sin_h, cos_h = encode_hour_sin_cos(hours)
            self.X = np.column_stack((sin_h, cos_h, days, polarity))
        else:
            self.X = self.X_raw.astype(float)

    def use_KMeans(self) -> tuple[np.ndarray, np.ndarray, float]:
        """
        Apply k-means clustering to the dataset and calculate silhouette coefficient.

        Returns:
            labels (np.ndarray): The cluster labels.
            centers (np.ndarray): The cluster centers in feature space.
            silh_score (float): silhouette coefficient.
        """
        self._prepare_features()

        if self.standardization:
            self.X = self.standardize(self.X)
        
        kmeans_model = KMeans(n_clusters=self.n_clusters, random_state=self.random_seed)
        labels = kmeans_model.fit_predict(self.X)
        centers = kmeans_model.cluster_centers_

        silh_score = silhouette_score(self.X, labels)

        return labels, centers, silh_score

    def operate(self) -> tuple[np.ndarray, np.ndarray]:
        labels, centers, silh_socre = self.use_KMeans()

        return labels, centers, silh_socre


def train(X:np.ndarray, ost_params_1:dict[str, object], kp_params:dict[str, object], sc_params:dict[str, object]) -> tuple[ApplyKmeans, tuple[np.ndarray, np.ndarray, float]]:
    if sc_params['silhouette coefficient']:
        all_results_ls, max_idx = [], []
        for i in sc_params['k_array']:
            kp_params['num_clusters'] = i
            ak = ApplyKmeans(X, ost_params_1['observation_days'], ost_params_1['time_resolution'], **kp_params)
            all_results_ls.append(ak.operate())
    else:
        results_ls = []
        ak = ApplyKmeans(X, ost_params_1['observation_days'], ost_params_1['time_resolution'], **kp_params)
        results_ls.append(ak.operate())
        results_tuple, = results_ls

    return ak, results_tuple


if __name__ == '__main__':
    print('----- Call it locally -----')
    ost_params_2: dict[str, object] = {
        'dataset_path': 'I:/IRSL/GIMTEC_interpolation_py', 
        'place_name': 'Afghanistan', 
        'location': [33.092, 69.514]
    }

    ost_params_1: dict[str, object] = {
        'start_time': [1999, 1, 1], 
        'end_time': [2021, 12, 31], 
        'min_magnitude': 6.0, 
        'observation_days': 30, 
        'reference_days': 15, 
        'time_resolution': 24, 
        'z_value': 1.96, 
        'k': 3
    }

    kp_params: dict[str, object] = {
        'num_clusters': 2, 
        'random_state': 42, 
        'standardize_X': True, 
        'use_circular_hour': True
    }

    sc_params: dict[str, object] = {
        'silhouette coefficient': False, 
        'k_array': np.arange(2, 26)
    }

    ost = OneSampleTest(**ost_params_1)
    clean_EQ, _, _, _, mask_arr = ost.operate(**ost_params_2)

    resized_mask, X = data_preprocessing(mask_arr, ost_params_1['observation_days'])

    ak, results_tuple = train(X, ost_params_1, kp_params, sc_params)

