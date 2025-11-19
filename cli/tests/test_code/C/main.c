/**
 * Main application entry point.
 * Sample C application for testing Badger's code graph analysis.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "user.h"
#include "service.h"

int main(void) {
    printf("Starting sample application...\n");
    
    // Initialize service
    UserService user_service;
    user_service_init(&user_service, NULL);
    
    // This will fail gracefully if config doesn't exist
    user_service_initialize(&user_service);
    
    // Create some test users
    const char* users_data[][2] = {
        {"Alice Johnson", "alice@example.com"},
        {"Bob Smith", "bob@example.com"},
        {"Charlie Brown", "charlie@example.com"}
    };
    
    const int num_users = sizeof(users_data) / sizeof(users_data[0]);
    User* created_users[MAX_USERS];
    int created_count = 0;
    
    for (int i = 0; i < num_users; i++) {
        const char* name = users_data[i][0];
        const char* email = users_data[i][1];
        
        if (validate_email(email)) {
            User* user = user_service_create_user(&user_service, name, email);
            if (user) {
                created_users[created_count++] = user;
                printf("Created user: %s (%d)\n", user->name, user->id);
            }
        } else {
            printf("Invalid email: %s\n", email);
        }
    }
    
    // Demonstrate user operations
    if (created_count > 0) {
        User* first_user = created_users[0];
        char* user_dict = user_to_dict(first_user);
        if (user_dict) {
            printf("\nFirst user details: %s\n", user_dict);
            free(user_dict);
        }
        
        // Update user
        User* updated = user_service_update_user(&user_service, first_user->id, "Alice Cooper", NULL);
        if (updated) {
            printf("Updated user: %s\n", updated->name);
        }
        
        // List all users
        User all_users[MAX_USERS];
        int total_users = user_service_list_users(&user_service, all_users, MAX_USERS);
        printf("\nTotal users: %d\n", total_users);
    }
    
    // Check service readiness
    if (base_service_is_ready((BaseService*)&user_service)) {
        printf("Service is ready\n");
    }
    
    // Cleanup
    if (user_service.base.config_path) {
        free(user_service.base.config_path);
    }
    
    printf("Sample application completed successfully\n");
    return 0;
}

