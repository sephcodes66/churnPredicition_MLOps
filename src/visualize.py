
import matplotlib.pyplot as plt
import seaborn as sns
import xgboost as xgb
import pandas as pd
import numpy as np
import optuna
from sklearn.metrics import confusion_matrix, roc_curve, ConfusionMatrixDisplay
import mlflow
from mlflow.tracking import MlflowClient
import os
import yaml
from sklearn.model_selection import train_test_split
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from src.build_features import build_features

def plot_feature_distributions(X: pd.DataFrame, output_path: str):
    """
    Creates and saves a grid of histograms for each feature in the dataset.
    """
    features = X.columns
    n_features = len(features)
    n_cols = 3
    n_rows = (n_features + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
    axes = axes.flatten() if n_rows * n_cols > 1 else [axes]
    
    for i, feature in enumerate(features):
        if i < len(axes):
            ax = axes[i]
            sns.histplot(X[feature], ax=ax, kde=True, color='skyblue')
            ax.set_title(f'Distribution of {feature}')
    
    for i in range(n_features, len(axes)):
        axes[i].set_visible(False)
    
    plt.tight_layout()
    fig.suptitle('Feature Distributions', y=1.02, fontsize=16)
    plt.savefig(output_path)
    plt.close(fig)

def plot_correlation_heatmap(X: pd.DataFrame, y: pd.Series, output_path: str):
    """
    Creates and saves a correlation heatmap of all features and the target variable.
    """
    data = X.copy()
    data['target'] = y
    
    corr_matrix = data.corr()
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    cmap = sns.diverging_palette(220, 10, as_cmap=True)
    sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap=cmap,
                center=0, square=True, linewidths=0.5, ax=ax)
    
    ax.set_title('Feature Correlation Heatmap', fontsize=16)
    plt.savefig(output_path)
    plt.close(fig)

def plot_optuna_trials(study: optuna.study.Study, output_path: str):
    """
    Creates and saves a plot showing the objective value of each Optuna trial.
    """
    trial_values = [t.value for t in study.trials]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(trial_values)
    ax.set_xlabel("Trial")
    ax.set_ylabel("Objective Value")
    ax.set_title("Optuna Optimization History")
    plt.savefig(output_path)
    plt.close(fig)

def plot_feature_importance(model: xgb.XGBRegressor, output_path: str):
    """
    Creates and saves a plot showing the feature importance of the best model.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    xgb.plot_importance(model, ax=ax, importance_type='gain')
    plt.title('Feature Importance')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close(fig)

def plot_confusion_matrix(y_true: pd.Series, y_pred: np.ndarray, output_path: str):
    """
    Creates and saves a confusion matrix plot.
    """
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    disp.plot(ax=ax, cmap='Blues')
    ax.set_title('Confusion Matrix')
    plt.savefig(output_path)
    plt.close(fig)

def plot_roc_curve(y_true: pd.Series, y_pred_proba: np.ndarray, output_path: str):
    """
    Creates and saves an ROC curve plot.
    """
    fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(fpr, tpr, color='darkorange', lw=2, label='ROC curve')
    ax.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title('Receiver Operating Characteristic (ROC) Curve')
    ax.legend(loc="lower right")
    plt.savefig(output_path)
    plt.close(fig)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and save visualizations.")
    parser.add_argument("--output_dir", type=str, default="visualizations", help="Directory to save the visualizations.")
    args = parser.parse_args()

    # Load config
    with open("config/main_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Create output directory
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Build features
    build_features()

    # Load data
    data = pd.read_parquet("data/processed/customer_features_realistic.parquet")
    X = data.drop(columns=[config["data"]["target_column"]])
    y = data[config["data"]["target_column"]]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config["data"]["test_size"], random_state=config["data"]["random_state"]
    )

    # Load best model from MLflow
    client = MlflowClient()
    experiment = client.get_experiment_by_name(config["mlflow"]["experiment_name"])
    best_run = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.best_auc DESC"],
        max_results=1,
    )[0]
    model_uri = f"runs:/{best_run.info.run_id}/model"
    model = mlflow.pyfunc.load_model(model_uri)

    # Generate and save plots
    plot_feature_distributions(X, os.path.join(output_dir, "feature_distributions.png"))
    plot_correlation_heatmap(X, y, os.path.join(output_dir, "correlation_heatmap.png"))
    
    # Optuna study is not saved, so we can't plot it.
    # plot_optuna_trials(study, os.path.join(output_dir, "optuna_trials.png"))
    
    # plot_feature_importance(model, os.path.join(output_dir, "feature_importance.png"))

    y_pred_proba = model.predict(X_test)
    y_pred = (y_pred_proba > 0.5).astype(int)

    plot_confusion_matrix(y_test, y_pred, os.path.join(output_dir, "confusion_matrix.png"))
    plot_roc_curve(y_test, y_pred_proba, os.path.join(output_dir, "roc_curve.png"))

    print(f"Visualizations saved to: {output_dir}")
