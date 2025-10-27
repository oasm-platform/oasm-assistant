"""
Compliance benchmarks repository
Industry statistics and benchmarks for comparison
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from data.database.models.compliance_benchmark import ComplianceBenchmark


class ComplianceBenchmarksRepository:
    """Repository for compliance benchmark operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_benchmark(
        self,
        industry_sector: str,
        standard_name: str,
        company_size: Optional[str] = None
    ) -> Optional[ComplianceBenchmark]:
        """Get benchmark for specific industry and standard"""
        query = self.session.query(ComplianceBenchmark)\
            .filter(and_(
                ComplianceBenchmark.industry_sector == industry_sector,
                ComplianceBenchmark.standard_name == standard_name
            ))

        if company_size:
            query = query.filter(ComplianceBenchmark.company_size == company_size)

        return query.first()

    def get_by_industry(self, industry_sector: str) -> List[ComplianceBenchmark]:
        """Get all benchmarks for an industry"""
        return self.session.query(ComplianceBenchmark)\
            .filter(ComplianceBenchmark.industry_sector == industry_sector)\
            .all()

    def get_by_standard(self, standard_name: str) -> List[ComplianceBenchmark]:
        """Get all benchmarks for a standard"""
        return self.session.query(ComplianceBenchmark)\
            .filter(ComplianceBenchmark.standard_name == standard_name)\
            .all()

    def compare_to_benchmark(
        self,
        score: float,
        industry_sector: str,
        standard_name: str,
        company_size: Optional[str] = None
    ) -> Dict:
        """
        Compare a score to industry benchmark

        Returns:
            Comparison analysis with percentile and recommendations
        """
        benchmark = self.get_benchmark(industry_sector, standard_name, company_size)

        if not benchmark:
            return {
                "error": "No benchmark data available",
                "industry": industry_sector,
                "standard": standard_name
            }

        # Determine percentile
        percentile = None
        if score >= benchmark.percentile_90:
            percentile = "90th+ (Excellent)"
        elif score >= benchmark.percentile_75:
            percentile = "75th-90th (Good)"
        elif score >= benchmark.percentile_50:
            percentile = "50th-75th (Average)"
        elif score >= benchmark.percentile_25:
            percentile = "25th-50th (Below Average)"
        else:
            percentile = "Below 25th (Poor)"

        # Calculate gap
        gap = score - benchmark.average_score
        gap_percentage = (gap / benchmark.average_score * 100) if benchmark.average_score > 0 else 0

        # Determine status
        meets_threshold = score >= benchmark.compliance_threshold

        return {
            "score": score,
            "industry": industry_sector,
            "standard": standard_name,
            "company_size": company_size,
            "benchmark": {
                "threshold": benchmark.compliance_threshold,
                "average": benchmark.average_score,
                "percentile_25": benchmark.percentile_25,
                "percentile_50": benchmark.percentile_50,
                "percentile_75": benchmark.percentile_75,
                "percentile_90": benchmark.percentile_90
            },
            "comparison": {
                "percentile": percentile,
                "gap_from_average": round(gap, 2),
                "gap_percentage": round(gap_percentage, 2),
                "meets_threshold": meets_threshold,
                "points_to_threshold": max(0, benchmark.compliance_threshold - score)
            },
            "recommendations": self._generate_recommendations(
                score,
                benchmark,
                meets_threshold
            )
        }

    def _generate_recommendations(
        self,
        score: float,
        benchmark: ComplianceBenchmark,
        meets_threshold: bool
    ) -> List[str]:
        """Generate recommendations based on score"""
        recommendations = []

        if not meets_threshold:
            gap = benchmark.compliance_threshold - score
            recommendations.append(
                f"Priority: Achieve compliance threshold ({benchmark.compliance_threshold}). "
                f"You need {gap:.1f} more points."
            )

        if score < benchmark.average_score:
            recommendations.append(
                f"Below industry average. Focus on addressing common gaps: {benchmark.common_gaps}"
            )

        if score < benchmark.percentile_75:
            recommendations.append(
                f"Target top 25% performers. Critical requirements: {benchmark.critical_requirements}"
            )

        if benchmark.average_remediation_time_days:
            estimated_days = int(benchmark.average_remediation_time_days * (100 - score) / 100)
            recommendations.append(
                f"Estimated time to full compliance: {estimated_days} days based on industry average"
            )

        return recommendations

    def get_industry_overview(self, industry_sector: str) -> Dict:
        """Get overview of all standards for an industry"""
        benchmarks = self.get_by_industry(industry_sector)

        return {
            "industry": industry_sector,
            "standards": [
                {
                    "name": b.standard_name,
                    "threshold": b.compliance_threshold,
                    "average": b.average_score,
                    "sample_size": b.sample_size
                }
                for b in benchmarks
            ],
            "total_standards": len(benchmarks)
        }

    def create_benchmark(
        self,
        industry_sector: str,
        standard_name: str,
        compliance_threshold: float,
        average_score: float,
        percentile_25: float,
        percentile_50: float,
        percentile_75: float,
        percentile_90: float,
        **kwargs
    ) -> ComplianceBenchmark:
        """Create a new compliance benchmark"""
        benchmark = ComplianceBenchmark(
            industry_sector=industry_sector,
            standard_name=standard_name,
            compliance_threshold=compliance_threshold,
            average_score=average_score,
            percentile_25=percentile_25,
            percentile_50=percentile_50,
            percentile_75=percentile_75,
            percentile_90=percentile_90,
            **kwargs
        )
        self.session.add(benchmark)
        self.session.commit()
        return benchmark
