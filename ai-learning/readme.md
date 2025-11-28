## ML Model Examples

This folder contains quick-start examples for classic tree-based models using scikit-learn datasets.

- `random_forest_example.py` trains a Random Forest classifier on the UCI Wine dataset via `sklearn.datasets.load_wine`.
- `xgboost_example.py` trains an XGBoost classifier on the Breast Cancer Wisconsin dataset via `sklearn.datasets.load_breast_cancer`.

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install scikit-learn xgboost
```

### Run the examples

```bash
python random_forest_example.py
python xgboost_example.py
```

Each script prints overall accuracy and a detailed classification report so you can compare model performance.
