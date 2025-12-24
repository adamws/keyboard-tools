package common

import (
	"os"
	"strconv"
)

// GetenvOrDefault returns the value of the environment variable or a default value.
func GetenvOrDefault(key string, defaultValue string) string {
	val, ok := os.LookupEnv(key)
	if !ok {
		return defaultValue
	}
	return val
}

// GetIntOrDefault returns the integer value of the environment variable or a default value.
func GetIntOrDefault(key string, defaultValue int) int {
	val, ok := os.LookupEnv(key)
	if !ok {
		return defaultValue
	}
	intVal, err := strconv.Atoi(val)
	if err != nil {
		return defaultValue
	}
	return intVal
}
