package web

import (
	"bytes"
	"encoding/json"
	"errors"
	"io/ioutil"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"regexp"
	"time"

	"github.com/gorilla/mux"
)

type App struct {
	production bool
	kicadUrl *url.URL
}

func NewApp(production bool) App {
	urlString := "http://localhost:5000"
	if production {
		urlString = "http://api:5000"
	}
	url, _ := url.Parse(urlString)

	app := App{production, url}
	return app
}

func (a *App) Serve() error {
	router := mux.NewRouter()

	kicadPcbHandler := a.KicadPcbHandler

	// disable cors for local development
	if !a.production {
		kicadPcbHandler = disableCors(kicadPcbHandler)
	}

	// TODO: when send GET to /api/pcb there is CORS issue reported by browser
	router.HandleFunc("/api/pcb", validateKleLayout(kicadPcbHandler)).Methods("POST")
	router.HandleFunc("/api/pcb", kicadPcbHandler).Methods("OPTIONS")
	router.HandleFunc("/api/pcb/{task_id}", kicadPcbHandler).Methods("GET")
	router.HandleFunc("/api/pcb/{task_id}/render", kicadPcbHandler).Methods("GET")
	router.HandleFunc("/api/pcb/{task_id}/result", kicadPcbHandler).Methods("GET")

	router.HandleFunc("/", http.FileServer(http.Dir("/webapp")).ServeHTTP)

	router.PathPrefix("/css/").Handler(http.StripPrefix("/css/", http.FileServer(http.Dir("/webapp/css"))))
	router.PathPrefix("/js/").Handler(http.StripPrefix("/js/", http.FileServer(http.Dir("/webapp/js"))))
	router.PathPrefix("/fonts/").Handler(http.StripPrefix("/fonts/", http.FileServer(http.Dir("/webapp/fonts"))))

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

func (a *App) KicadPcbHandler(w http.ResponseWriter, r *http.Request) {
	proxy := httputil.NewSingleHostReverseProxy(a.kicadUrl)

	r.URL.Host = a.kicadUrl.Host
	r.URL.Scheme = a.kicadUrl.Scheme
	r.Header.Set("X-Forwarded-Host", r.Header.Get("Host"))
	r.Host = a.kicadUrl.Host

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

// server side validation of uploaded json, let's not bother
// kicad backend with invalid requests
func validateKleLayout(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var layout kleJsonLayout
		var unmarshalErr *json.UnmarshalTypeError

		buf, _ := ioutil.ReadAll(r.Body)
		rdr1 := ioutil.NopCloser(bytes.NewBuffer(buf))
		rdr2 := ioutil.NopCloser(bytes.NewBuffer(buf))

		decoder := json.NewDecoder(rdr1)
		decoder.DisallowUnknownFields()
		err := decoder.Decode(&layout)

		if err != nil {
			if errors.As(err, &unmarshalErr) {
				sendErr(w, http.StatusBadRequest, "Bad Request. Wrong Type provided for field "+unmarshalErr.Field)
			} else {
				sendErr(w, http.StatusBadRequest, "Bad request. "+err.Error())
			}
			return
		}

		// currently only via-annotated layouts are supported
		re, _ := regexp.Compile(`^\d+\,\d+$`)
		for _, key := range layout.Keys {
			matrixPositionLabel := key.Labels[0]
			if !re.Match([]byte(matrixPositionLabel)) {
				sendErr(w, http.StatusBadRequest, "Unsupported json layout")
				return
			}
		}

		r.Body = rdr2
		h(w, r)
	}
}
