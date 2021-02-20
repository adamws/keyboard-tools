package main

import (
	"kle-app/web"
	"log"
)

func main() {
	app := web.NewApp()
	log.Fatal("Error", app.Serve())
}
