"""
Initialize database
"""

import sys
import os
# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from common.config.configs import PostgresConfigs
from sqlalchemy import create_engine

def initialize_database():
    """Initialize the database by creating all tables if they don't exist"""
    print("Initializing database...")
    
    # Use PostgresConfigs with overridden values for Docker port mapping
    # When running outside Docker, PostgreSQL is accessible via localhost:9432
    postgres_config = PostgresConfigs()
    
    # Override with Docker port mapping values if using default Docker config
    if postgres_config.host == 'postgresql' and postgres_config.port == 5432:
        # Create a temporary instance with localhost and correct port for Docker mapping
        from pydantic import BaseModel
        
        # Create a custom config with overridden values for connection
        class CustomPostgresConfig(BaseModel):
            host: str = "localhost"
            port: int = 9432  # Docker mapped port
            user: str = postgres_config.user
            password: str = postgres_config.password
            database: str = postgres_config.database
            
            @property
            def url(self) -> str:
                """Create connection URL"""
                return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        
        postgres_config = CustomPostgresConfig()
    
    db_url = postgres_config.url
    
    print(f"Connecting to database: {postgres_config.host}:{postgres_config.port}, database: {postgres_config.database}")
    
    # Temporarily modify the import system to avoid initializing the database connection
    # We'll temporarily replace the data/database/__init__.py module in sys.modules if it exists
    original_db_module = sys.modules.get('data.database', None)
    
    # Remove the module from sys.modules if it's already loaded to force reimport
    modules_to_remove = [key for key in sys.modules.keys() if key.startswith('data.database')]
    temporarily_removed_modules = {}
    for module_name in modules_to_remove:
        if module_name in sys.modules:
            temporarily_removed_modules[module_name] = sys.modules[module_name]
            del sys.modules[module_name]
    
    try:
        # Temporarily override the __init__.py file to prevent database initialization
        init_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'database', '__init__.py')
        backup_content = None
        
        # Read the original content
        with open(init_file_path, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        
        # Write a temporary version without the db initialization
        temp_content = '''from .database import PostgresDatabase

# Import all models to register them with the metadata
from .models import *

# Define db as None to avoid initialization during import
db = None
'''
        with open(init_file_path, 'w', encoding='utf-8') as f:
            f.write(temp_content)
        
        try:
            # Now import the actual models from the project
            from data.database.models.base import Base, BaseEntity
            from data.database.models.conversations import Conversation
            from data.database.models.messages import Message
            from data.database.models.knowledgebase import KnowledgeBase
            from data.database.models.nucleitemplate import NucleiTemplate

            # Create engine
            engine = create_engine(db_url, echo=False)
            
            # Create all tables if they don't exist using the imported models
            Base.metadata.create_all(engine, checkfirst=True)
            print("Database initialization completed successfully!")
            print("Tables created: conversations, messages, text_vectors, nuclei_template_vectors")
            return True
        finally:
            # Restore the original content
            with open(init_file_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("Make sure PostgreSQL is running.")
        if 'postgresql' in db_url:
            print("If running outside Docker, try setting POSTGRES_HOST=localhost")
        # Restore any modules we removed
        for module_name, module in temporarily_removed_modules.items():
            sys.modules[module_name] = module
        return False

    # Restore any modules we removed
    for module_name, module in temporarily_removed_modules.items():
        sys.modules[module_name] = module


if __name__ == "__main__":
    success = initialize_database()
    if not success:
        exit(1)