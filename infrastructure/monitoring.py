"""
Real-Time Monitoring System
Tracks API calls, errors, database writes, and alerts
"""

import time
import threading
from datetime import datetime, timedelta
from collections import deque, defaultdict
from typing import Dict, List, Any, Optional
import json


class APICallTracker:
    """Track actual API calls with detailed metrics"""
    
    def __init__(self, service_name: str, max_history: int = 1000):
        self.service_name = service_name
        self.max_history = max_history
        
        # Thread-safe data structures
        self.lock = threading.Lock()
        
        # Call history
        self.calls = deque(maxlen=max_history)
        
        # Metrics
        self.total_calls = 0
        self.success_count = 0
        self.error_count = 0
        self.last_call_time = None
        self.last_success_time = None
        self.last_error_time = None
        
        # Error tracking
        self.error_history = deque(maxlen=100)
        self.error_types = defaultdict(int)
        
    def record_call(self, success: bool, error_type: str = None, error_message: str = None, 
                   response_time: float = 0, http_status: int = None):
        """Record an API call with full details"""
        with self.lock:
            timestamp = datetime.now()
            
            call_record = {
                'timestamp': timestamp,
                'success': success,
                'response_time': response_time,
                'http_status': http_status,
                'error_type': error_type,
                'error_message': error_message
            }
            
            self.calls.append(call_record)
            self.total_calls += 1
            self.last_call_time = timestamp
            
            if success:
                self.success_count += 1
                self.last_success_time = timestamp
            else:
                self.error_count += 1
                self.last_error_time = timestamp
                
                if error_type:
                    self.error_types[error_type] += 1
                    
                error_record = {
                    'timestamp': timestamp,
                    'type': error_type,
                    'message': error_message,
                    'http_status': http_status
                }
                self.error_history.append(error_record)
    
    def get_metrics(self, time_window: int = 300) -> Dict[str, Any]:
        """Get metrics for last N seconds"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            
            recent_calls = [c for c in self.calls if c['timestamp'] > cutoff_time]
            recent_errors = [c for c in recent_calls if not c['success']]
            
            success_rate = (len(recent_calls) - len(recent_errors)) / len(recent_calls) * 100 if recent_calls else 0
            avg_response_time = sum(c['response_time'] for c in recent_calls) / len(recent_calls) if recent_calls else 0
            
            return {
                'service': self.service_name,
                'total_calls': self.total_calls,
                'success_count': self.success_count,
                'error_count': self.error_count,
                'success_rate': success_rate,
                'recent_calls': len(recent_calls),
                'recent_errors': len(recent_errors),
                'avg_response_time': avg_response_time,
                'last_call': self.last_call_time.isoformat() if self.last_call_time else None,
                'last_success': self.last_success_time.isoformat() if self.last_success_time else None,
                'last_error': self.last_error_time.isoformat() if self.last_error_time else None,
                'error_types': dict(self.error_types)
            }
    
    def get_recent_errors(self, limit: int = 20) -> List[Dict]:
        """Get recent errors for display"""
        with self.lock:
            return list(self.error_history)[-limit:]


class DatabaseWriteMonitor:
    """Monitor database write operations and track failures"""
    
    def __init__(self, max_history: int = 1000):
        self.lock = threading.Lock()
        
        # Write tracking
        self.write_history = deque(maxlen=max_history)
        self.total_writes = 0
        self.successful_writes = 0
        self.failed_writes = 0
        
        # Field-level tracking
        self.field_write_failures = defaultdict(int)
        self.field_write_success = defaultdict(int)
        self.field_errors = defaultdict(list)
        
        # Performance
        self.write_times = deque(maxlen=100)
        
    def record_write(self, success: bool, row_data: Dict = None, error: str = None, 
                    write_time: float = 0, failed_fields: List[str] = None):
        """Record a database write attempt"""
        with self.lock:
            timestamp = datetime.now()
            
            write_record = {
                'timestamp': timestamp,
                'success': success,
                'write_time': write_time,
                'error': error,
                'failed_fields': failed_fields or []
            }
            
            self.write_history.append(write_record)
            self.total_writes += 1
            self.write_times.append(write_time)
            
            if success:
                self.successful_writes += 1
                # Track successful field writes
                if row_data:
                    for field in row_data.keys():
                        if row_data[field] is not None:
                            self.field_write_success[field] += 1
            else:
                self.failed_writes += 1
                # Track failed fields
                if failed_fields:
                    for field in failed_fields:
                        self.field_write_failures[field] += 1
                        self.field_errors[field].append({
                            'timestamp': timestamp,
                            'error': error
                        })
    
    def get_metrics(self, time_window: int = 300) -> Dict[str, Any]:
        """Get write metrics"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            recent_writes = [w for w in self.write_history if w['timestamp'] > cutoff_time]
            recent_failures = [w for w in recent_writes if not w['success']]
            
            success_rate = (len(recent_writes) - len(recent_failures)) / len(recent_writes) * 100 if recent_writes else 0
            avg_write_time = sum(self.write_times) / len(self.write_times) if self.write_times else 0
            
            return {
                'total_writes': self.total_writes,
                'successful_writes': self.successful_writes,
                'failed_writes': self.failed_writes,
                'success_rate': success_rate,
                'recent_writes': len(recent_writes),
                'recent_failures': len(recent_failures),
                'avg_write_time': avg_write_time,
                'field_failures': dict(self.field_write_failures),
                'field_success': dict(self.field_write_success)
            }
    
    def get_field_errors(self, field_name: str, limit: int = 10) -> List[Dict]:
        """Get recent errors for specific field"""
        with self.lock:
            return self.field_errors.get(field_name, [])[-limit:]


class AlertManager:
    """Manage alerts for errors and failures"""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.alerts = deque(maxlen=100)
        self.alert_thresholds = {
            'error_rate': 10.0,  # % errors per minute
            'db_write_failure_rate': 5.0,  # % failures
            'api_consecutive_failures': 5,  # consecutive failures
            'db_consecutive_failures': 3
        }
        
        # Tracking for consecutive failures
        self.consecutive_failures = defaultdict(int)
        
    def check_api_metrics(self, service: str, metrics: Dict) -> Optional[str]:
        """Check API metrics and generate alert if needed"""
        with self.lock:
            # Check error rate
            if metrics['recent_calls'] > 0:
                error_rate = (metrics['recent_errors'] / metrics['recent_calls']) * 100
                if error_rate > self.alert_thresholds['error_rate']:
                    alert = {
                        'timestamp': datetime.now(),
                        'level': 'WARNING',
                        'type': 'API_ERROR_RATE',
                        'service': service,
                        'message': f"{service} error rate {error_rate:.1f}% exceeds threshold {self.alert_thresholds['error_rate']}%",
                        'details': metrics
                    }
                    self.alerts.append(alert)
                    return alert['message']
            
            return None
    
    def check_db_metrics(self, metrics: Dict) -> Optional[str]:
        """Check database metrics and generate alert if needed"""
        with self.lock:
            if metrics['recent_writes'] > 0:
                failure_rate = (metrics['recent_failures'] / metrics['recent_writes']) * 100
                if failure_rate > self.alert_thresholds['db_write_failure_rate']:
                    alert = {
                        'timestamp': datetime.now(),
                        'level': 'CRITICAL',
                        'type': 'DB_WRITE_FAILURE',
                        'message': f"Database write failure rate {failure_rate:.1f}% exceeds threshold {self.alert_thresholds['db_write_failure_rate']}%",
                        'details': metrics
                    }
                    self.alerts.append(alert)
                    return alert['message']
            
            return None
    
    def get_active_alerts(self, minutes: int = 10) -> List[Dict]:
        """Get alerts from last N minutes"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            return [a for a in self.alerts if a['timestamp'] > cutoff_time]


class MonitoringSystem:
    """Central monitoring system"""
    
    def __init__(self):
        self.api_trackers: Dict[str, APICallTracker] = {}
        self.db_monitor = DatabaseWriteMonitor()
        self.alert_manager = AlertManager()
        self.lock = threading.Lock()
        
    def get_or_create_tracker(self, service_name: str) -> APICallTracker:
        """Get or create API tracker for service"""
        with self.lock:
            if service_name not in self.api_trackers:
                self.api_trackers[service_name] = APICallTracker(service_name)
            return self.api_trackers[service_name]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all monitoring data for dashboard"""
        api_metrics = {}
        for service, tracker in self.api_trackers.items():
            api_metrics[service] = tracker.get_metrics()
            # Check for alerts
            self.alert_manager.check_api_metrics(service, api_metrics[service])
        
        db_metrics = self.db_monitor.get_metrics()
        self.alert_manager.check_db_metrics(db_metrics)
        
        alerts = self.alert_manager.get_active_alerts()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'api_metrics': api_metrics,
            'db_metrics': db_metrics,
            'alerts': alerts
        }
    
    def get_error_details(self, service: str = None, limit: int = 50) -> List[Dict]:
        """Get detailed error logs"""
        if service and service in self.api_trackers:
            return self.api_trackers[service].get_recent_errors(limit)
        
        # Get all errors
        all_errors = []
        for tracker in self.api_trackers.values():
            all_errors.extend(tracker.get_recent_errors(limit))
        
        # Sort by timestamp
        all_errors.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_errors[:limit]


# Global monitoring instance
MONITOR = MonitoringSystem()
