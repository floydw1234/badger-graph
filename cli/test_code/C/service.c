/**
 * Service management implementation.
 */

#define _POSIX_C_SOURCE 200809L
#include "service.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#ifdef _WIN32
#include <direct.h>
#define mkdir(path, mode) _mkdir(path)
#else
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#endif

static void user_service_load_users(UserService* service);
static void user_service_save_users(UserService* service);

void base_service_init(BaseService* service, const char* config_path) {
    if (!service) {
        return;
    }
    
    service->initialized = false;
    
    if (config_path) {
        service->config_path = strdup(config_path);
    } else {
        service->config_path = strdup(DEFAULT_CONFIG_PATH);
    }
}

bool base_service_is_ready(const BaseService* service) {
    return service && service->initialized;
}

void user_service_init(UserService* service, const char* config_path) {
    if (!service) {
        return;
    }
    
    base_service_init(&service->base, config_path);
    service->user_count = 0;
    service->next_id = 1;
    
    for (int i = 0; i < MAX_USERS; i++) {
        service->users[i].id = 0;
        service->users[i].name[0] = '\0';
        service->users[i].email[0] = '\0';
        service->users[i].is_active = false;
    }
}

void user_service_initialize(UserService* service) {
    if (!service) {
        return;
    }
    
    FILE* file = fopen(service->base.config_path, "r");
    if (file) {
        fclose(file);
        user_service_load_users(service);
    }
    
    service->base.initialized = true;
    printf("UserService initialized successfully\n");
}

User* user_service_create_user(UserService* service, const char* name, const char* email) {
    if (!service || service->user_count >= MAX_USERS) {
        return NULL;
    }
    
    if (!validate_email(email)) {
        return NULL;
    }
    
    User* user = &service->users[service->user_count];
    user_init(user, service->next_id, name, email);
    
    service->next_id++;
    service->user_count++;
    
    user_service_save_users(service);
    
    return user;
}

User* user_service_get_user(UserService* service, int user_id) {
    if (!service) {
        return NULL;
    }
    
    for (int i = 0; i < service->user_count; i++) {
        if (service->users[i].id == user_id) {
            return &service->users[i];
        }
    }
    
    return NULL;
}

int user_service_list_users(UserService* service, User* users, int max_users) {
    if (!service || !users) {
        return 0;
    }
    
    int count = service->user_count < max_users ? service->user_count : max_users;
    for (int i = 0; i < count; i++) {
        users[i] = service->users[i];
    }
    
    return count;
}

User* user_service_update_user(UserService* service, int user_id, const char* name, const char* email) {
    if (!service) {
        return NULL;
    }
    
    User* user = user_service_get_user(service, user_id);
    if (!user) {
        return NULL;
    }
    
    if (name) {
        strncpy(user->name, name, MAX_NAME_LENGTH - 1);
        user->name[MAX_NAME_LENGTH - 1] = '\0';
    }
    
    if (email) {
        strncpy(user->email, email, MAX_EMAIL_LENGTH - 1);
        user->email[MAX_EMAIL_LENGTH - 1] = '\0';
    }
    
    user_service_save_users(service);
    
    return user;
}

bool user_service_delete_user(UserService* service, int user_id) {
    if (!service) {
        return false;
    }
    
    for (int i = 0; i < service->user_count; i++) {
        if (service->users[i].id == user_id) {
            // Shift remaining users
            for (int j = i; j < service->user_count - 1; j++) {
                service->users[j] = service->users[j + 1];
            }
            service->user_count--;
            user_service_save_users(service);
            return true;
        }
    }
    
    return false;
}

static void user_service_load_users(UserService* service) {
    // Simplified: In a real implementation, this would parse JSON
    // For testing purposes, we'll just print a message
    printf("No existing user data found, starting fresh\n");
}

static void user_service_save_users(UserService* service) {
    if (!service || !service->base.config_path) {
        return;
    }
    
    // Simplified: In a real implementation, this would write JSON
    // For testing purposes, we'll create the directory if needed
    char* path = strdup(service->base.config_path);
    char* dir = strrchr(path, '/');
    
    if (dir) {
        *dir = '\0';
        #ifdef _WIN32
        mkdir(path);
        #else
        mkdir(path, 0755);
        #endif
    }
    
    free(path);
}

