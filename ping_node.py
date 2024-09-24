import socket
import time
import concurrent.futures
from tqdm import tqdm

# Configuration parameters
PEERS_FILE = "peers_list.txt"
TOP_N_PEERS = 10
SUCCESSFUL_PEERS_LOG_FILE = "successful_peers_log.txt"
FULL_PEERS_LOG_FILE = "full_peers_log.txt"
SORTED_PEERS_FILE = "sorted_peers.txt"
FINAL_PEERS_FILE = "final_peers_for_validators.txt"

NUM_PINGS = 3
MAX_WORKERS = 50
LOG_INTERVAL = 10

# Initialize the log files
with open(SUCCESSFUL_PEERS_LOG_FILE, "w") as file:
    file.write("")
with open(FULL_PEERS_LOG_FILE, "w") as file:
    file.write("")

def ping_peer(peer, num_pings=NUM_PINGS):
    id_ip_port = peer.strip()
    try:
        if "@" not in id_ip_port:
            return None, f"Invalid format (missing '@'): {id_ip_port}"

        ip_port = id_ip_port.split("@")[1]
        if ":" not in ip_port:
            return None, f"Invalid format (missing ':'): {id_ip_port}"

        ip, port = ip_port.split(":")
        port = int(port)
    except (IndexError, ValueError):
        return None, f"Invalid format: {id_ip_port}"

    response_times = []
    for _ in range(num_pings):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)  # Timeout 1 second
            start_time_ping = time.time()
            result = sock.connect_ex((ip, port))
            end_time_ping = time.time()
            sock.close()

            response_time = (end_time_ping - start_time_ping) * 1000
            if result == 0:
                response_times.append(response_time)
            else:
                response_times.append(None)
        except socket.error:
            response_times.append(None)

    valid_response_times = [t for t in response_times if t is not None]
    avg_response_time = sum(valid_response_times) / len(valid_response_times) if valid_response_times else None

    if avg_response_time is not None:
        return id_ip_port, f"{avg_response_time:.0f}ms - {id_ip_port}"
    else:
        return None, f"Failed - {id_ip_port}"

valid_peers = []
invalid_peers = []

# Normalize and process the peer list from file
with open(PEERS_FILE, "r") as file:
    raw_peers = file.read()

# Replace newlines with commas and split by commas to handle multiple formats
normalized_peers = raw_peers.replace("\n", ",").replace(", ", ",").split(",")

for peer in normalized_peers:
    peer = peer.strip()
    if peer and "@" in peer and ":" in peer.split("@")[1]:
        valid_peers.append(peer)
    else:
        invalid_peers.append(peer)

if invalid_peers:
    print("The following peers have invalid formats and will be skipped:")
    for invalid in invalid_peers:
        print(f" - {invalid}")

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(ping_peer, peer) for peer in valid_peers]
    results = []
    for idx, future in tqdm(enumerate(concurrent.futures.as_completed(futures)), total=len(futures)):
        try:
            result = future.result()
            results.append(result)
            if idx % LOG_INTERVAL == 0 and result[0] is not None:
                print(f"{result[0]}: Connected successfully, average response time: {result[1].split()[0]}")
        except Exception as e:
            print(f"Error processing a peer: {e}")

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

ping_data = []
for line in lines:
    ping, node = line.strip().split(' - ')
    if ping == "Failed":
        ping_data.append((float('inf'), node))  # Use 'inf' to treat failed nodes as last
    elif "ms" in ping:
        try:
            ping_ms = int(ping.replace('ms', '').strip())
            ping_data.append((ping_ms, node))
        except ValueError:
            ping_data.append((float('inf'), node))

# Sort the data
sorted_ping_data = sorted(ping_data, key=lambda x: x[0])

# Filter the top N nodes
top_n_nodes = sorted_ping_data[:TOP_N_PEERS]
nodes_below_100 = [(ping, node) for ping, node in sorted_ping_data if ping < 100]
nodes_below_200 = [(ping, node) for ping, node in sorted_ping_data if ping < 200]

count_below_100 = len(nodes_below_100)
count_below_200 = len(nodes_below_200)
count_above_200 = sum(1 for ping, _ in sorted_ping_data if ping >= 200)
count_failed = sum(1 for ping, _ in ping_data if ping == float('inf'))
total_nodes = len(ping_data)

# Write sorted data to the log file
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

    file.write(f"\nFailed nodes: {count_failed}/{total_nodes} ({count_failed/total_nodes*100:.2f}%)\n")

with open(FINAL_PEERS_FILE, 'w') as file:
    file.write(','.join(node for _, node in top_n_nodes))

print(f"Top {TOP_N_PEERS} nodes with the lowest ping: {len(top_n_nodes)}/{total_nodes} ({len(top_n_nodes)/total_nodes*100:.2f}%)")
print(f"Nodes with ping below 100ms: {count_below_100}/{total_nodes} ({count_below_100/total_nodes*100:.2f}%)")
print(f"Nodes with ping below 200ms: {count_below_200}/{total_nodes} ({count_below_200/total_nodes*100:.2f}%)")
print(f"Nodes with ping above 200ms: {count_above_200}/{total_nodes} ({count_above_200/total_nodes*100:.2f}%)")
print(f"Failed nodes: {count_failed}/{total_nodes} ({count_failed/total_nodes*100:.2f}%)")