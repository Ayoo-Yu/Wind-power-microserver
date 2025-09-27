const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const rateLimit = require('express-rate-limit');
const swaggerUi = require('swagger-ui-express');
const swaggerJsdoc = require('swagger-jsdoc');
require('dotenv').config();

const routes = require('./routes');
const { sequelize } = require('./models');
const logger = require('./utils/logger');
const errorHandler = require('./middleware/errorHandler');
const requestLogger = require('./middleware/requestLogger');
const ReportService = require('./services/reportService');

const app = express();
const PORT = process.env.PORT || 3005;

// Initialize services
const reportService = new ReportService();

// Trust proxy if behind load balancer
app.set('trust proxy', 1);

// Security middleware
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            scriptSrc: ["'self'"],
            imgSrc: ["'self'", "data:", "https:"]
        }
    }
}));

// CORS configuration
app.use(cors({
    origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
    credentials: true,
    optionsSuccessStatus: 200
}));

// Rate limiting
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 1000, // limit each IP to 1000 requests per windowMs
    message: 'Too many requests from this IP, please try again later.',
    standardHeaders: true,
    legacyHeaders: false
});
app.use('/api/', limiter);

// Stricter rate limiting for report generation
const reportLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 50, // limit each IP to 50 report generation requests per windowMs
    message: 'Too many report generation requests, please try again later.',
    skipSuccessfulRequests: true
});

// Compression
app.use(compression());

// Body parsing middleware
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Request logging
app.use(requestLogger);

// Swagger configuration
const swaggerOptions = {
    definition: {
        openapi: '3.0.0',
        info: {
            title: 'Wind Power Report Service API',
            version: '1.0.0',
            description: 'API for generating and managing wind power reports',
            contact: {
                name: 'Wind Power Systems',
                email: 'support@windpower.com'
            }
        },
        servers: [
            {
                url: `http://localhost:${PORT}`,
                description: 'Development server'
            },
            {
                url: 'https://api.windpower.com',
                description: 'Production server'
            }
        ],
        components: {
            securitySchemes: {
                bearerAuth: {
                    type: 'http',
                    scheme: 'bearer',
                    bearerFormat: 'JWT'
                }
            }
        }
    },
    apis: ['./src/routes/*.js', './src/models/*.js']
};

const specs = swaggerJsdoc(swaggerOptions);

// Health check endpoint
app.get('/health', (req, res) => {
    res.status(200).json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        service: 'report-service',
        version: process.env.npm_package_version || '1.0.0',
        uptime: process.uptime()
    });
});

// Readiness check endpoint
app.get('/ready', async (req, res) => {
    try {
        // Check database connection
        await sequelize.authenticate();

        res.status(200).json({
            status: 'ready',
            timestamp: new Date().toISOString(),
            service: 'report-service',
            database: 'connected'
        });
    } catch (error) {
        logger.error('Readiness check failed:', error);
        res.status(503).json({
            status: 'not_ready',
            timestamp: new Date().toISOString(),
            service: 'report-service',
            database: 'disconnected',
            error: error.message
        });
    }
});

// API documentation
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(specs, {
    explorer: true,
    customCss: '.swagger-ui .topbar { display: none }',
    customSiteTitle: 'Wind Power Report Service API'
}));

// API routes
app.use('/api/v1', routes);

// Apply stricter rate limiting to report generation endpoints
app.use('/api/v1/reports/generate', reportLimiter);
app.use('/api/v1/reports/schedule', reportLimiter);

// Error handling middleware
app.use(errorHandler);

// 404 handler
app.use('*', (req, res) => {
    res.status(404).json({
        error: 'Route not found',
        message: `Cannot ${req.method} ${req.originalUrl}`,
        path: req.originalUrl,
        method: req.method
    });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
    logger.info('SIGTERM received, starting graceful shutdown...');

    try {
        // Stop accepting new connections
        server.close(() => {
            logger.info('HTTP server closed');
        });

        // Shutdown services
        await reportService.shutdown();

        // Close database connection
        await sequelize.close();
        logger.info('Database connection closed');

        logger.info('Graceful shutdown complete');
        process.exit(0);
    } catch (error) {
        logger.error('Error during graceful shutdown:', error);
        process.exit(1);
    }
});

process.on('SIGINT', async () => {
    logger.info('SIGINT received, starting graceful shutdown...');
    process.emit('SIGTERM');
});

// Database connection and server startup
async function startServer() {
    try {
        // Test database connection
        await sequelize.authenticate();
        logger.info('Database connection established successfully');

        // Sync database models
        if (process.env.NODE_ENV !== 'production') {
            await sequelize.sync({ alter: true });
            logger.info('Database models synchronized');
        }

        // Start server
        const server = app.listen(PORT, () => {
            logger.info(`🚀 Report Service running on port ${PORT}`);
            logger.info(`📚 API Documentation available at http://localhost:${PORT}/api-docs`);
            logger.info(`🏥 Health check available at http://localhost:${PORT}/health`);
            logger.info(`📊 Ready check available at http://localhost:${PORT}/ready`);
        });

        // Handle server errors
        server.on('error', (error) => {
            logger.error('Server error:', error);
            process.exit(1);
        });

        return server;
    } catch (error) {
        logger.error('Failed to start server:', error);
        process.exit(1);
    }
}

// Start the server if this file is run directly
if (require.main === module) {
    startServer();
}

module.exports = { app, startServer, reportService };