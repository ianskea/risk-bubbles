import numpy as np
import time

# Simulate 3000 days of price data
days = 3000
t = np.arange(days)
prices = np.exp(0.001 * t + np.random.normal(0, 0.1, days))
log_prices = np.log(prices)

start_time = time.time()

# Expanding Window Loop (Simulating "Historic Analysis" for every day)
# Start from day 100 to have enough data
min_periods = 100
risks = []

print(f"Running expanding window regression for {days} days...")

for i in range(min_periods, days):
    # Data known up to day i
    current_t = t[:i+1]
    current_log = log_prices[:i+1]
    
    # Fit Quadratic
    coeffs = np.polyfit(current_t, current_log, 2)
    
    # Predict current day i
    pred = np.polyval(coeffs, i)
    resid = current_log[i] - pred
    
    # Simple Z-score logic for test
    # (In real code we calculate ranking vs past residuals)
    risks.append(resid)

end_time = time.time()
print(f"Total time: {end_time - start_time:.4f} seconds")
print(f"Avg time per day: {(end_time - start_time)/(days-min_periods):.6f} seconds")
