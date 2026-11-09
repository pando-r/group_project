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

HCC_DEFINITION = DiseaseDefinition(
    id="hcc",
    name="肝细胞癌分期与治疗风险",
    short_name="肝细胞癌",
    specialty="hpb",
    specialty_label="肝胆胰外科",
    summary="结合 Child-Pugh、BCLC、CNLC、肿瘤负荷与 AFP 评估治疗风险。",
    sources=[SOURCES["child_pugh_1973"], SOURCES["bclc_2022"], SOURCES["cnlc_2022"]],
    fields=[
        FieldSpec(
            key="child_pugh",
            label="Child-Pugh 分级",
            type="select",
            options=[
                FieldOption(value="A", label="A 级：代偿良好"),
                FieldOption(value="B", label="B 级：中度受损"),
                FieldOption(value="C", label="C 级：失代偿"),
            ],
        ),
        FieldSpec(
            key="bclc",
            label="BCLC 分期",
            type="select",
            options=[
                FieldOption(value="0", label="0 期：极早期"),
                FieldOption(value="A", label="A 期：早期"),
                FieldOption(value="B", label="B 期：中期"),
                FieldOption(value="C", label="C 期：晚期"),
                FieldOption(value="D", label="D 期：终末期"),
            ],
        ),
        FieldSpec(
            key="cnlc",
            label="CNLC 分期",
            type="select",
            options=[
                FieldOption(value="Ia", label="Ia 期"),
                FieldOption(value="Ib", label="Ib 期"),
                FieldOption(value="IIa", label="IIa 期"),
                FieldOption(value="IIb", label="IIb 期"),
                FieldOption(value="IIIa", label="IIIa 期"),
                FieldOption(value="IIIb", label="IIIb 期"),
                FieldOption(value="IV", label="IV 期"),
            ],
        ),
        FieldSpec(
            key="tumor_size",
            label="最大肿瘤径",
            type="number",
            unit="cm",
            minimum=0,
            maximum=50,
            step=0.1,
        ),
        FieldSpec(key="afp", label="AFP", type="number", unit="ng/mL", minimum=0, maximum=1_000_000),
        FieldSpec(key="portal_invasion", label="门静脉侵犯", type="boolean", default=False),
    ],
)

_HCC_LABELS = ["极早期", "早期", "中期", "晚期", "终末期"]
_HCC_TONES = ["success", "success", "warning", "danger", "danger"]


def evaluate_hcc(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(HCC_DEFINITION, raw_fields)
    child: str = fields["child_pugh"]
    bclc: str = fields["bclc"]
    cnlc: str = fields["cnlc"]
    tumor_size: float = fields["tumor_size"]
    afp: float = fields["afp"]
    portal_invasion: bool = fields["portal_invasion"]

    bclc_level = {"0": 1, "A": 2, "B": 3, "C": 4, "D": 5}[bclc]
    child_base = {"A": 8.0, "B": 24.0, "C": 48.0}[child]
    burden = 4 * bclc_level
    burden += 5 if tumor_size > 5 else 0
    burden += 5 if tumor_size > 10 else 0
    burden += 8 if portal_invasion else 0
    burden += 3 if afp > 400 else 0
    percent = round(min(92.0, child_base + burden), 1)
    tier = tier_for_percent(percent)

    # The stage itself is the severity; do not independently invent a second grade.
    level = bclc_level
    grade = f"BCLC {bclc}"

    stage_recs: list[Recommendation] = []
    if bclc in {"0", "A"}:
        stage_recs.append(
            Recommendation(
                id="hcc.curative",
                text="在肝功能允许时评估根治性路径：切除、局部消融或肝移植；选择取决于肿瘤位置、门脉高压与全身状况。",
                priority="consider",
                citations=[guideline_citation("bclc-2022", SOURCES["bclc_2022"])],
            )
        )
    elif bclc == "B":
        stage_recs.append(
            Recommendation(
                id="hcc.tace",
                text="中期以肝动脉化疗栓塞（TACE）为主要候选，需评估肝功能储备、肿瘤负荷与栓塞风险。",
                priority="consider",
                citations=[guideline_citation("bclc-b", "BCLC B 期治疗路径")],
            )
        )
    elif bclc == "C":
        stage_recs.append(
            Recommendation(
                id="hcc.systemic",
                text="晚期以系统抗肿瘤治疗为基础，结合多学科评估局部治疗或转化治疗机会。",
                priority="urgent",
                citations=[guideline_citation("bclc-c", "BCLC C 期系统治疗路径")],
            )
        )
    else:
        stage_recs.append(
            Recommendation(
                id="hcc.supportive",
                text="终末期以症状控制、营养与心理支持为主；避免不适合的高风险抗肿瘤治疗。",
                priority="urgent",
                citations=[guideline_citation("bclc-d", "BCLC D 期支持治疗")],
            )
        )

    recs = [
        *stage_recs,
        Recommendation(
            id="hcc.liver_function",
            text="治疗前优化肝功能与并发症（腹水、脑病、黄疸、营养），并复核 Child-Pugh。",
            priority="urgent" if child == "C" else "consider",
            citations=[guideline_citation("child-pugh", SOURCES["child_pugh_1973"])],
        ),
        Recommendation(
            id="hcc.cnlc",
            text="结合 CNLC 规范复核分期与可切除性；本院路径须由肝胆胰 MDT 最终确认。",
            priority="consider",
            citations=[guideline_citation("cnlc-2022", SOURCES["cnlc_2022"])],
        ),
    ]

    red_flags = []
    if child == "C":
        red_flags.append(
            RedFlag(
                code="HCC_CHILD_C",
                text="Child-Pugh C 级，肝功能失代偿，需优先优化支持治疗。",
                severity="critical",
            )
        )
    if portal_invasion:
        red_flags.append(
            RedFlag(
                code="HCC_PORTAL_INVASION",
                text="存在门静脉侵犯，根治性治疗窗口需重新评估。",
                severity="warning",
            )
        )
    if bclc == "D":
        red_flags.append(
            RedFlag(code="HCC_BCLC_D", text="BCLC D 期，治疗目标以支持治疗为主。", severity="critical")
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=grade,
            level=level,
            tone=_HCC_TONES[level - 1],
            scale=make_scale(_HCC_LABELS),
            basis=[
                BasisItem(id="hcc.child", label="Child-Pugh", value=child, source=SOURCES["child_pugh_1973"]),
                BasisItem(id="hcc.bclc", label="BCLC", value=bclc, source=SOURCES["bclc_2022"]),
                BasisItem(id="hcc.cnlc", label="CNLC", value=cnlc, source=SOURCES["cnlc_2022"]),
                BasisItem(id="hcc.size", label="最大肿瘤径", value=f"{tumor_size:g} cm", source="影像学"),
                BasisItem(id="hcc.afp", label="AFP", value=f"{afp:g} ng/mL", source="实验室检查"),
                BasisItem(
                    id="hcc.portal",
                    label="门静脉侵犯",
                    value="是" if portal_invasion else "否",
                    source="影像学",
                ),
            ],
            summary=f"以 BCLC {bclc} 期为严重程度主轴，肝功能为 {child} 级；治疗风险需结合 MDT。",
        ),
        risk=RiskResult(
            label="治疗相关肝功能失代偿风险（演示）",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 15, "低"), (15, 30, "中"), (30, 50, "高"), (50, 100, "极高")]),
            drivers=[
                RiskDriver(
                    label="肝功能储备",
                    direction="increase" if child != "A" else "decrease",
                    detail=f"Child-Pugh {child} 级",
                ),
                RiskDriver(
                    label="肿瘤负荷与侵袭",
                    direction="increase" if tumor_size > 5 or portal_invasion else "decrease",
                    detail=f"最大径 {tumor_size:g} cm，门静脉侵犯{'有' if portal_invasion else '无'}",
                ),
                RiskDriver(
                    label="BCLC 分期",
                    direction="increase",
                    detail=f"BCLC {bclc} 期",
                ),
            ],
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准；不用于判断能否治疗。",
        ),
        prognosis=PrognosisResult(
            tier="需 MDT 评估" if level >= 3 else "有根治机会",
            summary="预后与肝功能、肿瘤分期、治疗反应密切相关；分期越晚，根治性窗口越小。",
            metrics=[
                PrognosisMetric(label="治疗目标", value="根治 / 转化 / 控制 / 支持", note="随分期变化"),
                PrognosisMetric(label="随访影像", value="按治疗方案动态安排", note="演示建议"),
            ],
        ),
        recommendations=recs,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=HCC_DEFINITION.id,
            disease_name=HCC_DEFINITION.name,
            specialty=HCC_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


CHOLECYSTITIS_DEFINITION = DiseaseDefinition(
    id="acute_cholecystitis",
    name="急性胆囊炎严重程度与手术风险",
    short_name="急性胆囊炎",
    specialty="hpb",
    specialty_label="肝胆胰外科",
    summary="依据 Tokyo Guidelines 2018 分级、ASA、炎症指标与症状时长评估。",
    sources=[SOURCES["tg18"]],
    fields=[
        FieldSpec(
            key="tokyo_grade",
            label="TG18 严重程度",
            type="select",
            options=[
                FieldOption(value="I", label="Grade I：轻度"),
                FieldOption(value="II", label="Grade II：中度"),
                FieldOption(value="III", label="Grade III：重度"),
            ],
        ),
        FieldSpec(
            key="asa",
            label="ASA 分级",
            type="select",
            options=[
                FieldOption(value="I", label="I 级"),
                FieldOption(value="II", label="II 级"),
                FieldOption(value="III", label="III 级"),
                FieldOption(value="IV", label="IV 级"),
            ],
        ),
        FieldSpec(
            key="wbc", label="白细胞计数", type="number", unit="10⁹/L", minimum=0.1, maximum=100, step=0.1
        ),
        FieldSpec(
            key="bilirubin", label="总胆红素", type="number", unit="μmol/L", minimum=0, maximum=1000, step=0.1
        ),
        FieldSpec(key="symptom_days", label="症状持续天数", type="integer", unit="天", minimum=0, maximum=60),
    ],
)

_CHOLE_LABELS = ["Grade I 轻度", "Grade II 中度", "Grade III 重度"]


def evaluate_acute_cholecystitis(raw_fields: dict[str, Any]) -> EvaluationResult:
    fields = validate_fields(CHOLECYSTITIS_DEFINITION, raw_fields)
    grade: str = fields["tokyo_grade"]
    asa: str = fields["asa"]
    wbc: float = fields["wbc"]
    bilirubin: float = fields["bilirubin"]
    symptom_days: int = fields["symptom_days"]

    level = {"I": 1, "II": 2, "III": 3}[grade]
    asa_points = {"I": 0, "II": 2, "III": 5, "IV": 8}[asa]
    percent = round(
        min(
            80.0,
            {1: 8.0, 2: 18.0, 3: 35.0}[level]
            + asa_points
            + (3 if wbc >= 18 else 0)
            + (4 if bilirubin > 100 else 0)
            + (3 if symptom_days > 7 else 0),
        ),
        1,
    )
    tier = tier_for_percent(percent)

    if grade == "I":
        operation = "病情允许时优先早期腹腔镜胆囊切除；围手术期抗感染并控制基础病。"
    elif grade == "II":
        operation = "由有经验的团队评估早期腹腔镜胆囊切除；若手术风险高，讨论引流后延期手术。"
    else:
        operation = "先进行器官支持与抗感染治疗，评估胆囊引流/胆囊造瘘；待稳定后再评估手术。"

    recs = [
        Recommendation(
            id="chole.operation",
            text=operation,
            priority="urgent" if grade == "III" else "consider",
            citations=[guideline_citation("tg18-grade", SOURCES["tg18"])],
        ),
        Recommendation(
            id="chole.antibiotics",
            text="尽早采集培养并给予覆盖胆道感染的抗菌治疗，按肾功能与本地耐药情况调整。",
            priority="urgent" if grade == "III" else "routine",
            citations=[guideline_citation("tg18-antibiotics", "TG18 抗感染原则")],
        ),
        Recommendation(
            id="chole.comorbidity",
            text="评估麻醉与基础疾病风险，必要时请重症、麻醉和老年医学科共同管理。",
            priority="consider" if asa_points >= 5 else "routine",
            citations=[rule_citation("chole.asa", "围手术期合并症评估")],
        ),
    ]
    if bilirubin > 100:
        recs.append(
            Recommendation(
                id="chole.biliary",
                text="胆红素明显升高时评估胆总管结石或胆道梗阻，完善影像并讨论 ERCP/胆道引流指征。",
                priority="consider",
                citations=[guideline_citation("tg18-biliary", "TG18 胆道评估")],
            )
        )

    red_flags = []
    if grade == "III":
        red_flags.append(
            RedFlag(
                code="CHOLE_GRADE_III",
                text="Tokyo Grade III，可能合并器官功能障碍，需紧急处理。",
                severity="critical",
            )
        )
    if asa == "IV":
        red_flags.append(
            RedFlag(code="CHOLE_ASA_IV", text="ASA IV 级，手术风险高，需共同决策。", severity="critical")
        )
    if bilirubin > 100:
        red_flags.append(
            RedFlag(code="CHOLE_BILIARY", text="总胆红素 >100 μmol/L，需排查胆道梗阻。", severity="warning")
        )

    return EvaluationResult(
        severity=SeverityResult(
            grade=f"Tokyo Grade {grade}",
            level=level,
            tone=tone_for_level(level),
            scale=make_scale(_CHOLE_LABELS),
            basis=[
                BasisItem(
                    id="chole.grade", label="TG18 分级", value=f"Grade {grade}", source=SOURCES["tg18"]
                ),
                BasisItem(id="chole.asa", label="ASA", value=asa, source=SOURCES["asa"]),
                BasisItem(id="chole.wbc", label="WBC", value=f"{wbc:g} ×10⁹/L", source="实验室检查"),
                BasisItem(
                    id="chole.bili", label="总胆红素", value=f"{bilirubin:g} μmol/L", source="实验室检查"
                ),
                BasisItem(id="chole.days", label="症状持续", value=f"{symptom_days} 天", source="病史"),
            ],
            summary=f"按 TG18 分级为 Grade {grade}，严重程度为{_CHOLE_LABELS[level - 1]}。",
        ),
        risk=RiskResult(
            label="围手术期并发症风险（演示）",
            percent=percent,
            tier=tier,
            tone=tone_for_tier(tier),
            cuts=make_risk_cuts([(0, 12, "低"), (12, 25, "中"), (25, 42, "高"), (42, 100, "极高")]),
            drivers=[
                RiskDriver(
                    label="TG18 严重程度",
                    direction="increase",
                    detail=f"Grade {grade}",
                ),
                RiskDriver(
                    label="麻醉风险",
                    direction="increase" if asa_points else "decrease",
                    detail=f"ASA {asa}",
                ),
                RiskDriver(
                    label="炎症与胆道指标",
                    direction="increase" if wbc >= 18 or bilirubin > 100 else "decrease",
                    detail=f"WBC {wbc:g}，总胆红素 {bilirubin:g} μmol/L",
                ),
            ],
            summary=f"演示模型估计为 {percent:.1f}%，未经外部校准。",
        ),
        prognosis=PrognosisResult(
            tier="需积极处理" if level >= 2 else "总体可控",
            summary="及时控制感染并在合适时机解除胆囊病灶是改善预后的关键。",
            metrics=[
                PrognosisMetric(label="治疗窗口", value="尽早评估", note="随严重程度变化"),
                PrognosisMetric(label="复发风险", value="如仅保守治疗则较高", note="演示表述"),
            ],
        ),
        recommendations=recs,
        red_flags=red_flags,
        meta=ResultMeta(
            disease_id=CHOLECYSTITIS_DEFINITION.id,
            disease_name=CHOLECYSTITIS_DEFINITION.name,
            specialty=CHOLECYSTITIS_DEFINITION.specialty,
            rule_version=ACTIVE_RULE_VERSION,
        ),
    )


__all__ = [
    "CHOLECYSTITIS_DEFINITION",
    "HCC_DEFINITION",
    "evaluate_acute_cholecystitis",
    "evaluate_hcc",
]
