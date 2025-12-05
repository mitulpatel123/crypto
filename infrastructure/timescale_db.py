"""
TimescaleDB Database Handler
Manages connection pooling and hypertable operations
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values, RealDictCursor
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging


class TimescaleDB:
    """Handle all database operations for crypto data storage"""
    
    def __init__(self, host="localhost", port=5432, user="postgres", 
                 password="crypto_secure_pass_2025", dbname="crypto_data"):
        self.config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "dbname": dbname
        }
        
        # Connection Pool (Thread Safe)
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                dbname=self.config["dbname"]
            )
            print("✅ Database connection pool created")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
        
        self.init_db()
    
    def get_conn(self):
        """Get connection from pool"""
        return self.pool.getconn()
    
    def put_conn(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
    
    def init_db(self):
        """Initialize database schema and hypertables"""
        conn = self.get_conn()
        try:
            cur = conn.cursor()
            
            # Enable TimescaleDB Extension (skip if not available for local testing)
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                print("✅ TimescaleDB extension enabled")
            except Exception as e:
                print(f"⚠️  TimescaleDB not available, using regular PostgreSQL: {e}")
                conn.rollback()  # Reset transaction state
            
            # Create the 60-Column Master Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feature_store (
                    timestamp TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    
                    -- GROUP A: Price & Volume (10 columns)
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    volume_buy DOUBLE PRECISION,
                    volume_sell DOUBLE PRECISION,
                    trade_count INT,
                    vwap DOUBLE PRECISION,
                    volatility_hv DOUBLE PRECISION,
                    
                    -- GROUP B: Order Book & Flow (15 columns)
                    bid_ask_spread DOUBLE PRECISION,
                    ob_imbalance_5 DOUBLE PRECISION,
                    ob_wall_bid DOUBLE PRECISION,
                    ob_wall_ask DOUBLE PRECISION,
                    flow_delta_1m DOUBLE PRECISION,
                    flow_delta_5m DOUBLE PRECISION,
                    large_trade_count INT,
                    bid_qty_1 DOUBLE PRECISION,
                    bid_qty_2 DOUBLE PRECISION,
                    bid_qty_3 DOUBLE PRECISION,
                    ask_qty_1 DOUBLE PRECISION,
                    ask_qty_2 DOUBLE PRECISION,
                    ask_qty_3 DOUBLE PRECISION,
                    bid_price_1 DOUBLE PRECISION,
                    ask_price_1 DOUBLE PRECISION,
                    
                    -- GROUP C: Derivatives & Greeks (15 columns)
                    funding_rate DOUBLE PRECISION,
                    funding_predicted DOUBLE PRECISION,
                    open_interest DOUBLE PRECISION,
                    oi_change_1h DOUBLE PRECISION,
                    long_short_ratio DOUBLE PRECISION,
                    implied_volatility DOUBLE PRECISION,
                    iv_rank DOUBLE PRECISION,
                    delta_exposure DOUBLE PRECISION,
                    put_call_ratio_vol DOUBLE PRECISION,
                    put_call_ratio_oi DOUBLE PRECISION,
                    gamma_strike_1 DOUBLE PRECISION,
                    gamma_strike_2 DOUBLE PRECISION,
                    gamma_strike_3 DOUBLE PRECISION,
                    theta DOUBLE PRECISION,
                    vega DOUBLE PRECISION,
                    
                    -- GROUP D: Sentiment & External (10 columns)
                    whale_inflow DOUBLE PRECISION,
                    whale_outflow DOUBLE PRECISION,
                    news_sentiment DOUBLE PRECISION,
                    social_hype_index DOUBLE PRECISION,
                    fear_greed_index DOUBLE PRECISION,
                    correlation_spx DOUBLE PRECISION,
                    correlation_dxy DOUBLE PRECISION,
                    time_hour INT,
                    time_day INT,
                    is_weekend BOOLEAN,
                    
                    PRIMARY KEY (timestamp, symbol)
                );
            """)
            conn.commit()  # Commit table creation before attempting hypertable conversion
            
            # Convert to Hypertable (The Magic Command) - skip if TimescaleDB not available
            try:
                cur.execute("""
                    SELECT create_hypertable('feature_store', 'timestamp', 
                                            if_not_exists => TRUE,
                                            chunk_time_interval => INTERVAL '1 day');
                """)
                print("✅ Hypertable created")
            except Exception as e:
                print(f"⚠️  Running without hypertable (regular table): {e}")
                conn.rollback()  # Reset transaction state
            
            # Create indexes for faster queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_time 
                ON feature_store (symbol, timestamp DESC);
            """)
            
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_close_price 
                ON feature_store (close) WHERE close IS NOT NULL;
            """)
            
            conn.commit()
            print("✅ Database & Hypertable Initialized")
            
            # Print table info
            self._print_table_info(cur)
            
        except Exception as e:
            print(f"❌ DB Init Failed: {e}")
            conn.rollback()
            raise
        finally:
            cur.close()
            self.put_conn(conn)
    
    def _print_table_info(self, cur):
        """Print database statistics"""
        try:
            cur.execute("SELECT COUNT(*) FROM feature_store;")
            count = cur.fetchone()[0]
            print(f"📊 Current rows in database: {count:,}")
            
            if count > 0:
                cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM feature_store;")
                min_time, max_time = cur.fetchone()
                print(f"📅 Data range: {min_time} to {max_time}")
        except:
            pass
    
    def insert_batch(self, rows: List[Dict[str, Any]]):
        """
        Insert a batch of rows efficiently
        rows = [{'timestamp': '...', 'symbol': 'BTCUSDT', 'close': 95000, ...}, ...]
        """
        if not rows:
            return
        
        conn = self.get_conn()
        try:
            cur = conn.cursor()
            
            # Get all possible columns
            all_columns = ['timestamp', 'symbol',
                          'open', 'high', 'low', 'close', 'volume', 'volume_buy', 'volume_sell',
                          'trade_count', 'vwap', 'volatility_hv',
                          'bid_ask_spread', 'ob_imbalance_5', 'ob_wall_bid', 'ob_wall_ask',
                          'flow_delta_1m', 'flow_delta_5m', 'large_trade_count',
                          'bid_qty_1', 'bid_qty_2', 'bid_qty_3',
                          'ask_qty_1', 'ask_qty_2', 'ask_qty_3',
                          'bid_price_1', 'ask_price_1',
                          'funding_rate', 'funding_predicted', 'open_interest', 'oi_change_1h',
                          'long_short_ratio', 'implied_volatility', 'iv_rank', 'delta_exposure',
                          'put_call_ratio_vol', 'put_call_ratio_oi',
                          'gamma_strike_1', 'gamma_strike_2', 'gamma_strike_3',
                          'theta', 'vega',
                          'whale_inflow', 'whale_outflow', 'news_sentiment',
                          'social_hype_index', 'fear_greed_index',
                          'correlation_spx', 'correlation_dxy',
                          'time_hour', 'time_day', 'is_weekend']
            
            # Prepare values (fill missing columns with None)
            values = []
            for row in rows:
                row_values = [row.get(col) for col in all_columns]
                values.append(row_values)
            
            # Build INSERT query with ON CONFLICT
            query = f"""
                INSERT INTO feature_store ({','.join(all_columns)})
                VALUES %s
                ON CONFLICT (timestamp, symbol) DO UPDATE SET
                    {','.join([f"{col}=EXCLUDED.{col}" for col in all_columns if col not in ['timestamp', 'symbol']])}
            """
            
            execute_values(cur, query, values)
            conn.commit()
            
        except Exception as e:
            print(f"❌ Batch Insert Failed: {e}")
            conn.rollback()
        finally:
            cur.close()
            self.put_conn(conn)
    
    def insert_single(self, row: Dict[str, Any]):
        """Insert a single row"""
        self.insert_batch([row])
    
    def query(self, sql: str, params: tuple = None) -> List[Dict]:
        """Execute a SELECT query and return results as dict"""
        conn = self.get_conn()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            results = cur.fetchall()
            return [dict(row) for row in results]
        except Exception as e:
            print(f"❌ Query Failed: {e}")
            return []
        finally:
            cur.close()
            self.put_conn(conn)
    
    def get_latest_data(self, symbol: str = "BTCUSDT", limit: int = 100) -> List[Dict]:
        """Get latest data for a symbol"""
        sql = """
            SELECT * FROM feature_store
            WHERE symbol = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        return self.query(sql, (symbol, limit))
    
    def close(self):
        """Close all connections"""
        if self.pool:
            self.pool.closeall()
            print("✅ Database connections closed")
