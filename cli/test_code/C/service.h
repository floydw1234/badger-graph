/**
 * Service management header file.
 * Defines base service and user service structures.
 */

#ifndef SERVICE_H
#define SERVICE_H

#include "user.h"
#include <stdbool.h>

#define DEFAULT_CONFIG_PATH "/etc/app/config.json"
#define MAX_RETRIES 3
#define MAX_USERS 100

/**
 * Base service structure.
 * All services should include this as their first member.
 */
typedef struct {
    char* config_path;
    bool initialized;
} BaseService;

/**
 * User service structure.
 */
typedef struct {
    BaseService base;
    User users[MAX_USERS];
    int user_count;
    int next_id;
} UserService;

/**
 * Initialize base service.
 */
void base_service_init(BaseService* service, const char* config_path);

/**
 * Check if service is ready.
 */
bool base_service_is_ready(const BaseService* service);

/**
 * Initialize user service.
 */
void user_service_init(UserService* service, const char* config_path);

/**
 * Initialize user service (load from config).
 */
void user_service_initialize(UserService* service);

/**
 * Create a new user.
 */
User* user_service_create_user(UserService* service, const char* name, const char* email);

/**
 * Get user by ID.
 */
User* user_service_get_user(UserService* service, int user_id);

/**
 * Get all users (returns count, fills users array).
 */
int user_service_list_users(UserService* service, User* users, int max_users);

/**
 * Update user information.
 */
User* user_service_update_user(UserService* service, int user_id, const char* name, const char* email);

/**
 * Delete a user.
 */
bool user_service_delete_user(UserService* service, int user_id);

#endif /* SERVICE_H */


