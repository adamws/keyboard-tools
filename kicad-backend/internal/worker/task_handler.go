package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"runtime/debug"

	"kicad-backend/internal/common"
	"kicad-backend/internal/kicad"

	"github.com/hibiken/asynq"
)

const (
	TaskTypeGenerateKicad = "generate_kicad_project"
)

// TaskRequest represents the structure of a KiCad project generation request
type TaskRequest struct {
	Layout   map[string]interface{} `json:"layout"`
	Settings struct {
		SwitchFootprint   string `json:"switchFootprint"`
		DiodeFootprint    string `json:"diodeFootprint"`
		Routing           string `json:"routing"`
		KeyDistance       string `json:"keyDistance"`
		ControllerCircuit string `json:"controllerCircuit"`
	} `json:"settings"`
}

// RegisterTasks registers all task handlers with the mux
func (w *Worker) RegisterTasks() {
	log.Println("Registering task: generate_kicad_project")
	w.mux.HandleFunc(TaskTypeGenerateKicad, w.HandleGenerateKicadProject)
}

// HandleGenerateKicadProject is the asynq task handler for KiCad project generation
func (w *Worker) HandleGenerateKicadProject(ctx context.Context, task *asynq.Task) error {
	// Extract task ID (asynq provides this via task metadata)
	taskID := task.ResultWriter().TaskID()

	log.Printf("[Task %s] Starting KiCad project generation", taskID)

	// Update progress: Starting
	if err := w.reportProgress(task, 0, "Initializing task"); err != nil {
		log.Printf("[Task %s] Failed to report progress: %v", taskID, err)
	}

	// Defer panic recovery
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[Task %s] Panic recovered: %v", taskID, r)
			log.Printf("[Task %s] Stack trace: %s", taskID, debug.Stack())

			// Report error progress
			w.reportProgress(task, 0, fmt.Sprintf("Panic: %v", r))
		}
	}()

	// Parse task payload
	var taskRequest map[string]interface{}
	if err := json.Unmarshal(task.Payload(), &taskRequest); err != nil {
		log.Printf("[Task %s] Failed to parse request JSON (non-retriable): %v", taskID, err)
		w.reportProgress(task, 0, "Invalid JSON payload")
		return fmt.Errorf("failed to parse request JSON: %w", asynq.SkipRetry)
	}

	// Update progress: 10% - Generating PCB
	if err := w.reportProgress(task, 10, "Generating KiCad PCB files"); err != nil {
		log.Printf("[Task %s] Failed to report progress: %v", taskID, err)
	}

	// Generate KiCad project
	workDir, err := kicad.NewPCB(taskID, taskRequest)
	if err != nil {
		log.Printf("[Task %s] Error generating PCB: %v", taskID, err)

		// Check if this is a validation error (non-retriable)
		if kicad.IsValidationError(err) {
			log.Printf("[Task %s] Validation error detected, will not retry", taskID)
			errMsg := fmt.Sprintf("Invalid input: %v", err)
			w.reportProgress(task, 0, errMsg)
			// Wrap with SkipRetry to prevent retries, but include the error message
			return fmt.Errorf("%s: %w", errMsg, asynq.SkipRetry)
		}

		// Transient error, allow retry
		log.Printf("[Task %s] Transient error, will retry", taskID)
		w.reportProgress(task, 0, fmt.Sprintf("PCB generation failed: %v", err))
		return fmt.Errorf("PCB generation failed: %w", err)
	}

	log.Printf("[Task %s] PCB generated successfully, work directory: %s", taskID, workDir)

	// Update progress: 50% - Uploading to S3
	if err := w.reportProgress(task, 50, "Uploading files to storage"); err != nil {
		log.Printf("[Task %s] Failed to report progress: %v", taskID, err)
	}

	// Upload to Filer
	if err := w.filerUploader.UploadToStorage(ctx, taskID, workDir); err != nil {
		log.Printf("[Task %s] Error uploading to storage: %v", taskID, err)
		w.reportProgress(task, 50, fmt.Sprintf("Upload failed: %v", err))
		return fmt.Errorf("Filer upload failed: %w", err)
	}

	log.Printf("[Task %s] Files uploaded to Filer successfully", taskID)

	// Update progress: 100% - Complete
	if err := w.reportProgress(task, 100, "Task completed successfully"); err != nil {
		log.Printf("[Task %s] Failed to report final progress: %v", taskID, err)
	}

	log.Printf("[Task %s] Task completed successfully", taskID)
	return nil
}

// reportProgress writes progress updates to the task's result writer
func (w *Worker) reportProgress(task *asynq.Task, percentage int, message string) error {
	progress := common.Progress{
		Percentage: percentage,
		Message:    message,
	}

	progressJSON, err := json.Marshal(progress)
	if err != nil {
		return fmt.Errorf("failed to marshal progress: %w", err)
	}

	// Write progress to result (stored in Redis)
	_, err = task.ResultWriter().Write(progressJSON)
	return err
}
