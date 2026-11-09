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
    guideline_citation,
    make_risk_cuts,
    make_scale,
    rule_citation,
    tier_for_percent,
    tone_for_level,
    tone_for_tier,
    validate_fields,
)
from app.rules.constants import ACTIVE_RULE_VERSION, SOURCES

NODULE_DEFINITION = DiseaseDefinition(
    id="pulmonary_nodule",
    name="肺结节恶性风险分层",
    short_name="肺结节",
    specialty="thoracic",
    specialty_label="胸外科",
    summary="依据 Lung-RADS 1.1 的结节类型、大小与生长情况给出随访分层。",
    sources=[SOURCES["lung_rads_11"]],
    fields=[
        FieldSpec(
            key="nodule_type",
            label="结节类型",
            type="select",
            options=[
                FieldOption(value="solid", label="实性结节"),
                FieldOption(value="part_solid", label="部分实性结节"),
                FieldOption(value="ground_glass", label="纯磨玻璃结节"),
            ],
        ),
        FieldSpec(
            key="diameter_mm",
            label="最大径",
            type="number",
            unit="mm",
            minimum=1,
            maximum=150,
            step=0.1,
        ),
        FieldSpec(key="growth", label="较前增大", type="boolean", default=False),
        FieldSpec(
            key="age",
            label="年龄",
            type="integer",
            unit="岁",
            minimum=18,
            maximum=100,
        ),
        FieldSpec(
            key="smoking_pack_years",
            label="吸烟包年",
            type="number",
            unit="包年",
            minimum=0,
            maximum=200,
            default=0,
            required=False,
            step=1,
        ),
    ],
)

_NODULE_LABELS = [
    "Lung-RADS 1",
    "Lung-RADS 2",
    "Lung-RADS 3",
    "Lung-RADS 4A",
    "Lung-RADS 4B",
]
_NODULE_TONES = ["success", "success", "warning", "danger", "danger"]  # type: ignore[list-item]


def evaluate_pulmonary_nodule(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(NODULE_DEFINITION, raw_fields)
    nodule_type: str = fields["nodule_type"]
    size: float = fields["diameter_mm"]
    growth: bool = fields["growth"]
    age: int = fields["age"]
    pack_years: float = fields["smoking_pack_years"]

    if nodule_type == "solid":
        if size < 6:
            category = "2"
        elif size < 8:
            category = "3"
        elif size < 15:
            category = "4A"
        else:
            category = "4B"
    elif nodule_type == "part_solid":
        if size < 6:
            category = "2"
        elif size < 15:
            category = "3"
        else:
            category = "4A"
    else:
        category = "2" if size < 20 else "3"

    category_order = ["1", "2", "3", "4A", "4B"]
    if growth and category != "4B":
        category = category_order[min(category_order.index(category) + 1, 4)]

    category_level = {"2": 2, "3": 3, "4A": 4, "4B": 5}[category]
    base_risk = {"2": 0.8, "3": 1.5, "4A": 10.0, "4B": 25.0}[category]
    modifiers = 3.0 if pack_years >= 30 else 0.0
    modifiers += 2.0 if growth else 0.0
    modifiers += 1.0 if age >= 70 else 0.0
    percent = round(min(80.0, base_risk + modifiers), 1)
    tier = tier_for_percent(percent)

    drivers = [
        RiskDriver(
            label="结节大小与类型",
            direction="increase",
            detail=f"{nodule_type}，最大径 {size:g} mm；Lung-RADS 分类赋权",
        ),
        RiskDriver(
            label="间隔生长",
            direction="increase" if growth else "decrease",
            detail="较前增大时上调分类" if growth else "未见生长信息",
        ),
        RiskDriver(
            label="吸烟暴露",
            direction="increase" if pack_years >= 30 else "decrease",
            detail=f"{pack_years:g} 包年",
        ),
    ]

    if category in {"2", "3"}:
        follow_up = "按 Lung-RADS 复查低剂量胸部 CT。"
    elif category == "4A":
        follow_up = "考虑 3 个月复查或 PET/CT，并由胸外科/呼吸科评估。"
    else:
        follow_up = "尽快完成增强 CT/PET-CT 与活检或多学科评估。"

    recs = [
        Recommendation(
            id="nodule.follow_up",
            text=follow_up,
            priority="urgent" if category == "4B" else "consider" if category == "4A" else "routine",
            citations=[guideline_citation("lung-rads-1.1", SOURCES["lung_rads_11"])],
        ),
        Recommendation(
            id="nodule.risk_factors",
            text="结合吸烟史、职业暴露、既往肿瘤史与家族史复核风险，不单凭结节大小决策。",
            priority="consider",
            citations=[rule_citation("nodule.risk_factors", "肺癌风险因素复核")],
        ),
    ]
    if growth:
        recs.append(
            Recommendation(
                id="nodule.growth",
                text="记录体积倍增时间与形态变化；若随访间期明显增大，缩短复查间隔或直接评估病理。",
                priority="urgent" if category == "4B" else "consider",
                citations=[guideline_citation("lung-rads-growth", "Lung-RADS 生长评估")],
            )
        )

    red_flags = []
    if category == "4B":
        red_flags.append(
            RedFlag(
                code="NODULE_4B", text="Lung-RADS 4B，高度可疑恶性，应尽快完成诊断路径。", severity="critical"
            )
        )
    elif growth:
        red_flags.append(
            RedFlag(code="NODULE_GROWTH", text="结节较前增大，需缩短随访或进一步检查。", severity="warning")
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=f"Lung-RADS {category}",
            level=category_level,
            tone=_NODULE_TONES[category_level - 2],
            scale=make_scale(_NODULE_LABELS),
            basis=[
                BasisItem(
                    id="nodule.size",
                    label="最大径",
                    value=f"{size:g} mm",
                    source=SOURCES["lung_rads_11"],
                ),
                BasisItem(
                    id="nodule.type", label="结节类型", value=nodule_type, source=SOURCES["lung_rads_11"]
                ),
                BasisItem(
                    id="nodule.growth",
                    label="生长情况",
                    value="较前增大" if growth else "未记录增大",
                    source="随访对比",
                ),
            ],
            summary=f"按 Lung-RADS 1.1 归为 {category} 类；分类仅用于随访管理。",
        ),
        risk=RiskResult(
            label="恶性概率（演示映射）",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 1, "1–2 类"), (1, 5, "3 类"), (5, 15, "4A 类"), (15, 100, "4B 类")]),
            drivers=drivers,
            summary=f"演示映射 {percent:.1f}%，未进行本地校准；不得作为病理或治疗依据。",
        ),
        prognosis=PrognosisResult(
            tier="需随访" if category in {"2", "3"} else "需进一步诊断",
            summary="预后取决于最终病理、分期与可切除性，影像分类本身不能确定良恶性。",
            metrics=[
                PrognosisMetric(label="下一步", value=follow_up, note="演示建议"),
                PrognosisMetric(label="随访依从性", value="关键", note="失访会削弱分层价值"),
            ],
        ),
        recommendations=recs,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=NODULE_DEFINITION.id,
            disease_name=NODULE_DEFINITION.name,
            specialty=NODULE_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


LUNG_CANCER_DEFINITION = DiseaseDefinition(
    id="lung_cancer_preop",
    name="肺癌术前风险评估",
    short_name="肺癌术前",
    specialty="thoracic",
    specialty_label="胸外科",
    summary="结合 TNM8 分期、ppoFEV1/DLCO 与 RCRI 评估肺癌手术风险。",
    sources=[SOURCES["ajcc_tnm8"], SOURCES["rcri_1999"]],
    fields=[
        FieldSpec(
            key="tnm_stage",
            label="TNM 分期（第 8 版）",
            type="select",
            options=[
                FieldOption(value="I", label="I 期"),
                FieldOption(value="II", label="II 期"),
                FieldOption(value="IIIA", label="IIIA 期"),
                FieldOption(value="IIIB", label="IIIB 期"),
                FieldOption(value="IV", label="IV 期"),
            ],
        ),
        FieldSpec(
            key="ppo_fev1",
            label="预计术后 FEV1",
            type="number",
            unit="%",
            minimum=10,
            maximum=120,
            step=0.1,
        ),
        FieldSpec(
            key="ppo_dlco",
            label="预计术后 DLCO",
            type="number",
            unit="%",
            minimum=10,
            maximum=120,
            step=0.1,
        ),
        FieldSpec(key="rcri", label="RCRI 评分", type="integer", unit="分", minimum=0, maximum=6),
    ],
)

_LUNG_CANCER_LABELS = ["低危", "中危", "高危", "极高危"]


def evaluate_lung_cancer_preop(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(LUNG_CANCER_DEFINITION, raw_fields)
    stage: str = fields["tnm_stage"]
    ppo_fev1: float = fields["ppo_fev1"]
    ppo_dlco: float = fields["ppo_dlco"]
    rcri: int = fields["rcri"]

    stage_points = {"I": 0, "II": 1, "IIIA": 2, "IIIB": 3, "IV": 4}[stage]
    fev1_points = 4 if ppo_fev1 < 30 else 2 if ppo_fev1 < 40 else 1 if ppo_fev1 < 60 else 0
    dlco_points = 3 if ppo_dlco < 30 else 2 if ppo_dlco < 40 else 1 if ppo_dlco < 60 else 0
    cardiac_points = 3 if rcri >= 3 else 2 if rcri == 2 else 1 if rcri == 1 else 0
    total = stage_points + fev1_points + dlco_points + cardiac_points
    level = 4 if total >= 9 else 3 if total >= 6 else 2 if total >= 3 else 1

    percent = round(
        min(70.0, 4 + stage_points * 2.2 + fev1_points * 2.8 + dlco_points * 2.3 + cardiac_points * 2.4), 1
    )
    tier = tier_for_percent(percent)

    recs = [
        Recommendation(
            id="lung.mdT",
            text="III 期及以上建议胸外科、肿瘤内科、放疗科与影像科进行多学科讨论，明确可切除性与综合治疗顺序。",
            priority="consider" if stage in {"I", "II"} else "urgent",
            citations=[guideline_citation("ajcc-8", SOURCES["ajcc_tnm8"])],
        ),
        Recommendation(
            id="lung.prehab",
            text="存在肺功能或运动耐量下降时，转介术前预康复（呼吸训练、运动训练、营养支持）。",
            priority="consider" if ppo_fev1 < 60 or ppo_dlco < 60 else "routine",
            citations=[rule_citation("lung.prehab", "肺癌术前预康复原则")],
        ),
        Recommendation(
            id="lung.cardiac",
            text="RCRI ≥2 时完善心血管风险评估，必要时请心内科共同决策。",
            priority="consider" if rcri >= 2 else "routine",
            citations=[guideline_citation("rcri", SOURCES["rcri_1999"])],
        ),
        Recommendation(
            id="lung.smoking",
            text="建议戒烟并接受结构化戒烟支持，至少贯穿术前与术后恢复期。",
            priority="routine",
            citations=[rule_citation("lung.smoking", "围手术期戒烟")],
        ),
    ]

    red_flags = []
    if ppo_fev1 < 30 or ppo_dlco < 30:
        red_flags.append(
            RedFlag(
                code="LUNG_PFT_CRITICAL",
                text="预计术后肺功能 <30%，需高级评估并讨论非手术方案。",
                severity="critical",
            )
        )
    if rcri >= 3:
        red_flags.append(
            RedFlag(
                code="LUNG_CARDIAC_HIGH", text="RCRI ≥3，围手术期重大心脏事件风险升高。", severity="warning"
            )
        )
    if stage == "IV":
        red_flags.append(
            RedFlag(
                code="LUNG_STAGE_IV", text="IV 期通常不以根治性手术为首选，需多学科评估。", severity="warning"
            )
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=f"TNM {stage}",
            level=level,
            tone=tone_for_level(level),
            scale=make_scale(_LUNG_CANCER_LABELS),
            basis=[
                BasisItem(id="lung.stage", label="TNM 分期", value=stage, source=SOURCES["ajcc_tnm8"]),
                BasisItem(
                    id="lung.ppo_fev1", label="ppoFEV1", value=f"{ppo_fev1:g}%", source="术后肺功能预测"
                ),
                BasisItem(
                    id="lung.ppo_dlco", label="ppoDLCO", value=f"{ppo_dlco:g}%", source="术后肺功能预测"
                ),
                BasisItem(id="lung.rcri", label="RCRI", value=f"{rcri} 分", source=SOURCES["rcri_1999"]),
            ],
            summary=f"综合分期与术前器官功能，手术风险分层为{_LUNG_CANCER_LABELS[level - 1]}。",
        ),
        risk=RiskResult(
            label="术后心肺并发症风险",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 12, "低"), (12, 22, "中"), (22, 38, "高"), (38, 100, "极高")]),
            drivers=[
                RiskDriver(
                    label="TNM 分期",
                    direction="increase" if stage_points else "decrease",
                    detail=f"{stage} 期，分期权重 {stage_points} 分",
                ),
                RiskDriver(
                    label="术后肺功能",
                    direction="increase" if fev1_points or dlco_points else "decrease",
                    detail=f"ppoFEV1 {ppo_fev1:g}%，ppoDLCO {ppo_dlco:g}%",
                ),
                RiskDriver(
                    label="心脏风险",
                    direction="increase" if cardiac_points else "decrease",
                    detail=f"RCRI {rcri} 分",
                ),
            ],
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准。",
        ),
        prognosis=PrognosisResult(
            tier=_LUNG_CANCER_LABELS[level - 1],
            summary="预后由病理分期、切缘、术后并发症与分子分型共同决定；此处未纳入分子信息。",
            metrics=[
                PrognosisMetric(
                    label="治疗路径",
                    value="以多学科讨论为准",
                    note="术式与辅助治疗需结合完整分期",
                ),
                PrognosisMetric(
                    label="术后监测",
                    value="按分期随访",
                    note="演示建议",
                ),
            ],
        ),
        recommendations=recs,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=LUNG_CANCER_DEFINITION.id,
            disease_name=LUNG_CANCER_DEFINITION.name,
            specialty=LUNG_CANCER_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


__all__ = [
    "LUNG_CANCER_DEFINITION",
    "NODULE_DEFINITION",
    "evaluate_lung_cancer_preop",
    "evaluate_pulmonary_nodule",
]
