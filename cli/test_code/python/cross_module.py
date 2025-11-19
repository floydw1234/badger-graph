"""
Test file that imports and uses code from sample_app.py
"""

from sample_app import (
    User,
    UserService,
    validate_email,
    DEFAULT_CONFIG_PATH
)
from sample_app import User as AppUser
import sample_app

def create_test_user() -> User:
    """Create a user using imported class."""
    return User(
        id=999,
        name="Test User",
        email="test@example.com"
    )

def use_service() -> None:
    """Use the imported service."""
    service = UserService(config_path="/tmp/test_config.json")
    service.initialize()
    
    # Call methods
    user = service.create_user("Cross Module User", "cross@example.com")
    retrieved = service.get_user(user.id)
    
    if retrieved:
        user_dict = retrieved.to_dict()
        print(f"Retrieved user: {user_dict}")

def validate_emails(emails: list) -> list:
    """Validate multiple emails using imported function."""
    return [email for email in emails if validate_email(email)]

def use_module_directly():
    """Access module attributes directly."""
    print(f"Default config path: {sample_app.DEFAULT_CONFIG_PATH}")
    print(f"Max retries: {sample_app.MAX_RETRIES}")

def create_user_via_alias() -> AppUser:
    """Create user using aliased import."""
    return AppUser(
        id=888,
        name="Alias User",
        email="alias@example.com"
    )

def call_module_function():
    """Call function from module namespace."""
    # Access function through module
    result = sample_app.validate_email("module@example.com")
    print(f"Module function result: {result}")

def main():
    """Test cross-module imports and calls."""
    # Direct class usage
    user1 = create_test_user()
    print(f"Created user: {user1.name}")
    
    # Service usage
    use_service()
    
    # Function usage
    emails = ["valid@example.com", "invalid", "also@valid.com"]
    valid = validate_emails(emails)
    print(f"Valid emails: {valid}")
    
    # Module attribute access
    use_module_directly()
    
    # Aliased class
    user2 = create_user_via_alias()
    print(f"Alias user: {user2.name}")
    
    # Module namespace access
    call_module_function()

if __name__ == "__main__":
    main()


