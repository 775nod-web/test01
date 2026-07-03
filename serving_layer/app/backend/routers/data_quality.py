"""データエンジニアリング向け: データ品質サマリー (`gold.data_quality_summary`)。"""

from fastapi import APIRouter, Query

from ..db import qualified_table, run_query
from ..models import DataQualitySummary

router = APIRouter(prefix="/data-quality-summary", tags=["data-quality-summary"])


@router.get("", response_model=list[DataQualitySummary])
def list_data_quality_summary(
    days: int = Query(14, ge=1, le=90, description="直近何日分を返すか"),
) -> list[DataQualitySummary]:
    sql_text = f"""
        SELECT
            run_date, source_table, dq_check_name,
            failed_record_count, checked_record_count,
            CASE WHEN checked_record_count > 0
                 THEN failed_record_count / checked_record_count
                 ELSE NULL END AS failed_rate
        FROM {qualified_table('data_quality_summary')}
        WHERE run_date >= date_sub(current_date(), %(days)s)
        ORDER BY run_date DESC, source_table, dq_check_name
    """
    rows = run_query(sql_text, {"days": days})
    return [DataQualitySummary(**row) for row in rows]
