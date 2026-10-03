# FALCON web image: build the React app, then serve it with Caddy (HTTPS + reverse proxy).
#   docker build -t falcon-web ./frontend
FROM node:22-slim AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
# Only the built files ship: no source code, no node_modules, no build tools.
COPY --from=build /web/dist /srv
