"""
Centralized configuration loader.
Loads config.yaml then overrides sensitive values from environment variables (.env file).
"""

import os
import yaml

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_DIR, '.env'))
except ImportError:
    pass  # python-dotenv not installed, rely on config.yaml only

# Load base config from YAML
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.yaml")
with open(CONFIG_PATH, 'r') as f:
    CONFIG = yaml.safe_load(f)

# Override with environment variables if present (only when non-empty)
CONFIG['anthropic_api_key'] = os.environ.get('ANTHROPIC_API_KEY') or CONFIG.get('anthropic_api_key', '')
CONFIG['gmail_address'] = os.environ.get('GMAIL_ADDRESS') or CONFIG.get('gmail_address', '')
CONFIG['gmail_app_password'] = os.environ.get('GMAIL_APP_PASSWORD') or CONFIG.get('gmail_app_password', '')
CONFIG['notification_email'] = os.environ.get('NOTIFICATION_EMAIL') or CONFIG.get('notification_email', '')
CONFIG['model'] = os.environ.get('CLAUDE_MODEL') or CONFIG.get('model', 'claude-sonnet-4-20250514')

# Export PROJECT_DIR for use by other modules
CONFIG['_project_dir'] = PROJECT_DIR
