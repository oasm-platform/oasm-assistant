"""
Complete Knowledge Base Seeder
Seeds all tables needed for Analysis Agent
"""
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy.orm import Session
from data.database import postgres_db
from data.database.seeders.seed_analysis_knowledge import AnalysisKnowledgeSeeder
from scripts.knowledge_data_collector import KnowledgeDataCollector
from scripts.generate_security_playbooks import SecurityPlaybookGenerator
from common.logger import logger

# Retrieval system (optional)
try:
    from data.retrieval import HybridSearchEngine
    RETRIEVAL_AVAILABLE = True
except ImportError:
    RETRIEVAL_AVAILABLE = False
    HybridSearchEngine = None


class CompleteKnowledgeBaseSeeder:
    """Complete knowledge base initialization"""

    def __init__(self, session: Session):
        self.session = session

    def seed_all(self, generate_playbooks: bool = True, collect_external_data: bool = False):
        """
        Seed complete knowledge base

        Args:
            generate_playbooks: Generate PDF playbooks
            collect_external_data: Collect data from NVD, etc. (requires internet)
        """
        logger.info("=" * 70)
        logger.info("Starting Complete Knowledge Base Seeding")
        logger.info("=" * 70)

        # Step 1: Seed static data (OWASP, CWE, etc.)
        logger.info("\n[1/5] Seeding static knowledge data...")
        seeder = AnalysisKnowledgeSeeder(self.session)
        seeder.seed_all()

        # Step 2: Generate security playbooks
        if generate_playbooks:
            logger.info("\n[2/5] Generating security playbooks...")
            try:
                generator = SecurityPlaybookGenerator()
                generator.generate_all_playbooks()
                logger.info("✓ Playbooks generated successfully")
            except Exception as e:
                logger.error(f"✗ Playbook generation failed: {e}", exc_info=True)
        else:
            logger.info("\n[2/5] Skipping playbook generation")

        # Step 3: Initialize retrieval system (optional)
        logger.info("\n[3/5] Initializing retrieval system...")
        if RETRIEVAL_AVAILABLE:
            try:
                # TODO: Index security knowledge into HybridSearchEngine
                logger.info("✓ Retrieval system available (indexing not yet implemented)")
            except Exception as e:
                logger.error(f"✗ Retrieval system initialization failed: {e}", exc_info=True)
        else:
            logger.info("⊘ Retrieval system not available (optional)")

        # Step 4: Collect external data (optional)
        if collect_external_data:
            logger.info("\n[4/5] Collecting external security data...")
            try:
                collector = KnowledgeDataCollector(self.session)
                asyncio.run(collector.collect_all())
                logger.info("✓ External data collected successfully")
            except Exception as e:
                logger.error(f"✗ External data collection failed: {e}", exc_info=True)
        else:
            logger.info("\n[4/5] Skipping external data collection")

        # Step 5: Verify seeding
        logger.info("\n[5/5] Verifying knowledge base...")
        self._verify_seeding()

        logger.info("\n" + "=" * 70)
        logger.info("Knowledge Base Seeding Completed!")
        logger.info("=" * 70)

    def _verify_seeding(self):
        """Verify that data was seeded correctly"""
        from data.database.models import (
            OWASPMapping, CWE, CVSSScore,
            ContextFactor, ComplianceStandard
        )

        counts = {
            "OWASP Mappings": self.session.query(OWASPMapping).count(),
            "CWE Entries": self.session.query(CWE).count(),
            "Context Factors": self.session.query(ContextFactor).count(),
            "Compliance Standards": self.session.query(ComplianceStandard).count(),
        }

        logger.info("\nDatabase Statistics:")
        for name, count in counts.items():
            status = "✓" if count > 0 else "✗"
            logger.info(f"  {status} {name}: {count}")

        # Check playbooks
        playbooks_dir = Path("knowledge/playbooks")
        if playbooks_dir.exists():
            pdf_count = len(list(playbooks_dir.glob("*.pdf")))
            logger.info(f"  {'✓' if pdf_count > 0 else '✗'} PDF Playbooks: {pdf_count}")
        else:
            logger.warning(f"  ✗ Playbooks directory not found: {playbooks_dir}")


def main():
    """Main seeding function"""
    import argparse

    parser = argparse.ArgumentParser(description="Seed OASM Assistant Knowledge Base")
    parser.add_argument(
        "--skip-playbooks",
        action="store_true",
        help="Skip PDF playbook generation"
    )
    parser.add_argument(
        "--collect-external",
        action="store_true",
        help="Collect data from NVD and other external sources (requires internet)"
    )

    args = parser.parse_args()

    try:
        with postgres_db.get_session() as session:
            seeder = CompleteKnowledgeBaseSeeder(session)
            seeder.seed_all(
                generate_playbooks=not args.skip_playbooks,
                collect_external_data=args.collect_external
            )

        print("\n✓ Knowledge base seeding completed successfully!")
        print("\nNext steps:")
        print("1. Verify playbooks in: knowledge/playbooks/")
        print("2. Test Analysis Agent with: python tests/test_analysis_agent.py")
        print("3. Start scheduler with: python scripts/knowledge_scheduler.py")

    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        print(f"\n✗ Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
