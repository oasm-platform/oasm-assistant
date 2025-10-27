"""
Knowledge Base Scheduler
Automated scheduling for knowledge base updates
"""
import asyncio
import schedule
import time
from datetime import datetime
from pathlib import Path

from knowledge_data_collector import KnowledgeDataCollector
from generate_security_playbooks import SecurityPlaybookGenerator
from data.database import postgres_db
from common.logger import logger


class KnowledgeScheduler:
    """Schedule knowledge base updates"""

    def __init__(self):
        self.playbook_generator = SecurityPlaybookGenerator()

    def schedule_jobs(self):
        """Setup scheduled jobs"""
        logger.info("Setting up knowledge base scheduler...")

        # Daily: Collect CVEs from NVD
        schedule.every().day.at("02:00").do(self.job_collect_nvd_cves)

        # Weekly: Update CWE data (Sunday 3 AM)
        schedule.every().sunday.at("03:00").do(self.job_collect_cwe_data)

        # Weekly: Update OWASP mappings (Sunday 4 AM)
        schedule.every().sunday.at("04:00").do(self.job_collect_owasp_mappings)

        # Daily: Update exploit intelligence
        schedule.every().day.at("05:00").do(self.job_collect_exploit_data)

        # Monthly: Regenerate playbooks (1st of month, 6 AM)
        schedule.every().day.at("06:00").do(self.job_regenerate_playbooks_if_first_day)

        logger.info("Scheduled jobs:")
        logger.info("  - Daily 02:00: Collect NVD CVEs")
        logger.info("  - Sunday 03:00: Update CWE data")
        logger.info("  - Sunday 04:00: Update OWASP mappings")
        logger.info("  - Daily 05:00: Update exploit intelligence")
        logger.info("  - Monthly 06:00: Regenerate playbooks")

    def job_collect_nvd_cves(self):
        """Job: Collect NVD CVEs"""
        try:
            logger.info("[JOB] Starting NVD CVE collection...")
            with postgres_db.get_session() as session:
                collector = KnowledgeDataCollector(session)
                asyncio.run(collector.collect_nvd_cves(days_back=7))  # Last 7 days
            logger.info("[JOB] NVD CVE collection completed")
        except Exception as e:
            logger.error(f"[JOB] NVD CVE collection failed: {e}", exc_info=True)

    def job_collect_cwe_data(self):
        """Job: Collect CWE data"""
        try:
            logger.info("[JOB] Starting CWE data collection...")
            with postgres_db.get_session() as session:
                collector = KnowledgeDataCollector(session)
                asyncio.run(collector.collect_cwe_data())
            logger.info("[JOB] CWE data collection completed")
        except Exception as e:
            logger.error(f"[JOB] CWE data collection failed: {e}", exc_info=True)

    def job_collect_owasp_mappings(self):
        """Job: Collect OWASP mappings"""
        try:
            logger.info("[JOB] Starting OWASP mappings collection...")
            with postgres_db.get_session() as session:
                collector = KnowledgeDataCollector(session)
                asyncio.run(collector.collect_owasp_mappings())
            logger.info("[JOB] OWASP mappings collection completed")
        except Exception as e:
            logger.error(f"[JOB] OWASP mappings collection failed: {e}", exc_info=True)

    def job_collect_exploit_data(self):
        """Job: Collect exploit intelligence"""
        try:
            logger.info("[JOB] Starting exploit intelligence collection...")
            with postgres_db.get_session() as session:
                collector = KnowledgeDataCollector(session)
                asyncio.run(collector.collect_exploit_db())
            logger.info("[JOB] Exploit intelligence collection completed")
        except Exception as e:
            logger.error(f"[JOB] Exploit intelligence collection failed: {e}", exc_info=True)

    def job_regenerate_playbooks_if_first_day(self):
        """Job: Regenerate playbooks on 1st of month"""
        if datetime.now().day == 1:
            try:
                logger.info("[JOB] Starting playbook regeneration...")
                self.playbook_generator.generate_all_playbooks()
                logger.info("[JOB] Playbook regeneration completed")
            except Exception as e:
                logger.error(f"[JOB] Playbook regeneration failed: {e}", exc_info=True)

    def run(self):
        """Run scheduler"""
        logger.info("Knowledge base scheduler started")

        # Run initial collection
        logger.info("Running initial knowledge base collection...")
        self.job_collect_cwe_data()
        self.job_collect_owasp_mappings()

        # Generate initial playbooks
        try:
            self.playbook_generator.generate_all_playbooks()
        except Exception as e:
            logger.error(f"Initial playbook generation failed: {e}")

        # Run scheduler loop
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


def main():
    """Main entry point"""
    scheduler = KnowledgeScheduler()
    scheduler.schedule_jobs()
    scheduler.run()


if __name__ == "__main__":
    main()
