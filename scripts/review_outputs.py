import json
import re
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

MARKET_ANALYSIS_REPORT_FILE = (
    REPO_ROOT / "outputs/reports/market_analysis_report.md"
)
RANKED_SOURCES_FILE = REPO_ROOT / "outputs/reports/ranked_sources.md"
SLIDE_DRAFT_FILE = REPO_ROOT / "outputs/slides/slide_draft.md"
CLEAN_ARTICLES_FILE = REPO_ROOT / "data/clean_articles/clean_articles.json"
ARTICLES_KNOWLEDGE_FILE = (
    REPO_ROOT / "data/knowledge/articles_knowledge.json"
)
OUTPUT_REVIEW_FILE = REPO_ROOT / "outputs/reports/output_quality_review.md"

ALLOWED_FRESHNESS_STATUSES = {"new", "updated", "unknown"}
EXCLUDED_FRESHNESS_STATUSES = {"repeated", "old"}

QUALITY_WEIGHTS = {
    "Report Structure": 20,
    "Source Coverage": 20,
    "Use Case Quality": 20,
    "Freshness Quality": 15,
    "Slide Quality": 15,
    "Product Insight Quality": 10,
}


def load_text(path):
    if not path.exists():
        return "", f"Warning: Missing file: {path.relative_to(REPO_ROOT)}"

    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as error:
        return "", f"Warning: Could not read {path.relative_to(REPO_ROOT)}: {error}"


def load_json_file(path):
    if not path.exists():
        return {}, f"Warning: Missing file: {path.relative_to(REPO_ROOT)}"

    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError:
        return {}, f"Warning: Invalid JSON: {path.relative_to(REPO_ROOT)}"
    except OSError as error:
        return {}, f"Warning: Could not read {path.relative_to(REPO_ROOT)}: {error}"


def has_any(text, keywords):
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def has_url(text):
    return bool(re.search(r"https?://\S+", text))


def is_fallback_report(report_text, ranked_sources_text):
    fallback_keywords = [
        "本週未觀察到足夠的新市場訊號",
        "本週沒有可評分的新文章",
        "no eligible",
        "fallback report",
    ]
    combined_text = f"{report_text}\n{ranked_sources_text}".lower()
    return any(keyword.lower() in combined_text for keyword in fallback_keywords)


def status_for_keyword(text, pass_keywords, warning_keywords=None):
    if has_any(text, pass_keywords):
        return "pass"

    if warning_keywords and has_any(text, warning_keywords):
        return "warning"

    return "fail"


def calculate_section_score(checks, weight):
    if not checks:
        return 0

    points_per_check = weight / len(checks)
    score = 0

    for check in checks:
        if check["status"] == "pass":
            score += points_per_check
        elif check["status"] == "warning":
            score += points_per_check * 0.5

    return score


def get_overall_status(score):
    if score >= 80:
        return "pass"

    if score >= 60:
        return "warning"

    return "fail"


def get_freshness_counts(clean_articles):
    counts = {}

    if not isinstance(clean_articles, list):
        return counts

    for article in clean_articles:
        status = article.get("freshness_status", "missing")
        counts[status] = counts.get(status, 0) + 1

    return counts


def get_referenced_freshness_statuses(text):
    statuses = []

    for line in text.splitlines():
        if line.startswith("- Freshness status:"):
            status = line.replace("- Freshness status:", "").strip()
            statuses.append(status)

    return statuses


def count_slide_headings(slide_text):
    return len(re.findall(r"^##\s+Slide\s+\d+", slide_text, flags=re.MULTILINE))


def get_slide_sections(slide_text):
    sections = []
    current_section = []

    for line in slide_text.splitlines():
        if line.startswith("## Slide "):
            if current_section:
                sections.append("\n".join(current_section))
            current_section = [line]
        elif current_section:
            current_section.append(line)

    if current_section:
        sections.append("\n".join(current_section))

    return sections


def review_report_structure(report_text, fallback):
    checks = [
        {
            "label": "Market trend section",
            "status": status_for_keyword(
                report_text,
                ["市場趨勢", "新趨勢", "trend", "market signal"],
                ["本週未觀察到足夠的新市場訊號", "市場狀態"],
            ),
        },
        {
            "label": "Market pain point section",
            "status": status_for_keyword(
                report_text,
                ["市場問題", "痛點", "pain point", "problem"],
            ),
        },
        {
            "label": "Solutions section",
            "status": status_for_keyword(
                report_text,
                ["現有工具", "解法", "solution", "tool"],
            ),
        },
        {
            "label": "Product implications section",
            "status": status_for_keyword(
                report_text,
                ["給產品的啟示", "產品啟示", "product implication", "產品"],
            ),
        },
        {
            "label": "References section",
            "status": status_for_keyword(
                report_text,
                ["參考資料", "references", "- url:", "http"],
            ),
        },
    ]

    if fallback:
        for check in checks:
            if check["status"] == "fail":
                check["status"] = "warning"

    return checks


def review_source_coverage(report_text, ranked_sources_text, fallback):
    combined_text = f"{report_text}\n{ranked_sources_text}"

    checks = [
        {
            "label": "Report has references",
            "status": status_for_keyword(
                report_text,
                ["參考資料", "references", "[來源", "- url:", "http"],
            ),
        },
        {
            "label": "References include URL",
            "status": "pass" if has_url(report_text) else "fail",
        },
        {
            "label": "References include source/category/recommendation",
            "status": "pass" if (
                has_any(combined_text, ["- Source:"])
                and has_any(combined_text, ["- Category:"])
                and has_any(combined_text, ["- Recommendation:"])
            ) else "fail",
        },
        {
            "label": "Core / Useful sources used",
            "status": "pass" if has_any(
                combined_text,
                ["Recommendation: Core", "Recommendation: Useful"],
            ) else "fail",
        },
    ]

    if fallback:
        for check in checks:
            if check["status"] == "fail":
                check["status"] = "warning"

    return checks


def review_use_case_quality(ranked_sources_text, knowledge_articles, fallback):
    knowledge_values = (
        knowledge_articles.values()
        if isinstance(knowledge_articles, dict)
        else []
    )
    knowledge_has_use_case = any(
        article.get("use_case")
        for article in knowledge_values
    )
    knowledge_has_problem = any(
        article.get("problem_solved")
        for article in knowledge_values
    )

    checks = [
        {
            "label": "Ranked sources include use case",
            "status": "pass" if (
                has_any(ranked_sources_text, ["### Use Case", "use_case"])
                or knowledge_has_use_case
            ) else "fail",
        },
        {
            "label": "Ranked sources include problem solved",
            "status": "pass" if (
                has_any(ranked_sources_text, ["### Problem Solved", "problem_solved"])
                or knowledge_has_problem
            ) else "fail",
        },
        {
            "label": "Ranked sources include clear recommendation",
            "status": "pass" if has_any(
                ranked_sources_text,
                ["- Recommendation: Core", "- Recommendation: Useful", "- Recommendation: Background", "- Recommendation: Exclude"],
            ) else "fail",
        },
        {
            "label": "At least one Core / Useful article",
            "status": "pass" if has_any(
                ranked_sources_text,
                ["- Recommendation: Core", "- Recommendation: Useful"],
            ) else "fail",
        },
    ]

    if fallback:
        for check in checks:
            if check["status"] == "fail":
                check["status"] = "warning"

    return checks


def review_freshness_quality(clean_articles, ranked_sources_text, report_text, fallback):
    freshness_counts = get_freshness_counts(clean_articles)
    referenced_statuses = get_referenced_freshness_statuses(ranked_sources_text)
    all_articles_have_status = bool(clean_articles) and all(
        article.get("freshness_status")
        for article in clean_articles
    )
    excluded_statuses_in_ranked_sources = [
        status for status in referenced_statuses
        if status in EXCLUDED_FRESHNESS_STATUSES
    ]
    used_statuses_are_allowed = all(
        status in ALLOWED_FRESHNESS_STATUSES
        for status in referenced_statuses
    )
    has_new_data = (
        freshness_counts.get("new", 0)
        + freshness_counts.get("updated", 0)
        + freshness_counts.get("unknown", 0)
    ) > 0

    checks = [
        {
            "label": "Clean articles include freshness_status",
            "status": "pass" if all_articles_have_status else "fail",
        },
        {
            "label": "Report uses only new / updated / unknown articles",
            "status": "pass" if (
                referenced_statuses and used_statuses_are_allowed
            ) else "warning",
        },
        {
            "label": "Repeated / old articles are excluded from ranked sources",
            "status": "pass" if not excluded_statuses_in_ranked_sources else "fail",
        },
        {
            "label": "Fallback report exists when no new articles are available",
            "status": "pass" if (
                has_new_data or fallback or has_any(report_text, ["Fallback Report"])
            ) else "fail",
        },
    ]

    if fallback:
        checks[1]["status"] = "pass"

    return checks, freshness_counts


def review_slide_quality(slide_text):
    slide_sections = get_slide_sections(slide_text)
    slide_count = count_slide_headings(slide_text)
    expected_titles = [
        ["Slide 1", "市場趨勢", "新趨勢"],
        ["Slide 2", "市場問題", "現有解法"],
        ["Slide 3", "Use Case", "工具案例"],
        ["Slide 4", "產品", "後續觀察"],
    ]
    expected_title_hits = 0

    for keywords in expected_titles:
        if all(has_any(slide_text, [keyword]) for keyword in keywords[:1]) and has_any(slide_text, keywords[1:]):
            expected_title_hits += 1

    pages_with_core_message = sum(
        1 for section in slide_sections
        if has_any(section, ["核心訊息", "key message"])
    )
    pages_with_content = sum(
        1 for section in slide_sections
        if len([line for line in section.splitlines() if line.strip()]) >= 3
    )
    pages_with_speaker_notes = sum(
        1 for section in slide_sections
        if has_any(section, ["講稿", "speaker note", "speaker notes"])
    )

    checks = [
        {
            "label": "Slide draft includes 4 pages",
            "status": "pass" if slide_count >= 4 else (
                "warning" if slide_count > 0 else "fail"
            ),
        },
        {
            "label": "Slide pages match expected topics",
            "status": "pass" if expected_title_hits >= 4 else (
                "warning" if expected_title_hits > 0 else "fail"
            ),
        },
        {
            "label": "Each page has core message",
            "status": "pass" if (
                slide_sections and pages_with_core_message >= len(slide_sections)
            ) else ("warning" if pages_with_core_message else "fail"),
        },
        {
            "label": "Each page has key content",
            "status": "pass" if (
                slide_sections and pages_with_content >= len(slide_sections)
            ) else "fail",
        },
        {
            "label": "Each page has speaker notes",
            "status": "pass" if (
                slide_sections and pages_with_speaker_notes >= len(slide_sections)
            ) else ("warning" if pages_with_speaker_notes else "fail"),
        },
        {
            "label": "Slide draft has References",
            "status": "pass" if has_any(slide_text, ["References", "參考資料", "http"]) else "fail",
        },
    ]

    return checks


def review_product_insight_quality(report_text, slide_text):
    combined_text = f"{report_text}\n{slide_text}"
    insight_keywords = [
        "產品啟示",
        "給產品的啟示",
        "product implication",
        "產品",
        "後續觀察",
    ]
    direction_keywords = [
        "governance",
        "workflow integration",
        "workflow",
        "cost",
        "reliability",
        "ux",
        "automation",
        "治理",
        "工作流",
        "成本",
        "可靠",
        "使用者體驗",
        "自動化",
    ]
    synthesis_keywords = [
        "啟示",
        "建議",
        "觀察",
        "use case",
        "problem solved",
        "不是新聞摘要",
    ]

    return [
        {
            "label": "Includes concrete product implications",
            "status": status_for_keyword(combined_text, insight_keywords),
        },
        {
            "label": "Mentions governance / workflow / cost / reliability / UX / automation",
            "status": status_for_keyword(combined_text, direction_keywords),
        },
        {
            "label": "Avoids being only a news summary",
            "status": status_for_keyword(combined_text, synthesis_keywords),
        },
    ]


def add_recommendations(recommendations, checks, mapping):
    failed_or_warning_labels = {
        check["label"]
        for check in checks
        if check["status"] in ["warning", "fail"]
    }

    for label, recommendation in mapping.items():
        if label in failed_or_warning_labels and recommendation not in recommendations:
            recommendations.append(recommendation)


def build_recommendations(section_results, fallback, warnings):
    recommendations = []

    if warnings:
        recommendations.append("Check whether required output files are missing.")

    add_recommendations(
        recommendations,
        section_results["Source Coverage"],
        {
            "Core / Useful sources used": "Add more Core / Useful sources before generating the final report.",
            "References include URL": "Check whether references are missing URLs.",
            "References include source/category/recommendation": "Include source, category, and recommendation metadata in references.",
        },
    )
    add_recommendations(
        recommendations,
        section_results["Use Case Quality"],
        {
            "Ranked sources include use case": "Improve use case extraction in ranked sources.",
            "Ranked sources include problem solved": "Improve problem_solved extraction in ranked sources.",
            "At least one Core / Useful article": "Review ranking criteria if all articles are Background or Exclude.",
        },
    )
    add_recommendations(
        recommendations,
        section_results["Report Structure"],
        {
            "Product implications section": "Add more product implications to the market analysis report.",
            "References section": "Check whether references are missing from the report.",
        },
    )
    add_recommendations(
        recommendations,
        section_results["Slide Quality"],
        {
            "Slide draft includes 4 pages": "Expand the slide draft to 4 pages.",
            "Each page has speaker notes": "Add speaker notes for each slide.",
            "Slide draft has References": "Add References to the slide draft.",
        },
    )
    add_recommendations(
        recommendations,
        section_results["Product Insight Quality"],
        {
            "Includes concrete product implications": "Add more concrete product implications.",
            "Mentions governance / workflow / cost / reliability / UX / automation": "Connect findings to governance, workflow integration, cost, reliability, UX, or automation.",
            "Avoids being only a news summary": "Strengthen synthesis so the output is more than a news summary.",
        },
    )

    if fallback:
        recommendations.append(
            "Review fallback report because no new articles were found."
        )

    if not recommendations:
        recommendations.append("No major issues found. Continue monitoring output quality.")

    return recommendations


def format_checks(checks):
    lines = []

    for check in checks:
        lines.append(f"- {check['label']}: {check['status']}")

    return lines


def build_review():
    report_text, report_warning = load_text(MARKET_ANALYSIS_REPORT_FILE)
    ranked_sources_text, ranked_sources_warning = load_text(RANKED_SOURCES_FILE)
    slide_text, slide_warning = load_text(SLIDE_DRAFT_FILE)
    clean_articles, clean_articles_warning = load_json_file(CLEAN_ARTICLES_FILE)

    knowledge_articles = {}
    knowledge_warning = ""

    if ARTICLES_KNOWLEDGE_FILE.exists():
        knowledge_articles, knowledge_warning = load_json_file(ARTICLES_KNOWLEDGE_FILE)

    warnings = [
        warning for warning in [
            report_warning,
            ranked_sources_warning,
            slide_warning,
            clean_articles_warning,
            knowledge_warning,
        ]
        if warning
    ]
    fallback = is_fallback_report(report_text, ranked_sources_text)

    report_structure = review_report_structure(report_text, fallback)
    source_coverage = review_source_coverage(
        report_text,
        ranked_sources_text,
        fallback,
    )
    use_case_quality = review_use_case_quality(
        ranked_sources_text,
        knowledge_articles,
        fallback,
    )
    freshness_quality, freshness_counts = review_freshness_quality(
        clean_articles,
        ranked_sources_text,
        report_text,
        fallback,
    )
    slide_quality = review_slide_quality(slide_text)
    product_insight_quality = review_product_insight_quality(
        report_text,
        slide_text,
    )

    section_results = {
        "Report Structure": report_structure,
        "Source Coverage": source_coverage,
        "Use Case Quality": use_case_quality,
        "Freshness Quality": freshness_quality,
        "Slide Quality": slide_quality,
        "Product Insight Quality": product_insight_quality,
    }
    section_scores = {}

    for section, checks in section_results.items():
        section_scores[section] = calculate_section_score(
            checks,
            QUALITY_WEIGHTS[section],
        )

    total_score = round(sum(section_scores.values()))
    overall_status = get_overall_status(total_score)
    recommendations = build_recommendations(section_results, fallback, warnings)
    generated_at = datetime.now().replace(microsecond=0).isoformat()

    return {
        "generated_at": generated_at,
        "total_score": total_score,
        "overall_status": overall_status,
        "section_results": section_results,
        "section_scores": section_scores,
        "freshness_counts": freshness_counts,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def create_markdown_review(review):
    lines = [
        "# Output Quality Review",
        "",
        f"Generated at: {review['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Total Score: {review['total_score']}/100",
        f"- Overall Status: {review['overall_status']}",
        "",
    ]

    if review["warnings"]:
        lines.extend([
            "## Warnings",
            "",
        ])

        for warning in review["warnings"]:
            lines.append(f"- {warning}")

        lines.append("")

    section_number = 1

    for section, checks in review["section_results"].items():
        section_score = round(review["section_scores"][section], 1)
        section_weight = QUALITY_WEIGHTS[section]
        lines.extend([
            f"## {section_number}. {section}",
            "",
            f"Score: {section_score}/{section_weight}",
            "",
        ])
        lines.extend(format_checks(checks))

        if section == "Freshness Quality":
            lines.extend([
                "",
                "Freshness counts:",
            ])
            freshness_counts = review["freshness_counts"]

            if freshness_counts:
                for status, count in sorted(freshness_counts.items()):
                    lines.append(f"- {status}: {count}")
            else:
                lines.append("- No clean article freshness data available.")

        lines.append("")
        section_number += 1

    lines.extend([
        "## Recommendations",
        "",
    ])

    for recommendation in review["recommendations"]:
        lines.append(f"- {recommendation}")

    lines.append("")
    return "\n".join(lines)


def save_review(content):
    OUTPUT_REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REVIEW_FILE.write_text(content, encoding="utf-8")


def main():
    print("Reviewing generated outputs...")

    review = build_review()
    markdown_review = create_markdown_review(review)
    save_review(markdown_review)

    for warning in review["warnings"]:
        print(warning)

    print(f"Output quality score: {review['total_score']}/100")
    print(
        "Saved review to "
        f"{OUTPUT_REVIEW_FILE.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
