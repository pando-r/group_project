from __future__ import annotations

from app.rules.base import RuleVersionInfo

ACTIVE_RULE_VERSION = "rules-2026.11.1"

RULE_VERSION_INFO = RuleVersionInfo(
    version=ACTIVE_RULE_VERSION,
    changelog="演示首版：8 个病种确定性评分、统一三层输出与规则级引用。",
)

# Sources are intentionally limited to named, published classifications and
# guidelines. Percentages produced by this demo engine are composites and are
# never presented as externally calibrated probabilities.
SOURCES = {
    "ao_ota_2018": "AO/OTA 2018 股骨近端骨折分型",
    "asa": "ASA Physical Status Classification System",
    "kl_1957": "Kellgren-Lawrence 骨关节炎分级（1957）",
    "lung_rads_11": "Lung-RADS v1.1（2019）",
    "ajcc_tnm8": "AJCC 第 8 版 TNM 分期（2017）",
    "rcri_1999": "Revised Cardiac Risk Index（Lee et al., 1999）",
    "child_pugh_1973": "Child-Pugh 分级（1973）",
    "bclc_2022": "BCLC 分期更新（2022）",
    "cnlc_2022": "中国肝癌临床分期与治疗规范（2022）",
    "tg18": "Tokyo Guidelines 2018（TG18）",
    "damico_1998": "D'Amico 前列腺癌风险分层（1998）",
    "capra_2005": "CAPRA 评分（Cooperberg et al., 2005）",
    "gss_2011": "Guy's Stone Score（Thomas et al., 2011）",
}

# Tone is restricted to risk semantics. These values are data, not UI styling.
RISK_DISCLAIMER = "演示模型，未经校准，不替代医生决策"
