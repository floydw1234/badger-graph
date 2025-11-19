# Makefile for sample C application

CC = gcc
CFLAGS = -Wall -Wextra -std=c11 -g
TARGET = sample_app
SOURCES = main.c user.c service.c
OBJECTS = $(SOURCES:.c=.o)
HEADERS = user.h service.h

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJECTS)

%.o: %.c $(HEADERS)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(TARGET)

run: $(TARGET)
	./$(TARGET)


