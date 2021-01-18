package web

import (
	"encoding/json"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"

	"github.com/gorilla/mux"
)

type App struct {
	handlers map[string]http.HandlerFunc
}

func NewApp(cors bool) App {
	app := App{
		handlers: make(map[string]http.HandlerFunc),
	}
	kicadPcbHandler := app.KicadPcbHandler
	if !cors {
		kicadPcbHandler = disableCors(kicadPcbHandler)
	}
	app.handlers["/api/pcb"] = kicadPcbHandler
	app.handlers["/api/pcb/{task_id}"] = kicadPcbHandler
	app.handlers["/api/pcb/{task_id}/result"] = kicadPcbHandler
	app.handlers["/"] = http.FileServer(http.Dir("/webapp")).ServeHTTP
	return app
}

func (a *App) Serve() error {
	router := mux.NewRouter()
	for path, handler := range a.handlers {
		router.HandleFunc(path, handler)
	}
	srv := &http.Server{
		Handler: router,
		Addr:    "127.0.0.1:8080",
		// Good practice: enforce timeouts for servers you create!
		WriteTimeout: 15 * time.Second,
		ReadTimeout:  15 * time.Second,
	}
	log.Println("Web server is available on port 8080")

	return srv.ListenAndServe()
}

func (a *App) KicadPcbHandler(w http.ResponseWriter, r *http.Request) {
	url, _ := url.Parse("http://127.0.0.1:5000")
	proxy := httputil.NewSingleHostReverseProxy(url)

	r.URL.Host = url.Host
	r.URL.Scheme = url.Scheme
	r.Header.Set("X-Forwarded-Host", r.Header.Get("Host"))
	r.Host = url.Host

	proxy.ServeHTTP(w, r)
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
