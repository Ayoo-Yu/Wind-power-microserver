const nodemailer = require('nodemailer');
const handlebars = require('handlebars');
const fs = require('fs').promises;
const path = require('path');
const logger = require('../utils/logger');

/**
 * Advanced email service for report distribution
 */
class EmailService {
    constructor() {
        this.transporter = this.createTransporter();
        this.templates = new Map();
        this.loadTemplates();
    }

    /**
     * Create email transporter
     */
    createTransporter() {
        const config = {
            host: process.env.SMTP_HOST || 'smtp.gmail.com',
            port: parseInt(process.env.SMTP_PORT) || 587,
            secure: process.env.SMTP_SECURE === 'true' || false,
            auth: {
                user: process.env.SMTP_USER || 'reports@windpower.com',
                pass: process.env.SMTP_PASS || 'your-smtp-password'
            },
            pool: true,
            maxConnections: 5,
            maxMessages: 100,
            rateDelta: 1000,
            rateLimit: 5
        };

        return nodemailer.createTransporter(config);
    }

    /**
     * Load email templates
     */
    async loadTemplates() {
        const templatesDir = path.join(__dirname, '../templates/email');

        try {
            const templateFiles = await fs.readdir(templatesDir);

            for (const file of templateFiles) {
                if (file.endsWith('.hbs')) {
                    const templateName = path.basename(file, '.hbs');
                    const templateContent = await fs.readFile(
                        path.join(templatesDir, file),
                        'utf-8'
                    );
                    this.templates.set(templateName, handlebars.compile(templateContent));
                }
            }

            logger.info(`Loaded ${this.templates.size} email templates`);
        } catch (error) {
            logger.warn('Could not load email templates:', error.message);
        }
    }

    /**
     * Send scheduled report
     */
    async sendScheduledReport(report, recipients, filePath) {
        try {
            const templateData = {
                reportName: report.name,
                reportType: report.type,
                generatedAt: report.created_at,
                reportDescription: report.description,
                fileName: path.basename(filePath),
                fileSize: this.formatFileSize(report.file_size || 0)
            };

            const mailOptions = {
                from: `"Wind Power Reports" <${process.env.SMTP_USER || 'reports@windpower.com'}>`,
                to: recipients.join(', '),
                subject: `Scheduled Report: ${report.name}`,
                html: await this.renderTemplate('scheduled-report', templateData),
                attachments: [
                    {
                        filename: path.basename(filePath),
                        path: filePath,
                        contentType: this.getContentType(report.format)
                    }
                ]
            };

            const result = await this.transporter.sendMail(mailOptions);

            logger.info(`Scheduled report sent successfully to ${recipients.length} recipients`, {
                messageId: result.messageId,
                reportId: report.id,
                recipients: recipients.length
            });

            return result;
        } catch (error) {
            logger.error('Failed to send scheduled report:', error);
            throw error;
        }
    }

    /**
     * Send report notification
     */
    async sendReportNotification(report, recipients) {
        try {
            const templateData = {
                reportName: report.name,
                reportType: report.type,
                reportDescription: report.description,
                downloadUrl: `${process.env.API_BASE_URL || 'http://localhost:3000'}/api/v1/reports/${report.id}/download`,
                viewUrl: `${process.env.API_BASE_URL || 'http://localhost:3000'}/api/v1/reports/${report.id}`,
                generatedAt: report.created_at,
                expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) // 30 days
            };

            const mailOptions = {
                from: `"Wind Power Reports" <${process.env.SMTP_USER || 'reports@windpower.com'}>`,
                to: recipients.join(', '),
                subject: `Report Ready: ${report.name}`,
                html: await this.renderTemplate('report-ready', templateData)
            };

            const result = await this.transporter.sendMail(mailOptions);

            logger.info(`Report notification sent successfully to ${recipients.length} recipients`, {
                messageId: result.messageId,
                reportId: report.id,
                recipients: recipients.length
            });

            return result;
        } catch (error) {
            logger.error('Failed to send report notification:', error);
            throw error;
        }
    }

    /**
     * Send error notification
     */
    async sendErrorNotification(recipient, subject, errorData) {
        try {
            const templateData = {
                subject,
                error: errorData,
                timestamp: new Date(),
                systemInfo: {
                    environment: process.env.NODE_ENV || 'production',
                    version: process.env.APP_VERSION || '1.0.0',
                    hostname: require('os').hostname()
                }
            };

            const mailOptions = {
                from: `"Wind Power System" <${process.env.SMTP_USER || 'alerts@windpower.com'}>`,
                to: recipient,
                subject: `🚨 ${subject}`,
                html: await this.renderTemplate('error-notification', templateData),
                priority: 'high'
            };

            const result = await this.transporter.sendMail(mailOptions);

            logger.info('Error notification sent successfully', {
                messageId: result.messageId,
                recipient,
                subject
            });

            return result;
        } catch (error) {
            logger.error('Failed to send error notification:', error);
            throw error;
        }
    }

    /**
     * Send system status report
     */
    async sendSystemStatusReport(recipients, statusData) {
        try {
            const templateData = {
                reportDate: new Date(),
                systemStatus: statusData.systemStatus,
                uptime: statusData.uptime,
                performance: statusData.performance,
                alerts: statusData.alerts,
                recommendations: statusData.recommendations
            };

            const mailOptions = {
                from: `"Wind Power System" <${process.env.SMTP_USER || 'reports@windpower.com'}>`,
                to: recipients.join(', '),
                subject: `System Status Report - ${new Date().toLocaleDateString()}`,
                html: await this.renderTemplate('system-status', templateData)
            };

            const result = await this.transporter.sendMail(mailOptions);

            logger.info(`System status report sent successfully to ${recipients.length} recipients`, {
                messageId: result.messageId,
                recipients: recipients.length
            });

            return result;
        } catch (error) {
            logger.error('Failed to send system status report:', error);
            throw error;
        }
    }

    /**
     * Send bulk reports
     */
    async sendBulkReports(reports, recipients) {
        const results = [];
        const errors = [];

        for (const report of reports) {
            try {
                const result = await this.sendReportNotification(report, recipients);
                results.push({ reportId: report.id, success: true, messageId: result.messageId });
            } catch (error) {
                errors.push({ reportId: report.id, success: false, error: error.message });
                logger.error(`Failed to send report ${report.id}:`, error);
            }
        }

        return {
            successful: results.length,
            failed: errors.length,
            results,
            errors
        };
    }

    /**
     * Render email template
     */
    async renderTemplate(templateName, data) {
        try {
            const template = this.templates.get(templateName);
            if (!template) {
                // Return basic HTML if template not found
                return `
                    <html>
                        <body>
                            <h2>Wind Power System Report</h2>
                            <p>Generated at: ${new Date().toISOString()}</p>
                            <pre>${JSON.stringify(data, null, 2)}</pre>
                        </body>
                    </html>
                `;
            }

            return template(data);
        } catch (error) {
            logger.error(`Failed to render template ${templateName}:`, error);
            throw error;
        }
    }

    /**
     * Get content type for file attachment
     */
    getContentType(format) {
        const contentTypes = {
            'pdf': 'application/pdf',
            'html': 'text/html',
            'json': 'application/json',
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        };

        return contentTypes[format] || 'application/octet-stream';
    }

    /**
     * Format file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';

        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Test email configuration
     */
    async testConnection() {
        try {
            await this.transporter.verify();
            logger.info('Email service connection test successful');
            return true;
        } catch (error) {
            logger.error('Email service connection test failed:', error);
            return false;
        }
    }

    /**
     * Get email statistics
     */
    async getStatistics() {
        try {
            // This would integrate with your email provider's API
            // For now, return basic statistics
            return {
                templatesLoaded: this.templates.size,
                transporterReady: this.transporter.isIdle(),
                lastConnectionTest: new Date()
            };
        } catch (error) {
            logger.error('Failed to get email statistics:', error);
            throw error;
        }
    }

    /**
     * Create email template
     */
    async createTemplate(name, subject, htmlContent) {
        try {
            const template = handlebars.compile(htmlContent);
            this.templates.set(name, template);

            // Save to file system
            const templatePath = path.join(__dirname, '../templates/email', `${name}.hbs`);
            await fs.writeFile(templatePath, htmlContent);

            logger.info(`Email template created: ${name}`);
            return true;
        } catch (error) {
            logger.error(`Failed to create email template ${name}:`, error);
            throw error;
        }
    }

    /**
     * Graceful shutdown
     */
    async shutdown() {
        logger.info('Shutting down email service...');

        if (this.transporter) {
            await this.transporter.close();
        }

        logger.info('Email service shutdown complete');
    }
}

module.exports = EmailService;