import numpy as np

from src.statistical_clustering.clustering import (
    prepare_clustering_features,
)

from validation.legacy.statistical_clustering.OneSampleTest_latest import (
    OneSampleTest,
)

from validation.statistical_clustering.config import (
    GIMTEC_DATASET_DIR,
)

# --------------------------------------------------
# 1. Use the validated B5 Afghanistan mask
# --------------------------------------------------

ost_params_2: dict[str, object] = {
    "dataset_path": str(GIMTEC_DATASET_DIR),
    "place_name": "Afghanistan",
    "location": [33.092, 69.514],
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
ost = OneSampleTest(**ost_params_1)
clean_EQ, _, _, _, mask_arr = ost.operate(**ost_params_2)
full_mask = np.asarray(mask_arr)

assert full_mask.shape == (61, 24)

full_relative_days = np.arange(-30, 31)

# Paper clustering window: Day -30 through Day 0.
paper_window = full_relative_days <= 0

paper_mask = full_mask[paper_window, :]

relative_days = full_relative_days[paper_window]

assert paper_mask.shape == (31, 24)

assert np.array_equal(
    relative_days,
    np.arange(-30, 1),
)


# --------------------------------------------------
# 2. Modern feature preparation
# --------------------------------------------------

result = prepare_clustering_features(
    mask=paper_mask,
    relative_days=relative_days,
    use_circular_hour=True,
)

print("\n=== Modern clustering features ===")

print("Raw feature shape:", result.raw_features.shape)
print("Circular feature shape:", result.features.shape)

print(
    "Positive points:",
    np.count_nonzero(result.polarities == 1),
)

print(
    "Negative points:",
    np.count_nonzero(result.polarities == -1),
)

assert result.raw_features.shape == (34, 3)
assert result.features.shape == (34, 4)

assert np.count_nonzero(result.polarities == 1) == 18
assert np.count_nonzero(result.polarities == -1) == 16


# --------------------------------------------------
# 3. Legacy feature preparation
# --------------------------------------------------

from validation.legacy.statistical_clustering.OneSampleTest_and_KMeans_5 import (
    data_preprocessing,
    encode_hour_sin_cos,
)


legacy_resized_mask, legacy_X = (
    data_preprocessing(
        mask_arr=full_mask,
        obs_days=30,
    )
)

print("\n=== Legacy clustering features ===")

print("Legacy X shape:", legacy_X.shape)

assert legacy_X.shape == (34, 3)


# --------------------------------------------------
# 4. Exact comparison of raw features
# --------------------------------------------------

print("\n=== Raw feature equivalence ===")

print(
    "Raw features equal:",
    np.array_equal(
        legacy_X,
        result.raw_features,
    ),
)

np.testing.assert_array_equal(
    legacy_X,
    result.raw_features,
)

print("PASS: Raw features match legacy exactly.")


# --------------------------------------------------
# 5. Legacy circular-hour feature construction
# --------------------------------------------------

legacy_hours = legacy_X[:, 0].astype(float)
legacy_days = legacy_X[:, 1].astype(float)
legacy_polarities = legacy_X[:, 2].astype(float)

legacy_sin, legacy_cos = (
    encode_hour_sin_cos(legacy_hours)
)

legacy_features = np.column_stack(
    (
        legacy_sin,
        legacy_cos,
        legacy_days,
        legacy_polarities,
    )
)


# --------------------------------------------------
# 6. Four-dimensional feature equivalence
# --------------------------------------------------

print("\n=== Circular feature equivalence ===")

print(
    "Legacy shape:",
    legacy_features.shape,
)

print(
    "Modern shape:",
    result.features.shape,
)

assert legacy_features.shape == (34, 4)
assert result.features.shape == (34, 4)

np.testing.assert_array_equal(
    legacy_features,
    result.features,
)

print(
    "PASS: Circular features match legacy exactly."
)

from sklearn.preprocessing import StandardScaler

from src.statistical_clustering.feature_scaling import (
    standardize_clustering_features,
)


# --------------------------------------------------
# 7. Legacy standardization
# --------------------------------------------------

legacy_scaler = StandardScaler()

legacy_standardized = (
    legacy_scaler.fit_transform(
        legacy_features
    )
)


# --------------------------------------------------
# 8. Modern standardization
# --------------------------------------------------

modern_scaled = (
    standardize_clustering_features(
        result.features
    )
)


# --------------------------------------------------
# 9. Standardized feature equivalence
# --------------------------------------------------

print("\n=== C2 StandardScaler equivalence ===")

print(
    "Legacy shape:",
    legacy_standardized.shape,
)

print(
    "Modern shape:",
    modern_scaled.standardized_features.shape,
)

np.testing.assert_array_equal(
    legacy_standardized,
    modern_scaled.standardized_features,
)

print(
    "PASS: Standardized features match legacy exactly."
)


# --------------------------------------------------
# 10. Fitted scaler equivalence
# --------------------------------------------------

np.testing.assert_array_equal(
    legacy_scaler.mean_,
    modern_scaled.scaler.mean_,
)

np.testing.assert_array_equal(
    legacy_scaler.var_,
    modern_scaled.scaler.var_,
)

np.testing.assert_array_equal(
    legacy_scaler.scale_,
    modern_scaled.scaler.scale_,
)

print(
    "PASS: Scaler parameters match legacy exactly."
)


# --------------------------------------------------
# 11. Inverse transformation
# --------------------------------------------------

restored_features = (
    modern_scaled.scaler.inverse_transform(
        modern_scaled.standardized_features
    )
)

np.testing.assert_allclose(
    restored_features,
    result.features,
    rtol=0,
    atol=1e-12,
)

print(
    "PASS: Inverse transformation restores "
    "the original four-dimensional features."
)


import sklearn

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


print("\n=== C3 Environment ===")

print(
    "scikit-learn version:",
    sklearn.__version__,
)


# --------------------------------------------------
# 12. Legacy K-Means reference
# --------------------------------------------------

legacy_kmeans = KMeans(
    n_clusters=2,
    random_state=42,
)

legacy_labels = legacy_kmeans.fit_predict(
    legacy_standardized
)

legacy_centers = (
    legacy_kmeans.cluster_centers_
)

legacy_silhouette = silhouette_score(
    legacy_standardized,
    legacy_labels,
)

print("\n=== Legacy K-Means ===")

print(
    "Labels shape:",
    legacy_labels.shape,
)

print(
    "Centers shape:",
    legacy_centers.shape,
)

print(
    "Silhouette:",
    legacy_silhouette,
)

print(
    "Cluster sizes:",
    np.bincount(legacy_labels),
)


from src.statistical_clustering.kmeans_clustering import (
    apply_kmeans_clustering,
)


# --------------------------------------------------
# 13. Modern K-Means
# --------------------------------------------------

modern_kmeans = apply_kmeans_clustering(
    standardized_features=(
        modern_scaled.standardized_features
    ),
    n_clusters=2,
    random_state=42,
)

print("\n=== Modern K-Means ===")

print(
    "Labels shape:",
    modern_kmeans.labels.shape,
)

print(
    "Centers shape:",
    modern_kmeans.centers.shape,
)

print(
    "Silhouette:",
    modern_kmeans.silhouette,
)

print(
    "Cluster sizes:",
    np.bincount(modern_kmeans.labels),
)


# --------------------------------------------------
# 14. C3 K-Means equivalence
# --------------------------------------------------

print("\n=== C3 K-Means equivalence ===")

assert modern_kmeans.labels.shape == (34,)
assert modern_kmeans.centers.shape == (2, 4)

np.testing.assert_array_equal(
    legacy_labels,
    modern_kmeans.labels,
)

print(
    "PASS: Cluster labels match legacy exactly."
)

np.testing.assert_array_equal(
    legacy_centers,
    modern_kmeans.centers,
)

print(
    "PASS: Cluster centers match legacy exactly."
)

assert (
    legacy_silhouette
    == modern_kmeans.silhouette
)

print(
    "PASS: Silhouette score matches legacy exactly."
)


# --------------------------------------------------
# 15. Legacy centroid inverse transformation
# --------------------------------------------------

legacy_unscaled_centers = (
    legacy_scaler.inverse_transform(
        legacy_centers
    )
)

legacy_hours = np.round(
    np.mod(
        np.arctan2(
            legacy_unscaled_centers[:, 0],
            legacy_unscaled_centers[:, 1],
        )
        * 24.0
        / (2.0 * np.pi),
        24.0,
    )
).astype(int)

legacy_decoded_centers = np.column_stack(
    (
        legacy_hours,
        legacy_unscaled_centers[:, 2],
        legacy_unscaled_centers[:, 3],
    )
)

print("\n=== Legacy decoded centroids ===")

print(legacy_decoded_centers)


from src.statistical_clustering.centroid_decoding import (
    decode_cluster_centroids,
)


# --------------------------------------------------
# 16. Modern centroid decoding
# --------------------------------------------------

modern_decoded = decode_cluster_centroids(
    standardized_centers=modern_kmeans.centers,
    scaler=modern_scaled.scaler,
)

print("\n=== Modern decoded centroids ===")

print(modern_decoded.decoded_centers)


# --------------------------------------------------
# 17. C4 centroid equivalence
# --------------------------------------------------

print("\n=== C4 Centroid equivalence ===")

np.testing.assert_array_equal(
    legacy_unscaled_centers,
    modern_decoded.unscaled_centers,
)

print(
    "PASS: Unscaled centers match legacy exactly."
)

np.testing.assert_array_equal(
    legacy_hours,
    modern_decoded.hours,
)

print(
    "PASS: Decoded hours match legacy exactly."
)

np.testing.assert_array_equal(
    legacy_decoded_centers,
    modern_decoded.decoded_centers,
)

print(
    "PASS: Decoded centroids match legacy exactly."
)


print("\n=== Afghanistan centroid summary ===")

for cluster_id, center in enumerate(
    modern_decoded.decoded_centers
):
    hour, day, polarity = center

    print(
        f"Cluster {cluster_id}: "
        f"hour={int(hour)}, "
        f"day={day:.6f}, "
        f"polarity={polarity:.6f}"
    )


# --------------------------------------------------
# 18. Cluster polarity composition
# --------------------------------------------------

print("\n=== C5 Cluster polarity composition ===")

raw_polarities = result.raw_features[:, 2].astype(int)

labels = modern_kmeans.labels

n_clusters = modern_kmeans.centers.shape[0]

for cluster_id in range(n_clusters):

    member_mask = labels == cluster_id

    cluster_polarities = raw_polarities[member_mask]

    n_positive = np.count_nonzero(
        cluster_polarities == 1
    )

    n_negative = np.count_nonzero(
        cluster_polarities == -1
    )

    n_total = np.count_nonzero(member_mask)

    print(
        f"Cluster {cluster_id}: "
        f"total={n_total}, "
        f"positive={n_positive}, "
        f"negative={n_negative}"
    )

    assert n_positive + n_negative == n_total


from src.statistical_clustering.temporal_anchors import (
    extract_temporal_anchors,
)


# --------------------------------------------------
# 19. Extract Afghanistan temporal anchors
# --------------------------------------------------

anchors = extract_temporal_anchors(
    decoded_centers=modern_decoded.decoded_centers,
    labels=modern_kmeans.labels,
    raw_features=result.raw_features,
)

print("\n=== C5 Afghanistan temporal anchors ===")

for anchor in anchors:

    print(
        f"Cluster {anchor.cluster_id}: "
        f"hour={anchor.hour}, "
        f"centroid_day={anchor.centroid_day:.6f}, "
        f"rounded_day={anchor.rounded_day}, "
        f"centroid_polarity={anchor.centroid_polarity:.6f}, "
        f"dominant_polarity={anchor.dominant_polarity:+d}, "
        f"positive={anchor.n_positive}, "
        f"negative={anchor.n_negative}, "
        f"total={anchor.n_members}"
    )


# --------------------------------------------------
# 20. Validate cluster membership counts
# --------------------------------------------------

assert len(anchors) == 2

assert sum(
    anchor.n_members for anchor in anchors
) == 34

assert sum(
    anchor.n_positive for anchor in anchors
) == 18

assert sum(
    anchor.n_negative for anchor in anchors
) == 16

assert sorted(
    anchor.n_members for anchor in anchors
) == [16, 18]

print(
    "PASS: Anchor membership counts match "
    "the validated Afghanistan clustering."
)


# --------------------------------------------------
# 21. Validate Afghanistan centroid coordinates
# --------------------------------------------------

np.testing.assert_allclose(
    np.asarray(
        [
            anchors[0].centroid_day,
            anchors[1].centroid_day,
        ]
    ),
    np.asarray(
        [
            -7.77777778,
            -22.0625,
        ]
    ),
    atol=1e-8,
    rtol=0,
)

assert anchors[0].hour == 8
assert anchors[1].hour == 6

print(
    "PASS: Anchor coordinates match "
    "the validated Afghanistan centroids."
)


from src.statistical_clustering.centroid_presentation import (
    prepare_centroid_presentation,
)


# --------------------------------------------------
# 22. Prepare paper-compatible centroid coordinates
# --------------------------------------------------

presentation = prepare_centroid_presentation(
    modern_decoded.decoded_centers
)

print("\n=== C6 Continuous centroids ===")
print(presentation.continuous_centers)

print("\n=== C6 Paper-style rounded centroids ===")
print(presentation.rounded_centers)


# --------------------------------------------------
# 23. Validate Afghanistan presentation coordinates
# --------------------------------------------------

expected_rounded = np.asarray(
    [
        [8.0, -8.0, 1.0],
        [6.0, -22.0, -1.0],
    ],
    dtype=np.float64,
)

np.testing.assert_array_equal(
    presentation.continuous_centers,
    modern_decoded.decoded_centers,
)

np.testing.assert_array_equal(
    presentation.rounded_centers,
    expected_rounded,
)

print(
    "PASS: Continuous centroid coordinates are preserved."
)

print(
    "PASS: Rounded centroid coordinates match "
    "the expected Afghanistan presentation."
)


from src.statistical_clustering.pipeline import (
    run_statistical_clustering,
)


# --------------------------------------------------
# 24. Run integrated Afghanistan pipeline
# --------------------------------------------------

pipeline_result = run_statistical_clustering(
    mask=paper_mask,
    relative_days=relative_days,
    n_clusters=2,
    random_state=42,
)

print("\n=== C7 Afghanistan pipeline ===")

print(
    "Raw features:",
    pipeline_result.clustering_features.raw_features.shape,
)

print(
    "Standardized features:",
    pipeline_result.scaled_features.standardized_features.shape,
)

print(
    "Cluster sizes:",
    np.bincount(pipeline_result.kmeans.labels),
)

print(
    "Silhouette:",
    pipeline_result.kmeans.silhouette,
)

print(
    "Continuous centroids:\n",
    pipeline_result.decoded_centroids.decoded_centers,
)

print(
    "Paper-style centroids:\n",
    pipeline_result.centroid_presentation.rounded_centers,
)


# --------------------------------------------------
# 25. C7 end-to-end regression checks
# --------------------------------------------------

print("\n=== C7 End-to-end regression ===")

# C1
np.testing.assert_array_equal(
    pipeline_result.clustering_features.raw_features,
    result.raw_features,
)

np.testing.assert_array_equal(
    pipeline_result.clustering_features.features,
    result.features,
)

print("PASS: C1 features unchanged.")

# C2
np.testing.assert_array_equal(
    pipeline_result.scaled_features.standardized_features,
    modern_scaled.standardized_features,
)

print("PASS: C2 standardized features unchanged.")

# C3
np.testing.assert_array_equal(
    pipeline_result.kmeans.labels,
    modern_kmeans.labels,
)

np.testing.assert_array_equal(
    pipeline_result.kmeans.centers,
    modern_kmeans.centers,
)

assert (
    pipeline_result.kmeans.silhouette
    == modern_kmeans.silhouette
)

print("PASS: C3 K-Means results unchanged.")

# C4
np.testing.assert_array_equal(
    pipeline_result.decoded_centroids.decoded_centers,
    modern_decoded.decoded_centers,
)

print("PASS: C4 decoded centroids unchanged.")

# C5
assert pipeline_result.temporal_anchors == anchors

print("PASS: C5 temporal anchors unchanged.")

# C6
np.testing.assert_array_equal(
    pipeline_result.centroid_presentation.continuous_centers,
    presentation.continuous_centers,
)

np.testing.assert_array_equal(
    pipeline_result.centroid_presentation.rounded_centers,
    presentation.rounded_centers,
)

print("PASS: C6 centroid presentation unchanged.")


# --------------------------------------------------
# 26. Afghanistan regression reference
# --------------------------------------------------

assert pipeline_result.clustering_features.raw_features.shape == (
    34,
    3,
)

assert pipeline_result.scaled_features.standardized_features.shape == (
    34,
    4,
)

np.testing.assert_array_equal(
    np.bincount(pipeline_result.kmeans.labels),
    np.asarray([18, 16]),
)

np.testing.assert_allclose(
    pipeline_result.kmeans.silhouette,
    0.31105623341145205,
    rtol=0,
    atol=1e-12,
)

expected_paper_centroids = np.asarray(
    [
        [8.0, -8.0, 1.0],
        [6.0, -22.0, -1.0],
    ],
    dtype=np.float64,
)

np.testing.assert_array_equal(
    pipeline_result.centroid_presentation.rounded_centers,
    expected_paper_centroids,
)

print(
    "PASS: Afghanistan end-to-end regression reference."
)


# from pathlib import Path


# fixture_path = Path(
#     "tests/fixtures/afghanistan/b5_paper_mask.npz"
# )

# fixture_path.parent.mkdir(
#     parents=True,
#     exist_ok=True,
# )

# np.savez_compressed(
#     fixture_path,
#     mask=paper_mask,
#     relative_days=relative_days,
# )

# print(
#     "Saved Afghanistan B5 fixture:",
#     fixture_path,
# )

# with np.load(
#     fixture_path,
#     allow_pickle=False,
# ) as data:

#     saved_mask = data["mask"]

#     saved_days = data["relative_days"]


# assert saved_mask.shape == (31, 24)

# np.testing.assert_array_equal(
#     saved_days,
#     np.arange(-30, 1),
# )

# assert np.count_nonzero(saved_mask == 1) == 18

# assert np.count_nonzero(saved_mask == -1) == 16

# print("PASS: Afghanistan B5 fixture verified.")