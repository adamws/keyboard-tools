package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/gorilla/mux"
	"github.com/hibiken/asynq"
)

type App struct {
	production     bool
	asynqClient    *asynq.Client
	asynqInspector *asynq.Inspector
	httpClient     *http.Client
	filerURL       string
}

type WebAppHandler struct {
	staticPath string
	indexPath  string
}

func (h WebAppHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// get the absolute path to prevent directory traversal
	path, err := filepath.Abs(r.URL.Path)
	if err != nil {
		// if we failed to get the absolute path respond with a 400 bad request and stop
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// prepend the path with the path to the static directory
	path = filepath.Join(h.staticPath, path)

	// check whether a file exists at the given path
	_, err = os.Stat(path)
	if os.IsNotExist(err) {
		// file does not exist, serve index.html
		http.ServeFile(w, r, filepath.Join(h.staticPath, h.indexPath))
		return
	} else if err != nil {
		// if we got an error (that wasn't that the file doesn't exist) stating the
		// file, return a 500 internal server error and stop
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// otherwise, use http.FileServer to serve the static dir
	http.FileServer(http.Dir(h.staticPath)).ServeHTTP(w, r)
}

func GetenvOrDefault(key string, defaultValue string) string {
	val, ok := os.LookupEnv(key)
	if !ok {
		return defaultValue
	}
	return val
}

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

func NewApp() App {
	// Parse Redis connection from environment variables
	redisAddr := GetenvOrDefault("REDIS_ADDR", "localhost:6379")
	redisPassword := GetenvOrDefault("REDIS_PASSWORD", "")
	redisDB := getIntOrDefault("REDIS_DB", 0)

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

	filerURL := GetenvOrDefault("FILER_URL", "http://localhost:8888")

	// CORS is enabled only in prod profile
	production := os.Getenv("PROFILE") == "PRODUCTION"

	app := App{
		production:     production,
		asynqClient:    asynqClient,
		asynqInspector: asynqInspector,
		httpClient:     httpClient,
		filerURL:       filerURL,
	}
	return app
}

func (a *App) Serve() error {
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
	kicadGetTaskRender := a.KicadGetTaskRender
	kicadGetTaskResult := a.KicadGetTaskResult

	// disable cors for local development
	if !a.production {
		kicadPostNewTask = disableCors(kicadPostNewTask)
		kicadGetTaskStatus = disableCors(kicadGetTaskStatus)
		kicadGetTaskRender = disableCors(kicadGetTaskRender)
		kicadGetTaskResult = disableCors(kicadGetTaskResult)
	}

	// KiCad subdomain routes
	kicadRouter.HandleFunc("/api/pcb", kicadPostNewTask)
	kicadRouter.HandleFunc("/api/pcb/{task_id}", kicadGetTaskStatus).Methods("GET")
	kicadRouter.HandleFunc("/api/pcb/{task_id}/render/{name}", kicadGetTaskRender).Methods("GET")
	kicadRouter.HandleFunc("/api/pcb/{task_id}/result", kicadGetTaskResult).Methods("GET")

	// This server no longer serves frontent,
	// it has been migrted to editor.keyboard-tool.xyz which hosted on github pages.
	// This is only interface for /api worker calls

	// redirect /help to external editor
	kicadRouter.HandleFunc("/help", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "https://editor.keyboard-tools.xyz/", http.StatusMovedPermanently)
	})

	// redirect root to external editor
	kicadRouter.PathPrefix("/").HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "https://editor.keyboard-tools.xyz/", http.StatusMovedPermanently)
	})

	if a.production {
		// Create landing page router (main domain)
		landingRouter := router.Host("{domain:.*}").Subrouter()
		// serve landing page on main domain
		landingSpa := WebAppHandler{staticPath: "/landing-page", indexPath: "index.html"}
		landingRouter.PathPrefix("/").Handler(landingSpa)
	}

	srv := &http.Server{
		Handler: router,
		Addr:    "0.0.0.0:8080",
		// Good practice: enforce timeouts for servers you create!
		WriteTimeout: 15 * time.Second,
		ReadTimeout:  15 * time.Second,
	}
	log.Println("Web server is available on port 8080")

	return srv.ListenAndServe()
}

type taskStatus struct {
	TaskId     string                 `json:"task_id"`
	TaskStatus string                 `json:"task_status"`
	Result     map[string]interface{} `json:"task_result"`
}

// Progress represents task progress information (matches worker definition)
type Progress struct {
	Percentage int    `json:"percentage"`
	Status     string `json:"status"`
	Message    string `json:"message,omitempty"`
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
			var progress Progress
			if err := json.Unmarshal(taskInfo.Result, &progress); err == nil {
				response.Result = map[string]interface{}{
					"percentage": progress.Percentage,
					"status":     progress.Status,
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
			var progress Progress
			if err := json.Unmarshal(taskInfo.Result, &progress); err == nil {
				response.Result = map[string]interface{}{
					"percentage": progress.Percentage,
					"status":     progress.Status,
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
