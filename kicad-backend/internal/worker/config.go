package worker

import (
	"os"
	"strconv"
)

// Config holds configuration for the worker
type Config struct {
	RedisAddr     string
	RedisPassword string
	RedisDB       int
	Concurrency   int
	QueueName     string
	FilerURL      string
}

// GetenvOrDefault returns the value of the environment variable or a default value
func GetenvOrDefault(key string, defaultValue string) string {
	val, ok := os.LookupEnv(key)
	if !ok {
		return defaultValue
	}
	return val
}

// getIntOrDefault returns the integer value of the environment variable or a default value
func getIntOrDefault(key string, defaultValue int) int {
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

// LoadConfig loads configuration from environment variables
func LoadConfig() Config {
	return Config{
		RedisAddr:     GetenvOrDefault("REDIS_ADDR", "localhost:6379"),
		RedisPassword: GetenvOrDefault("REDIS_PASSWORD", ""),
		RedisDB:       getIntOrDefault("REDIS_DB", 0),
		Concurrency:   getIntOrDefault("WORKER_CONCURRENCY", 10),
		QueueName:     GetenvOrDefault("QUEUE_NAME", "kicad"),
		FilerURL:      GetenvOrDefault("FILER_URL", "http://localhost:8888"),
	}
}
