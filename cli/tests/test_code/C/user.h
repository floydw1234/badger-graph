/**
 * User management header file.
 * Defines the User structure and related functions.
 */

#ifndef USER_H
#define USER_H

#include <stdbool.h>
#include <stdint.h>

#define MAX_NAME_LENGTH 128
#define MAX_EMAIL_LENGTH 256

/**
 * User structure representing a user in the system.
 */
typedef struct {
    int id;
    char name[MAX_NAME_LENGTH];
    char email[MAX_EMAIL_LENGTH];
    bool is_active;
} User;

/**
 * Convert user to a dictionary-like string representation.
 * Caller must free the returned string.
 */
char* user_to_dict(const User* user);

/**
 * Create a new user with the given parameters.
 */
User user_create(int id, const char* name, const char* email);

/**
 * Initialize a user structure.
 */
void user_init(User* user, int id, const char* name, const char* email);

/**
 * Validate email format.
 */
bool validate_email(const char* email);

#endif /* USER_H */

