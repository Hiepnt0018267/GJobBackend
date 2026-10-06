# Held-out Semantic-v1 vs Baseline-v1

## Final interpretation and verification

The new calibration-only thresholds were persisted before the single test evaluation.
No original 0.5/default/global-best operating point was substituted in the test table.
All 220 labels and original semantic/lexical scores remain unchanged.

Assessment: **mixed / inconclusive for production selection**. Lexical has better pooled
F1/precision/AUC/AP point estimates; semantic has better hard-group ranking/recall.
Paired bootstrap 95% F1 difference interval (lexical-minus-semantic) is
[-0.025609,0.151141], so it includes zero. No statistically established winner is claimed.

This remains retrospective and transductive: all labels were previously analyzed,
and lexical IDF included all corpus texts. Calibration/test identity intersections
are zero, but these facts do not certify a new blind or fully inductive external test.
The fixed split places all multi-pair components in calibration; test has 88 singleton
components. This structural sampling bias is disclosed, not repaired after results.

Sanity review covered five FP/FN examples per method, hard disagreements and both
one-sided correctness buckets. Broad occupational overlap can hide role-specific
requirements; literal title/terms can miss transferable experience. These are
post-result interpretations of existing human reasons, not new features/annotations.
Details and anonymous IDs are in task_14b4_report.md; no labels or thresholds changed.

Full regression: **459 passed, 3 warnings in 184.47s**, exit0, existing gjob_db_test only.
Focused evaluation:67 passed; pure matching/embedding regression:90 passed. No new
DB/config or production code changes. The full 31-section report is task_14b4_report.md.

## 1. Objective

Grouped calibration/test separation for threshold selection on frozen scores, not an external blind validation.

## 2. Ground Truth

28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8; 220 original human decisions, unchanged. Sampling groups are not labels.

## 3. Split Method

Typed bipartite CV/JD graph; whole connected components. Fixed greedy + improving flips/swaps using counts only; seed42.

## 4. Split Statistics

{
  "calibration": {
    "candidate_groups": {
      "EASY_NEGATIVE_CANDIDATE": 18,
      "HARD_NEGATIVE_CANDIDATE": 60,
      "POSITIVE_CANDIDATE": 54
    },
    "easy_human_negative": 18,
    "hard_human_negative": 30,
    "negative": 62,
    "pairs": 132,
    "positive": 70,
    "unique_cvs": 114,
    "unique_jobs": 92
  },
  "calibration_fraction": 0.6,
  "component_count": 162,
  "component_size_distribution": {
    "1": 129,
    "2": 19,
    "3": 6,
    "4": 5,
    "5": 3
  },
  "largest_component": 5,
  "leakage": {
    "cv_id": 0,
    "job_id": 0,
    "pair_id": 0
  },
  "objective": 76,
  "test": {
    "candidate_groups": {
      "EASY_NEGATIVE_CANDIDATE": 12,
      "HARD_NEGATIVE_CANDIDATE": 40,
      "POSITIVE_CANDIDATE": 36
    },
    "easy_human_negative": 12,
    "hard_human_negative": 22,
    "negative": 42,
    "pairs": 88,
    "positive": 46,
    "unique_cvs": 88,
    "unique_jobs": 88
  },
  "top10": [
    {
      "component_id": "component_0d0ccaf6173e7ebd",
      "pairs": 5
    },
    {
      "component_id": "component_16a58d4675a93288",
      "pairs": 5
    },
    {
      "component_id": "component_ae0d9851a8661f65",
      "pairs": 5
    },
    {
      "component_id": "component_2ee0acd99dbeedc1",
      "pairs": 4
    },
    {
      "component_id": "component_372e6b87a128a5f8",
      "pairs": 4
    },
    {
      "component_id": "component_5b4b78902c94a3ec",
      "pairs": 4
    },
    {
      "component_id": "component_99e6bef2fa03c0e9",
      "pairs": 4
    },
    {
      "component_id": "component_bcf836228153aa13",
      "pairs": 4
    },
    {
      "component_id": "component_18ba871ecdb02550",
      "pairs": 3
    },
    {
      "component_id": "component_211ba8de6fa4d9e6",
      "pairs": 3
    }
  ]
}

## 5. Leakage Verification

Shared CV=0, shared JD=0, shared pair=0; all220 exactly once; component membership/labels verified.

## 6. Algorithms Frozen

Semantic-v1: unchanged BGE-M3 raw cosine. Baseline-v1-offline-lexical: unchanged 0.7 TF-IDF lexical cosine + 0.3 title coverage. Original scores/artifacts unchanged; no IDF refit/provider call.

## 7. Calibration Threshold Selection

max calibration F1, higher precision, lower FP, higher threshold. Candidates from calibration only; score >= threshold.

## 8. Calibrated Thresholds

{
  "baseline-v1": 0.24733698756646583,
  "semantic-v1": 0.5867267674262028
}

## 9. Calibration Results

{
  "baseline-v1": {
    "groups": {
      "EASY_NEGATIVE_CANDIDATE": {
        "FN": 0,
        "FP": 0,
        "TN": 18,
        "TP": 0,
        "accuracy": 1.0,
        "average_precision": null,
        "balanced_accuracy": null,
        "count": 18,
        "f1": null,
        "false_positive_rate": 0.0,
        "human_negative": 18,
        "human_positive": 0,
        "mcc": null,
        "negative_ratio": 1.0,
        "negative_scores": {
          "count": 18,
          "mean": 0.05875120991340542,
          "median": 0.042676012458919235,
          "percentiles": {
            "0": 0.02344913470597548,
            "100": 0.11950390733871383,
            "25": 0.033295227603952315,
            "5": 0.02401722388466155,
            "50": 0.042676012458919235,
            "75": 0.0798703373703505,
            "95": 0.1134875375454465
          }
        },
        "positive_ratio": 0.0,
        "positive_scores": {
          "count": 0,
          "mean": null,
          "median": null,
          "percentiles": {}
        },
        "precision": null,
        "recall": null,
        "roc_auc": null,
        "score_distribution": {
          "count": 18,
          "mean": 0.05875120991340542,
          "median": 0.042676012458919235,
          "percentiles": {
            "0": 0.02344913470597548,
            "100": 0.11950390733871383,
            "25": 0.033295227603952315,
            "5": 0.02401722388466155,
            "50": 0.042676012458919235,
            "75": 0.0798703373703505,
            "95": 0.1134875375454465
          }
        },
        "specificity": 1.0,
        "threshold": 0.24733698756646583
      },
      "HARD_NEGATIVE_CANDIDATE": {
        "FN": 3,
        "FP": 9,
        "TN": 21,
        "TP": 27,
        "accuracy": 0.8,
        "average_precision": 0.7365733109317432,
        "balanced_accuracy": 0.8,
        "count": 60,
        "f1": 0.8181818181818182,
        "false_positive_rate": 0.3,
        "human_negative": 30,
        "human_positive": 30,
        "mcc": 0.6123724356957946,
        "negative_ratio": 0.5,
        "negative_scores": {
          "count": 30,
          "mean": 0.23825869817256623,
          "median": 0.217465026140944,
          "percentiles": {
            "0": 0.07310866307777837,
            "100": 0.450397062486599,
            "25": 0.19187271040656573,
            "5": 0.11595981105599626,
            "50": 0.217465026140944,
            "75": 0.2662497203207177,
            "95": 0.4043956211364461
          }
        },
        "positive_ratio": 0.5,
        "positive_scores": {
          "count": 30,
          "mean": 0.3376152172232121,
          "median": 0.3460579508780569,
          "percentiles": {
            "0": 0.19906581886829045,
            "100": 0.44782914048521316,
            "25": 0.26510983294291507,
            "5": 0.21083410113856935,
            "50": 0.3460579508780569,
            "75": 0.396968144294052,
            "95": 0.4417596446637252
          }
        },
        "precision": 0.75,
        "recall": 0.9,
        "roc_auc": 0.8033333333333333,
        "score_distribution": {
          "count": 60,
          "mean": 0.28793695769788913,
          "median": 0.265835243906861,
          "percentiles": {
            "0": 0.07310866307777837,
            "100": 0.450397062486599,
            "25": 0.2161747152648999,
            "5": 0.14466896084241349,
            "50": 0.265835243906861,
            "75": 0.38361850740650727,
            "95": 0.44029302143010574
          }
        },
        "specificity": 0.7,
        "threshold": 0.24733698756646583
      },
      "POSITIVE_CANDIDATE": {
        "FN": 2,
        "FP": 11,
        "TN": 3,
        "TP": 38,
        "accuracy": 0.7592592592592593,
        "average_precision": 0.8666062051863679,
        "balanced_accuracy": 0.5821428571428571,
        "count": 54,
        "f1": 0.8539325842696629,
        "false_positive_rate": 0.7857142857142857,
        "human_negative": 14,
        "human_positive": 40,
        "mcc": 0.2483766536917779,
        "negative_ratio": 0.25925925925925924,
        "negative_scores": {
          "count": 14,
          "mean": 0.32738527978718707,
          "median": 0.3160455848273718,
          "percentiles": {
            "0": 0.19882307076696784,
            "100": 0.45871986333511905,
            "25": 0.2815612828875131,
            "5": 0.21306365365497096,
            "50": 0.3160455848273718,
            "75": 0.4008113665259131,
            "95": 0.431071976664466
          }
        },
        "positive_ratio": 0.7407407407407407,
        "positive_scores": {
          "count": 40,
          "mean": 0.3762549237120855,
          "median": 0.4161617319866685,
          "percentiles": {
            "0": 0.20731977308539803,
            "100": 0.4826871150228295,
            "25": 0.3102128286402395,
            "5": 0.24628771646243522,
            "50": 0.4161617319866685,
            "75": 0.4313358788873897,
            "95": 0.46018893987955817
          }
        },
        "precision": 0.7755102040816326,
        "recall": 0.95,
        "roc_auc": 0.6964285714285714,
        "score_distribution": {
          "count": 54,
          "mean": 0.3635850160278526,
          "median": 0.3966530726969129,
          "percentiles": {
            "0": 0.19882307076696784,
            "100": 0.4826871150228295,
            "25": 0.29027879708616,
            "5": 0.2243845985047067,
            "50": 0.3966530726969129,
            "75": 0.42587156841183965,
            "95": 0.45888097653765797
          }
        },
        "specificity": 0.21428571428571427,
        "threshold": 0.24733698756646583
      }
    },
    "overall": {
      "FN": 5,
      "FP": 20,
      "TN": 42,
      "TP": 65,
      "accuracy": 0.8106060606060606,
      "average_precision": 0.8176095817934529,
      "balanced_accuracy": 0.8029953917050692,
      "count": 132,
      "f1": 0.8387096774193549,
      "false_positive_rate": 0.3225806451612903,
      "human_negative": 62,
      "human_positive": 70,
      "mcc": 0.6316150822354546,
      "negative_ratio": 0.4696969696969697,
      "negative_scores": {
        "count": 62,
        "mean": 0.20626897807482103,
        "median": 0.21251174220849703,
        "percentiles": {
          "0": 0.02344913470597548,
          "100": 0.45871986333511905,
          "25": 0.1076123859717677,
          "5": 0.030005714035794422,
          "50": 0.21251174220849703,
          "75": 0.28329998483562685,
          "95": 0.41098818463115067
        }
      },
      "positive_ratio": 0.5303030303030303,
      "positive_scores": {
        "count": 70,
        "mean": 0.3596950495025683,
        "median": 0.3893846057212579,
        "percentiles": {
          "0": 0.19906581886829045,
          "100": 0.4826871150228295,
          "25": 0.2901302780420383,
          "5": 0.22444639775591826,
          "50": 0.3893846057212579,
          "75": 0.4248802648015764,
          "95": 0.44971960723639315
        }
      },
      "precision": 0.7647058823529411,
      "recall": 0.9285714285714286,
      "roc_auc": 0.8412442396313364,
      "score_distribution": {
        "count": 132,
        "mean": 0.2876312886804446,
        "median": 0.29666026010959967,
        "percentiles": {
          "0": 0.02344913470597548,
          "100": 0.4826871150228295,
          "25": 0.2105619125256433,
          "5": 0.038934897215374076,
          "50": 0.29666026010959967,
          "75": 0.4061542874557255,
          "95": 0.44811164629467587
        }
      },
      "specificity": 0.6774193548387096,
      "threshold": 0.24733698756646583
    }
  },
  "semantic-v1": {
    "groups": {
      "EASY_NEGATIVE_CANDIDATE": {
        "FN": 0,
        "FP": 1,
        "TN": 17,
        "TP": 0,
        "accuracy": 0.9444444444444444,
        "average_precision": null,
        "balanced_accuracy": null,
        "count": 18,
        "f1": 0.0,
        "false_positive_rate": 0.05555555555555555,
        "human_negative": 18,
        "human_positive": 0,
        "mcc": null,
        "negative_ratio": 1.0,
        "negative_scores": {
          "count": 18,
          "mean": 0.5306768031895759,
          "median": 0.5353862872332846,
          "percentiles": {
            "0": 0.43281486749777986,
            "100": 0.6371670126336936,
            "25": 0.4931607428649852,
            "5": 0.4536757714927529,
            "50": 0.5353862872332846,
            "75": 0.5689871158619626,
            "95": 0.5912594198532963
          }
        },
        "positive_ratio": 0.0,
        "positive_scores": {
          "count": 0,
          "mean": null,
          "median": null,
          "percentiles": {}
        },
        "precision": 0.0,
        "recall": null,
        "roc_auc": null,
        "score_distribution": {
          "count": 18,
          "mean": 0.5306768031895759,
          "median": 0.5353862872332846,
          "percentiles": {
            "0": 0.43281486749777986,
            "100": 0.6371670126336936,
            "25": 0.4931607428649852,
            "5": 0.4536757714927529,
            "50": 0.5353862872332846,
            "75": 0.5689871158619626,
            "95": 0.5912594198532963
          }
        },
        "specificity": 0.9444444444444444,
        "threshold": 0.5867267674262028
      },
      "HARD_NEGATIVE_CANDIDATE": {
        "FN": 1,
        "FP": 19,
        "TN": 11,
        "TP": 29,
        "accuracy": 0.6666666666666666,
        "average_precision": 0.8008834496663835,
        "balanced_accuracy": 0.6666666666666666,
        "count": 60,
        "f1": 0.7435897435897436,
        "false_positive_rate": 0.6333333333333333,
        "human_negative": 30,
        "human_positive": 30,
        "mcc": 0.4166666666666667,
        "negative_ratio": 0.5,
        "negative_scores": {
          "count": 30,
          "mean": 0.5954161761097583,
          "median": 0.6029573855896729,
          "percentiles": {
            "0": 0.5164217314279558,
            "100": 0.6994389222388364,
            "25": 0.565230413991311,
            "5": 0.5225195291125487,
            "50": 0.6029573855896729,
            "75": 0.6186598640977461,
            "95": 0.6597493566887066
          }
        },
        "positive_ratio": 0.5,
        "positive_scores": {
          "count": 30,
          "mean": 0.6478192098904394,
          "median": 0.6420779008597344,
          "percentiles": {
            "0": 0.5536403638199675,
            "100": 0.7560300207393359,
            "25": 0.6192869581761004,
            "5": 0.5890703275436859,
            "50": 0.6420779008597344,
            "75": 0.6754619096810046,
            "95": 0.7325152068965842
          }
        },
        "precision": 0.6041666666666666,
        "recall": 0.9666666666666667,
        "roc_auc": 0.7977777777777778,
        "score_distribution": {
          "count": 60,
          "mean": 0.6216176930000988,
          "median": 0.6190716346269318,
          "percentiles": {
            "0": 0.5164217314279558,
            "100": 0.7560300207393359,
            "25": 0.5936005918669979,
            "5": 0.5340573386535779,
            "50": 0.6190716346269318,
            "75": 0.645205610164352,
            "95": 0.7217351235066268
          }
        },
        "specificity": 0.36666666666666664,
        "threshold": 0.5867267674262028
      },
      "POSITIVE_CANDIDATE": {
        "FN": 7,
        "FP": 9,
        "TN": 5,
        "TP": 33,
        "accuracy": 0.7037037037037037,
        "average_precision": 0.7857637830915896,
        "balanced_accuracy": 0.5910714285714286,
        "count": 54,
        "f1": 0.8048780487804879,
        "false_positive_rate": 0.6428571428571429,
        "human_negative": 14,
        "human_positive": 40,
        "mcc": 0.19199542936736588,
        "negative_ratio": 0.25925925925925924,
        "negative_scores": {
          "count": 14,
          "mean": 0.6133457427493573,
          "median": 0.6138752112439909,
          "percentiles": {
            "0": 0.5173834310399343,
            "100": 0.6906315195576421,
            "25": 0.5835292697731911,
            "5": 0.5199679465221578,
            "50": 0.6138752112439909,
            "75": 0.6630969694538468,
            "95": 0.6871026004905061
          }
        },
        "positive_ratio": 0.7407407407407407,
        "positive_scores": {
          "count": 40,
          "mean": 0.6330195398560587,
          "median": 0.644792090795737,
          "percentiles": {
            "0": 0.5305938562307524,
            "100": 0.7281100658165947,
            "25": 0.6074720004309194,
            "5": 0.5446210890949681,
            "50": 0.644792090795737,
            "75": 0.6594463520901751,
            "95": 0.6903374882140477
          }
        },
        "precision": 0.7857142857142857,
        "recall": 0.825,
        "roc_auc": 0.5946428571428571,
        "score_distribution": {
          "count": 54,
          "mean": 0.6279189257913584,
          "median": 0.638416721234115,
          "percentiles": {
            "0": 0.5173834310399343,
            "100": 0.7281100658165947,
            "25": 0.5988725064063214,
            "5": 0.5344954437821163,
            "50": 0.638416721234115,
            "75": 0.6601538910852749,
            "95": 0.6901664689653099
          }
        },
        "specificity": 0.35714285714285715,
        "threshold": 0.5867267674262028
      }
    },
    "overall": {
      "FN": 8,
      "FP": 29,
      "TN": 33,
      "TP": 62,
      "accuracy": 0.7196969696969697,
      "average_precision": 0.7780796849122736,
      "balanced_accuracy": 0.7089861751152073,
      "count": 132,
      "f1": 0.7701863354037267,
      "false_positive_rate": 0.46774193548387094,
      "human_negative": 62,
      "human_positive": 70,
      "mcc": 0.4507957297422995,
      "negative_ratio": 0.4696969696969697,
      "negative_scores": {
        "count": 62,
        "mean": 0.5806694861160664,
        "median": 0.5840086405050338,
        "percentiles": {
          "0": 0.43281486749777986,
          "100": 0.6994389222388364,
          "25": 0.5515560567906937,
          "5": 0.48239103352126644,
          "50": 0.5840086405050338,
          "75": 0.615853965551703,
          "95": 0.6749099367689368
        }
      },
      "positive_ratio": 0.5303030303030303,
      "positive_scores": {
        "count": 70,
        "mean": 0.6393622555850791,
        "median": 0.6433267067552431,
        "percentiles": {
          "0": 0.5305938562307524,
          "100": 0.7560300207393359,
          "25": 0.6116627090562695,
          "5": 0.5573768074962083,
          "50": 0.6433267067552431,
          "75": 0.6658300805101734,
          "95": 0.7250800965229977
        }
      },
      "precision": 0.6813186813186813,
      "recall": 0.8857142857142857,
      "roc_auc": 0.7868663594470046,
      "score_distribution": {
        "count": 132,
        "mean": 0.611794439622361,
        "median": 0.6184228999252857,
        "percentiles": {
          "0": 0.43281486749777986,
          "100": 0.7560300207393359,
          "25": 0.5697204997181233,
          "5": 0.5098740123320481,
          "50": 0.6184228999252857,
          "75": 0.6520709274885115,
          "95": 0.6941024414105869
        }
      },
      "specificity": 0.532258064516129,
      "threshold": 0.5867267674262028
    }
  }
}

## 10. Held-out Test Results

| Metric | Semantic-v1 | Frozen offline lexical baseline |
|---|---:|---:|
| TP | 39 | 39 |
| TN | 20 | 28 |
| FP | 22 | 14 |
| FN | 7 | 7 |
| precision | 0.639344262295082 | 0.7358490566037735 |
| recall | 0.8478260869565217 | 0.8478260869565217 |
| f1 | 0.7289719626168224 | 0.7878787878787878 |
| accuracy | 0.6704545454545454 | 0.7613636363636364 |
| specificity | 0.47619047619047616 | 0.6666666666666666 |
| balanced_accuracy | 0.6620082815734989 | 0.7572463768115942 |
| roc_auc | 0.7613871635610766 | 0.8198757763975155 |
| average_precision | 0.7842970684117562 | 0.8262522382511788 |

## 11. Hard Negative Held-out Results

{
  "baseline-v1": {
    "count": 40,
    "human_positive": 18,
    "human_negative": 22,
    "positive_ratio": 0.45,
    "negative_ratio": 0.55,
    "TP": 12,
    "TN": 15,
    "FP": 7,
    "FN": 6,
    "threshold": 0.24733698756646583,
    "precision": 0.631578947368421,
    "recall": 0.6666666666666666,
    "f1": 0.6486486486486487,
    "accuracy": 0.675,
    "specificity": 0.6818181818181818,
    "false_positive_rate": 0.3181818181818182,
    "balanced_accuracy": 0.6742424242424242,
    "mcc": 0.3471722831863234,
    "roc_auc": 0.6616161616161617,
    "average_precision": 0.6311893469981705,
    "score_distribution": {
      "count": 40,
      "mean": 0.2736249028892755,
      "median": 0.23957060712383696,
      "percentiles": {
        "0": 0.09015233988122275,
        "5": 0.15049607699314882,
        "25": 0.2065796149115596,
        "50": 0.23957060712383696,
        "75": 0.3764761844823965,
        "95": 0.4137754190825565,
        "100": 0.4170285565026649
      }
    },
    "positive_scores": {
      "count": 18,
      "mean": 0.2994360991150427,
      "median": 0.3179170179423544,
      "percentiles": {
        "0": 0.09015233988122275,
        "5": 0.14320518190863885,
        "25": 0.23076664447611062,
        "50": 0.3179170179423544,
        "75": 0.38434720796303823,
        "95": 0.4147194977391981,
        "100": 0.4170285565026649
      }
    },
    "negative_scores": {
      "count": 22,
      "mean": 0.25250665143182954,
      "median": 0.22567394864705448,
      "percentiles": {
        "0": 0.13628216999176745,
        "5": 0.1522386428573815,
        "25": 0.19568696135950506,
        "50": 0.22567394864705448,
        "75": 0.28365989304912714,
        "95": 0.401478579871291,
        "100": 0.4137471770984311
      }
    }
  },
  "semantic-v1": {
    "count": 40,
    "human_positive": 18,
    "human_negative": 22,
    "positive_ratio": 0.45,
    "negative_ratio": 0.55,
    "TP": 14,
    "TN": 9,
    "FP": 13,
    "FN": 4,
    "threshold": 0.5867267674262028,
    "precision": 0.5185185185185185,
    "recall": 0.7777777777777778,
    "f1": 0.6222222222222222,
    "accuracy": 0.575,
    "specificity": 0.4090909090909091,
    "false_positive_rate": 0.5909090909090909,
    "balanced_accuracy": 0.5934343434343434,
    "mcc": 0.19848631482949888,
    "roc_auc": 0.6994949494949495,
    "average_precision": 0.7251300133411723,
    "score_distribution": {
      "count": 40,
      "mean": 0.6088060699690904,
      "median": 0.606354051183358,
      "percentiles": {
        "0": 0.5138906922940993,
        "5": 0.5306086732428064,
        "25": 0.5812110499388182,
        "50": 0.606354051183358,
        "75": 0.6341361253270075,
        "95": 0.6850223681488586,
        "100": 0.7060130025747311
      }
    },
    "positive_scores": {
      "count": 18,
      "mean": 0.6270560412088664,
      "median": 0.6173314184777429,
      "percentiles": {
        "0": 0.5304236742205632,
        "5": 0.5567240152863766,
        "25": 0.6050660613708826,
        "50": 0.6173314184777429,
        "75": 0.6700051227370531,
        "95": 0.7045492056946067,
        "100": 0.7060130025747311
      }
    },
    "negative_scores": {
      "count": 22,
      "mean": 0.5938742753183646,
      "median": 0.5923218052347259,
      "percentiles": {
        "0": 0.5138906922940993,
        "5": 0.5322644299516867,
        "25": 0.5751797007046684,
        "50": 0.5923218052347259,
        "75": 0.6217024909087955,
        "95": 0.6391199102161544,
        "100": 0.6478439475480242
      }
    }
  }
}

## 12. Easy Negative Held-out Results

{
  "baseline-v1": {
    "count": 12,
    "human_positive": 0,
    "human_negative": 12,
    "positive_ratio": 0.0,
    "negative_ratio": 1.0,
    "TP": 0,
    "TN": 12,
    "FP": 0,
    "FN": 0,
    "threshold": 0.24733698756646583,
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
      "count": 12,
      "mean": 0.0888023567628108,
      "median": 0.04815981293054086,
      "percentiles": {
        "0": 0.03445471897358548,
        "5": 0.03519427042674359,
        "25": 0.04161991321108025,
        "50": 0.04815981293054086,
        "75": 0.14191292829866814,
        "95": 0.1906099912753974,
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
      "count": 12,
      "mean": 0.0888023567628108,
      "median": 0.04815981293054086,
      "percentiles": {
        "0": 0.03445471897358548,
        "5": 0.03519427042674359,
        "25": 0.04161991321108025,
        "50": 0.04815981293054086,
        "75": 0.14191292829866814,
        "95": 0.1906099912753974,
        "100": 0.19448224733772965
      }
    }
  },
  "semantic-v1": {
    "count": 12,
    "human_positive": 0,
    "human_negative": 12,
    "positive_ratio": 0.0,
    "negative_ratio": 1.0,
    "TP": 0,
    "TN": 10,
    "FP": 2,
    "FN": 0,
    "threshold": 0.5867267674262028,
    "precision": 0.0,
    "recall": null,
    "f1": 0.0,
    "accuracy": 0.8333333333333334,
    "specificity": 0.8333333333333334,
    "false_positive_rate": 0.16666666666666666,
    "balanced_accuracy": null,
    "mcc": null,
    "roc_auc": null,
    "average_precision": null,
    "score_distribution": {
      "count": 12,
      "mean": 0.5242860733448069,
      "median": 0.5107263036054384,
      "percentiles": {
        "0": 0.4594491696069742,
        "5": 0.46689508479374575,
        "25": 0.4991145431121963,
        "50": 0.5107263036054384,
        "75": 0.5481137334752303,
        "95": 0.611030640168166,
        "100": 0.6228403566921057
      }
    },
    "positive_scores": {
      "count": 0,
      "mean": null,
      "median": null,
      "percentiles": {}
    },
    "negative_scores": {
      "count": 12,
      "mean": 0.5242860733448069,
      "median": 0.5107263036054384,
      "percentiles": {
        "0": 0.4594491696069742,
        "5": 0.46689508479374575,
        "25": 0.4991145431121963,
        "50": 0.5107263036054384,
        "75": 0.5481137334752303,
        "95": 0.611030640168166,
        "100": 0.6228403566921057
      }
    }
  }
}

## 13. Positive Candidate Held-out Results

{
  "baseline-v1": {
    "count": 36,
    "human_positive": 28,
    "human_negative": 8,
    "positive_ratio": 0.7777777777777778,
    "negative_ratio": 0.2222222222222222,
    "TP": 27,
    "TN": 1,
    "FP": 7,
    "FN": 1,
    "threshold": 0.24733698756646583,
    "precision": 0.7941176470588235,
    "recall": 0.9642857142857143,
    "f1": 0.8709677419354839,
    "accuracy": 0.7777777777777778,
    "specificity": 0.125,
    "false_positive_rate": 0.875,
    "balanced_accuracy": 0.5446428571428572,
    "mcc": 0.1620509308880411,
    "roc_auc": 0.75,
    "average_precision": 0.9169641036208432,
    "score_distribution": {
      "count": 36,
      "mean": 0.3561502201551325,
      "median": 0.3381577222049036,
      "percentiles": {
        "0": 0.23609874455862023,
        "5": 0.2515563244974145,
        "25": 0.29012456089308614,
        "50": 0.3381577222049036,
        "75": 0.4256250267604368,
        "95": 0.45439159379730126,
        "100": 0.479674312129205
      }
    },
    "positive_scores": {
      "count": 28,
      "mean": 0.37127920147817806,
      "median": 0.3968802595643257,
      "percentiles": {
        "0": 0.23609874455862023,
        "5": 0.25995537905576477,
        "25": 0.309765897567299,
        "50": 0.3968802595643257,
        "75": 0.430596544969997,
        "95": 0.46574327971195795,
        "100": 0.479674312129205
      }
    },
    "negative_scores": {
      "count": 8,
      "mean": 0.303198785524473,
      "median": 0.29259666864925354,
      "percentiles": {
        "0": 0.23941197010415993,
        "5": 0.2452405452958939,
        "25": 0.263838386444043,
        "50": 0.29259666864925354,
        "75": 0.3218323246858269,
        "95": 0.39421615472366045,
        "100": 0.42633043541098403
      }
    }
  },
  "semantic-v1": {
    "count": 36,
    "human_positive": 28,
    "human_negative": 8,
    "positive_ratio": 0.7777777777777778,
    "negative_ratio": 0.2222222222222222,
    "TP": 25,
    "TN": 1,
    "FP": 7,
    "FN": 3,
    "threshold": 0.5867267674262028,
    "precision": 0.78125,
    "recall": 0.8928571428571429,
    "f1": 0.8333333333333334,
    "accuracy": 0.7222222222222222,
    "specificity": 0.125,
    "false_positive_rate": 0.875,
    "balanced_accuracy": 0.5089285714285714,
    "mcc": 0.0236227795630767,
    "roc_auc": 0.5982142857142857,
    "average_precision": 0.847691120158488,
    "score_distribution": {
      "count": 36,
      "mean": 0.630550132261032,
      "median": 0.6251034139703529,
      "percentiles": {
        "0": 0.49234342290780964,
        "5": 0.5580756023930196,
        "25": 0.6054838280672687,
        "50": 0.6251034139703529,
        "75": 0.659303287326247,
        "95": 0.6927477950834231,
        "100": 0.7654083740190964
      }
    },
    "positive_scores": {
      "count": 28,
      "mean": 0.6336333913095347,
      "median": 0.6274900887835695,
      "percentiles": {
        "0": 0.49234342290780964,
        "5": 0.571420449259138,
        "25": 0.6066479773955604,
        "50": 0.6274900887835695,
        "75": 0.6630543853465025,
        "95": 0.6927999387321784,
        "100": 0.7654083740190964
      }
    },
    "negative_scores": {
      "count": 8,
      "mean": 0.6197587255912721,
      "median": 0.6154909771618836,
      "percentiles": {
        "0": 0.5371062860271915,
        "5": 0.5574273966723746,
        "25": 0.6024526263177266,
        "50": 0.6154909771618836,
        "75": 0.6484841516320263,
        "95": 0.6769213222339775,
        "100": 0.689160450035321
      }
    }
  }
}

## 14. Error Overlap

{
  "error_overlap": {
    "BASELINE_ONLY_CORRECT": 14,
    "BOTH_CORRECT": 53,
    "BOTH_WRONG": 15,
    "SEMANTIC_ONLY_CORRECT": 6
  },
  "hard_negative_head_to_head": {
    "human_negatives": 22,
    "semantic_fp": 13,
    "baseline_fp": 7,
    "both_fp": 5,
    "semantic_only_fp": 8,
    "baseline_only_fp": 2
  }
}

## 15. False Positive Analysis

Test-only FP CSVs use fixed thresholds, sorted highest score first. Human reasons are diagnostic only.

## 16. False Negative Analysis

Test-only FN CSVs sorted lowest score first. No annotation revision or post-test tuning.

## 17. Ranking vs Classification

ROC-AUC/AP use continuous test scores; classification uses calibration-frozen thresholds. Easy groups cannot establish hard-case superiority.

## 18. Confidence / Uncertainty

{
  "seed": 42,
  "resamples": 1000,
  "method": "paired row percentile bootstrap after grouping; thresholds fixed",
  "limitation": "Rows sharing entities inside test are dependent; row intervals may understate uncertainty.",
  "intervals": {
    "baseline-v1": {
      "precision": {
        "low": 0.6110294117647059,
        "high": 0.8518518518518519,
        "valid_resamples": 1000
      },
      "recall": {
        "low": 0.7333333333333333,
        "high": 0.9512195121951219,
        "valid_resamples": 1000
      },
      "f1": {
        "low": 0.6874842171717171,
        "high": 0.8703932893289329,
        "valid_resamples": 1000
      },
      "roc_auc": {
        "low": 0.7215789473684211,
        "high": 0.908398033126294,
        "valid_resamples": 1000
      },
      "average_precision": {
        "low": 0.7100403823947873,
        "high": 0.9205144109936866,
        "valid_resamples": 1000
      }
    },
    "semantic-v1": {
      "precision": {
        "low": 0.5166406250000001,
        "high": 0.7636631016042781,
        "valid_resamples": 1000
      },
      "recall": {
        "low": 0.7346598639455783,
        "high": 0.95,
        "valid_resamples": 1000
      },
      "f1": {
        "low": 0.6226415094339622,
        "high": 0.8160166666666666,
        "valid_resamples": 1000
      },
      "roc_auc": {
        "low": 0.6542408936818875,
        "high": 0.8516498283305006,
        "valid_resamples": 1000
      },
      "average_precision": {
        "low": 0.6654269892114529,
        "high": 0.8848938157634424,
        "valid_resamples": 1000
      }
    }
  },
  "paired_f1_delta_baseline_minus_semantic": {
    "low": -0.02560896768370997,
    "high": 0.15114056260333508,
    "valid_resamples": 1000
  }
}

## 19. Algorithm Selection Assessment

Interpret measured test tradeoffs and uncertainty; no automatic winner or production switch. Retrospective/transductive limitations prevent confirmatory deployment claims.

## 20. Recommended Next Step

Collect genuinely unseen independent labels and calibrate/evaluate frozen models on grouped data. No hybrid or next-step implementation here.

## Critical validity limitations

Retrospective partition: all 220 labels previously analyzed.
Frozen baseline IDF used the full corpus: transductive covariate exposure.
Not a new blind external or fully inductive test.
Single reviewer; difficulty-focused small sample; shared-entity test rows; no representative prevalence/per-job ranking pool; extraction quality not evaluated.
