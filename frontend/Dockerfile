FROM node:20-alpine

# Set working directory
WORKDIR /app

# Add a non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Copy package.json and package-lock.json first to leverage Docker cache
COPY --chown=appuser:appgroup package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY --chown=appuser:appgroup . .

# Expose the default React dev server port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
