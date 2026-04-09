import datetime
from typing import Dict, List, Optional


class ReportGenerator:
    def generate_report(
        self,
        analysis: dict,
        selected_plans: List[dict],
        success: bool,
        validation_logs: list,
        validation_result: Optional[Dict[str, str]] = None,
    ) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "SUCCESS" if success else "FAILED"

        report = "# Legacy Python Modernization Report\n"
        report += f"**Date:** {timestamp}\n"
        report += f"**Status:** {status}\n"
        report += f"**Probable Source Version:** {analysis.get('probable_source_version', 'Unknown')}\n"
        report += f"**Execution Mode:** {analysis.get('mode', 'N/A')}\n\n"

        report += "## Analysis Summary\n"
        report += f"- **LOC:** {analysis.get('loc', 'N/A')}\n"
        report += f"- **Complexity:** {analysis.get('complexity', 'N/A')}\n"
        report += f"- **Risk Score:** {analysis.get('risk_score', 'N/A')}\n"
        report += f"- **Legacy Issues:** {len(analysis.get('legacy_issues', []))}\n\n"

        report += "## Planned Transformations\n"
        if selected_plans:
            for plan in selected_plans:
                suggestion = plan.get("suggestion", {})
                report += (
                    f"- `{suggestion.get('id', 'unknown')}` on line {suggestion.get('line', 'N/A')}: "
                    f"{suggestion.get('reasoning', 'N/A')} "
                    f"(score={plan.get('safety_score', 'N/A')})\n"
                )
        else:
            report += "- No transformations were selected.\n"
        report += "\n"

        report += "## Semantic Risks\n"
        if analysis.get("semantic_risks"):
            for risk in analysis["semantic_risks"]:
                report += f"- {risk['message']} ({risk['risk']})\n"
        else:
            report += "- No additional semantic risks were detected.\n"
        report += "\n"

        report += "## Validation\n"
        if validation_result:
            report += f"- **Stage:** {validation_result.get('stage', 'N/A')}\n"
            report += f"- **Message:** {validation_result.get('message', validation_result.get('error', 'N/A'))}\n"
            for warning in validation_result.get("warnings", []):
                report += f"- **Warning:** {warning}\n"
        report += "\n"

        report += "## Execution Logs\n"
        for log in validation_logs:
            report += f"- {log}\n"

        return report
