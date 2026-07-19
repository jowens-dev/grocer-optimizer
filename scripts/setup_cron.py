import os
import subprocess

def main():
    print("Setting up daily crontab job for AisleOne price scraping...")
    
    python_bin = "/Users/yella4jella/workspace/praxis/.venv/bin/python"
    script_path = "/Users/yella4jella/workspace/grocer-optimizer/ingest/scrape_instacart.py"
    log_path = "/Users/yella4jella/workspace/grocer-optimizer/scraper_cron.log"
    
    # 4:00 AM local time daily cron definition
    cron_cmd = f"0 4 * * * {python_bin} {script_path} --zip 90210 >> {log_path} 2>&1"
    
    # Get current crontab
    try:
        current_cron = subprocess.check_output("crontab -l", shell=True, stderr=subprocess.STDOUT).decode("utf-8")
    except subprocess.CalledProcessError:
        current_cron = ""
        
    lines = current_cron.splitlines()
    
    # Check if a task for scrape_instacart.py already exists
    exists = False
    for i, line in enumerate(lines):
        if "scrape_instacart.py" in line:
            print(f"Replacing existing cron configuration:\n  Old: {line}\n  New: {cron_cmd}")
            lines[i] = cron_cmd
            exists = True
            break
            
    if not exists:
        print(f"Adding new cron job:\n  {cron_cmd}")
        lines.append(cron_cmd)
        
    # Re-assemble crontab text
    new_cron_text = "\n".join(lines).strip() + "\n"
    
    # Write the new crontab back to system scheduler
    p = subprocess.Popen("crontab -", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input=new_cron_text.encode("utf-8"))
    
    if p.returncode == 0:
        print("✓ Successfully installed cron job! The scraper will run at 4:00 AM daily.")
    else:
        print(f"ERROR: Failed to register cron: {stderr.decode('utf-8')}")

if __name__ == "__main__":
    main()
