from __future__ import annotations

from typing import Any

from app.rules.base import (
    BasisItem,
    DiseaseDefinition,
    EvaluationResult,
    FieldOption,
    FieldSpec,
    PrognosisMetric,
    PrognosisResult,
    Recommendation,
    RedFlag,
    ResultMeta,
    RiskDriver,
    RiskResult,
    SeverityResult,
    make_risk_cuts,
    make_scale,
    rule_citation,
    tier_for_percent,
    tone_for_level,
    tone_for_tier,
    validate_fields,
)
from app.rules.constants import ACTIVE_RULE_VERSION, RULE_VERSION_INFO, SOURCES

HIP_DEFINITION = DiseaseDefinition(
    id="hip_fracture",
    name="髋部骨折围手术期风险评估",
    short_name="髋部骨折",
    specialty="orthopedics",
    specialty_label="骨科",
    summary="结合 AO/OTA 分型、ASA 分级、血红蛋白与年龄评估围手术期风险。",
    sources=[SOURCES["ao_ota_2018"], SOURCES["asa"]],
    fields=[
        FieldSpec(key="age", label="年龄", type="integer", unit="岁", minimum=18, maximum=120),
        FieldSpec(
            key="asa",
            label="ASA 分级",
            type="select",
            options=[
                FieldOption(value="I", label="I 级：健康"),
                FieldOption(value="II", label="II 级：轻度系统性疾病"),
                FieldOption(value="III", label="III 级：重度系统性疾病"),
                FieldOption(value="IV", label="IV 级：持续威胁生命"),
            ],
        ),
        FieldSpec(
            key="hemoglobin",
            label="血红蛋白",
            type="number",
            unit="g/L",
            minimum=30,
            maximum=200,
            step=1,
        ),
        FieldSpec(
            key="fracture_type",
            label="AO/OTA 分型",
            type="select",
            options=[
                FieldOption(value="31A", label="31A：转子间稳定型"),
                FieldOption(value="31B", label="31B：转子间不稳定型"),
                FieldOption(value="31C", label="31C：股骨颈骨折"),
                FieldOption(value="32", label="32：转子下骨折"),
            ],
        ),
    ],
)

_HIP_LABELS = ["低危", "中危", "高危", "极高危"]
_HIP_ASA_POINTS = {"I": 0, "II": 1, "III": 3, "IV": 5}


def evaluate_hip_fracture(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(HIP_DEFINITION, raw_fields)
    age: int = fields["age"]
    asa: str = fields["asa"]
    hb: float = fields["hemoglobin"]
    fracture_type: str = fields["fracture_type"]

    age_points = 3 if age >= 80 else 1 if age >= 65 else 0
    anemia_points = 4 if hb < 70 else 3 if hb < 90 else 1 if hb < 110 else 0
    fracture_points = 2 if fracture_type in {"31B", "32"} else 1 if fracture_type == "31C" else 0
    asa_points = _HIP_ASA_POINTS[asa]
    total = age_points + anemia_points + fracture_points + asa_points

    if total >= 9:
        level = 4
    elif total >= 6:
        level = 3
    elif total >= 3:
        level = 2
    else:
        level = 1

    percent = round(min(60.0, 4 + asa_points * 3.4 + anemia_points * 2.8 + age_points * 1.5), 1)
    tier = tier_for_percent(percent)

    drivers = [
        RiskDriver(
            label="ASA 分级",
            direction="increase" if asa_points else "decrease",
            detail=f"ASA {asa}，麻醉与围手术期风险权重 {asa_points} 分",
        ),
        RiskDriver(
            label="术前贫血",
            direction="increase" if anemia_points else "decrease",
            detail=f"血红蛋白 {hb:g} g/L，贫血权重 {anemia_points} 分",
        ),
        RiskDriver(
            label="骨折稳定性",
            direction="increase" if fracture_points else "decrease",
            detail=f"AO/OTA {fracture_type}，分型权重 {fracture_points} 分",
        ),
    ]

    recommendations = [
        Recommendation(
            id="hip.early_surgery",
            text="在可耐受的前提下尽早完成手术，减少卧床相关并发症；具体时机由骨科、麻醉与内科共同决定。",
            priority="urgent" if level >= 3 else "consider",
            citations=[rule_citation("hip.timing", "髋部骨折早期手术原则")],
        ),
        Recommendation(
            id="hip.anemia",
            text="评估贫血原因与输血指征，纠正可逆因素后复核血红蛋白。"
            if hb >= 90
            else "血红蛋白偏低，需尽快评估输血及术前优化方案。",
            priority="urgent" if hb < 70 else "consider",
            citations=[rule_citation("hip.hemoglobin", "术前血红蛋白分层")],
        ),
        Recommendation(
            id="hip.co_manage",
            text="建议老年医学科/内科共同管理，评估谵妄、压疮、静脉血栓与跌倒风险。",
            priority="consider",
            citations=[rule_citation("hip.orthogeriatric", "老年髋部骨折共管原则")],
        ),
        Recommendation(
            id="hip.mobilization",
            text="术后尽早活动并落实静脉血栓预防；具体药物与机械预防由治疗团队决定。",
            priority="routine",
            citations=[rule_citation("hip.vte", "髋部骨折 VTE 预防原则")],
        ),
    ]

    red_flags = []
    if hb < 70:
        red_flags.append(
            RedFlag(code="HIP_SEVERE_ANEMIA", text="血红蛋白 <70 g/L，需紧急评估输血。", severity="critical")
        )
    if asa == "IV":
        red_flags.append(
            RedFlag(code="HIP_ASA_IV", text="ASA IV 级，麻醉与手术风险显著升高。", severity="critical")
        )
    if age >= 90:
        red_flags.append(
            RedFlag(code="HIP_VERY_OLD", text="高龄（≥90 岁），需加强围手术期综合评估。", severity="warning")
        )

    prognosis_tier = "较差" if level >= 4 else "需密切观察" if level == 3 else "总体可控"
    return EvaluationResult(
        severity=SeverityResult(
            grade=_HIP_LABELS[level - 1],
            level=level,
            tone=tone_for_level(level),
            scale=make_scale(_HIP_LABELS),
            basis=[
                BasisItem(id="hip.age", label="年龄", value=f"{age} 岁", source="年龄分层"),
                BasisItem(id="hip.asa", label="ASA 分级", value=asa, source=SOURCES["asa"]),
                BasisItem(
                    id="hip.hemoglobin",
                    label="血红蛋白",
                    value=f"{hb:g} g/L",
                    source="术前贫血分层",
                ),
                BasisItem(
                    id="hip.fracture",
                    label="AO/OTA 分型",
                    value=fracture_type,
                    source=SOURCES["ao_ota_2018"],
                ),
            ],
            summary=f"综合年龄、ASA、贫血与骨折稳定性，严重程度为{_HIP_LABELS[level - 1]}（{total} 分）。",
        ),
        risk=RiskResult(
            label="围手术期重大并发症风险",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 10, "低"), (10, 20, "中"), (20, 35, "高"), (35, 100, "极高")]),
            drivers=drivers,
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准，仅用于风险沟通与流程演示。",
        ),
        prognosis=PrognosisResult(
            tier=prognosis_tier,
            summary="预后取决于手术时机、合并症控制与早期康复；以下指标为演示估计。",
            metrics=[
                PrognosisMetric(label="预计住院时长", value="7–14 天", note="演示估计"),
                PrognosisMetric(label="术后 1 年功能目标", value="恢复伤前行走能力", note="个体差异大"),
            ],
        ),
        recommendations=recommendations,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=HIP_DEFINITION.id,
            disease_name=HIP_DEFINITION.name,
            specialty=HIP_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


KNEE_DEFINITION = DiseaseDefinition(
    id="knee_oa",
    name="膝骨关节炎严重程度与进展风险",
    short_name="膝骨关节炎",
    specialty="orthopedics",
    specialty_label="骨科",
    summary="依据 K-L 分级、疼痛评分、年龄与 BMI 评估严重程度及进展风险。",
    sources=[SOURCES["kl_1957"]],
    fields=[
        FieldSpec(
            key="kl_grade",
            label="Kellgren-Lawrence 分级",
            type="select",
            options=[
                FieldOption(value="0", label="0 级：无骨质增生"),
                FieldOption(value="1", label="1 级：可疑关节间隙狭窄"),
                FieldOption(value="2", label="2 级：轻度骨赘"),
                FieldOption(value="3", label="3 级：关节间隙明显狭窄"),
                FieldOption(value="4", label="4 级：骨磨损、关节间隙消失"),
            ],
        ),
        FieldSpec(key="pain_vas", label="疼痛 VAS", type="integer", unit="分", minimum=0, maximum=10),
        FieldSpec(key="age", label="年龄", type="integer", unit="岁", minimum=18, maximum=100),
        FieldSpec(key="bmi", label="BMI", type="number", unit="kg/m²", minimum=12, maximum=60, step=0.1),
    ],
)

_KNEE_LABELS = ["轻度", "中度", "重度", "终末期"]


def evaluate_knee_oa(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(KNEE_DEFINITION, raw_fields)
    kl = int(fields["kl_grade"])
    vas: int = fields["pain_vas"]
    age: int = fields["age"]
    bmi: float = fields["bmi"]

    kl_points = {0: 0, 1: 0, 2: 2, 3: 4, 4: 6}[kl]
    pain_points = 2 if vas >= 7 else 1 if vas >= 4 else 0
    bmi_points = 1 if bmi >= 35 else 0.5 if bmi >= 30 else 0
    total = kl_points + pain_points + bmi_points
    level = 4 if total >= 6 else 3 if total >= 4 else 2 if total >= 2 else 1

    percent = round(
        min(70.0, 3 + kl * 8 + vas * 1.5 + max(0.0, bmi - 25) * 0.8 + (2 if age >= 70 else 0)),
        1,
    )
    tier = tier_for_percent(percent)

    recs = [
        Recommendation(
            id="knee.exercise",
            text="以股四头肌力量训练、低冲击有氧运动与体重管理为基础治疗；由康复科制定个体化方案。",
            priority="routine",
            citations=[rule_citation("knee.conservative", "膝骨关节炎基础治疗")],
        ),
        Recommendation(
            id="knee.analgesia",
            text="在评估胃肠道、肾脏与心血管风险后，考虑短期外用或口服镇痛；不自行长期使用。",
            priority="consider" if vas >= 4 else "routine",
            citations=[rule_citation("knee.pain", "疼痛管理原则")],
        ),
        Recommendation(
            id="knee.surgery",
            text="若影像为 K-L 3–4 级且疼痛显著影响生活，转诊关节外科评估关节置换。",
            priority="consider" if level >= 3 else "routine",
            citations=[rule_citation("knee.kl", SOURCES["kl_1957"])],
        ),
    ]
    if bmi >= 30:
        recs.append(
            Recommendation(
                id="knee.weight",
                text="BMI 升高与症状进展相关，建议设定渐进式减重目标并随访。",
                priority="consider",
                citations=[rule_citation("knee.bmi", "BMI 与膝骨关节炎负荷")],
            )
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=_KNEE_LABELS[level - 1],
            level=level,
            tone=tone_for_level(level),
            scale=make_scale(_KNEE_LABELS),
            basis=[
                BasisItem(id="knee.kl", label="K-L 分级", value=f"{kl} 级", source=SOURCES["kl_1957"]),
                BasisItem(id="knee.vas", label="疼痛 VAS", value=f"{vas} 分", source="疼痛评分"),
                BasisItem(id="knee.bmi", label="BMI", value=f"{bmi:g}", source="体重负荷"),
            ],
            summary=f"以 K-L {kl} 级与 VAS {vas} 分为主，严重程度为{_KNEE_LABELS[level - 1]}。",
        ),
        risk=RiskResult(
            label="进展至关节置换的风险（演示）",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 15, "低"), (15, 30, "中"), (30, 50, "高"), (50, 100, "极高")]),
            drivers=[
                RiskDriver(
                    label="影像分级",
                    direction="increase" if kl >= 2 else "decrease",
                    detail=f"K-L {kl} 级，结构改变权重 {kl_points} 分",
                ),
                RiskDriver(
                    label="疼痛负荷",
                    direction="increase" if pain_points else "decrease",
                    detail=f"VAS {vas} 分，疼痛权重 {pain_points} 分",
                ),
                RiskDriver(
                    label="BMI",
                    direction="increase" if bmi_points else "decrease",
                    detail=f"BMI {bmi:g}，体重负荷权重 {bmi_points:g} 分",
                ),
            ],
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准。",
        ),
        prognosis=PrognosisResult(
            tier=_KNEE_LABELS[level - 1],
            summary="通过运动、体重与疼痛管理可延缓功能下降；终末期可评估关节置换。",
            metrics=[
                PrognosisMetric(label="保守治疗目标", value="维持行走与日常活动", note="演示估计"),
                PrognosisMetric(
                    label="随访建议", value="3–6 个月" if level <= 2 else "2–3 个月", note="按症状调整"
                ),
            ],
        ),
        recommendations=recs,
        red_flags=(
            [RedFlag(code="KNEE_SEVERE_PAIN", text="VAS ≥7，需尽快评估镇痛与功能支持。", severity="warning")]
            if vas >= 7
            else []
        ),
        meta=ResultMeta(
            disease_id=KNEE_DEFINITION.id,
            disease_name=KNEE_DEFINITION.name,
            specialty=KNEE_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


# Keep the changelog reachable from tests and seed code without duplicating it.
__all__ = [
    "HIP_DEFINITION",
    "KNEE_DEFINITION",
    "RULE_VERSION_INFO",
    "evaluate_hip_fracture",
    "evaluate_knee_oa",
]
