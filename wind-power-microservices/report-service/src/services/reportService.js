const { Report, ReportTemplate, ReportSchedule } = require('../models');
const ReportGenerator = require('./reportGenerator');
const ReportScheduler = require('./scheduler');
const EmailService = require('./emailService');
const logger = require('../utils/logger');
const path = require('path');
const fs = require('fs').promises;

/**
 * Main report service that coordinates report generation, scheduling, and distribution
 */
class ReportService {
    constructor() {
        this.reportGenerator = new ReportGenerator();
        this.reportScheduler = new ReportScheduler();
        this.emailService = new EmailService();
        this.reportsDir = path.join(__dirname, '../../reports');
        this.ensureReportsDirectory();
    }

    /**
     * Ensure reports directory exists
     */
    async ensureReportsDirectory() {
        try {
            await fs.mkdir(this.reportsDir, { recursive: true });
            logger.info('Reports directory ensured');
        } catch (error) {
            logger.error('Failed to create reports directory:', error);
        }
    }

    /**
     * Generate a new report
     */
    async generateReport(reportData) {
        const startTime = Date.now();

        try {
            logger.info('Starting report generation', {
                name: reportData.name,
                type: reportData.type,
                format: reportData.format
            });

            // Create report record
            const report = await Report.create({
                name: reportData.name,
                type: reportData.type,
                description: reportData.description,
                format: reportData.format,
                template: reportData.template,
                parameters: reportData.parameters || {},
                status: 'generating',
                scheduled: false,
                created_by: reportData.createdBy || 'system'
            });

            // Generate report data
            const data = await this.collectReportData(reportData);

            // Generate report file
            const generatedReport = await this.reportGenerator.generateReport(
                report.id,
                reportData.template,
                data,
                reportData.format
            );

            // Update report record
            await report.update({
                status: 'completed',
                file_path: generatedReport.filePath,
                file_size: generatedReport.fileSize,
                data: data,
                completed_at: new Date()
            });

            const duration = Date.now() - startTime;
            logger.info(`Report generated successfully in ${duration}ms`, {
                reportId: report.id,
                filePath: generatedReport.filePath
            });

            return {
                success: true,
                report: report.toJSON(),
                filePath: generatedReport.filePath,
                downloadUrl: `/api/v1/reports/${report.id}/download`
            };

        } catch (error) {
            logger.error('Report generation failed:', error);

            // Update report status to failed
            if (report) {
                await report.update({
                    status: 'failed',
                    error_message: error.message
                });
            }

            throw error;
        }
    }

    /**
     * Collect report data based on type and parameters
     */
    async collectReportData(reportData) {
        const data = {
            metadata: {
                reportName: reportData.name,
                generatedAt: new Date(),
                timezone: reportData.timezone || 'America/New_York',
                parameters: reportData.parameters || {}
            },
            data: {}
        };

        // Collect data based on report type
        switch (reportData.type) {
            case 'operational':
                data.data = await this.collectOperationalData(reportData.parameters);
                break;
            case 'performance':
                data.data = await this.collectPerformanceData(reportData.parameters);
                break;
            case 'financial':
                data.data = await this.collectFinancialData(reportData.parameters);
                break;
            case 'environmental':
                data.data = await this.collectEnvironmentalData(reportData.parameters);
                break;
            case 'system_status':
                data.data = await this.collectSystemStatusData(reportData.parameters);
                break;
            default:
                data.data = await this.collectGenericData(reportData.parameters);
        }

        return data;
    }

    /**
     * Collect operational data
     */
    async collectOperationalData(parameters) {
        const data = {
            powerGeneration: await this.getPowerGenerationData(),
            turbineStatus: await this.getTurbineStatusData(),
            weatherSummary: await this.getWeatherSummaryData(),
            maintenance: await this.getMaintenanceData()
        };

        // Apply date filters if specified
        if (parameters.startDate && parameters.endDate) {
            data.dateRange = {
                start: parameters.startDate,
                end: parameters.endDate
            };
        }

        return data;
    }

    /**
     * Collect performance data
     */
    async collectPerformanceData(parameters) {
        return {
            efficiency: await this.getEfficiencyData(),
            predictionAccuracy: await this.getPredictionAccuracyData(),
            powerOutput: await this.getPowerOutputData(),
            systemHealth: await this.getSystemHealthData()
        };
    }

    /**
     * Collect financial data
     */
    async collectFinancialData(parameters) {
        return {
            revenue: await this.getRevenueData(),
            costs: await this.getCostsData(),
            profitability: await this.getProfitabilityData(),
            roi: await this.getROIData()
        };
    }

    /**
     * Collect environmental data
     */
    async collectEnvironmentalData(parameters) {
        return {
            carbonOffset: await this.getCarbonOffsetData(),
            environmentalBenefits: await this.getEnvironmentalBenefitsData(),
            sustainabilityScore: await this.getSustainabilityScoreData()
        };
    }

    /**
     * Collect system status data
     */
    async collectSystemStatusData(parameters) {
        return {
            systemStatus: await this.getSystemHealthData(),
            uptime: await this.getUptimeData(),
            performance: await this.getPerformanceMetrics(),
            alerts: await this.getAlertsData(),
            recommendations: await this.getRecommendationsData()
        };
    }

    /**
     * Collect generic data
     */
    async collectGenericData(parameters) {
        return {
            timestamp: new Date(),
            parameters: parameters,
            message: 'Generic report data collection'
        };
    }

    /**
     * Get power generation data from meteorological service
     */
    async getPowerGenerationData() {
        try {
            // This would make an actual API call to meteorological service
            // For now, return sample data
            return {
                totalPower: 1250.5,
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
        } catch (error) {
            logger.warn('Failed to get power generation data:', error.message);
            return { error: 'Data unavailable' };
        }
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
     * Get weather summary data
     */
    async getWeatherSummaryData() {
        return {
            current: {
                windSpeed: 15.2,
                windDirection: 'NW',
                temperature: 18.5,
                humidity: 65,
                pressure: 1013.2
            },
            forecast: {
                '24h': { windSpeed: 12.8, power: 1180.3 },
                '48h': { windSpeed: 18.1, power: 1420.7 },
                '72h': { windSpeed: 14.3, power: 1290.2 }
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
     * Get power output data
     */
    async getPowerOutputData() {
        return {
            actual: 1250.5,
            predicted: 1280.2,
            variance: -2.3,
            accuracy: 97.7
        };
    }

    /**
     * Get system health data
     */
    async getSystemHealthData() {
        return {
            status: 'healthy',
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
     * Get costs data
     */
    async getCostsData() {
        return {
            operational: 45000,
            maintenance: 12000,
            infrastructure: 25000,
            total: 82000,
            trends: {
                daily: { current: 82000, previous: 85000, change: -3.5 },
                weekly: { current: 574000, previous: 595000, change: -3.5 },
                monthly: { current: 2296000, previous: 2380000, change: -3.5 }
            }
        };
    }

    /**
     * Get profitability data
     */
    async getProfitabilityData() {
        return {
            gross: 43000,
            net: 35000,
            margin: 28.0,
            trends: {
                daily: { current: 35000, previous: 28000, change: 25.0 },
                weekly: { current: 245000, previous: 196000, change: 25.0 },
                monthly: { current: 980000, previous: 784000, change: 25.0 }
            }
        };
    }

    /**
     * Get ROI data
     */
    async getROIData() {
        return {
            daily: 2.8,
            weekly: 2.8,
            monthly: 2.8,
            annual: 18.5,
            target: 15.0
        };
    }

    /**
     * Get carbon offset data
     */
    async getCarbonOffsetData() {
        return {
            daily: 2450,
            weekly: 17150,
            monthly: 68600,
            trees: 125000,
            cars: 520
        };
    }

    /**
     * Get environmental benefits data
     */
    async getEnvironmentalBenefitsData() {
        return {
            airQuality: 'Improved by 15%',
            ecosystem: 'Protected 250 acres',
            sustainability: 'Reduced fossil fuel dependency by 8%'
        };
    }

    /**
     * Get sustainability score data
     */
    async getSustainabilityScoreData() {
        return {
            current: 87,
            target: 90,
            factors: {
                renewable: 95,
                efficiency: 85,
                impact: 82,
                innovation: 88
            }
        };
    }

    /**
     * Get uptime data
     */
    async getUptimeData() {
        return {
            percentage: 99.8,
            totalDowntime: 17, // minutes in last 24h
            byService: {
                'meteorological-service': 99.9,
                'power-prediction-service': 99.8,
                'data-service': 99.9,
                'report-service': 99.7,
                'notification-service': 99.8
            }
        };
    }

    /**
     * Get performance metrics
     */
    async getPerformanceMetrics() {
        return {
            avgResponseTime: 145,
            throughput: 1250,
            errorRate: 0.8,
            cpuUsage: 45,
            memoryUsage: 68,
            diskUsage: 52,
            networkIO: 125
        };
    }

    /**
     * Get alerts data
     */
    async getAlertsData() {
        return {
            critical: 2,
            warning: 8,
            info: 15,
            items: [
                {
                    id: 1,
                    title: 'High Memory Usage',
                    description: 'Memory usage exceeded 85% threshold',
                    severity: 'warning',
                    time: '2 hours ago',
                    service: 'power-prediction-service'
                },
                {
                    id: 2,
                    title: 'Database Connection Pool',
                    description: 'Connection pool utilization at 75%',
                    severity: 'info',
                    time: '4 hours ago',
                    service: 'data-service'
                }
            ]
        };
    }

    /**
     * Get recommendations data
     */
    async getRecommendationsData() {
        return [
            {
                id: 1,
                title: 'Optimize Memory Usage',
                description: 'Consider increasing memory allocation for power prediction service',
                priority: 'medium',
                impact: 'Improved performance',
                effort: 'Low'
            },
            {
                id: 2,
                title: 'Database Index Optimization',
                description: 'Add indexes to frequently queried columns',
                priority: 'low',
                impact: 'Faster query performance',
                effort: 'Medium'
            }
        ];
    }

    /**
     * Get all reports
     */
    async getReports(filters = {}) {
        try {
            const where = {};

            if (filters.type) where.type = filters.type;
            if (filters.status) where.status = filters.status;
            if (filters.createdBy) where.created_by = filters.createdBy;
            if (filters.scheduled !== undefined) where.scheduled = filters.scheduled;

            if (filters.startDate || filters.endDate) {
                where.created_at = {};
                if (filters.startDate) where.created_at[Op.gte] = filters.startDate;
                if (filters.endDate) where.created_at[Op.lte] = filters.endDate;
            }

            const reports = await Report.findAll({
                where,
                order: [['created_at', 'DESC']],
                limit: filters.limit || 50,
                offset: filters.offset || 0
            });

            return reports;
        } catch (error) {
            logger.error('Failed to get reports:', error);
            throw error;
        }
    }

    /**
     * Get report by ID
     */
    async getReportById(reportId) {
        try {
            const report = await Report.findByPk(reportId);
            if (!report) {
                throw new Error(`Report not found: ${reportId}`);
            }
            return report;
        } catch (error) {
            logger.error(`Failed to get report ${reportId}:`, error);
            throw error;
        }
    }

    /**
     * Delete report
     */
    async deleteReport(reportId) {
        try {
            const report = await Report.findByPk(reportId);
            if (!report) {
                throw new Error(`Report not found: ${reportId}`);
            }

            // Delete file if exists
            if (report.file_path) {
                try {
                    await fs.unlink(report.file_path);
                } catch (fileError) {
                    logger.warn('Failed to delete report file:', fileError.message);
                }
            }

            await report.destroy();
            logger.info(`Report deleted: ${reportId}`);
            return true;
        } catch (error) {
            logger.error(`Failed to delete report ${reportId}:`, error);
            throw error;
        }
    }

    /**
     * Schedule a report
     */
    async scheduleReport(scheduleData) {
        try {
            // Create schedule record
            const schedule = await ReportSchedule.create({
                name: scheduleData.name,
                type: scheduleData.type,
                description: scheduleData.description,
                cron_expression: scheduleData.cronExpression,
                template: scheduleData.template,
                format: scheduleData.format,
                parameters: scheduleData.parameters || {},
                recipients: scheduleData.recipients || [],
                enabled: scheduleData.enabled !== false,
                timezone: scheduleData.timezone || 'America/New_York',
                created_by: scheduleData.createdBy || 'system'
            });

            // Schedule with cron
            const success = this.reportScheduler.scheduleReport(
                schedule.id,
                scheduleData.cronExpression,
                {
                    type: scheduleData.type,
                    name: scheduleData.name,
                    description: scheduleData.description,
                    format: scheduleData.format,
                    template: scheduleData.template,
                    recipients: scheduleData.recipients || [],
                    timezone: scheduleData.timezone || 'America/New_York',
                    includeMetrics: scheduleData.includeMetrics || []
                }
            );

            if (!success) {
                throw new Error('Failed to schedule report');
            }

            logger.info(`Report scheduled: ${schedule.id}`);
            return schedule;
        } catch (error) {
            logger.error('Failed to schedule report:', error);
            throw error;
        }
    }

    /**
     * Get scheduled reports
     */
    async getScheduledReports() {
        try {
            const schedules = await ReportSchedule.findAll({
                where: { enabled: true },
                order: [['created_at', 'DESC']]
            });

            const activeSchedules = this.reportScheduler.getScheduledReports();

            return schedules.map(schedule => {
                const active = activeSchedules.find(s => s.id === schedule.id);
                return {
                    ...schedule.toJSON(),
                    nextRun: active?.nextRun,
                    lastRun: active?.lastRun,
                    successCount: active?.successCount || 0,
                    failureCount: active?.failureCount || 0,
                    status: active?.status || 'inactive'
                };
            });
        } catch (error) {
            logger.error('Failed to get scheduled reports:', error);
            throw error;
        }
    }

    /**
     * Send report notification
     */
    async sendReportNotification(report, recipients) {
        try {
            const result = await this.emailService.sendReportNotification(report, recipients);
            logger.info(`Report notification sent to ${recipients.length} recipients`);
            return result;
        } catch (error) {
            logger.error('Failed to send report notification:', error);
            throw error;
        }
    }

    /**
     * Send scheduled report
     */
    async sendScheduledReport(report, recipients, filePath) {
        try {
            const result = await this.emailService.sendScheduledReport(report, recipients, filePath);
            logger.info(`Scheduled report sent to ${recipients.length} recipients`);
            return result;
        } catch (error) {
            logger.error('Failed to send scheduled report:', error);
            throw error;
        }
    }

    /**
     * Send system status report
     */
    async sendSystemStatusReport(recipients) {
        try {
            const statusData = await this.collectSystemStatusData({});
            const result = await this.emailService.sendSystemStatusReport(recipients, statusData);
            logger.info(`System status report sent to ${recipients.length} recipients`);
            return result;
        } catch (error) {
            logger.error('Failed to send system status report:', error);
            throw error;
        }
    }

    /**
     * Get report statistics
     */
    async getReportStatistics() {
        try {
            const totalReports = await Report.count();
            const completedReports = await Report.count({ where: { status: 'completed' } });
            const failedReports = await Report.count({ where: { status: 'failed' } });
            const scheduledReports = await ReportSchedule.count({ where: { enabled: true } });

            // Get reports from last 7 days
            const lastWeek = new Date();
            lastWeek.setDate(lastWeek.getDate() - 7);

            const recentReports = await Report.count({
                where: {
                    created_at: {
                        [Op.gte]: lastWeek
                    }
                }
            });

            return {
                totalReports,
                completedReports,
                failedReports,
                scheduledReports,
                recentReports,
                successRate: totalReports > 0 ? Math.round((completedReports / totalReports) * 100) : 0,
                failureRate: totalReports > 0 ? Math.round((failedReports / totalReports) * 100) : 0
            };
        } catch (error) {
            logger.error('Failed to get report statistics:', error);
            throw error;
        }
    }

    /**
     * Graceful shutdown
     */
    async shutdown() {
        logger.info('Shutting down report service...');

        try {
            await this.reportScheduler.shutdown();
            await this.emailService.shutdown();
            logger.info('Report service shutdown complete');
        } catch (error) {
            logger.error('Error during shutdown:', error);
            throw error;
        }
    }
}

module.exports = ReportService;