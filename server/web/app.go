package web

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
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
	app.handlers["/"] = http.FileServer(http.Dir("/webapp")).ServeHTTP
	return app
}

func (a *App) Serve() error {
	for path, handler := range a.handlers {
		http.Handle(path, handler)
	}
	log.Println("Web server is available on port 8080")
	return http.ListenAndServe(":8080", nil)
}

func (a *App) KicadPcbHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		return
	}

	keyboard_layout, err := ioutil.ReadAll(r.Body)
	if err != nil {
		sendErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	// post to kicad-api backend
	resp, err := http.Post("http://localhost:5000/api/pcb",
		"application/json", bytes.NewBuffer(keyboard_layout))

	if err != nil {
		sendErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "application/json")
	err = json.NewEncoder(w).Encode("OK")
	if err != nil {
		sendErr(w, http.StatusInternalServerError, err.Error())
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
