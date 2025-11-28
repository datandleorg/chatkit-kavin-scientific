from __future__ import annotations

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


def main() -> None:
    """Train and evaluate an XGBoost classifier on the Breast Cancer dataset."""
    data = load_breast_cancer()
    print("Feature shape:", data.data.shape)
    print("Target shape:", data.target.shape)
    print("Feature names:", data.feature_names)
    print("Target names:", data.target_names)
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

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        eval_metric="logloss",
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    print("XGBoost on Breast Cancer Dataset")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")
    print("\nDetailed classification report:\n")
    print(
        classification_report(
            y_test,
            y_pred,
            target_names=data.target_names,
            zero_division=0,
        )
    )


if __name__ == "__main__":
    main()

