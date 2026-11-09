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

PROSTATE_DEFINITION = DiseaseDefinition(
    id="prostate_cancer",
    name="前列腺癌风险分层",
    short_name="前列腺癌",
    specialty="urology",
    specialty_label="泌尿外科",
    summary="结合 D'Amico 分层与 CAPRA 评分评估生化复发风险。",
    sources=[SOURCES["damico_1998"], SOURCES["capra_2005"]],
    fields=[
        FieldSpec(key="psa", label="PSA", type="number", unit="ng/mL", minimum=0, maximum=10_000, step=0.1),
        FieldSpec(
            key="grade_group",
            label="Grade Group / Gleason 分组",
            type="select",
            options=[
                FieldOption(value="1", label="GG1（Gleason ≤6）"),
                FieldOption(value="2", label="GG2（3+4）"),
                FieldOption(value="3", label="GG3（4+3）"),
                FieldOption(value="4", label="GG4（Gleason 8）"),
                FieldOption(value="5", label="GG5（Gleason 9–10）"),
            ],
        ),
        FieldSpec(
            key="clinical_t",
            label="临床 T 分期",
            type="select",
            options=[
                FieldOption(value="T1", label="T1"),
                FieldOption(value="T2a", label="T2a"),
                FieldOption(value="T2b", label="T2b"),
                FieldOption(value="T2c", label="T2c"),
                FieldOption(value="T3a", label="T3a"),
                FieldOption(value="T3b", label="T3b"),
                FieldOption(value="T4", label="T4"),
            ],
        ),
        FieldSpec(
            key="positive_cores_pct",
            label="阳性穿刺针占比",
            type="number",
            unit="%",
            minimum=0,
            maximum=100,
            step=0.1,
        ),
        FieldSpec(key="capra", label="CAPRA 评分", type="integer", unit="分", minimum=0, maximum=10),
    ],
)

_PROSTATE_LABELS = ["低危", "中危", "高危", "极高危"]


def evaluate_prostate_cancer(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(PROSTATE_DEFINITION, raw_fields)
    psa: float = fields["psa"]
    grade_group = int(fields["grade_group"])
    clinical_t: str = fields["clinical_t"]
    positive_cores_pct: float = fields["positive_cores_pct"]
    capra: int = fields["capra"]

    high_risk = psa > 20 or grade_group >= 4 or clinical_t in {"T3a", "T3b", "T4"}
    low_risk = psa < 10 and grade_group == 1 and clinical_t in {"T1", "T2a"}
    if high_risk:
        damico = "高危"
    elif low_risk:
        damico = "低危"
    else:
        damico = "中危"

    if capra >= 9:
        level = 4
        grade = "极高危（CAPRA 9–10）"
    elif high_risk:
        level = 3
        grade = f"{damico}（D'Amico）"
    elif damico == "中危":
        level = 2
        grade = f"{damico}（D'Amico）"
    else:
        level = 1
        grade = f"{damico}（D'Amico）"

    percent = round(
        min(
            85.0,
            4
            + capra * 4.5
            + (4 if psa > 20 else 2 if psa >= 10 else 0)
            + (3 if grade_group >= 4 else 0)
            + (2 if clinical_t in {"T3a", "T3b", "T4"} else 0)
            + (1 if positive_cores_pct >= 50 else 0),
        ),
        1,
    )
    tier = tier_for_percent(percent)

    if level <= 1:
        strategy = "低危患者可与泌尿外科讨论主动监测；主动监测需要规范 PSA、影像与重复活检随访。"
    elif level == 2:
        strategy = "中危患者应在根治性手术、放疗等方案间共同决策，必要时结合 PSMA PET/CT 与分子风险信息。"
    else:
        strategy = "高危/极高危患者建议多学科讨论，评估以根治为目的的综合治疗及盆腔淋巴结评估。"

    recs = [
        Recommendation(
            id="prostate.strategy",
            text=strategy,
            priority="consider" if level <= 2 else "urgent",
            citations=[
                guideline_citation("damico-1998", SOURCES["damico_1998"]),
                guideline_citation("capra-2005", SOURCES["capra_2005"]),
            ],
        ),
        Recommendation(
            id="prostate.staging",
            text="结合影像分期、穿刺病理与 PSA 复核风险分组；高危患者评估 PSMA PET/CT 或盆腔淋巴结评估。",
            priority="consider" if level >= 2 else "routine",
            citations=[rule_citation("prostate.staging", "前列腺癌危险度分层与分期")],
        ),
        Recommendation(
            id="prostate.genetics",
            text="极高危、家族史显著或年轻发病者，转介遗传咨询评估胚系检测指征。",
            priority="consider" if level >= 3 else "routine",
            citations=[rule_citation("prostate.genetics", "前列腺癌遗传风险评估")],
        ),
    ]

    red_flags = []
    if capra >= 9:
        red_flags.append(
            RedFlag(
                code="PROSTATE_CAPRA_HIGH",
                text="CAPRA 9–10，生化复发风险高，需多学科讨论。",
                severity="warning",
            )
        )
    if clinical_t == "T4":
        red_flags.append(
            RedFlag(code="PROSTATE_T4", text="临床 T4，局部侵犯范围广，需综合治疗评估。", severity="warning")
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=grade,
            level=level,
            tone=tone_for_level(level),
            scale=make_scale(_PROSTATE_LABELS),
            basis=[
                BasisItem(id="prostate.psa", label="PSA", value=f"{psa:g} ng/mL", source="实验室检查"),
                BasisItem(id="prostate.gg", label="Grade Group", value=f"GG{grade_group}", source="病理"),
                BasisItem(
                    id="prostate.t", label="临床 T 分期", value=clinical_t, source=SOURCES["damico_1998"]
                ),
                BasisItem(
                    id="prostate.capra", label="CAPRA", value=f"{capra} 分", source=SOURCES["capra_2005"]
                ),
            ],
            summary=f"D'Amico 分层为{damico}；CAPRA {capra} 分，综合严重程度为{_PROSTATE_LABELS[level - 1]}。",
        ),
        risk=RiskResult(
            label="生化复发风险（演示）",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 15, "低"), (15, 30, "中"), (30, 50, "高"), (50, 100, "极高")]),
            drivers=[
                RiskDriver(
                    label="CAPRA 评分",
                    direction="increase" if capra >= 3 else "decrease",
                    detail=f"{capra} 分",
                ),
                RiskDriver(
                    label="PSA 与 Grade Group",
                    direction="increase" if psa >= 10 or grade_group >= 3 else "decrease",
                    detail=f"PSA {psa:g} ng/mL，GG{grade_group}",
                ),
                RiskDriver(
                    label="临床分期与穿刺负荷",
                    direction="increase" if clinical_t in {"T3a", "T3b", "T4"} else "decrease",
                    detail=f"{clinical_t}，阳性针占比 {positive_cores_pct:g}%",
                ),
            ],
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准，不能用于个体预后承诺。",
        ),
        prognosis=PrognosisResult(
            tier=_PROSTATE_LABELS[level - 1],
            summary="预后受病理、分期、治疗选择与 PSA 动力学影响；风险分层用于沟通与路径选择。",
            metrics=[
                PrognosisMetric(label="治疗决策", value="共同决策", note="结合患者偏好与合并症"),
                PrognosisMetric(label="随访重点", value="PSA 动态与影像", note="演示建议"),
            ],
        ),
        recommendations=recs,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=PROSTATE_DEFINITION.id,
            disease_name=PROSTATE_DEFINITION.name,
            specialty=PROSTATE_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


STONE_DEFINITION = DiseaseDefinition(
    id="upper_urinary_stone",
    name="上尿路结石清除难度评估",
    short_name="上尿路结石",
    specialty="urology",
    specialty_label="泌尿外科",
    summary="依据 Guy's Stone Score、结石负荷、位置、肾积水与 eGFR 评估清除难度。",
    sources=[SOURCES["gss_2011"]],
    fields=[
        FieldSpec(
            key="guy_score",
            label="Guy's Stone Score",
            type="select",
            options=[
                FieldOption(value="1", label="Grade 1"),
                FieldOption(value="2", label="Grade 2"),
                FieldOption(value="3", label="Grade 3"),
                FieldOption(value="4", label="Grade 4"),
            ],
        ),
        FieldSpec(
            key="stone_size",
            label="最大结石径",
            type="number",
            unit="mm",
            minimum=1,
            maximum=150,
            step=0.1,
        ),
        FieldSpec(
            key="stone_location",
            label="结石位置",
            type="select",
            options=[
                FieldOption(value="renal_upper", label="肾上盏"),
                FieldOption(value="renal_mid", label="肾中盏"),
                FieldOption(value="renal_lower", label="肾下盏"),
                FieldOption(value="pelvis", label="肾盂"),
                FieldOption(value="ureter", label="输尿管"),
            ],
        ),
        FieldSpec(
            key="hydronephrosis",
            label="肾积水程度",
            type="select",
            options=[
                FieldOption(value="none", label="无"),
                FieldOption(value="mild", label="轻度"),
                FieldOption(value="moderate", label="中度"),
                FieldOption(value="severe", label="重度"),
            ],
        ),
        FieldSpec(
            key="egfr", label="eGFR", type="number", unit="mL/min/1.73m²", minimum=1, maximum=200, step=1
        ),
    ],
)

_STONE_LABELS = ["Grade 1", "Grade 2", "Grade 3", "Grade 4"]
_STONE_LOCATION_LABELS = {
    "renal_upper": "肾上盏",
    "renal_mid": "肾中盏",
    "renal_lower": "肾下盏",
    "pelvis": "肾盂",
    "ureter": "输尿管",
}


def evaluate_upper_urinary_stone(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(STONE_DEFINITION, raw_fields)
    guy = int(fields["guy_score"])
    size: float = fields["stone_size"]
    location: str = fields["stone_location"]
    hydro: str = fields["hydronephrosis"]
    egfr: float = fields["egfr"]

    level = guy
    percent = round(
        min(
            88.0,
            {1: 8.0, 2: 18.0, 3: 32.0, 4: 48.0}[guy]
            + (5 if size > 20 else 0)
            + (2 if location == "renal_lower" else 0)
            + (5 if hydro in {"moderate", "severe"} else 0)
            + (5 if egfr < 60 else 0),
        ),
        1,
    )
    tier = tier_for_percent(percent)

    if guy <= 2:
        surgery = "根据结石大小、位置与解剖，选择输尿管软镜或经皮肾镜；单纯输尿管结石可评估体外碎石。"
    else:
        surgery = "高复杂度结石建议由经验丰富的团队评估经皮肾镜或联合路径，必要时分期手术。"

    recs = [
        Recommendation(
            id="stone.surgery",
            text=surgery,
            priority="consider" if guy <= 2 else "urgent",
            citations=[guideline_citation("gss", SOURCES["gss_2011"])],
        ),
        Recommendation(
            id="stone.obstruction",
            text="中重度肾积水或感染风险需优先解除梗阻，必要时先行肾造瘘或输尿管支架引流。",
            priority="urgent" if hydro in {"moderate", "severe"} else "routine",
            citations=[rule_citation("stone.decompression", "梗阻优先处理原则")],
        ),
        Recommendation(
            id="stone.metabolic",
            text="完成结石成分与代谢评估，针对高钙尿、低枸橼酸尿等可逆因素制定预防方案。",
            priority="routine",
            citations=[rule_citation("stone.metabolic", "结石代谢评估")],
        ),
    ]
    if egfr < 60:
        recs.append(
            Recommendation(
                id="stone.renal",
                text="eGFR 下降，需与肾内科共同评估肾功能保护、造影剂与围手术期药物调整。",
                priority="consider",
                citations=[rule_citation("stone.egfr", "肾功能风险")],
            )
        )

    red_flags = []
    if hydro == "severe":
        red_flags.append(
            RedFlag(
                code="STONE_SEVERE_HYDRO", text="重度肾积水，需尽快解除梗阻并评估感染。", severity="critical"
            )
        )
    if egfr < 30:
        red_flags.append(
            RedFlag(
                code="STONE_EGFR_LOW", text="eGFR <30，围手术期与肾功能风险显著增加。", severity="critical"
            )
        )
    if guy == 4:
        red_flags.append(
            RedFlag(code="STONE_GSS4", text="Guy's Stone Score Grade 4，结石清除难度高。", severity="warning")
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=f"Guy's Grade {guy}",
            level=level,
            tone=tone_for_level(level),
            scale=make_scale(_STONE_LABELS),
            basis=[
                BasisItem(
                    id="stone.gss",
                    label="Guy's Stone Score",
                    value=f"Grade {guy}",
                    source=SOURCES["gss_2011"],
                ),
                BasisItem(id="stone.size", label="结石最大径", value=f"{size:g} mm", source="影像学"),
                BasisItem(
                    id="stone.location",
                    label="结石位置",
                    value=_STONE_LOCATION_LABELS[location],
                    source="影像学",
                ),
                BasisItem(id="stone.hydro", label="肾积水", value=hydro, source="影像学"),
                BasisItem(id="stone.egfr", label="eGFR", value=f"{egfr:g}", source="实验室检查"),
            ],
            summary=f"Guy's Stone Score Grade {guy}，清除难度评级为{_STONE_LABELS[level - 1]}。",
        ),
        risk=RiskResult(
            label="结石清除失败或并发症风险（演示）",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 15, "低"), (15, 30, "中"), (30, 50, "高"), (50, 100, "极高")]),
            drivers=[
                RiskDriver(
                    label="Guy's Stone Score",
                    direction="increase" if guy >= 3 else "decrease",
                    detail=f"Grade {guy}",
                ),
                RiskDriver(
                    label="结石负荷",
                    direction="increase" if size > 20 else "decrease",
                    detail=f"最大径 {size:g} mm",
                ),
                RiskDriver(
                    label="肾积水与肾功能",
                    direction="increase" if hydro in {"moderate", "severe"} or egfr < 60 else "decrease",
                    detail=f"肾积水 {hydro}，eGFR {egfr:g}",
                ),
            ],
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准，仅用于手术规划沟通。",
        ),
        prognosis=PrognosisResult(
            tier="复杂路径" if guy >= 3 else "标准路径",
            summary="清除率取决于结石负荷、解剖、术式与术者经验；复杂病例应预设分期或联合方案。",
            metrics=[
                PrognosisMetric(label="手术规划", value="个体化", note="结合影像与解剖"),
                PrognosisMetric(label="随访", value="术后影像复查", note="演示建议"),
            ],
        ),
        recommendations=recs,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=STONE_DEFINITION.id,
            disease_name=STONE_DEFINITION.name,
            specialty=STONE_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


__all__ = [
    "PROSTATE_DEFINITION",
    "STONE_DEFINITION",
    "evaluate_prostate_cancer",
    "evaluate_upper_urinary_stone",
]
