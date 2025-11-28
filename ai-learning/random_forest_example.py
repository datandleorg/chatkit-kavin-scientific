from __future__ import annotations

import numpy as np
from sklearn.datasets import load_wine
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def main() -> None:
    """Train and evaluate a Random Forest classifier on the UCI Wine dataset."""
    data = load_wine()
    print("Loaded Wine Dataset:")
    print(f"Feature shape: {data.data.shape}")
    print(f"Target shape: {data.target.shape}")
    print(f"Feature names: {data.feature_names}")
    print(f"Target names: {data.target_names}")
    X, y = data.data, data.target

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    print("Random Forest on Wine Dataset")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print("\nDetailed classification report:\n")
    print(classification_report(y_test, y_pred, target_names=data.target_names))


if __name__ == "__main__":
    main()

