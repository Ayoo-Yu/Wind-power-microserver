from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import logging
import os
import sys
from datetime import datetime, date
from typing import Dict, Any
from db_session import db_session
from db_models.weather_fetch import WeatherTask, WeatherConnection, WeatherLog
from services.task_executor import execute_weather_task
from services.partition_maintenance_service import ensure_future_partitions

# Make backend/scripts importable for etext_pipeline inside the Docker image.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

logger = logging.getLogger(__name__)

class WeatherSchedulerService:
    """气象数据拉取定时任务调度服务"""
    
    def __init__(self, database_url: str):
        # 配置执行器
        executors = {
            'default': ThreadPoolExecutor(20),
        }
        
        # 作业默认设置
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        # 创建调度器（使用内存存储以避免KingbaseES兼容性问题）
        # 注意：内存存储意味着重启后调度任务会丢失，但会在启动时重新加载
        self.scheduler = BackgroundScheduler(
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )
        
        self.is_running = False
        self._etext_last_success_date = None

    def start(self):
        """启动调度器"""
        if not self.is_running:
            try:
                self.scheduler.start()
                self.is_running = True
                logger.info("气象数据拉取调度器已启动")
                
                # 加载所有启用的任务
                self.load_all_tasks()
                self.add_partition_maintenance_job()
                self.add_etext_pipeline_job()
                self._execute_partition_maintenance()
                
            except Exception as e:
                logger.error(f"启动调度器失败: {e}")
                raise
    
    def add_partition_maintenance_job(self):
        """Ensure future monthly partitions exist and drain default partitions."""
        job_id = "partition_maintenance_daily"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            func=self._execute_partition_maintenance,
            trigger=CronTrigger(hour=2, minute=10),
            id=job_id,
            name="Partition maintenance",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("Partition maintenance job scheduled")

    def _execute_partition_maintenance(self):
        try:
            result = ensure_future_partitions()
            logger.info("Partition maintenance result: %s", result)
        except Exception as e:
            logger.error(f"Partition maintenance failed: {e}", exc_info=True)

    # --- E text pipeline ---

    def add_etext_pipeline_job(self):
        """Schedule E text pipeline from config file."""
        try:
            from services.etext_config import read_config
            cfg = read_config()
        except Exception:
            cfg = {"enabled": True, "schedule_hour": 8, "schedule_minutes": [40, 45, 50, 55]}

        if not cfg.get("enabled", True):
            logger.info("E text pipeline disabled in config, skipping")
            return

        self._register_etext_job(cfg)

    def _register_etext_job(self, cfg):
        """Register or update the APScheduler job from config dict."""
        job_id = "etext_pipeline_daily"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        minutes_str = ",".join(str(m) for m in cfg.get("schedule_minutes", [40, 45, 50, 55]))
        trigger = CronTrigger(hour=cfg.get("schedule_hour", 8), minute=minutes_str)
        self.scheduler.add_job(
            func=self._execute_etext_pipeline,
            trigger=trigger,
            id=job_id,
            name="E text pipeline",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "E text pipeline job scheduled (hour=%s, minutes=%s)",
            cfg.get("schedule_hour", 8), minutes_str,
        )

    def update_etext_pipeline_schedule(self, cfg):
        """Called by API to reschedule or disable the pipeline."""
        job_id = "etext_pipeline_daily"
        if not cfg.get("enabled", True):
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            logger.info("E text pipeline job removed (disabled)")
            return
        self._register_etext_job(cfg)

    def _execute_etext_pipeline(self):
        """Run E text pipeline, skip if already succeeded today."""
        today = date.today()
        if self._etext_last_success_date == today:
            logger.info("E text pipeline already succeeded today, skipping")
            return

        try:
            from etext_pipeline import run_pipeline
            from services.etext_config import read_config

            cfg = read_config()
            incoming_dir = cfg.get("incoming_dir") or None
            results = run_pipeline(incoming_dir=incoming_dir)

            if results:
                self._etext_last_success_date = today
                total_ins = sum(r.get("inserted", 0) for r in results)
                total_upd = sum(r.get("updated", 0) for r in results)
                logger.info(
                    "E text pipeline completed: %d tables, ins=%d upd=%d",
                    len(results), total_ins, total_upd,
                )
            else:
                logger.info("E text pipeline: no new files found")

        except Exception as e:
            logger.error("E text pipeline failed: %s", e, exc_info=True)

    def stop(self):
        """停止调度器"""
        if self.is_running:
            try:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("气象数据拉取调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")
    
    def load_all_tasks(self):
        """加载所有启用的任务到调度器"""
        try:
            with db_session() as session:
                tasks = session.query(WeatherTask).filter(
                    WeatherTask.enabled == True,
                    WeatherTask.deleted_at.is_(None)
                ).all()
                
                for task in tasks:
                    self.add_task_to_scheduler(task)
                    
                logger.info(f"已加载 {len(tasks)} 个启用的任务到调度器")
                
        except Exception as e:
            logger.error(f"加载任务失败: {e}")
    
    def add_task_to_scheduler(self, task: WeatherTask):
        """添加任务到调度器"""
        try:
            job_id = f"weather_task_{task.id}"
            
            # 如果任务已存在，先移除
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # 解析cron表达式
            trigger = CronTrigger.from_crontab(task.schedule)
            
            # 添加作业
            self.scheduler.add_job(
                func=self._execute_scheduled_task,
                trigger=trigger,
                id=job_id,
                args=[task.id],
                name=f"气象数据拉取任务: {task.name}",
                replace_existing=True
            )
            
            logger.info(f"任务已添加到调度器: {task.name} (ID: {task.id})")
            
        except Exception as e:
            logger.error(f"添加任务到调度器失败: {e}")
    
    def remove_task_from_scheduler(self, task_id: int):
        """从调度器中移除任务"""
        try:
            job_id = f"weather_task_{task_id}"
            
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"任务已从调度器中移除: {task_id}")
            
        except Exception as e:
            logger.error(f"从调度器移除任务失败: {e}")
    
    def update_task_in_scheduler(self, task: WeatherTask):
        """更新调度器中的任务"""
        if task.enabled:
            self.add_task_to_scheduler(task)
        else:
            self.remove_task_from_scheduler(task.id)
    
    def _execute_scheduled_task(self, task_id: int):
        """执行定时任务"""
        try:
            with db_session() as session:
                task = session.query(WeatherTask).filter_by(
                    id=task_id,
                    enabled=True,
                    deleted_at=None
                ).first()
                
                if not task:
                    logger.warning(f"任务不存在或已被禁用: {task_id}")
                    return
                
                connection = session.query(WeatherConnection).filter_by(
                    id=task.connection_id,
                    deleted_at=None
                ).first()
                
                if not connection:
                    logger.error(f"任务关联的连接不存在: {task_id}")
                    # 记录错误日志
                    log_entry = WeatherLog(
                        task_id=task.id,
                        log_level='error',
                        message='关联的SSH连接不存在',
                        created_at=datetime.now()
                    )
                    session.add(log_entry)
                    session.commit()
                    return
                
                logger.info(f"开始执行定时任务: {task.name} (ID: {task.id})")
                
                # 执行任务
                result = execute_weather_task(task, connection, session)
                
                if result['success']:
                    logger.info(f"定时任务执行成功: {task.name}, "
                              f"处理文件数: {result.get('files_processed', 0)}, "
                              f"插入记录数: {result.get('total_records', 0)}")
                else:
                    logger.error(f"定时任务执行失败: {task.name}, 错误: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"执行定时任务时发生错误: {e}")
            
            # 记录错误日志到数据库
            try:
                with db_session() as session:
                    log_entry = WeatherLog(
                        task_id=task_id,
                        log_level='error',
                        message='定时任务执行异常',
                        details=str(e),
                        created_at=datetime.now()
                    )
                    session.add(log_entry)
                    session.commit()
            except Exception as log_error:
                logger.error(f"记录错误日志失败: {log_error}")
    
    def get_scheduled_jobs(self) -> Dict[str, Any]:
        """获取所有已调度的作业信息"""
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })
            
            return {
                'is_running': self.is_running,
                'jobs': jobs,
                'total_jobs': len(jobs)
            }
            
        except Exception as e:
            logger.error(f"获取调度作业信息失败: {e}")
            return {'is_running': self.is_running, 'jobs': [], 'total_jobs': 0}
    
    def pause_task(self, task_id: int):
        """暂停任务"""
        try:
            job_id = f"weather_task_{task_id}"
            job = self.scheduler.get_job(job_id)
            
            if job:
                self.scheduler.pause_job(job_id)
                logger.info(f"任务已暂停: {task_id}")
            else:
                logger.warning(f"任务未在调度器中找到: {task_id}")
                
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
    
    def resume_task(self, task_id: int):
        """恢复任务"""
        try:
            job_id = f"weather_task_{task_id}"
            job = self.scheduler.get_job(job_id)
            
            if job:
                self.scheduler.resume_job(job_id)
                logger.info(f"任务已恢复: {task_id}")
            else:
                logger.warning(f"任务未在调度器中找到: {task_id}")
                
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
    
    def get_task_next_run_time(self, task_id: int) -> str:
        """获取任务下次执行时间"""
        try:
            job_id = f"weather_task_{task_id}"
            job = self.scheduler.get_job(job_id)
            
            if job and job.next_run_time:
                return job.next_run_time.isoformat()
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取任务执行时间失败: {e}")
            return None

# 全局调度器实例
weather_scheduler = None

def init_scheduler(database_url: str):
    """初始化调度器"""
    global weather_scheduler
    try:
        weather_scheduler = WeatherSchedulerService(database_url)
        weather_scheduler.start()
        logger.info("气象数据拉取调度器初始化成功")
    except Exception as e:
        logger.error(f"初始化调度器失败: {e}")
        raise

def get_scheduler() -> WeatherSchedulerService:
    """获取调度器实例"""
    return weather_scheduler 
