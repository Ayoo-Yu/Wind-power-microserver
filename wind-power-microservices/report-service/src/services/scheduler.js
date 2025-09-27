const cron = require('node-cron');
const ReportService = require('./reportService');
const EmailService = require('./emailService');
const logger = require('../utils/logger');
const { Report } = require('../models');

/**
 * Advanced report scheduling service with cron-based automation
 */
class ReportScheduler {
    constructor() {
        this.scheduledJobs = new Map();
        this.reportService = new ReportService();
        this.emailService = new EmailService();
        this.initializeSchedulers();
    }

    /**
     * Initialize default report schedulers
     */
    initializeSchedulers() {
        logger.info('Initializing report schedulers...');

        // Daily operational report - 8:00 AM
        this.scheduleReport('daily-operational', '0 8 * * *', {
            type: 'operational',
            name: 'Daily Operational Report',
            description: 'Daily wind farm operations summary',
            format: 'pdf',
            recipients: ['operations@windpower.com', 'management@windpower.com'],
            template: 'daily-operational',
            includeMetrics: ['power_generation', 'turbine_status', 'maintenance', 'weather_summary'],
            timezone: 'America/New_York'
        });

        // Weekly performance report - Monday 9:00 AM
        this.scheduleReport('weekly-performance', '0 9 * * 1', {
            type: 'performance',
            name: 'Weekly Performance Report',
            description: 'Weekly wind power generation and efficiency analysis',
            format: 'pdf',
            recipients: ['performance@windpower.com', 'analytics@windpower.com'],
            template: 'weekly-performance',
            includeMetrics: ['efficiency', 'prediction_accuracy', 'power_output', 'revenue'],
            timezone: 'America/New_York'
        });

        // Monthly financial report - 1st day of month 10:00 AM
        this.scheduleReport('monthly-financial', '0 10 1 * *', {
            type: 'financial',
            name: 'Monthly Financial Report',
            description: 'Monthly financial performance and revenue analysis',
            format: 'pdf',
            recipients: ['finance@windpower.com', 'executives@windpower.com'],
            template: 'monthly-financial',
            includeMetrics: ['revenue', 'costs', 'profitability', 'roi'],
            timezone: 'America/New_York'
        });

        // Real-time critical alerts - every 15 minutes
        this.scheduleReport('critical-alerts', '*/15 * * * *', {
            type: 'alert',
            name: 'Critical System Alerts',
            description: 'Real-time critical system status and alerts',
            format: 'json',
            recipients: ['oncall@windpower.com'],
            template: 'critical-alerts',
            includeMetrics: ['system_health', 'errors', 'performance_degradation'],
            condition: 'only_if_critical'
        });

        // Environmental impact report - daily 6:00 PM
        this.scheduleReport('environmental-impact', '0 18 * * *', {
            type: 'environmental',
            name: 'Environmental Impact Report',
            description: 'Daily environmental impact and carbon offset metrics',
            format: 'pdf',
            recipients: ['sustainability@windpower.com', 'compliance@windpower.com'],
            template: 'environmental-impact',
            includeMetrics: ['carbon_offset', 'environmental_benefits', 'sustainability_score'],
            timezone: 'America/New_York'
        });

        logger.info('Default report schedulers initialized');
    }

    /**
     * Schedule a new report
     */
    scheduleReport(reportId, cronExpression, config) {
        try {
            // Validate cron expression
            if (!cron.validate(cronExpression)) {
                throw new Error(`Invalid cron expression: ${cronExpression}`);
            }

            // Stop existing schedule if present
            if (this.scheduledJobs.has(reportId)) {
                this.unscheduleReport(reportId);
            }

            logger.info(`Scheduling report ${reportId} with cron: ${cronExpression}`);

            const job = cron.schedule(cronExpression, async () => {
                await this.generateScheduledReport(reportId, config);
            }, {
                scheduled: true,
                timezone: config.timezone || 'America/New_York'
            });

            this.scheduledJobs.set(reportId, {
                job,
                config,
                cronExpression,
                createdAt: new Date(),
                lastRun: null,
                nextRun: job.nextDate()
            });

            logger.info(`Report ${reportId} scheduled successfully`);
            return true;
        } catch (error) {
            logger.error(`Failed to schedule report ${reportId}:`, error);
            return false;
        }
    }

    /**
     * Generate a scheduled report
     */
    async generateScheduledReport(reportId, config) {
        const startTime = Date.now();

        try {
            logger.info(`Generating scheduled report: ${reportId}`);

            // Check if report should be generated (based on conditions)
            if (config.condition === 'only_if_critical') {
                const hasCriticalIssues = await this.checkCriticalIssues();
                if (!hasCriticalIssues) {
                    logger.info(`No critical issues found, skipping report ${reportId}`);
                    return;
                }
            }

            // Generate report data
            const reportData = await this.generateReportData(config);

            // Create report record
            const report = await Report.create({
                name: config.name,
                type: config.type,
                description: config.description,
                format: config.format,
                template: config.template,
                data: reportData,
                status: 'generating',
                scheduled: true,
                scheduled_by: 'system',
                recipients: config.recipients,
                metadata: {
                    reportId,
                    cronExpression: this.scheduledJobs.get(reportId).cronExpression,
                    generatedAt: new Date()
                }
            });

            // Generate report file
            const generatedReport = await this.reportService.generateReportFromTemplate(
                report.id,
                config.template,
                reportData,
                config.format
            );

            // Update report status
            await report.update({
                status: 'completed',
                file_path: generatedReport.filePath,
                file_size: generatedReport.fileSize,
                completed_at: new Date()
            });

            // Send report via email
            if (config.recipients && config.recipients.length > 0) {
                await this.emailService.sendScheduledReport(
                    report,
                    config.recipients,
                    generatedReport.filePath
                );
            }

            // Update scheduler statistics
            const jobInfo = this.scheduledJobs.get(reportId);
            jobInfo.lastRun = new Date();
            jobInfo.nextRun = jobInfo.job.nextDate();
            jobInfo.successCount = (jobInfo.successCount || 0) + 1;

            const duration = Date.now() - startTime;
            logger.info(`Scheduled report ${reportId} generated successfully in ${duration}ms`);

        } catch (error) {
            logger.error(`Failed to generate scheduled report ${reportId}:`, error);

            // Update failure statistics
            const jobInfo = this.scheduledJobs.get(reportId);
            jobInfo.failureCount = (jobInfo.failureCount || 0) + 1;
            jobInfo.lastError = error.message;

            // Send error notification
            await this.sendErrorNotification(reportId, error);
        }
    }

    /**
     * Generate report data based on configuration
     */
    async generateReportData(config) {
        const data = {
            metadata: {
                reportName: config.name,
                generatedAt: new Date(),
                timezone: config.timezone || 'America/New_York'
            },
            metrics: {}
        };

        // Collect requested metrics
        for (const metric of config.includeMetrics || []) {
            switch (metric) {
                case 'power_generation':
                    data.metrics.powerGeneration = await this.getPowerGenerationData();
                    break;
                case 'turbine_status':
                    data.metrics.turbineStatus = await this.getTurbineStatusData();
                    break;
                case 'efficiency':
                    data.metrics.efficiency = await this.getEfficiencyData();
                    break;
                case 'prediction_accuracy':
                    data.metrics.predictionAccuracy = await this.getPredictionAccuracyData();
                    break;
                case 'revenue':
                    data.metrics.revenue = await this.getRevenueData();
                    break;
                case 'carbon_offset':
                    data.metrics.carbonOffset = await this.getCarbonOffsetData();
                    break;
                case 'system_health':
                    data.metrics.systemHealth = await this.getSystemHealthData();
                    break;
                case 'errors':
                    data.metrics.errors = await this.getErrorData();
                    break;
                default:
                    logger.warn(`Unknown metric: ${metric}`);
            }
        }

        return data;
    }

    /**
     * Check for critical system issues
     */
    async checkCriticalIssues() {
        try {
            // Check system health
            const systemHealth = await this.getSystemHealthData();

            // Check for critical alerts
            const criticalAlerts = await this.getCriticalAlerts();

            return systemHealth.status === 'critical' || criticalAlerts.length > 0;
        } catch (error) {
            logger.error('Error checking for critical issues:', error);
            return false;
        }
    }

    /**
     * Get power generation data
     */
    async getPowerGenerationData() {
        // This would integrate with the wind farm service
        // For now, return sample data structure
        return {
            totalPower: 1250.5, // MW
            farms: [
                { name: 'North Farm', power: 450.2, efficiency: 0.85 },
                { name: 'South Farm', power: 380.1, efficiency: 0.82 },
                { name: 'East Farm', power: 420.2, efficiency: 0.88 }
            ],
            trends: {
                daily: { current: 1250.5, previous: 1180.3, change: 5.9 },
                weekly: { current: 8753.5, previous: 8262.1, change: 5.9 },
                monthly: { current: 35014.0, previous: 33048.4, change: 5.9 }
            }
        };
    }

    /**
     * Get turbine status data
     */
    async getTurbineStatusData() {
        return {
            totalTurbines: 150,
            online: 142,
            offline: 8,
            maintenance: 3,
            byFarm: {
                'North Farm': { total: 50, online: 48, offline: 2 },
                'South Farm': { total: 45, online: 42, offline: 3 },
                'East Farm': { total: 55, online: 52, offline: 3 }
            }
        };
    }

    /**
     * Get prediction accuracy data
     */
    async getPredictionAccuracyData() {
        return {
            current: 0.89,
            target: 0.90,
            trends: {
                daily: [0.87, 0.88, 0.89, 0.90, 0.88, 0.89, 0.91],
                weekly: [0.85, 0.87, 0.88, 0.89, 0.90],
                monthly: [0.83, 0.85, 0.87, 0.89]
            },
            byHorizon: {
                '1h': 0.95,
                '6h': 0.92,
                '24h': 0.89,
                '72h': 0.85
            }
        };
    }

    /**
     * Get efficiency data
     */
    async getEfficiencyData() {
        return {
            current: 0.87,
            target: 0.90,
            trends: {
                daily: [0.85, 0.86, 0.87, 0.88, 0.86, 0.87, 0.89],
                weekly: [0.83, 0.85, 0.86, 0.87, 0.88],
                monthly: [0.81, 0.83, 0.85, 0.87]
            }
        };
    }

    /**
     * Get revenue data
     */
    async getRevenueData() {
        return {
            daily: 125000,
            weekly: 875000,
            monthly: 3500000,
            trends: {
                daily: { current: 125000, previous: 118000, change: 5.9 },
                weekly: { current: 875000, previous: 826000, change: 5.9 },
                monthly: { current: 3500000, previous: 3304000, change: 5.9 }
            }
        };
    }

    /**
     * Get carbon offset data
     */
    async getCarbonOffsetData() {
        return {
            daily: 2450, // tons CO2
            weekly: 17150,
            monthly: 68600,
            trees: 125000, // equivalent trees planted
            cars: 520 // equivalent cars removed
        };
    }

    /**
     * Get system health data
     */
    async getSystemHealthData() {
        return {
            status: 'healthy', // healthy, warning, critical
            services: {
                'meteorological-service': { status: 'healthy', uptime: 99.9 },
                'power-prediction-service': { status: 'healthy', uptime: 99.8 },
                'data-service': { status: 'healthy', uptime: 99.9 },
                'report-service': { status: 'healthy', uptime: 99.7 },
                'notification-service': { status: 'healthy', uptime: 99.8 }
            },
            database: { status: 'healthy', connections: 45, maxConnections: 100 },
            cache: { status: 'healthy', hitRate: 0.94 },
            messageQueue: { status: 'healthy', queueSize: 12 }
        };
    }

    /**
     * Get error data
     */
    async getErrorData() {
        return {
            total: 23,
            byService: {
                'meteorological-service': 5,
                'power-prediction-service': 8,
                'data-service': 3,
                'report-service': 4,
                'notification-service': 3
            },
            bySeverity: {
                critical: 2,
                error: 8,
                warning: 13
            },
            byTime: {
                '1h': 2,
                '6h': 8,
                '24h': 23
            }
        };
    }

    /**
     * Get critical alerts
     */
    async getCriticalAlerts() {
        return [
            {
                id: 1,
                title: 'High Memory Usage',
                description: 'Memory usage exceeded 85% threshold',
                severity: 'warning',
                time: '2 hours ago',
                service: 'power-prediction-service'
            }
        ];
    }

    /**
     * Get maintenance data
     */
    async getMaintenanceData() {
        return {
            scheduled: [
                {
                    id: 1,
                    title: 'Database Maintenance',
                    description: 'Monthly database optimization',
                    scheduledFor: 'Tomorrow 2:00 AM',
                    duration: '2 hours',
                    impact: 'Minor service degradation'
                }
            ],
            completed: [
                {
                    id: 2,
                    title: 'Security Update',
                    description: 'Applied security patches',
                    completedAt: 'Yesterday 4:00 PM',
                    duration: '30 minutes'
                }
            ]
        };
    }

    /**
     * Unschedule a report
     */
    unscheduleReport(reportId) {
        const jobInfo = this.scheduledJobs.get(reportId);
        if (jobInfo) {
            jobInfo.job.stop();
            this.scheduledJobs.delete(reportId);
            logger.info(`Report ${reportId} unscheduled`);
            return true;
        }
        return false;
    }

    /**
     * Get all scheduled reports
     */
    getScheduledReports() {
        const reports = [];
        for (const [reportId, jobInfo] of this.scheduledJobs) {
            reports.push({
                id: reportId,
                name: jobInfo.config.name,
                type: jobInfo.config.type,
                cronExpression: jobInfo.cronExpression,
                nextRun: jobInfo.nextRun,
                lastRun: jobInfo.lastRun,
                successCount: jobInfo.successCount || 0,
                failureCount: jobInfo.failureCount || 0,
                status: jobInfo.job.running ? 'active' : 'inactive'
            });
        }
        return reports;
    }

    /**
     * Send error notification
     */
    async sendErrorNotification(reportId, error) {
        try {
            const errorData = {
                reportId,
                error: error.message,
                timestamp: new Date(),
                severity: 'error'
            };

            // Send to monitoring system
            logger.error('Report generation error', errorData);

            // Could also send email notification to administrators
            await this.emailService.sendErrorNotification(
                'admin@windpower.com',
                `Report Generation Error: ${reportId}`,
                errorData
            );
        } catch (notificationError) {
            logger.error('Failed to send error notification:', notificationError);
        }
    }

    /**
     * Graceful shutdown
     */
    async shutdown() {
        logger.info('Shutting down report scheduler...');

        for (const [reportId, jobInfo] of this.scheduledJobs) {
            jobInfo.job.stop();
            logger.info(`Stopped scheduler for report: ${reportId}`);
        }

        this.scheduledJobs.clear();
        logger.info('Report scheduler shutdown complete');
    }
}

module.exports = ReportScheduler;