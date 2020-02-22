# Keyboard tools

## About
Features:
 - KiCAD project generator for mechanical keyboards with web interface.

## Environment setup

You need to have [Go](https://golang.org/),
[Node.js](https://nodejs.org/),
[Docker](https://www.docker.com/), and
[Docker Compose](https://docs.docker.com/compose/)
(comes pre-installed with Docker on Mac and Windows)
installed on your computer.

Verify the tools by running the following commands:

```sh
go version
npm --version
docker --version
docker-compose --version
```

## Start in development mode

From `kicad-api` directory run the command (you might
need to prepend it with `sudo` depending on your setup):

```sh
docker-compose up
```
This starts a `kicad` specific containers required by `server`.

Navigate to the `server` folder and start the back end:

```sh
cd server
go run server.go
```
The back end will serve on http://localhost:8080.

Navigate to the `webapp` folder, install dependencies,
and start the front end development server by running:

```sh
cd webapp
npm install
npm start
```
The application will be available on http://localhost:3000.

## Start in production mode (not working yet)

From `kicad-api` directory run:
```sh
docker-compose up
```

Next, from project root perform:
```sh
docker-compose up
```
This will build the application and start.
Access the application on http://localhost:8080.

### Credits
- project structure generated with [goxygen](https://github.com/Shpota/goxygen)
