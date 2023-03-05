package web

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"io/ioutil"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"

	"os"
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

	app := App{production, celeryClient, celeryBackend, minioClient}
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

	router.PathPrefix("/").HandlerFunc(http.FileServer(http.Dir("/webapp")).ServeHTTP)
	router.PathPrefix("/assets/").Handler(http.StripPrefix("/assets/", http.FileServer(http.Dir("/webapp/assets"))))

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
	SwitchLibrary     string `json:"switchLibrary"`
	SwitchFootprint   string `json:"switchFootprint"`
	Routing           string `json:"routing"`
	ControllerCircuit string `json:"controllerCircuit"`
}

type taskStatus struct {
	TaskId     string                 `json:"task_id"`
	TaskStatus string                 `json:"task_status"`
	Result     map[string]interface{} `json:"task_result"`
}

func (a *App) KicadPostNewTask(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case "POST":
		var request kleJsonRequest
		var unmarshalErr *json.UnmarshalTypeError
		var response taskStatus

		buf, _ := ioutil.ReadAll(r.Body)
		rdr1 := ioutil.NopCloser(bytes.NewBuffer(buf))

		decoder := json.NewDecoder(rdr1)
		decoder.DisallowUnknownFields()
		err := decoder.Decode(&request)

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
				sendErr(w, http.StatusBadRequest, "Unsupported json layout")
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

func (a *App) KicadGetTaskStatus(w http.ResponseWriter, r *http.Request) {
	var response taskStatus

	vars := mux.Vars(r)
	taskId := vars["task_id"]

	result, err := a.celeryBackend.GetResult(taskId)
	if err != nil {
		sendErr(w, http.StatusNotFound, err.Error())
		return
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
