from data.database import db
from common.logger import logger
from data.database.models import Conversation

def health_check():
    try:
        db.health_check()
        logger.info("Database health check passed")
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
def add_data(conversation: Conversation):
    try:
        with db.get_session() as session:
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            logger.info(f"Data added to database successfully: {conversation.__dict__}")
    except Exception as e:
        logger.error(f"Failed to add data to database: {e}")
    
def main():
    health_check()
    conversation = Conversation(title="Test Conversation")
    add_data(conversation)
    db.close()

if __name__ == "__main__":
    main()
    