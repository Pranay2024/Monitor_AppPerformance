from flask import Flask, render_template, request, jsonify
import os
import time
import subprocess
import psutil
import winreg
import datetime

app = Flask(__name__)

LOG_FILE = "app_performance_log.txt"

# Function to retrieve installed applications
def get_installed_apps():
    installed_apps = []
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    
    for reg_path in reg_paths:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as hkey:
                for i in range(winreg.QueryInfoKey(hkey)[0]):
                    sub_key_name = winreg.EnumKey(hkey, i)
                    with winreg.OpenKey(hkey, sub_key_name) as sub_key:
                        try:
                            app_name = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                            install_location = winreg.QueryValueEx(sub_key, "InstallLocation")[0]
                            if install_location and os.path.exists(install_location):
                                installed_apps.append((app_name, install_location))
                        except FileNotFoundError:
                            continue
        except Exception as e:
            print(f"Error accessing registry: {e}")
    
    return installed_apps

# Function to open an application
def open_app(app_path):
    try:
        process = subprocess.Popen(app_path, shell=True)
        return process
    except Exception as e:
        print(f"Error opening application: {e}")
        return None

# Function to measure performance
def measure_performance(process, app_name, start_time):
    cpu_usage = []
    memory_usage = []
    
    try:
        while process.poll() is None:
            cpu_usage.append(psutil.cpu_percent(interval=1))
            memory_info = psutil.Process(process.pid).memory_info().rss / 1024 ** 2
            memory_usage.append(memory_info)
            time.sleep(1)
    except psutil.NoSuchProcess:
        pass
    
    avg_cpu = sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
    avg_memory = sum(memory_usage) / len(memory_usage) if memory_usage else 0
    end_time = time.time()
    response_time = (end_time - start_time) * 1000  # in milliseconds
    
    with open(LOG_FILE, "a") as log:
        log.write(f"{app_name}: CPU={avg_cpu:.2f}%, Memory={avg_memory:.2f}MB, Response Time={response_time:.2f}ms\n")
    
    return avg_cpu, avg_memory, response_time

# Function to calculate throughput and uptime
def get_system_metrics():
    uptime = time.time() - psutil.boot_time()
    uptime_percentage = (uptime / (24 * 60 * 60)) * 100  # Percentage uptime
    rps = psutil.cpu_count(logical=True) * 10  # Rough estimation of Requests Per Second
    return uptime_percentage, rps

@app.route('/')
def home():
    apps = get_installed_apps()
    return render_template('index.html', apps=apps)

@app.route('/open', methods=['POST'])
def open_application():
    app_name = request.form.get('app_name')
    app_path = request.form.get('app_path')
    
    if not app_path:
        return jsonify({"success": False, "error": "Invalid application path"})
    
    start_time = time.time()
    process = open_app(app_path)
    if process:
        avg_cpu, avg_memory, response_time = measure_performance(process, app_name, start_time)
        uptime_percentage, rps = get_system_metrics()
        
        return jsonify({
            "success": True,
            "app_name": app_name,
            "cpu": avg_cpu,
            "memory": avg_memory,
            "response_time": response_time,
            "uptime": uptime_percentage,
            "throughput": rps
        })
    else:
        return jsonify({"success": False, "error": "Failed to launch application"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
