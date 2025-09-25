FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Disable host checking for development
ENV DANGEROUSLY_DISABLE_HOST_CHECK=true

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]