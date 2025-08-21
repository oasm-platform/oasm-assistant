from pathlib import Path
import shutil
from run_command import RunCommand
from base import ToolBase

class NucleiTemplateManager(ToolBase):
    def __init__(self, templates_dir="data/nuclei_templates"):
        super().__init__(
            name="NucleiTemplateManager",
            description="Manages Nuclei security testing templates from ProjectDiscovery"
        )
        self.templates_dir = Path(templates_dir)
        self.nuclei_repo_url = "https://github.com/projectdiscovery/nuclei-templates.git"
    
    def is_git_repo(self, path):
        """Check if the given path is a git repository"""
        return (Path(path) / ".git").exists()
    
    def clone_templates(self):
        """Clone nuclei templates repository"""
        print(f"Cloning nuclei templates to {self.templates_dir}...")
        
        # Create parent directory if it doesn't exist
        self.templates_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # Clone the repository
        success, stdout, stderr = RunCommand(
            f'git clone {self.nuclei_repo_url} "{self.templates_dir}"'
        ).run()
        
        if success:
            print("Nuclei templates cloned successfully!")
            return True
        else:
            print(f"Failed to clone nuclei templates: {stderr}")
            return False
    
    def pull_templates(self):
        """Pull latest changes from nuclei templates repository"""
        print(f"Updating nuclei templates in {self.templates_dir}...")
        
        success, stdout, stderr = RunCommand(
            "git pull origin main",
            cwd=self.templates_dir
        ).run()
        
        if success:
            print("Nuclei templates updated successfully!")
            return True
        else:
            print(f"Failed to update nuclei templates: {stderr}")
            return False
    
    def get_template_count(self):
        """Get count of template files"""
        if not self.templates_dir.exists():
            return 0
        
        yaml_files = list(self.templates_dir.rglob("*.yaml"))
        yml_files = list(self.templates_dir.rglob("*.yml"))
        return len(yaml_files) + len(yml_files)
    
    def sync_templates(self):
        """Main method to sync nuclei templates"""
        print("=" * 50)
        print("Nuclei Templates Synchronization")
        print("=" * 50)
        
        if not self.templates_dir.exists():
            print(f"Templates directory '{self.templates_dir}' does not exist.")
            return self.clone_templates()
        
        if not self.is_git_repo(self.templates_dir):
            print(f"Directory '{self.templates_dir}' exists but is not a git repository.")
            print("Removing directory and cloning fresh...")
            
            try:
                shutil.rmtree(self.templates_dir)
            except Exception as e:
                print(f"Error removing directory: {e}")
                return False
            
            return self.clone_templates()
        
        print(f"Git repository found in '{self.templates_dir}'.")
        result = self.pull_templates()
        
        if result:
            count = self.get_template_count()
            print(f"Total templates available: {count}")
        
        return result
    