FROM node:18-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --only=production --ignore-scripts

FROM node:18-alpine
WORKDIR /app
RUN apk add --no-cache dumb-init
COPY --from=builder /app/node_modules ./node_modules
COPY src/ ./src/
EXPOSE 8080
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "src/server.js"]
