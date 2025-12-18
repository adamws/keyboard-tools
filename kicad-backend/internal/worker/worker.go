package worker

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"kicad-backend/internal/storage"

	"github.com/hibiken/asynq"
)

// Worker represents the asynq worker with all its dependencies
type Worker struct {
	asynqServer   *asynq.Server
	mux           *asynq.ServeMux
	filerUploader *storage.FilerUploader
	config        Config
}

// NewWorker creates and initializes a new Worker instance
func NewWorker() *Worker {
	log.Println("Initializing worker...")

	// Load configuration
	config := LoadConfig()

	// Create asynq Redis connection options
	redisOpt := asynq.RedisClientOpt{
		Addr:     config.RedisAddr,
		Password: config.RedisPassword,
		DB:       config.RedisDB,
	}

	// Create asynq server with configuration
	asynqServer := asynq.NewServer(
		redisOpt,
		asynq.Config{
			Concurrency: config.Concurrency,
			Queues: map[string]int{
				config.QueueName: 10, // priority weight
				"critical":       20, // higher priority for critical tasks
			},
			// Retry configuration with exponential backoff
			RetryDelayFunc: func(n int, err error, task *asynq.Task) time.Duration {
				// Exponential backoff: 1min, 2min, 4min, 8min
				return time.Duration(1<<uint(n)) * time.Minute
			},
			// Error handler
			ErrorHandler: asynq.ErrorHandlerFunc(func(ctx context.Context, task *asynq.Task, err error) {
				log.Printf("[ERROR] Task %s failed: %v", task.Type(), err)
			}),
			// Logging
			LogLevel: asynq.InfoLevel,
		},
	)

	log.Println("Asynq server created")

	// Create ServeMux for task routing
	mux := asynq.NewServeMux()

	// Initialize Filer uploader
	filerUploader := storage.NewFilerUploader(config.FilerURL)

	log.Println("Filer uploader created")
	log.Println("Worker initialized successfully")

	return &Worker{
		asynqServer:   asynqServer,
		mux:           mux,
		filerUploader: filerUploader,
		config:        config,
	}
}

// Start starts the worker and waits for tasks
func (w *Worker) Start() {
	log.Println("Starting Asynq worker...")

	// Run server in goroutine
	go func() {
		if err := w.asynqServer.Run(w.mux); err != nil {
			log.Fatalf("Could not run asynq server: %v", err)
		}
	}()

	log.Println("Worker started, waiting for tasks...")

	// Wait for termination signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)
	<-sigChan

	log.Println("Shutting down worker...")
	w.asynqServer.Shutdown()
	log.Println("Worker stopped")
}
