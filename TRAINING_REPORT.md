# AI Drug Toxicity Prediction System - Training Report

## Dataset Information

### Source Datasets Used

1. **Tox21 Dataset**
   - Source: U.S. EPA ToxCast/Tox21 program
   - Purpose: Toxicity screening data from 12 assay endpoints
   - Compounds: ~8,000 molecules
   - Assay endpoints: NR-AR, NR-AR-LBD, NR-AhR, NR-Aromatase, NR-ER, NR-ER-LBD, NR-PPAR-gamma, SR-ARE, SR-ATAD5, SR-HSE, SR-MMP, SR-p53

2. **ChEMBL Dataset**
   - Source: ChEMBL database (European Bioinformatics Institute)
   - Purpose: Bioactivity data with IC50 values
   - Compounds: ~1,500 compounds with IC50 measurements
   - Used for: pIC50-based toxicity classification

3. **ZINC250k Dataset**
   - Source: ZINC database (Irwin Shoichet Laboratory)
   - Purpose: Drug-like compound library
   - Compounds: 5,000 sampled compounds
   - Role: Non-toxic control group

### Final Merged Dataset Statistics

- **Total Samples**: 12,822 compounds
- **Training Set**: 10,257 compounds (80%)
- **Test Set**: 2,565 compounds (20%)
- **Features**: 1,218 features per compound
  - 30 physicochemical descriptors (MolWt, LogP, TPSA, etc.)
  - 1,024 Morgan fingerprint bits (radius=2)
  - 167 MACCS keys

### Class Distribution (5-Category Toxicity Scale)

| Class | Label | Count | Percentage |
|-------|-------|-------|------------|
| 0 | NON-TOXIC | 9,953 | 77.6% |
| 1 | MODERATE | 2,065 | 16.1% |
| 2 | TOXIC | 612 | 4.8% |
| 3 | HIGH RISK | 163 | 1.3% |
| 4 | CRITICAL | 29 | 0.2% |

**Note**: Imbalanced dataset with majority non-toxic compounds. This reflects real-world chemical distributions.

---

## Model Training Results

### Models Trained

1. **XGBoost** (Extreme Gradient Boosting)
   - Parameters: n_estimators=300, max_depth=6, learning_rate=0.1
   - Objective: multi:softprob (5-class classification)

2. **RandomForest** (Random Forest Classifier)
   - Parameters: n_estimators=300, max_depth=20, class_weight="balanced"
   - **Selected as Best Model**

3. **LightGBM** (Light Gradient Boosting Machine)
   - Parameters: n_estimators=300, max_depth=-1, num_leaves=31
   - Objective: multiclass (5-class classification)

### Performance Comparison

| Metric | XGBoost | RandomForest | LightGBM |
|--------|--------|--------------|----------|
| **Accuracy** | 80.12% | 79.22% | 77.15% |
| **Precision** | 75.83% | 76.90% | 76.28% |
| **Recall** | 80.12% | 79.22% | 77.15% |
| **F1 Score** | 76.87% | **77.83%** | 76.64% |
| **ROC-AUC** | **84.41%** | 83.66% | 83.14% |

**Best Model**: RandomForest (highest F1 Score: 0.7783)

---

## Detailed Classification Report (RandomForest - Best Model)

### Per-Class Performance

| Toxicity Class | Precision | Recall | F1-Score | Support |
|----------------|-----------|--------|----------|---------|
| NON-TOXIC | 86.76% | 92.47% | 89.52% | 1,991 |
| MODERATE | 44.74% | 36.08% | 39.95% | 413 |
| TOXIC | 39.36% | 30.33% | 34.26% | 122 |
| HIGH RISK | 28.57% | 12.12% | 17.02% | 33 |
| CRITICAL | 50.00% | 16.67% | 25.00% | 6 |

### Confusion Matrix (RandomForest)

```
Predicted →  NON-TOXIC  MODERATE  TOXIC  HIGH RISK  CRITICAL
Actual ↓
NON-TOXIC       1841       133      13        4         0
MODERATE         232       149      31        1         0
TOXIC             38        42      37        5         0
HIGH RISK          9         8      11        4         1
CRITICAL           2         1       2        0         1
```

### Performance Analysis

**Strengths:**
- Excellent performance on NON-TOXIC class (89.52% F1)
- Good overall accuracy (79.22%)
- Strong ROC-AUC (83.66%) indicates good ranking capability

**Weaknesses:**
- Lower performance on minority classes (MODERATE, TOXIC, HIGH RISK, CRITICAL)
- Class imbalance affects minority class predictions
- CRITICAL class has very few samples (only 6 in test set)

---

## Feature Engineering

### Feature Types

1. **Physicochemical Descriptors (30 features)**
   - Molecular weight, LogP, TPSA
   - Hydrogen bond donors/acceptors
   - Rotatable bonds, ring counts
   - QED score, synthetic accessibility
   - Kappa indices, Chi indices

2. **Morgan Fingerprints (1,024 bits)**
   - Circular fingerprints (radius=2)
   - Captures local atomic environments
   - Important for substructure recognition

3. **MACCS Keys (167 bits)**
   - Predefined structural keys
   - Covers common chemical substructures
   - Useful for known toxicophores

### Feature Scaling
- StandardScaler applied to all features
- Mean=0, Standard Deviation=1
- Saved as `scaler.pkl` for consistent inference

---

## Training Configuration

### Data Split
- **Stratified split**: 80% train / 20% test
- **Random seed**: 42 (reproducible)
- **Stratification**: Maintains class distribution in both sets

### Model Hyperparameters

**XGBoost:**
```python
n_estimators=300
max_depth=6
learning_rate=0.1
objective='multi:softprob'
num_class=5
tree_method='hist'
random_state=42
```

**RandomForest:**
```python
n_estimators=300
max_depth=20
min_samples_split=5
min_samples_leaf=2
class_weight='balanced'
random_state=42
```

**LightGBM:**
```python
n_estimators=300
max_depth=-1
learning_rate=0.1
num_leaves=31
objective='multiclass'
num_class=5
class_weight='balanced'
random_state=42
```

---

## Model Artifacts Saved

```
models/
├── best_model.pkl              # RandomForest (selected as best)
├── RandomForest_model.pkl       # RandomForest model
├── XGBoost_model.pkl           # XGBoost model
├── LightGBM_model.pkl          # LightGBM model
├── scaler.pkl                  # StandardScaler for features
├── feature_names.pkl           # List of 1,218 feature names
├── test_data.npz               # Test set (X_test, y_test)
└── training_meta.json          # Training metadata and results
```

---

## Recommendations for Improvement

### Short-term Improvements
1. **Address class imbalance** - Use oversampling (SMOTE) or class weights
2. **Increase CRITICAL class samples** - Collect more high-toxicity compounds
3. **Ensemble methods** - Combine predictions from all 3 models
4. **Threshold optimization** - Adjust decision thresholds per class

### Long-term Improvements
1. **Expand training data** - Add more toxic compounds from diverse sources
2. **Transfer learning** - Pre-train on larger chemical databases
3. **Deep learning** - Graph neural networks for molecular representation
4. **Multi-task learning** - Predict multiple toxicity endpoints simultaneously

---

## Conclusion

The AI Drug Toxicity Prediction System has been successfully trained on a diverse dataset of 12,822 compounds from Tox21, ChEMBL, and ZINC databases. The RandomForest model achieved the best performance with an F1 score of 77.83% and ROC-AUC of 83.66%.

The system is particularly strong at identifying non-toxic compounds (89.52% F1) but has room for improvement on minority toxicity classes. The model is suitable for research screening applications but should be used with appropriate confidence thresholds and experimental validation for critical decisions.

**Training Date**: May 28, 2026
**Sklearn Version**: 1.8.0
**Python Version**: 3.14
