FROM node:22-alpine AS build

WORKDIR /app

COPY package.json .
COPY tsconfig.json .
COPY tsconfig.app.json .
COPY vite.config.ts .
COPY index.html .
COPY src ./src

RUN npm install
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
