from backend.services.ai_engine import analyze_device

print("===== TEST 1 =====")
print(analyze_device(30, 1.5))

print("\n===== TEST 2 =====")
print(analyze_device(36, 1.2))

print("\n===== TEST 3 =====")
print(analyze_device(32, 2.5))

print("\n===== TEST 4 =====")
print(analyze_device(38, 2.5))