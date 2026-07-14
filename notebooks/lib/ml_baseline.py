"""
Phase 7 (OPTIONAL) — baseline ML churn-classification comparison.

This is explicitly NOT part of the mandatory demo. The core app (Phases
1-6) never reads anything produced here. It exists to give an honest,
transparent point of comparison against the mandatory rule-based score
(sql/gold/retention_action_list.sql): does a simple ML model do
meaningfully better, and does adding behavioral features help over static
attributes alone? churn_label_90d (notebooks/lib/datagen.py) is a
SIMULATED ground-truth label generated alongside the archetypes, not a
real outcome.

Pure Python + pandas + scikit-learn, no Spark dependency, so it is
unit-tested directly (tests/test_ml_baseline.py) the same way
notebooks/lib/datagen.py is. notebooks/07_optional_ml_baseline.py wraps
this with MLflow tracking and writes the optional
gold.churn_model_scores table when run in Databricks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42

STATIC_CATEGORICAL_COLUMNS = ["age_band", "acquisition_channel", "home_region", "value_segment"]
STATIC_NUMERIC_COLUMNS = ["tenure_months"]

BEHAVIORAL_NUMERIC_COLUMNS = [
    "current_balance",
    "balance_change_30d_pct",
    "balance_change_90d_pct",
    "transfer_out_amount_90d",
    "salary_deposit_active",
    "salary_deposit_stopped_flag",
    "product_count",
    "product_count_change_90d",
    "card_spend_90d",
    "card_spend_change_30d_pct",
    "card_spend_change_90d_pct",
    "declined_txn_count_90d",
    "days_since_last_login",
    "login_count_90d",
    "login_change_30d_pct",
    "login_change_90d_pct",
    "app_engagement_score",
    "contact_count_90d",
    "complaint_count_90d",
    "unresolved_contacts_total",
    "campaign_count_12m",
    "campaign_response_rate_12m",
    "campaign_conversion_rate_12m",
]


@dataclass
class EvalResult:
    model_name: str
    precision: float
    recall: float
    roc_auc: float
    confusion_matrix: list[list[int]]
    n_train: int
    n_test: int
    notes: str = ""


def build_customer_frame(customer_360_rows: list[dict], retention_action_rows: list[dict]) -> pd.DataFrame:
    """Joins customer_360 (behavior + label) with retention_action_list
    (rule-based risk_score) on customer_id into one pandas DataFrame."""
    c360 = pd.DataFrame(customer_360_rows)
    actions = pd.DataFrame(retention_action_rows)[["customer_id", "risk_score", "risk_segment"]]
    df = c360.merge(actions, on="customer_id", how="inner")
    return df


def _one_hot(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return pd.get_dummies(df[columns], columns=columns, dummy_na=False)


def build_static_features(df: pd.DataFrame) -> pd.DataFrame:
    categorical = _one_hot(df, STATIC_CATEGORICAL_COLUMNS)
    numeric = df[STATIC_NUMERIC_COLUMNS].fillna(df[STATIC_NUMERIC_COLUMNS].median())
    return pd.concat([numeric.reset_index(drop=True), categorical.reset_index(drop=True)], axis=1)


def build_behavioral_features(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df[BEHAVIORAL_NUMERIC_COLUMNS].copy()
    # New customers have NULL 90d comparisons (see docs/data-dictionary.md);
    # median-impute rather than drop rows, and keep an explicit missingness
    # flag so the model can use "too new to compare" as a signal.
    for col in numeric.columns:
        if numeric[col].isna().any():
            numeric[f"{col}_was_missing"] = numeric[col].isna().astype(int)
            numeric[col] = numeric[col].fillna(numeric[col].median())
    return numeric


def _split_train_test(df: pd.DataFrame) -> tuple[pd.Index, pd.Index]:
    """One shared, stratified train/test split (by customer row index) so
    all three approaches — including the rule-based score, which isn't
    fitted — are compared on the identical held-out test set. Evaluating
    the rule against the full population while the ML models only see
    their 30% test split would inflate the rule's apparent performance
    relative to the models by construction, not by merit."""
    train_idx, test_idx = train_test_split(
        df.index, test_size=0.3, random_state=RANDOM_STATE, stratify=df["churn_label_90d"]
    )
    return train_idx, test_idx


def _fit_and_evaluate(
    X: pd.DataFrame, y: pd.Series, train_idx: pd.Index, test_idx: pd.Index, model_name: str
) -> EvalResult:
    X_train, X_test = X.loc[train_idx], X.loc[test_idx]
    y_train, y_test = y.loc[train_idx], y.loc[test_idx]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]

    return EvalResult(
        model_name=model_name,
        precision=round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        recall=round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        roc_auc=round(float(roc_auc_score(y_test, y_proba)), 4),
        confusion_matrix=confusion_matrix(y_test, y_pred).tolist(),
        n_train=len(X_train),
        n_test=len(X_test),
    )


def evaluate_static_model(df: pd.DataFrame, train_idx=None, test_idx=None) -> EvalResult:
    if train_idx is None or test_idx is None:
        train_idx, test_idx = _split_train_test(df)
    X = build_static_features(df)
    y = df["churn_label_90d"]
    return _fit_and_evaluate(X, y, train_idx, test_idx, "static_attributes_only")


def evaluate_behavioral_model(df: pd.DataFrame, train_idx=None, test_idx=None) -> EvalResult:
    if train_idx is None or test_idx is None:
        train_idx, test_idx = _split_train_test(df)
    X = build_behavioral_features(df)
    y = df["churn_label_90d"]
    return _fit_and_evaluate(X, y, train_idx, test_idx, "integrated_behavior_features")


def evaluate_rule_based_score(df: pd.DataFrame, test_idx=None) -> EvalResult:
    """Evaluates the MANDATORY rule-based risk_score as a classifier
    against the same simulated label, for direct comparison. Predicted
    positive = Medium or High risk segment (risk_score >= 15), matching
    docs/risk-scoring.md — the same threshold the app itself uses to
    decide whether a customer gets a retention action. Restricted to
    `test_idx` when provided so the comparison is apples-to-apples with
    the fitted models above; evaluates on the full population only when
    called standalone with no split given."""
    subset = df.loc[test_idx] if test_idx is not None else df
    y = subset["churn_label_90d"]
    y_proba = subset["risk_score"] / 129.0  # normalized score as a pseudo-probability
    y_pred = (subset["risk_segment"].isin(["Medium", "High"])).astype(int)

    return EvalResult(
        model_name="rule_based_risk_score",
        precision=round(float(precision_score(y, y_pred, zero_division=0)), 4),
        recall=round(float(recall_score(y, y_pred, zero_division=0)), 4),
        roc_auc=round(float(roc_auc_score(y, y_proba)), 4),
        confusion_matrix=confusion_matrix(y, y_pred).tolist(),
        n_train=0,
        n_test=len(subset),
        notes=(
            "Evaluated on the same held-out test split as the ML models "
            "(it's a fixed rule, not a fitted model, so it has no train set)."
            if test_idx is not None
            else "Evaluated on the full population — no shared split was provided."
        ),
    )


def run_comparison(customer_360_rows: list[dict], retention_action_rows: list[dict]) -> dict:
    df = build_customer_frame(customer_360_rows, retention_action_rows)
    train_idx, test_idx = _split_train_test(df)
    results = {
        "rule_based": evaluate_rule_based_score(df, test_idx=test_idx),
        "static_attributes": evaluate_static_model(df, train_idx=train_idx, test_idx=test_idx),
        "behavioral_features": evaluate_behavioral_model(df, train_idx=train_idx, test_idx=test_idx),
    }
    return {name: vars(result) for name, result in results.items()}
