package web

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"net/http"
	"net/http/httputil"
	"net/url"
	"regexp"
	"time"

	"github.com/gorilla/mux"
)

type App struct {
	production bool
	kicadUrl   *url.URL
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

	// there are two types of handlers for KiCad API,
	// 1) proxy handler which does not check or modify data - is used for most endpoints
	kicadProxyPcbHandler := a.KicadProxyPcbHandler
	// 2) request handler which checks POSTed data and can modify it in some scenarios
	//    before passing it further - is used for POST /api/pcb endpoint
	kicadPostPcbHandler := processKleLayout(kicadProxyPcbHandler)

	// disable cors for local development
	if !a.production {
		kicadProxyPcbHandler = disableCors(kicadProxyPcbHandler)
		kicadPostPcbHandler = disableCors(kicadPostPcbHandler)
	}

	router.HandleFunc("/api/pcb", kicadPostPcbHandler).Methods("POST")
	router.HandleFunc("/api/pcb", kicadProxyPcbHandler).Methods("OPTIONS")
	router.HandleFunc("/api/pcb/{task_id}", kicadProxyPcbHandler).Methods("GET")
	router.HandleFunc("/api/pcb/{task_id}/render", kicadProxyPcbHandler).Methods("GET")
	router.HandleFunc("/api/pcb/{task_id}/result", kicadProxyPcbHandler).Methods("GET")

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

func (a *App) KicadProxyPcbHandler(w http.ResponseWriter, r *http.Request) {
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

type kleJsonRequest struct {
	Layout   kleJsonLayout `json:"layout"`
	Settings pcbSettings   `json:"settings"`
}

type pcbSettings struct {
	MatrixOption    string `json:"matrixOption"`
	SwitchLibrary   string `json:"switchLibrary"`
	SwitchFootprint string `json:"switchFootprint"`
	Routing         string `json:"routing"`
}

// checks if all keys contains valid row-column assignment
func areKeysAnnotated(keys []kleKey) bool {
	re, _ := regexp.Compile(`^\d+\,\d+$`)
	for _, key := range keys {
		matrixPositionLabel := ""
		if len(key.Labels) != 0 {
			matrixPositionLabel = key.Labels[0]
		}
		if !re.Match([]byte(matrixPositionLabel)) {
			return false
		}
	}
	return true
}

func getKeyCenter(key kleKey) (float64, float64) {
	x := key.X + (key.Width / 2)
	y := key.Y + (key.Height / 2)

	rotOrginX := key.RotationX
	rotOrginY := key.RotationY
	angle := -1 * key.RotationAngle
	angleRad := angle * math.Pi / 180

	x = x - rotOrginX
	y = y - rotOrginY

	x = (x * math.Cos(angleRad)) - (y * math.Sin(angleRad))
	y = (y * math.Cos(angleRad)) + (x * math.Sin(angleRad))

	x = x + rotOrginX
	y = y + rotOrginY

	return x, y
}

func annotateKeys(keys []kleKey) {
	for i, key := range keys {
		x, y := getKeyCenter(key)
		key.Labels = []string{fmt.Sprintf("%d,%d", int(y), int(x))}
		keys[i] = key
	}
}

func processKleLayout(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var request kleJsonRequest
		var unmarshalErr *json.UnmarshalTypeError

		buf, _ := ioutil.ReadAll(r.Body)
		rdr1 := ioutil.NopCloser(bytes.NewBuffer(buf))
		rdr2 := ioutil.NopCloser(bytes.NewBuffer(buf))

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

		if request.Settings.MatrixOption == "Predefined" {
			if !areKeysAnnotated(request.Layout.Keys) {
				sendErr(w, http.StatusBadRequest, "Unsupported json layout")
				return
			}
			// rewrite without modification
			r.Body = rdr2
		} else {
			annotateKeys(request.Layout.Keys)
			newBodyBytes := new(bytes.Buffer)
			json.NewEncoder(newBodyBytes).Encode(request)

			// use modified request
			r.Body = ioutil.NopCloser(newBodyBytes)
			r.ContentLength = int64(newBodyBytes.Len())
		}

		h(w, r)
	}
}
