from __future__ import annotations

from app.schemas.common import AnalysisMeta, DataQuality, Kpis, SchemaModel


class SummaryResponse(SchemaModel):
    meta: AnalysisMeta
    kpis: Kpis
    data_quality: DataQuality
