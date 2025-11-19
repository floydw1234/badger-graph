"""
Sample Python application for testing Badger's code graph analysis.
This file demonstrates various Python constructs that create semantic relationships.
"""

import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Constants
DEFAULT_CONFIG_PATH = "/etc/app/config.json"
MAX_RETRIES = 3

@dataclass
class User:
    """Represents a user in the system."""
    id: int
    name: str
    email: str
    is_active: bool = True

    def to_dict(self) -> Dict:
        """Convert user to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "is_active": self.is_active
        }

class BaseService(ABC):
    """Abstract base class for all services."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the service."""
        pass

    def is_ready(self) -> bool:
        """Check if service is ready."""
        return self._initialized

class UserService(BaseService):
    """Service for managing users."""

    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)
        self.users: Dict[int, User] = {}
        self._next_id = 1

    def initialize(self) -> None:
        """Initialize user service."""
        try:
            if os.path.exists(self.config_path):
                self._load_users()
            self._initialized = True
            print("UserService initialized successfully")
        except Exception as e:
            print(f"Failed to initialize UserService: {e}")

    def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user = User(
            id=self._next_id,
            name=name,
            email=email
        )
        self.users[user.id] = user
        self._next_id += 1
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.users.get(user_id)

    def list_users(self) -> List[User]:
        """Get all users."""
        return list(self.users.values())

    def update_user(self, user_id: int, **updates) -> Optional[User]:
        """Update user information."""
        user = self.get_user(user_id)
        if user:
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            self._save_users()
        return user

    def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        if user_id in self.users:
            del self.users[user_id]
            self._save_users()
            return True
        return False

    def _load_users(self) -> None:
        """Load users from config file."""
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                users_data = data.get('users', [])
                for user_data in users_data:
                    user = User(**user_data)
                    self.users[user.id] = user
                    self._next_id = max(self._next_id, user.id + 1)
        except (FileNotFoundError, json.JSONDecodeError):
            print("No existing user data found, starting fresh")

    def _save_users(self) -> None:
        """Save users to config file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            data = {
                'users': [user.to_dict() for user in self.users.values()]
            }
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save users: {e}")

def validate_email(email: str) -> bool:
    """Validate email format."""
    return '@' in email and '.' in email

def main():
    """Main application entry point."""
    print("Starting sample application...")

    # Initialize service
    user_service = UserService()

    # This will fail gracefully if config doesn't exist
    user_service.initialize()

    # Create some test users
    users_data = [
        ("Alice Johnson", "alice@example.com"),
        ("Bob Smith", "bob@example.com"),
        ("Charlie Brown", "charlie@example.com")
    ]

    created_users = []
    for name, email in users_data:
        if validate_email(email):
            user = user_service.create_user(name, email)
            created_users.append(user)
            print(f"Created user: {user.name} ({user.id})")
        else:
            print(f"Invalid email: {email}")

    # Demonstrate user operations
    if created_users:
        first_user = created_users[0]
        print(f"\nFirst user details: {first_user.to_dict()}")

        # Update user
        updated = user_service.update_user(first_user.id, name="Alice Cooper")
        if updated:
            print(f"Updated user: {updated.name}")

        # List all users
        all_users = user_service.list_users()
        print(f"\nTotal users: {len(all_users)}")

    print("Sample application completed successfully")

if __name__ == "__main__":
    main()
