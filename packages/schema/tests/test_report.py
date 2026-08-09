"""DesignReport schema smoke。"""

from packages.schema.report import (
    REPORT_BOUNDARY_LINES,
    REPORT_SCHEMA_VERSION,
    CandidateSummary,
    DesignReport,
)


def test_design_report_roundtrip():
    report = DesignReport(
        candidate=CandidateSummary(candidate_id="c1", label="A", total_score=80.0),
    )
    data = report.model_dump(mode="json")
    again = DesignReport.model_validate(data)
    assert again.candidate.label == "A"
    assert again.report_schema_version == REPORT_SCHEMA_VERSION
    assert REPORT_BOUNDARY_LINES[0] in again.provenance.boundary_lines
