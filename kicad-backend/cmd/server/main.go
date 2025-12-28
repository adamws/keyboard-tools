package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"kicad-backend/internal/common"

	"github.com/gorilla/mux"
	"github.com/hibiken/asynq"
)

// TaskAccessTracker tracks the last access time for each task to detect abandonment
type TaskAccessTracker struct {
	mu         sync.RWMutex
	lastAccess map[string]time.Time
	timeout    time.Duration
}

func NewTaskAccessTracker(timeoutMinutes int) *TaskAccessTracker {
	return &TaskAccessTracker{
		lastAccess: make(map[string]time.Time),
		timeout:    time.Duration(timeoutMinutes) * time.Minute,
	}
}

// UpdateAccess records that a task was accessed at the current time
func (t *TaskAccessTracker) UpdateAccess(taskID string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.lastAccess[taskID] = time.Now()
}

// GetAbandonedTasks returns task IDs that haven't been accessed within the timeout period
func (t *TaskAccessTracker) GetAbandonedTasks() []string {
	t.mu.RLock()
	defer t.mu.RUnlock()

	now := time.Now()
	abandoned := make([]string, 0)

	for taskID, lastAccess := range t.lastAccess {
		if now.Sub(lastAccess) > t.timeout {
			abandoned = append(abandoned, taskID)
		}
	}

	return abandoned
}

// RemoveTask removes a task from tracking (when completed or cancelled)
func (t *TaskAccessTracker) RemoveTask(taskID string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	delete(t.lastAccess, taskID)
}

// GetTrackedCount returns the number of tasks currently being tracked
func (t *TaskAccessTracker) GetTrackedCount() int {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return len(t.lastAccess)
}

type App struct {
	production          bool
	asynqClient         *asynq.Client
	asynqInspector      *asynq.Inspector
	httpClient          *http.Client
	filerURL            string
	taskAccessTracker   *TaskAccessTracker
	shutdownCtx         context.Context
	shutdownCancel      context.CancelFunc
	abandonmentInterval time.Duration
}

func NewApp() App {
	// Parse Redis connection from environment variables
	redisAddr := common.GetenvOrDefault("REDIS_ADDR", "localhost:6379")
	redisPassword := common.GetenvOrDefault("REDIS_PASSWORD", "")
	redisDB := common.GetIntOrDefault("REDIS_DB", 0)

	// Create asynq Redis connection options
	redisOpt := asynq.RedisClientOpt{
		Addr:     redisAddr,
		Password: redisPassword,
		DB:       redisDB,
	}

	// Create asynq client for task submission
	asynqClient := asynq.NewClient(redisOpt)

	// Create asynq inspector for task status queries
	asynqInspector := asynq.NewInspector(redisOpt)

	// Initialize HTTP client for Filer API
	httpClient := &http.Client{
		Timeout: 30 * time.Second,
	}

	filerURL := common.GetenvOrDefault("FILER_URL", "http://localhost:8888")

	// CORS is enabled only in prod profile
	production := os.Getenv("PROFILE") == "PRODUCTION"

	// Load abandonment configuration
	abandonmentTimeoutMinutes := common.GetIntOrDefault("TASK_ABANDONMENT_TIMEOUT", 15)
	abandonmentCheckInterval := common.GetIntOrDefault("TASK_ABANDONMENT_CHECK_INTERVAL", 2)

	// Create task access tracker
	taskAccessTracker := NewTaskAccessTracker(abandonmentTimeoutMinutes)

	// Create shutdown context for graceful cleanup
	shutdownCtx, shutdownCancel := context.WithCancel(context.Background())

	log.Printf("Task abandonment detection enabled: timeout=%d minutes, check_interval=%d minutes",
		abandonmentTimeoutMinutes, abandonmentCheckInterval)

	app := App{
		production:          production,
		asynqClient:         asynqClient,
		asynqInspector:      asynqInspector,
		httpClient:          httpClient,
		filerURL:            filerURL,
		taskAccessTracker:   taskAccessTracker,
		shutdownCtx:         shutdownCtx,
		shutdownCancel:      shutdownCancel,
		abandonmentInterval: time.Duration(abandonmentCheckInterval) * time.Minute,
	}
	return app
}

// startAbandonmentDetector runs a background goroutine to detect and clean up abandoned tasks
func (a *App) startAbandonmentDetector() {
	go func() {
		ticker := time.NewTicker(a.abandonmentInterval)
		defer ticker.Stop()

		log.Printf("Abandonment detector started: checking every %v", a.abandonmentInterval)

		for {
			select {
			case <-a.shutdownCtx.Done():
				log.Println("Abandonment detector shutting down...")
				return

			case <-ticker.C:
				a.checkAbandonedTasks()
			}
		}
	}()
}

// checkAbandonedTasks identifies and handles abandoned tasks
func (a *App) checkAbandonedTasks() {
	abandonedTaskIDs := a.taskAccessTracker.GetAbandonedTasks()

	if len(abandonedTaskIDs) == 0 {
		trackedCount := a.taskAccessTracker.GetTrackedCount()
		log.Printf("[Abandonment Check] No abandoned tasks found (tracking %d tasks)", trackedCount)
		return
	}

	log.Printf("[Abandonment Check] Found %d potentially abandoned tasks", len(abandonedTaskIDs))

	for _, taskID := range abandonedTaskIDs {
		a.handleAbandonedTask(taskID)
	}
}

// handleAbandonedTask processes a single abandoned task
func (a *App) handleAbandonedTask(taskID string) {
	// Get task info to check current state
	taskInfo, err := a.asynqInspector.GetTaskInfo("kicad", taskID)
	if err != nil {
		// Task might be archived or deleted
		taskInfo, err = a.asynqInspector.GetTaskInfo("kicad:archived", taskID)
		if err != nil {
			log.Printf("[Abandonment] Task %s no longer exists, removing from tracking", taskID)
			a.taskAccessTracker.RemoveTask(taskID)
			return
		}

		log.Printf("[Abandonment] Task %s is archived, removing from tracking", taskID)
		a.taskAccessTracker.RemoveTask(taskID)
		return
	}

	// Handle based on task state
	switch taskInfo.State {
	case asynq.TaskStatePending, asynq.TaskStateRetry:
		// Cancel pending/retry tasks
		log.Printf("[Abandonment] Cancelling abandoned pending task: %s", taskID)
		err := a.asynqInspector.DeleteTask("kicad", taskID)
		if err != nil {
			log.Printf("[Abandonment] Failed to cancel task %s: %v", taskID, err)
		} else {
			log.Printf("[Abandonment] Successfully cancelled abandoned task: %s", taskID)
		}
		a.taskAccessTracker.RemoveTask(taskID)

	case asynq.TaskStateActive:
		// Log but don't cancel active tasks (let 10min timeout handle it)
		log.Printf("[Abandonment] Task %s is active but abandoned - will complete naturally", taskID)

	case asynq.TaskStateCompleted, asynq.TaskStateArchived:
		log.Printf("[Abandonment] Task %s is completed/archived, removing from tracking", taskID)
		a.taskAccessTracker.RemoveTask(taskID)

	default:
		log.Printf("[Abandonment] Task %s in unexpected state: %v", taskID, taskInfo.State)
		a.taskAccessTracker.RemoveTask(taskID)
	}
}

func (a *App) Serve() error {
	// Start abandonment detection background worker
	a.startAbandonmentDetector()

	router := mux.NewRouter()

	var kicadRouter *mux.Router
	if !a.production {
		kicadRouter = router
	} else {
		// Create kicad subdomain router
		kicadRouter = router.Host("{subdomain:kicad}.{domain:.*}").Subrouter()
	}

	kicadPostNewTask := a.KicadPostNewTask
	kicadGetTaskStatus := a.KicadGetTaskStatus
	kicadDeleteTask := a.KicadDeleteTask
	kicadGetTaskRender := a.KicadGetTaskRender
	kicadGetTaskResult := a.KicadGetTaskResult
	kicadGetWorkers := a.KicadGetWorkers

	// disable cors for local development
	if !a.production {
		kicadPostNewTask = disableCors(kicadPostNewTask)
		kicadGetTaskStatus = disableCors(kicadGetTaskStatus)
		kicadDeleteTask = disableCors(kicadDeleteTask)
		kicadGetTaskRender = disableCors(kicadGetTaskRender)
		kicadGetTaskResult = disableCors(kicadGetTaskResult)
		kicadGetWorkers = disableCors(kicadGetWorkers)
	}

	// KiCad subdomain routes
	kicadRouter.HandleFunc("/api/pcb", kicadPostNewTask)
	kicadRouter.HandleFunc("/api/pcb/{task_id}", kicadGetTaskStatus).Methods("GET")
	kicadRouter.HandleFunc("/api/pcb/{task_id}", kicadDeleteTask).Methods("DELETE")
	kicadRouter.HandleFunc("/api/pcb/{task_id}/render/{name}", kicadGetTaskRender).Methods("GET")
	kicadRouter.HandleFunc("/api/pcb/{task_id}/result", kicadGetTaskResult).Methods("GET")
	kicadRouter.HandleFunc("/api/workers", kicadGetWorkers).Methods("GET")

	// This server no longer serves frontend,
	// it has been migrated to editor.keyboard-tools.xyz which is hosted on github pages.
	// This is only an interface for /api worker calls.
	// All non-API routes redirect to the external editor.
	kicadRouter.PathPrefix("/").HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "https://editor.keyboard-tools.xyz/", http.StatusMovedPermanently)
	})

	srv := &http.Server{
		Handler: router,
		Addr:    "0.0.0.0:8080",
		// Good practice: enforce timeouts for servers you create!
		WriteTimeout: 15 * time.Second,
		ReadTimeout:  15 * time.Second,
	}
	log.Println("Web server is available on port 8080")

	// Handle graceful shutdown
	go func() {
		sigChan := make(chan os.Signal, 1)
		signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)
		<-sigChan

		log.Println("Shutdown signal received, stopping abandonment detector...")
		a.shutdownCancel()

		log.Println("Shutting down HTTP server...")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("Server shutdown error: %v", err)
		}
	}()

	return srv.ListenAndServe()
}

type taskStatus struct {
	TaskId     string                 `json:"task_id"`
	TaskStatus string                 `json:"task_status"`
	Result     map[string]interface{} `json:"task_result"`
}

// workersResponse represents the response for /api/workers endpoint
type workersResponse struct {
	WorkerProcesses int            `json:"worker_processes"` // Number of worker processes
	TotalCapacity   int            `json:"total_capacity"`   // Total concurrent task slots
	ActiveTasks     int            `json:"active_tasks"`     // Tasks currently processing
	IdleCapacity    int            `json:"idle_capacity"`    // Available task slots
	Workers         []workerDetail `json:"workers"`          // Detailed worker info
}

// workerDetail represents detailed information about a worker process
type workerDetail struct {
	ID           string         `json:"id"`
	Host         string         `json:"host"`
	PID          int            `json:"pid"`
	Concurrency  int            `json:"concurrency"`   // Max concurrent tasks for this worker
	Started      string         `json:"started"`       // ISO 8601 timestamp
	Status       string         `json:"status"`
	ActiveTasks  int            `json:"active_tasks"`  // Currently processing
	IdleCapacity int            `json:"idle_capacity"` // Available task slots
	Queues       map[string]int `json:"queues"`
}

func (a *App) KicadPostNewTask(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case "POST":
		// Check queue size for rate limiting using asynq inspector
		queueInfo, err := a.asynqInspector.GetQueueInfo("kicad")
		var pendingCount int
		if err != nil {
			// Queue doesn't exist yet (worker not started or no tasks yet)
			// This is normal, treat as empty queue
			log.Printf("Queue info not available (queue may not exist yet): %v", err)
			pendingCount = 0
		} else {
			pendingCount = queueInfo.Pending + queueInfo.Active
		}

		// Rate limiting: reject if too many pending/active tasks
		// pretty low limit but this currently runs on 1 core low performance server,
		// not expecting big concurrent traffic anyway:
		if pendingCount > 2 {
			sendErr(w, http.StatusServiceUnavailable, "Server overloaded, try again later")
			return
		}

		// Read request body as raw bytes
		body, err := io.ReadAll(r.Body)
		if err != nil {
			sendErr(w, http.StatusBadRequest, "Failed to read request body")
			return
		}

		// Validate JSON
		var requestData map[string]interface{}
		if err := json.Unmarshal(body, &requestData); err != nil {
			sendErr(w, http.StatusBadRequest, "Invalid JSON in request body")
			return
		}

		// Create asynq task
		// Note: We no longer need to add task_id to payload - asynq provides it
		task := asynq.NewTask(
			"generate_kicad_project",
			body,
			asynq.MaxRetry(3),
			asynq.Timeout(10*time.Minute),
			asynq.Queue("kicad"),
			asynq.Retention(24*time.Hour), // Keep task info for 24h
		)

		// Enqueue task (asynq will auto-generate unique task ID)
		taskInfo, err := a.asynqClient.Enqueue(task)
		if err != nil {
			log.Printf("Failed to enqueue task: %v", err)
			sendErr(w, http.StatusInternalServerError, "Failed to enqueue task")
			return
		}

		log.Printf("Enqueued task: %s", taskInfo.ID)

		// Start tracking this task for abandonment detection
		a.taskAccessTracker.UpdateAccess(taskInfo.ID)

		// Response with task ID
		var response taskStatus
		response.TaskId = taskInfo.ID
		response.TaskStatus = "pending"

		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(response)

	case "OPTIONS":
		w.WriteHeader(http.StatusOK)

	default:
		sendErr(w, http.StatusMethodNotAllowed, "Method not allowed")
	}
}

func (a *App) KicadGetTaskStatus(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID := vars["task_id"]

	// Update last access time for abandonment detection
	a.taskAccessTracker.UpdateAccess(taskID)

	// Get task info from asynq
	taskInfo, err := a.asynqInspector.GetTaskInfo("kicad", taskID)
	if err != nil {
		// Check archived tasks (completed/failed)
		taskInfo, err = a.asynqInspector.GetTaskInfo("kicad:archived", taskID)
		if err != nil {
			sendErr(w, http.StatusNotFound, "Task not found")
			return
		}
	}

	response := taskStatus{TaskId: taskInfo.ID}

	// Map asynq state to API response
	switch taskInfo.State {
	case asynq.TaskStatePending:
		response.TaskStatus = "PENDING"
		response.Result = map[string]interface{}{"percentage": 0}

	case asynq.TaskStateActive:
		response.TaskStatus = "PROGRESS"
		// Parse progress from result
		if len(taskInfo.Result) > 0 {
			var progress common.Progress
			if err := json.Unmarshal(taskInfo.Result, &progress); err == nil {
				response.Result = map[string]interface{}{
					"percentage": progress.Percentage,
					"message":    progress.Message,
				}
			} else {
				response.Result = map[string]interface{}{"percentage": 50}
			}
		} else {
			response.Result = map[string]interface{}{"percentage": 50}
		}

	case asynq.TaskStateCompleted:
		response.TaskStatus = "SUCCESS"
		// Parse final result
		if len(taskInfo.Result) > 0 {
			var progress common.Progress
			if err := json.Unmarshal(taskInfo.Result, &progress); err == nil {
				response.Result = map[string]interface{}{
					"percentage": progress.Percentage,
				}
			} else {
				response.Result = map[string]interface{}{"percentage": 100}
			}
		} else {
			response.Result = map[string]interface{}{"percentage": 100}
		}

	case asynq.TaskStateArchived:
		// Archived tasks are either completed or failed
		// Check LastErr to determine if it failed
		if taskInfo.LastErr != "" {
			response.TaskStatus = "FAILURE"
			response.Result = map[string]interface{}{
				"percentage": 0,
				"error":      taskInfo.LastErr,
			}
		} else {
			// Archived successfully completed task
			response.TaskStatus = "SUCCESS"
			response.Result = map[string]interface{}{"percentage": 100}
		}

	case asynq.TaskStateRetry:
		response.TaskStatus = "RETRY"
		response.Result = map[string]interface{}{
			"percentage": 0,
			"retries":    taskInfo.Retried,
			"max_retry":  taskInfo.MaxRetry,
		}

	default:
		response.TaskStatus = "UNKNOWN"
		response.Result = map[string]interface{}{}
	}

	json.NewEncoder(w).Encode(response)
}

// KicadDeleteTask handles DELETE /api/pcb/{task_id} - Cancel pending tasks
func (a *App) KicadDeleteTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID := vars["task_id"]

	log.Printf("[DELETE] Request to cancel task: %s", taskID)

	// Get task info to check current state
	taskInfo, err := a.asynqInspector.GetTaskInfo("kicad", taskID)
	if err != nil {
		// Check if task is already archived
		taskInfo, err = a.asynqInspector.GetTaskInfo("kicad:archived", taskID)
		if err != nil {
			log.Printf("[DELETE] Task not found: %s", taskID)
			sendErr(w, http.StatusNotFound, "Task not found")
			return
		}

		log.Printf("[DELETE] Task already completed/archived: %s", taskID)
		sendErr(w, http.StatusGone, "Task has already completed or failed")
		return
	}

	// Check task state
	switch taskInfo.State {
	case asynq.TaskStatePending, asynq.TaskStateRetry:
		// Cancel pending/retry task
		err := a.asynqInspector.DeleteTask("kicad", taskID)
		if err != nil {
			log.Printf("[DELETE] Failed to cancel task %s: %v", taskID, err)
			sendErr(w, http.StatusInternalServerError, "Failed to cancel task")
			return
		}

		a.taskAccessTracker.RemoveTask(taskID)

		log.Printf("[DELETE] Successfully cancelled task: %s", taskID)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{
			"task_id": taskID,
			"status":  "cancelled",
			"message": "Task successfully cancelled",
		})

	case asynq.TaskStateActive:
		log.Printf("[DELETE] Cannot cancel active task: %s", taskID)
		sendErr(w, http.StatusConflict, "Cannot cancel task that is currently running")

	case asynq.TaskStateCompleted, asynq.TaskStateArchived:
		log.Printf("[DELETE] Task already completed: %s", taskID)
		sendErr(w, http.StatusGone, "Task has already completed")

	default:
		log.Printf("[DELETE] Unknown task state for %s: %v", taskID, taskInfo.State)
		sendErr(w, http.StatusInternalServerError, "Unknown task state")
	}
}

func (a *App) KicadGetWorkers(w http.ResponseWriter, r *http.Request) {
	// Get worker server information from asynq inspector
	servers, err := a.asynqInspector.Servers()
	if err != nil {
		log.Printf("Failed to get worker info: %v", err)
		sendErr(w, http.StatusInternalServerError, "Failed to retrieve worker information")
		return
	}

	// Calculate total capacity and active tasks across all worker processes
	totalCapacity := 0
	activeTasks := 0
	workerDetails := make([]workerDetail, 0, len(servers))

	for _, server := range servers {
		activeTaskCount := len(server.ActiveWorkers)
		totalCapacity += server.Concurrency
		activeTasks += activeTaskCount

		workerDetails = append(workerDetails, workerDetail{
			ID:           server.ID,
			Host:         server.Host,
			PID:          server.PID,
			Concurrency:  server.Concurrency,
			Started:      server.Started.Format(time.RFC3339), // ISO 8601
			Status:       server.Status,
			ActiveTasks:  activeTaskCount,
			IdleCapacity: server.Concurrency - activeTaskCount,
			Queues:       server.Queues,
		})
	}

	response := workersResponse{
		WorkerProcesses: len(servers),
		TotalCapacity:   totalCapacity,
		ActiveTasks:     activeTasks,
		IdleCapacity:    totalCapacity - activeTasks,
		Workers:         workerDetails,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (a *App) KicadGetTaskRender(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID := vars["task_id"]
	name := vars["name"]

	objectName := fmt.Sprintf("%s/%s.svg", taskID, name)
	a.FilerProxy(objectName, "")(w, r)
}

func (a *App) KicadGetTaskResult(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID := vars["task_id"]

	archiveName := fmt.Sprintf("%s.zip", taskID)
	objectName := fmt.Sprintf("%s/%s", taskID, archiveName)

	contentDisposition := fmt.Sprintf("attachment; filename=\"%s\"", archiveName)
	a.FilerProxy(objectName, contentDisposition)(w, r)
}

func (a *App) FilerProxy(objectName string, contentDisposition string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Build Filer URL: http://s3:8888/{objectName}
		filerPath := fmt.Sprintf("%s/%s", a.filerURL, objectName)

		// Create GET request to Filer
		req, err := http.NewRequest("GET", filerPath, nil)
		if err != nil {
			sendErr(w, http.StatusInternalServerError, "Failed to create request")
			return
		}

		// Execute request
		resp, err := a.httpClient.Do(req)
		if err != nil {
			sendErr(w, http.StatusBadGateway, "Failed to fetch file")
			return
		}
		defer resp.Body.Close()

		// Handle errors
		if resp.StatusCode == http.StatusNotFound {
			sendErr(w, http.StatusNotFound, "File not found")
			return
		}
		if resp.StatusCode != http.StatusOK {
			sendErr(w, http.StatusBadGateway, fmt.Sprintf("Storage error: %d", resp.StatusCode))
			return
		}

		// Copy Filer response headers to client
		for key, values := range resp.Header {
			for _, value := range values {
				w.Header().Add(key, value)
			}
		}

		// Override Content-Disposition if specified
		if contentDisposition != "" {
			w.Header().Set("Content-Disposition", contentDisposition)
		}

		// Stream file to client
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}

func sendErr(w http.ResponseWriter, code int, message string) {
	resp, _ := json.Marshal(map[string]string{"error": message})
	http.Error(w, string(resp), code)
}

// Needed in order to disable CORS for local development
func disableCors(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "*")
		w.Header().Set("Access-Control-Allow-Headers", "*")
		h(w, r)
	}
}

func main() {
	app := NewApp()
	log.Fatal("Error", app.Serve())
}
