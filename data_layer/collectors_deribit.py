"""
Deribit Data Collector (Public API - No Authentication Required)
Provides Implied Volatility and Greeks for BTC Options
Enhanced with Black-Scholes calculation and Put/Call Ratio
https://docs.deribit.com/
"""

import requests
import threading
import time
import math
from typing import Dict, Any
from scipy.stats import norm

# Import monitoring
try:
    from infrastructure.monitoring import MONITOR
except:
    MONITOR = None


class DeribitCollector(threading.Thread):
    """
    Deribit Public API Collector for Options Greeks
    Endpoint: /api/v2/public/get_book_summary_by_currency
    Rate Limit: No authentication needed, reasonable rate limits
    """
    
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.lock = threading.Lock()
        self.base_url = "https://www.deribit.com/api/v2/public"
        self.latest_data = {
            "implied_volatility": 0.0,
            "delta_exposure": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "iv_rank": 0.0,
            "delta_bs": 0.0,
            "gamma_bs": 0.0,
            "vega_bs": 0.0,
            "theta_bs": 0.0,
            "put_call_ratio_oi": 0.0,
            "put_call_ratio_vol": 0.0
        }
        print("✅ DeribitCollector (Public API) initialized")
    
    def run(self):
        """Background thread loop - fetches data every 10 seconds"""
        self.running = True
        while self.running:
            try:
                self.fetch_options_data()
            except Exception as e:
                print(f"❌ Deribit: Unexpected error - {e}")
            time.sleep(10)  # Poll every 10 seconds
    
    def fetch_options_data(self):
        """Fetch BTC options data and calculate Greeks"""
        start_time = time.time()
        success = False
        error_type = None
        error_message = None
        http_status = None
        
        try:
            # Get all BTC options summary
            url = f"{self.base_url}/get_book_summary_by_currency"
            params = {
                "currency": "BTC",
                "kind": "option"
            }
            
            response = requests.get(url, params=params, timeout=10)
            http_status = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', [])
                
                if not result:
                    print("⚠️  Deribit: No options data available")
                    return
                
                # Calculate market-wide weighted averages
                total_oi = 0
                weighted_iv = 0
                net_delta = 0
                net_theta = 0
                net_vega = 0
                iv_values = []
                
                # For Put/Call Ratio
                total_put_oi = 0
                total_call_oi = 0
                total_put_vol = 0
                total_call_vol = 0
                
                # For Black-Scholes calculation
                spot_price = 0
                if result:
                    spot_price = result[0].get('underlying_price', 0)
                
                for instrument in result:
                    oi = instrument.get('open_interest', 0)
                    mark_iv = instrument.get('mark_iv', 0)
                    greeks = instrument.get('greeks', {})
                    volume_24h = instrument.get('volume_24h', 0)
                    instrument_name = instrument.get('instrument_name', '')
                    
                    # Determine if Put or Call
                    is_put = '-P-' in instrument_name
                    is_call = '-C-' in instrument_name
                    
                    if is_put:
                        total_put_oi += oi
                        total_put_vol += volume_24h
                    elif is_call:
                        total_call_oi += oi
                        total_call_vol += volume_24h
                    
                    if oi > 0 and mark_iv > 0:
                        total_oi += oi
                        weighted_iv += mark_iv * oi
                        iv_values.append(mark_iv)
                        
                        # Accumulate Greeks weighted by open interest
                        if greeks:
                            delta = greeks.get('delta', 0) or 0
                            theta = greeks.get('theta', 0) or 0
                            vega = greeks.get('vega', 0) or 0
                            
                            net_delta += delta * oi
                            net_theta += theta * oi
                            net_vega += vega * oi
                
                # Calculate Put/Call Ratios
                pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
                pcr_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0
                
                # Calculate final values
                if total_oi > 0:
                    avg_iv = weighted_iv / total_oi
                    # FIX: Deribit returns IV as decimal (0.57 = 57%), not percentage
                    # Convert to decimal format for Black-Scholes (57% → 0.57)
                    avg_iv_decimal = avg_iv if avg_iv < 5 else avg_iv / 100
                    avg_iv_display = avg_iv if avg_iv < 5 else avg_iv  # Keep original for display
                    
                    # Calculate IV Rank (percentile)
                    if len(iv_values) > 10:
                        iv_values.sort()
                        min_iv = min(iv_values)
                        max_iv = max(iv_values)
                        if max_iv > min_iv:
                            iv_rank = ((avg_iv - min_iv) / (max_iv - min_iv)) * 100
                        else:
                            iv_rank = 50.0
                    else:
                        iv_rank = 50.0
                    
                    # Calculate Black-Scholes Greeks if we have spot price
                    bs_greeks = self.calculate_black_scholes_greeks(spot_price, avg_iv_decimal)
                    
                    with self.lock:
                        self.latest_data["implied_volatility"] = avg_iv_display
                        self.latest_data["delta_exposure"] = net_delta
                        self.latest_data["theta"] = net_theta
                        self.latest_data["vega"] = net_vega
                        self.latest_data["iv_rank"] = iv_rank
                        self.latest_data["delta_bs"] = bs_greeks["delta"]
                        self.latest_data["gamma_bs"] = bs_greeks["gamma"]
                        self.latest_data["vega_bs"] = bs_greeks["vega"]
                        self.latest_data["theta_bs"] = bs_greeks["theta"]
                        self.latest_data["put_call_ratio_oi"] = pcr_oi
                        self.latest_data["put_call_ratio_vol"] = pcr_vol
                    
                    print(f"✅ Deribit: IV={avg_iv_display:.2f}%, PCR={pcr_oi:.3f}, Delta(BS)={bs_greeks['delta']:.4f}, Gamma(BS)={bs_greeks['gamma']:.6f}")
                    success = True
                else:
                    print("⚠️  Deribit: No valid options with open interest")
                    success = True  # Still successful response
                    
            else:
                print(f"⚠️  Deribit: HTTP {response.status_code}")
                error_type = f"HTTP {response.status_code}"
                error_message = f"API returned status {response.status_code}"
                
        except requests.exceptions.Timeout:
            error_type = "Timeout"
            error_message = "Request timeout"
            print("❌ Deribit: Request timeout")
        except requests.exceptions.RequestException as e:
            error_type = "NetworkError"
            error_message = str(e)
            print(f"❌ Deribit: Network error - {e}")
        except Exception as e:
            error_type = "ProcessingError"
            error_message = str(e)
            print(f"❌ Deribit: Error processing data - {e}")
        finally:
            # Record API call in monitoring system
            if MONITOR:
                tracker = MONITOR.get_or_create_tracker('Deribit')
                tracker.record_call(
                    success=success,
                    error_type=error_type,
                    error_message=error_message,
                    response_time=time.time() - start_time,
                    http_status=http_status
                )
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get current Greeks snapshot"""
        with self.lock:
            return self.latest_data.copy()
    
    def calculate_black_scholes_greeks(self, spot, iv, strike=None, time_to_expiry=30/365, risk_free_rate=0.05):
        """
        Calculate Black-Scholes Greeks
        If strike not provided, use ATM (spot price)
        """
        try:
            if spot <= 0 or iv <= 0:
                return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0}
            
            K = strike if strike else spot  # ATM strike
            S = spot
            T = time_to_expiry
            r = risk_free_rate
            sigma = iv
            
            # Calculate d1 and d2
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            # Standard normal PDF and CDF
            nd1 = norm.cdf(d1)
            nprime_d1 = norm.pdf(d1)
            
            # Greeks for ATM call option
            delta = nd1
            gamma = nprime_d1 / (S * sigma * math.sqrt(T))
            vega = S * nprime_d1 * math.sqrt(T) / 100  # Per 1% change in IV
            theta = -(S * nprime_d1 * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
            
            return {
                "delta": delta,
                "gamma": gamma,
                "vega": vega,
                "theta": theta
            }
        except Exception as e:
            print(f"⚠️  Black-Scholes calculation error: {e}")
            return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0}
    
    def stop(self):
        """Stop the collector"""
        self.running = False
        print("✅ DeribitCollector stopped")
