package worker

import (
	"backend/internal/common"
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

// LoadConfig loads configuration from environment variables
func LoadConfig() Config {
	return Config{
		RedisAddr:     common.GetenvOrDefault("REDIS_ADDR", "localhost:6379"),
		RedisPassword: common.GetenvOrDefault("REDIS_PASSWORD", ""),
		RedisDB:       common.GetIntOrDefault("REDIS_DB", 0),
		Concurrency:   common.GetIntOrDefault("WORKER_CONCURRENCY", 10),
		QueueName:     common.GetenvOrDefault("QUEUE_NAME", "kicad"),
		FilerURL:      common.GetenvOrDefault("FILER_URL", "http://localhost:8888"),
	}
}
