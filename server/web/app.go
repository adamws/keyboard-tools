package web

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"

	"io/ioutil"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"

	"os"
	"path/filepath"
	"time"

	"github.com/gocelery/gocelery"
	"github.com/gomodule/redigo/redis"
	"github.com/gorilla/mux"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type App struct {
	production    bool
	celeryClient  *gocelery.CeleryClient
	celeryBackend *gocelery.RedisCeleryBackend
	minioClient   *minio.Client
	redisPool     *redis.Pool
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

func NewApp() App {
	// create redis connection pool
	celeryBrokerUrl := GetenvOrDefault("CELERY_BROKER_URL", "redis:6379")
	redisPool := &redis.Pool{
		MaxIdle:     3,                 // maximum number of idle connections in the pool
		MaxActive:   0,                 // maximum number of connections allocated by the pool at a given time
		IdleTimeout: 240 * time.Second, // close connections after remaining idle for this duration
		Dial: func() (redis.Conn, error) {
			c, err := redis.DialURL(celeryBrokerUrl)
			if err != nil {
				return nil, err
			}
			return c, err
		},
		TestOnBorrow: func(c redis.Conn, t time.Time) error {
			_, err := c.Do("PING")
			return err
		},
	}

	// expose celeryBackend because there is no other way to get AsyncResult of task custom state
	// (would be formatted as error in gocelery's AsyncResult::AsyncGet when val.Statys != SUCCESS)
	celeryBackend := &gocelery.RedisCeleryBackend{Pool: redisPool}

	// initialize celery client
	celeryClient, _ := gocelery.NewCeleryClient(
		gocelery.NewRedisBroker(redisPool),
		celeryBackend,
		1,
	)

	// initialize minio client
	minioEndpoint := GetenvOrDefault("MINIO_URL", "localhost:9000")
	minioAccessKey := GetenvOrDefault("MINIO_ACCESS_KEY", "minio_dev")
	minioSecretKey := GetenvOrDefault("MINIO_SECRET_KEY", "minio_dev_secret")
	useSSL := false

	minioClient, err := minio.New(minioEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(minioAccessKey, minioSecretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		log.Fatalln(err)
	}

	// CORS is enabled only in prod profile
	production := os.Getenv("PROFILE") == "PRODUCTION"

	app := App{production, celeryClient, celeryBackend, minioClient, redisPool}
	return app
}

func (a *App) Serve() error {
	router := mux.NewRouter()

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

	router.HandleFunc("/api/pcb", kicadPostNewTask)
	router.HandleFunc("/api/pcb/{task_id}", kicadGetTaskStatus).Methods("GET")
	router.HandleFunc("/api/pcb/{task_id}/render/{side}", kicadGetTaskRender).Methods("GET")
	router.HandleFunc("/api/pcb/{task_id}/result", kicadGetTaskResult).Methods("GET")

	// create and use handler for single page web application
	spa := WebAppHandler{staticPath: "/webapp", indexPath: "index.html"}
	router.PathPrefix("/").Handler(spa)

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

type kleJsonRequest struct {
	Layout   kleJsonLayout `json:"layout"`
	Settings pcbSettings   `json:"settings"`
}

type pcbSettings struct {
	MatrixOption      string `json:"matrixOption"`
	SwitchFootprint   string `json:"switchFootprint"`
	DiodeFootprint    string `json:"diodeFootprint"`
	Routing           string `json:"routing"`
	ControllerCircuit string `json:"controllerCircuit"`
}

type taskStatus struct {
	TaskId     string                 `json:"task_id"`
	TaskStatus string                 `json:"task_status"`
	Result     map[string]interface{} `json:"task_result"`
}

type taskRequest struct {
	TaskId            string                 `json:"id"`
	TaskName          string                 `json:"task"`
	Arguments         []kleJsonRequest       `json:"args"`
	KeywordArguments  struct{}               `json:"kwargs"`
	Retries           int                    `json:"retries"`
	ETA               string                 `json:"eta"`
	Expires           string                 `json:"expires"`
}

type unackedTaskDetails struct {
	Body            string            `json:"body"`
	ContentType     string            `json:"content-type"`
	Properties      messageProperties `json:"properties"`
	ContentEncoding string            `json:"content-encoding"`
}

type messageProperties struct {
	BodyEncoding  string           `json:"body_encoding"`
	CorrelationID string           `json:"correlation_id"`
	ReplyTo       string           `json:"reply_to"`
	DeliveryInfo  deliveryInfo     `json:"delivery_info"`
	DeliveryMode  int              `json:"delivery_mode"`
	DeliveryTag   string           `json:"delivery_tag"`
}

type deliveryInfo struct {
	Priority   int    `json:"priority"`
	RoutingKey string `json:"routing_key"`
	Exchange   string `json:"exchange"`
}

func (a *App) KicadPostNewTask(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case "POST":
		// check how many tasks wait for worker and do not add new one
		// if above threshold, this is for better management of limited server
		// resources and part of ddos prevention
		conn := a.redisPool.Get()
		defer conn.Close()

		waitingCount, err := redis.Int64(conn.Do("LLEN", "celery"))
		if err != nil {
			sendErr(w, http.StatusInternalServerError, "Internal server error")
			return
		}

		// pretty low limit but this currently runs on 1 core low performance server,
		// not expecting big concurrent traffic anyway:
		if waitingCount > 2 {
			sendErr(w, http.StatusServiceUnavailable, "Server overloaded, try again later")
			return
		}

		var request kleJsonRequest
		var unmarshalErr *json.UnmarshalTypeError
		var response taskStatus

		buf, _ := ioutil.ReadAll(r.Body)
		rdr1 := ioutil.NopCloser(bytes.NewBuffer(buf))

		decoder := json.NewDecoder(rdr1)
		decoder.DisallowUnknownFields()
		err = decoder.Decode(&request)

		if err != nil {
			if errors.As(err, &unmarshalErr) {
				sendErr(w, http.StatusBadRequest, "Bad Request. Wrong Type provided for field "+unmarshalErr.Field)
			} else {
				sendErr(w, http.StatusBadRequest, "Bad request. "+err.Error())
			}
			return
		}

		if (len(request.Layout.Keys) > 150) {
			sendErr(w, http.StatusBadRequest, "Layout exceeds 150 key size limitation")
			return
		}

		// validate request body and modify if needed
		if request.Settings.MatrixOption == "Predefined" {
			if !areKeysAnnotated(request.Layout.Keys) {
				sendErr(w, http.StatusBadRequest,
					"Unsupported json layout, key annotations with matrix positions missing or illegal")
				return
			}
		} else {
			annotateKeys(request.Layout.Keys)
		}

		// start new task
		asyncResult, err := a.celeryClient.Delay("generate_kicad_project", request)
		if err != nil {
			sendErr(w, http.StatusBadRequest, "Bad request. "+err.Error())
			return
		}
		response.TaskId = asyncResult.TaskID

		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(response)

	case "OPTIONS":
		w.WriteHeader(http.StatusOK)

	default:
		sendErr(w, http.StatusMethodNotAllowed, "Method not allowed")
	}
}

func (a *App) IsTaskPrefetched(taskId string) bool {
	// check if task is prefetched by worker (but not yet running)
	// maximum prefetch number is equal `worker_prefetch_multiplier * worker_concurrency`
	conn := a.redisPool.Get()
	defer conn.Close()

	reply, err := redis.Values(conn.Do("HGETALL", "unacked"))
	if err != nil {
		log.Println(err)
		return false
	}

	for i := 0; i < len(reply); i += 2 {
		var values []json.RawMessage
		err := json.Unmarshal(reply[i+1].([]byte), &values)
		if err != nil {
			log.Println(err)
			return false
		}

		var details unackedTaskDetails
		err = json.Unmarshal(values[0], &details)
		if err != nil {
			log.Println(err)
			return false
		}

		decodedBody, err := base64.StdEncoding.DecodeString(details.Body)
		if err != nil {
			log.Println(err)
			return false
		}

		var request taskRequest
		err = json.Unmarshal(decodedBody, &request)
		if err != nil {
			log.Println(err)
			return false
		}

		if request.TaskId == taskId {
			return true
		}
	}
	return false
}

func (a *App) KicadGetTaskStatus(w http.ResponseWriter, r *http.Request) {
	var response taskStatus

	vars := mux.Vars(r)
	taskId := vars["task_id"]

	result, err := a.celeryBackend.GetResult(taskId)
	if err != nil {
		if a.IsTaskPrefetched(taskId) {
			response.TaskId = taskId
			response.TaskStatus = "PENDING"
			response.Result = map[string]interface{}{"percentage": 0}
			json.NewEncoder(w).Encode(response)
			return
		} else {
			sendErr(w, http.StatusNotFound, err.Error())
			return
		}
	}

	response.TaskId = result.ID
	response.TaskStatus = result.Status
	response.Result = result.Result.(map[string]interface{})

	json.NewEncoder(w).Encode(response)
}

func (a *App) KicadGetTaskRender(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskId := vars["task_id"]
	side := vars["side"]

	reqParams := make(url.Values)

	objectName := fmt.Sprintf("%s/%s.svg", taskId, side)
	a.MinioPresignedUrlProxy(objectName, reqParams)(w, r)
}

func (a *App) KicadGetTaskResult(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskId := vars["task_id"]

	archiveName := fmt.Sprintf("%s.zip", taskId)

	reqParams := make(url.Values)
	reqParams.Set("response-content-disposition", fmt.Sprintf("attachment; filename=\"%s\"", archiveName))

	objectName := fmt.Sprintf("%s/%s", taskId, archiveName)
	a.MinioPresignedUrlProxy(objectName, reqParams)(w, r)
}

func (a *App) MinioPresignedUrlProxy(objectName string, reqParams url.Values) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		presignedUrl, err := a.minioClient.PresignedGetObject(context.Background(), "kicad-projects", objectName, 24*time.Hour, reqParams)

		if err != nil {
			sendErr(w, http.StatusNotFound, err.Error())
			return
		}

		director := func(req *http.Request) {
			req.URL = presignedUrl
			// changing host is important, otherwise signature check will fail
			req.Host = presignedUrl.Host
			if _, ok := req.Header["User-Agent"]; !ok {
				// explicitly disable User-Agent so it's not set to default value
				req.Header.Set("User-Agent", "")
			}
		}

		proxy := &httputil.ReverseProxy{Director: director}
		proxy.ServeHTTP(w, r)
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
