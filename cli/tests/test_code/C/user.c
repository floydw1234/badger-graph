/**
 * User management implementation.
 */

#include "user.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char* user_to_dict(const User* user) {
    if (!user) {
        return NULL;
    }
    
    char* result = malloc(512);
    if (!result) {
        return NULL;
    }
    
    snprintf(result, 512,
        "{\"id\": %d, \"name\": \"%s\", \"email\": \"%s\", \"is_active\": %s}",
        user->id,
        user->name,
        user->email,
        user->is_active ? "true" : "false"
    );
    
    return result;
}

User user_create(int id, const char* name, const char* email) {
    User user;
    user_init(&user, id, name, email);
    return user;
}

void user_init(User* user, int id, const char* name, const char* email) {
    if (!user) {
        return;
    }
    
    user->id = id;
    user->is_active = true;
    
    if (name) {
        strncpy(user->name, name, MAX_NAME_LENGTH - 1);
        user->name[MAX_NAME_LENGTH - 1] = '\0';
    } else {
        user->name[0] = '\0';
    }
    
    if (email) {
        strncpy(user->email, email, MAX_EMAIL_LENGTH - 1);
        user->email[MAX_EMAIL_LENGTH - 1] = '\0';
    } else {
        user->email[0] = '\0';
    }
}

bool validate_email(const char* email) {
    if (!email) {
        return false;
    }
    
    bool has_at = false;
    bool has_dot = false;
    
    for (int i = 0; email[i] != '\0'; i++) {
        if (email[i] == '@') {
            has_at = true;
        }
        if (email[i] == '.' && has_at) {
            has_dot = true;
        }
    }
    
    return has_at && has_dot;
}

