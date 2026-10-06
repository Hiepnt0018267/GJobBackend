# Baseline-v1 Benchmark

## 1. Objective

Measure a frozen offline lexical reference on the same 220 human-labeled pairs.

## 2. Ground Truth

Only human label/label_reason; sampling groups are not labels. Input validated and hashed.

## 3. Baseline Definition

baseline-v1-offline-lexical, NOT the existing structured-skill production engine. See BASELINE_V1_FROZEN.md.

## 4. Preprocessing

NFKC/casefold, email/URL removal, punctuation-aware tokens, frozen local stopwords. No skills/seniority inference.

## 5. Exact Scoring Formula

{
  "version": "baseline-v1-offline-lexical",
  "preprocessing": "nfkc-casefold-static-stopwords-v1",
  "weights": {
    "tfidf_lexical_cosine": 0.7,
    "title_token_coverage": 0.3
  },
  "default_threshold": 0.5,
  "score_range": [
    0,
    1
  ],
  "term_frequency": "1 + ln(count)",
  "inverse_document_frequency": "ln((1+N)/(1+df)) + 1",
  "title_formula": "|unique JD title tokens intersect CV tokens| / |unique JD title tokens|; empty=0",
  "stopwords_sha256": "52763a8acc5453f2059bc9e8c118925333513e8c234e9f37d7bb758c9aac688c",
  "skill_vocabulary": null,
  "seniority_signal": null,
  "formula": "0.7 * TF-IDF lexical cosine + 0.3 * title-token coverage",
  "production_baseline": "Unchanged structured-skill coverage engine; not this raw-text reference."
}

## 6. Default Threshold

0.5, frozen before real run; evaluation assumption, not production calibration.

## 7. Main Results

{
  "count": 220,
  "human_positive": 116,
  "human_negative": 104,
  "positive_ratio": 0.5272727272727272,
  "negative_ratio": 0.4727272727272727,
  "TP": 0,
  "TN": 104,
  "FP": 0,
  "FN": 116,
  "threshold": 0.5,
  "precision": null,
  "recall": 0.0,
  "f1": 0.0,
  "accuracy": 0.4727272727272727,
  "specificity": 1.0,
  "false_positive_rate": 0.0,
  "balanced_accuracy": 0.5,
  "mcc": null,
  "roc_auc": 0.8344661803713528,
  "average_precision": 0.8199429081710353,
  "score_distribution": {
    "count": 220,
    "mean": 0.28545164740058276,
    "median": 0.2938227572570708,
    "percentiles": {
      "0": 0.02344913470597548,
      "5": 0.04100565658301278,
      "25": 0.2078057287612775,
      "50": 0.2938227572570708,
      "75": 0.3993378464821058,
      "95": 0.4456139431873795,
      "100": 0.4826871150228295
    }
  },
  "positive_scores": {
    "count": 116,
    "mean": 0.35314069733309944,
    "median": 0.3841847028436253,
    "percentiles": {
      "0": 0.09015233988122275,
      "5": 0.2071616843550555,
      "25": 0.2904748768818221,
      "50": 0.3841847028436253,
      "75": 0.4196968912894265,
      "95": 0.4490308748381286,
      "100": 0.4826871150228295
    }
  },
  "negative_scores": {
    "count": 104,
    "mean": 0.20995232247585258,
    "median": 0.21487237762131076,
    "percentiles": {
      "0": 0.02344913470597548,
      "5": 0.034656414824446785,
      "25": 0.11468776864405394,
      "50": 0.21487237762131076,
      "75": 0.2844122623214008,
      "95": 0.41064681427597277,
      "100": 0.45871986333511905
    }
  }
}

## 8. Confusion Matrix

{"TP": 0, "TN": 104, "FP": 0, "FN": 116}

## 9. Score Distribution

{
  "positive_scores": {
    "count": 116,
    "mean": 0.35314069733309944,
    "median": 0.3841847028436253,
    "percentiles": {
      "0": 0.09015233988122275,
      "5": 0.2071616843550555,
      "25": 0.2904748768818221,
      "50": 0.3841847028436253,
      "75": 0.4196968912894265,
      "95": 0.4490308748381286,
      "100": 0.4826871150228295
    }
  },
  "negative_scores": {
    "count": 104,
    "mean": 0.20995232247585258,
    "median": 0.21487237762131076,
    "percentiles": {
      "0": 0.02344913470597548,
      "5": 0.034656414824446785,
      "25": 0.11468776864405394,
      "50": 0.21487237762131076,
      "75": 0.2844122623214008,
      "95": 0.41064681427597277,
      "100": 0.45871986333511905
    }
  }
}

## 10. Threshold Analysis

This is an in-sample exploratory threshold estimate, not a held-out production calibration.
{"TP": 104, "TN": 70, "FP": 34, "FN": 12, "threshold": 0.24733698756646583, "precision": 0.7536231884057971, "recall": 0.896551724137931, "f1": 0.8188976377952756, "accuracy": 0.7909090909090909, "specificity": 0.6730769230769231, "false_positive_rate": 0.3269230769230769, "balanced_accuracy": 0.7848143236074271, "mcc": 0.5881539487965878}

## 11. Candidate Group Analysis

{
  "POSITIVE_CANDIDATE": {
    "count": 90,
    "human_positive": 68,
    "human_negative": 22,
    "positive_ratio": 0.7555555555555555,
    "negative_ratio": 0.24444444444444444,
    "TP": 0,
    "TN": 22,
    "FP": 0,
    "FN": 68,
    "threshold": 0.5,
    "precision": null,
    "recall": 0.0,
    "f1": 0.0,
    "accuracy": 0.24444444444444444,
    "specificity": 1.0,
    "false_positive_rate": 0.0,
    "balanced_accuracy": 0.5,
    "mcc": null,
    "roc_auc": 0.7045454545454546,
    "average_precision": 0.8797547278614176,
    "score_distribution": {
      "count": 90,
      "mean": 0.36061109767876454,
      "median": 0.3914614126630642,
      "percentiles": {
        "0": 0.19882307076696784,
        "5": 0.2375896960541131,
        "25": 0.2888600456598956,
        "50": 0.3914614126630642,
        "75": 0.42587156841183965,
        "95": 0.458973041224823,
        "100": 0.4826871150228295
      }
    },
    "positive_scores": {
      "count": 68,
      "mean": 0.3742060969098883,
      "median": 0.40756001302716804,
      "percentiles": {
        "0": 0.20731977308539803,
        "5": 0.2483733805918876,
        "25": 0.309765897567299,
        "50": 0.40756001302716804,
        "75": 0.4313358788873897,
        "95": 0.4699024685465642,
        "100": 0.4826871150228295
      }
    },
    "negative_scores": {
      "count": 22,
      "mean": 0.31859019096438196,
      "median": 0.3079966099463324,
      "percentiles": {
        "0": 0.19882307076696784,
        "5": 0.22166567533937048,
        "25": 0.26999510890227135,
        "50": 0.3079966099463324,
        "75": 0.37711549130632366,
        "95": 0.4258231462940636,
        "100": 0.45871986333511905
      }
    }
  },
  "HARD_NEGATIVE_CANDIDATE": {
    "count": 100,
    "human_positive": 48,
    "human_negative": 52,
    "positive_ratio": 0.48,
    "negative_ratio": 0.52,
    "TP": 0,
    "TN": 52,
    "FP": 0,
    "FN": 48,
    "threshold": 0.5,
    "precision": null,
    "recall": 0.0,
    "f1": 0.0,
    "accuracy": 0.52,
    "specificity": 1.0,
    "false_positive_rate": 0.0,
    "balanced_accuracy": 0.5,
    "mcc": null,
    "roc_auc": 0.7516025641025641,
    "average_precision": 0.6909475982139139,
    "score_distribution": {
      "count": 100,
      "mean": 0.2822121357744437,
      "median": 0.2637123519927327,
      "percentiles": {
        "0": 0.07310866307777837,
        "5": 0.1456534194891495,
        "25": 0.21105939039657085,
        "50": 0.2637123519927327,
        "75": 0.3803791421916631,
        "95": 0.41977832820539557,
        "100": 0.450397062486599
      }
    },
    "positive_scores": {
      "count": 48,
      "mean": 0.32329804793264855,
      "median": 0.3263435764830018,
      "percentiles": {
        "0": 0.09015233988122275,
        "5": 0.19421558832325703,
        "25": 0.2624414087180861,
        "50": 0.3263435764830018,
        "75": 0.38863853614666594,
        "95": 0.4388032609447121,
        "100": 0.44782914048521316
      }
    },
    "negative_scores": {
      "count": 52,
      "mean": 0.24428667839763918,
      "median": 0.22019077005784263,
      "percentiles": {
        "0": 0.07310866307777837,
        "5": 0.1274220421711432,
        "25": 0.1919083004584,
        "50": 0.22019077005784263,
        "75": 0.27089212514885974,
        "95": 0.4045176997239574,
        "100": 0.450397062486599
      }
    }
  },
  "EASY_NEGATIVE_CANDIDATE": {
    "count": 30,
    "human_positive": 0,
    "human_negative": 30,
    "positive_ratio": 0.0,
    "negative_ratio": 1.0,
    "TP": 0,
    "TN": 30,
    "FP": 0,
    "FN": 0,
    "threshold": 0.5,
    "precision": null,
    "recall": null,
    "f1": null,
    "accuracy": 1.0,
    "specificity": 1.0,
    "false_positive_rate": 0.0,
    "balanced_accuracy": null,
    "mcc": null,
    "roc_auc": null,
    "average_precision": null,
    "score_distribution": {
      "count": 30,
      "mean": 0.07077166865316757,
      "median": 0.04412787507305807,
      "percentiles": {
        "0": 0.02344913470597548,
        "5": 0.026678634965119755,
        "25": 0.03641347124277442,
        "50": 0.04412787507305807,
        "75": 0.10455866909936118,
        "95": 0.17595277082994018,
        "100": 0.19448224733772965
      }
    },
    "positive_scores": {
      "count": 0,
      "mean": null,
      "median": null,
      "percentiles": {}
    },
    "negative_scores": {
      "count": 30,
      "mean": 0.07077166865316757,
      "median": 0.04412787507305807,
      "percentiles": {
        "0": 0.02344913470597548,
        "5": 0.026678634965119755,
        "25": 0.03641347124277442,
        "50": 0.04412787507305807,
        "75": 0.10455866909936118,
        "95": 0.17595277082994018,
        "100": 0.19448224733772965
      }
    }
  }
}

## 12. Hard Negative Analysis

FPR denominator is human negatives, not all hard-group candidates. hard_negative_errors.csv lists all human negatives highest score first.

## 13. False Positives

false_positives.csv, highest score first; source IDs and allowed human reasons only.

## 14. False Negatives

false_negatives.csv, lowest score first; no labels changed.

## 15. Limitations

220 difficulty-focused, single-reviewer pairs; intentionally simple baseline; no held-out calibration; raw extraction not evaluated; no hybrid. IDF fitted transductively on this corpus; title tokens may be generic. Incidental source terms can affect lexical score. Not the production skill matcher.

## 16. Reproducibility

{
  "input": "C:\\DATN\\GJobBackend\\evaluation\\data\\derived\\evaluation_pairs_labeled.csv",
  "input_sha256": "28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8",
  "source_hashes": {
    "Resume.csv": "816a7cd985a9a41e3ce8d1e83cb7e1beb1e854a89c1cf1fd0d75494faaa0559d",
    "job_postings.csv": "d782e95f35cbd5f658ad7124021c938f5c8c1656f1c059b6dc9d402d1eaa195f"
  },
  "implementation_sha256": "4aa3f4d459a7ca57fa8403b1a2403ee4d1745ec2d709241bf61fe1854279083d",
  "frozen_definition_sha256": "379eb86fea36b4258c93294a41bd78c72a77762c6acfc9d22fa823d9014020ae",
  "semantic_artifact_hashes": {
    "report.md": "65f9bb3099a477fb898992775bec98d52ee6b55b5b24728ff300e1491928640c",
    "metrics.json": "8d9e608c1639e0f16fc2f474f1385b586dd59273baa97fd38fd6be52c49721f3",
    "predictions.csv": "588a6d0fbfddc4ef6f7088fb354166bdf3662b15ace5774e7d572aadc9eaae46",
    "threshold_analysis.csv": "6f87a1fabcb3c41260e49c204380f1965830e0a252bc6f3478964fb05ae6e012",
    "false_positives.csv": "88fee6a36c8f524da42d33459984e3df4d4b0772b7cf268a6f54d89c300c370f",
    "false_negatives.csv": "e805cea8e2ea8c0fbc253721c1d49f8ab682b4a9d39182fc41b20692a75c9c29",
    "hard_negative_errors.csv": "23f0ec7996a4ada000dc966db5bf18c3fc16f7a414911da977bde678a38b9fec"
  },
  "git_commit": "82c5840a8a03721c6f10d54628d796ade639f57f",
  "command": [
    "C:\\DATN\\GJobBackend\\evaluation\\run_baseline_benchmark.py",
    "--input",
    "evaluation/data/derived/evaluation_pairs_labeled.csv",
    "--data-dir",
    "C:/DATN/Datasets",
    "--output-dir",
    "evaluation/results/baseline-v1"
  ],
  "timestamp": "2026-10-05T07:04:19.375965+00:00",
  "partial": false,
  "unique_cvs": 202,
  "unique_jobs": 180
}

## 17. Conclusion

Interpret with comparison report; no production algorithm switch, no post-hoc tuning.
