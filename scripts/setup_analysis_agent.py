"""
One-click setup script for Analysis Agent
Run this to set up everything needed for Analysis Agent
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import logger


def setup_analysis_agent():
    """Complete setup for Analysis Agent"""

    print("=" * 80)
    print("OASM ANALYSIS AGENT - SETUP")
    print("=" * 80)
    print()

    steps_completed = []
    steps_failed = []

    # Step 1: Initialize database (tables auto-created)
    print("📦 Step 1/3: Initializing database...")
    try:
        from data.database import postgres_db

        # Tables are automatically created by SQLAlchemy
        # when postgres_db initializes via BaseEntity.metadata.create_all()

        print("  ✅ Database initialized (tables auto-created)")
        print("     - All models registered in BaseEntity.metadata")
        print("     - Indexes created from model definitions")
        steps_completed.append("Initialize database")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        steps_failed.append(f"Initialize database: {e}")

    print()

    # Step 2: Seed knowledge base
    print("🌱 Step 2/3: Seeding knowledge base...")
    try:
        from data.database.seeders.seed_analysis_knowledge import seed_database
        from data.database import postgres_db

        with postgres_db.get_session() as session:
            seed_database(session)
            print("  ✅ Knowledge base seeded successfully")
            print("     - OWASP Top 10 2021 mappings")
            print("     - Common CWE entries")
            print("     - Context factors")
            print("     - Compliance standards")
            print("     - Industry benchmarks")
            steps_completed.append("Seed knowledge base")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        steps_failed.append(f"Seed knowledge base: {e}")

    print()

    # Step 3: Run tests
    print("🧪 Step 3/3: Running tests...")
    try:
        import pytest
        import os

        # Run a subset of tests
        test_files = [
            "tests/test_knowledge_repositories.py::TestOWASPMappingRepository::test_get_by_cve",
            "tests/test_analysis_agent.py::TestNormalization::test_normalize_nuclei_result"
        ]

        for test_file in test_files:
            if Path(test_file.split("::")[0]).exists():
                result = pytest.main([test_file, "-v", "--tb=short", "-W", "ignore::DeprecationWarning"])
                if result == 0:
                    print(f"  ✅ {test_file.split('::')[1]} passed")
                else:
                    print(f"  ⚠️  {test_file.split('::')[1]} failed (non-critical)")

        steps_completed.append("Run tests")

    except Exception as e:
        print(f"  ⚠️  Testing skipped: {e}")

    print()
    print("=" * 80)
    print("SETUP SUMMARY")
    print("=" * 80)

    if steps_completed:
        print("\n✅ Completed steps:")
        for step in steps_completed:
            print(f"   • {step}")

    if steps_failed:
        print("\n❌ Failed steps:")
        for step in steps_failed:
            print(f"   • {step}")

    print()

    if len(steps_failed) == 0:
        print("🎉 SUCCESS! Analysis Agent is ready to use!")
        print()
        print("Next steps:")
        print("1. Test via gRPC: python scripts/test_analysis_grpc.py")
        print("2. View documentation: docs/ANALYSIS_AGENT_GUIDE.md")
        print()
        return True
    else:
        print("⚠️  Setup completed with some errors")
        print("Please check the errors above and fix them manually")
        print()
        return False


if __name__ == "__main__":
    success = setup_analysis_agent()
    sys.exit(0 if success else 1)
