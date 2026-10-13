"""Synthetic, fictional financial-document corpus + evaluation set.

Everything here is invented. No real company, person, or financial figure is
represented. Pages are keyword-rich so retrieval has genuine signal, and each
evaluation question has a known gold (document, page) citation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorpusDoc:
    filename: str
    pages: list[str]


@dataclass(frozen=True)
class EvalItem:
    question: str
    filename: str
    page: int  # 1-based gold page


ACME = CorpusDoc(
    filename="acme_robotics_fy2023.pdf",
    pages=[
        # p1
        "Acme Robotics (fictional) Annual Report FY2023. Acme Robotics designs and "
        "manufactures autonomous warehouse robots and fleet orchestration software "
        "for logistics and distribution centers. This report is illustrative only.",
        # p2
        "Consolidated Results of Operations. Total revenue for fiscal year 2023 was "
        "482.6 million dollars, compared with 401.2 million dollars in fiscal 2022. "
        "Operating income was 58.3 million dollars. Net income was 41.0 million dollars.",
        # p3
        "Research and Development. Research and development expenses increased to "
        "92.4 million dollars in fiscal 2023, reflecting continued investment in the "
        "Atlas autonomous navigation platform and next generation gripper hardware.",
        # p4
        "Liquidity and Capital Resources. Cash and cash equivalents stood at 210.7 "
        "million dollars at year end. Net cash provided by operating activities was "
        "74.9 million dollars. The company held no short term marketable securities.",
        # p5
        "Risk Factors. A principal risk is supply chain disruption for semiconductor "
        "components used in robot control units. The company also faces customer "
        "concentration risk among three large logistics clients.",
        # p6
        "Segment Results. The Americas segment generated 300.1 million dollars of "
        "revenue. The EMEA segment generated 120.5 million dollars. The APAC segment "
        "generated 62.0 million dollars. Americas remained the largest segment.",
    ],
)

GLOBEX = CorpusDoc(
    filename="globex_logistics_q2_2024.pdf",
    pages=[
        # p1
        "Globex Logistics (fictional) Interim Report Q2 2024. Globex Logistics "
        "operates a fleet of electric delivery vehicles and a parcel sorting network "
        "across regional hubs. This document is illustrative only.",
        # p2
        "Quarterly Revenue. Second quarter revenue reached 158.9 million dollars, a "
        "14 percent increase year over year. Gross margin for the quarter was 27 "
        "percent, up from 24 percent in the prior year period.",
        # p3
        "Capital Expenditure. Capital expenditure on the electric vehicle fleet "
        "totaled 44.2 million dollars during the quarter as Globex expanded its "
        "last mile delivery capacity in three new metropolitan markets.",
        # p4
        "Debt and Financing. Long term debt was 512.0 million dollars following the "
        "June green bond issuance of 150 million dollars. The weighted average "
        "interest rate on outstanding borrowings was 5.1 percent.",
        # p5
        "Outlook. Management guidance projects full year revenue between 640 and 660 "
        "million dollars. Guidance assumes stable fuel and electricity prices and no "
        "material disruption to the parcel sorting network.",
    ],
)

CORPUS: list[CorpusDoc] = [ACME, GLOBEX]

EVAL: list[EvalItem] = [
    EvalItem("What was Acme Robotics total revenue in fiscal year 2023?", ACME.filename, 2),
    EvalItem("How much did Acme spend on research and development?", ACME.filename, 3),
    EvalItem("What were Acme cash and cash equivalents at year end?", ACME.filename, 4),
    EvalItem("What is a principal supply chain risk factor for Acme Robotics?", ACME.filename, 5),
    EvalItem("How did the Americas segment perform for Acme Robotics?", ACME.filename, 6),
    EvalItem("What does Acme Robotics design and manufacture?", ACME.filename, 1),
    EvalItem("What was Globex Logistics second quarter revenue?", GLOBEX.filename, 2),
    EvalItem(
        "How much capital expenditure did Globex spend on its vehicle fleet?",
        GLOBEX.filename,
        3,
    ),
    EvalItem("What was Globex long term debt after the green bond issuance?", GLOBEX.filename, 4),
    EvalItem("What is Globex management full year revenue guidance?", GLOBEX.filename, 5),
]
