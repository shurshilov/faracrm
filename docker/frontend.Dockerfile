# --- Stage 1: Build ---
FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/ .
RUN yarn install --frozen-lockfile
RUN ./node_modules/.bin/vite build

# --- Stage 2: Serve ---
FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
