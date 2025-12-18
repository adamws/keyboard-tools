package main

import (
	"kicad-backend/internal/worker"
	"log"
)

func main() {
	log.Println("=== KiCad Worker Starting ===")

	// Create worker instance
	w := worker.NewWorker()

	// Register tasks
	w.RegisterTasks()

	// Start worker (blocks until termination signal)
	w.Start()

	log.Println("=== KiCad Worker Stopped ===")
}
