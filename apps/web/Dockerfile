FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
COPY packages/shared packages/shared
COPY apps/web/package.json apps/web/package.json

RUN npm install

COPY apps/web apps/web

WORKDIR /app/apps/web
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
