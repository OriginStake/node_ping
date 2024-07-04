import socket
import time
import concurrent.futures
import subprocess
from tqdm import tqdm

# Configuration parameters
PEERS_FILE = "initia_peers.txt"  # File containing the list of peers to ping
TOP_N_PEERS = 10  # Number of peers with the lowest ping to log
SUCCESSFUL_PEERS_LOG_FILE = "successful_peers_log.txt"  # File to log successfully pinged peers
FULL_PEERS_LOG_FILE = "full_peers_log.txt"  # File to log detailed results of all ping attempts
SORTED_PEERS_FILE = "sorted_peers.txt"  # File to log sorted peers based on ping response time
FINAL_PEERS_FILE = "final_peers_for_validators.txt"  # File to log the top N peers with the lowest ping, Use this result to replace the persistent_peers section in config.toml

# Workers & Log Configuration
NUM_PINGS = 3  # Number of ping attempts for each peer
MAX_WORKERS = 50  # Maximum number of concurrent threads for pinging
LOG_INTERVAL = 10  # Interval for printing log messages during pinging


# Read the list of peers from the file
with open(PEERS_FILE, "r") as file:
    peers = file.read().strip().split(",")

# Initialize the log files
with open(SUCCESSFUL_PEERS_LOG_FILE, "w") as file:
    file.write("")
with open(FULL_PEERS_LOG_FILE, "w") as file:
    file.write("")

def ping_peer(peer, num_pings=NUM_PINGS):
    start_time = time.time()
    
    id_ip_port = peer.strip()
    ip_port = id_ip_port.split("@")[1]
    ip, port = ip_port.split(":")
    port = int(port)
    
    response_times = []
    
    for _ in range(num_pings):
        try:
            # Create a new socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Set the timeout for the connection
            sock.settimeout(1)  # Timeout is 1 second
            
            # Start timing
            start_time_ping = time.time()
            
            # Connect to the IP address and port
            result = sock.connect_ex((ip, port))
            
            # End timing
            end_time_ping = time.time()
            
            # Calculate response time (ms)
            response_time = (end_time_ping - start_time_ping) * 1000
            
            # Close the socket
            sock.close()
            
            if result == 0:
                response_times.append(response_time)
            else:
                response_times.append(None)
        
        except socket.error:
            response_times.append(None)
    
    # Calculate average response time (excluding None values)
    valid_response_times = [time for time in response_times if time is not None]
    avg_response_time = sum(valid_response_times) / len(valid_response_times) if valid_response_times else None
    
    end_time = time.time()
    
    if avg_response_time is not None:
        return (id_ip_port, f"{avg_response_time:.0f}ms - {id_ip_port}")
    else:
        return (None, f"Failed - {id_ip_port}")

# Use ThreadPoolExecutor for concurrent pinging with a progress bar
with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = []
    for peer in peers:
        future = executor.submit(ping_peer, peer)
        futures.append(future)
    
    # Get results from threads with a progress bar
    results = []
    for idx, future in tqdm(enumerate(concurrent.futures.as_completed(futures)), total=len(futures)):
        result = future.result()
        results.append(result)
        if idx % LOG_INTERVAL == 0:
            if result[0] is not None:
                print(f"{result[0]}: Connected successfully, average response time: {result[1].split()[0]}")
            else:
                print(f"{result[1]}: Unable to connect")

# Write results to log files
with open(SUCCESSFUL_PEERS_LOG_FILE, "w") as log_file:
    for result in results:
        if result[0] is not None:
            log_file.write(result[0] + ",")

with open(FULL_PEERS_LOG_FILE, "w") as full_log_file:
    for result in results:
        full_log_file.write(result[1] + "\n")

# Process and sort ping data
with open(FULL_PEERS_LOG_FILE, 'r') as file:
    lines = file.readlines()

ping_data = [line.strip().split(' - ') for line in lines]
ping_data = [(int(ping[:-2]) if ping != "Failed" and ping != "0ms" else ping, node) for ping, node in ping_data]

zero_ping_nodes = [(ping, node) for ping, node in ping_data if ping == "0ms"]
ping_data = [(ping, node) for ping, node in ping_data if ping != "0ms"]

sorted_ping_data = sorted((ping, node) for ping, node in ping_data if ping != "Failed")

top_n_nodes = sorted_ping_data[:TOP_N_PEERS]
nodes_below_100 = [(ping, node) for ping, node in sorted_ping_data if ping < 100]
nodes_below_200 = [(ping, node) for ping, node in sorted_ping_data if ping < 200]

count_below_100 = len(nodes_below_100)
count_below_200 = len(nodes_below_200)
count_above_200 = sum(1 for ping, _ in ping_data if ping != "Failed" and ping >= 200)
count_failed = sum(1 for ping, _ in ping_data if ping == "Failed")

total_nodes = len(ping_data) + len(zero_ping_nodes)

with open(SORTED_PEERS_FILE, 'w') as file:
    file.write(f"Top {TOP_N_PEERS} nodes with the lowest ping:\n")
    for ping, node in top_n_nodes:
        file.write(f"{ping}ms - {node}\n")
    
    file.write(f"\nNodes with ping below 100ms: {count_below_100}/{total_nodes} ({count_below_100/total_nodes*100:.2f}%)\n")
    for ping, node in nodes_below_100:
        file.write(f"{ping}ms - {node}\n")
    
    file.write(f"\nNodes with ping below 200ms: {count_below_200}/{total_nodes} ({count_below_200/total_nodes*100:.2f}%)\n")
    for ping, node in nodes_below_200:
        file.write(f"{ping}ms - {node}\n")
    
    file.write(f"\nNodes with ping above 200ms: {count_above_200}/{total_nodes} ({count_above_200/total_nodes*100:.2f}%)\n")
    
    file.write(f"\nNodes with 0ms ping (possibly dead):\n")
    for ping, node in zero_ping_nodes:
        file.write(f"{ping} - {node}\n")
    
    file.write(f"\nFailed nodes: {count_failed}/{total_nodes} ({count_failed/total_nodes*100:.2f}%)\n")

with open(FINAL_PEERS_FILE, 'w') as file:
    file.write(','.join(node for _, node in top_n_nodes))

print("Completed sorting and statistics. Results are saved in sorted_peers.txt and final_peers_for_validators.txt.")
print(f"Top {TOP_N_PEERS} nodes with the lowest ping: {len(top_n_nodes)}/{total_nodes} ({len(top_n_nodes)/total_nodes*100:.2f}%)")
print(f"Nodes with ping below 100ms: {count_below_100}/{total_nodes} ({count_below_100/total_nodes*100:.2f}%)")
print(f"Nodes with ping below 200ms: {count_below_200}/{total_nodes} ({count_below_200/total_nodes*100:.2f}%)")
print(f"Nodes with ping above 200ms: {count_above_200}/{total_nodes} ({count_above_200/total_nodes*100:.2f}%)")
print(f"Nodes with 0ms ping (possibly dead): {len(zero_ping_nodes)}/{total_nodes} ({len(zero_ping_nodes)/total_nodes*100:.2f}%)")
print(f"Failed nodes: {count_failed}/{total_nodes} ({count_failed/total_nodes*100:.2f}%)")