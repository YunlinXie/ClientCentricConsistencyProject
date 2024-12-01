import grpc
from concurrent import futures
import multiprocessing
import banks_pb2_grpc
import branch
import json
import sys

def start_branch_server(branch_id, balance, branch_ids):
    # Initialize a gRPC server and assign it a unique port
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    branch_service = branch.Branch(branch_id, balance, branch_ids)
    banks_pb2_grpc.add_BankServicer_to_server(branch_service, server)

    # Set a base port number and add branch_id to ensure each branch has a unique port
    port = 50050 + branch_id
    server.add_insecure_port(f'[::]:{port}')

    server.start()
    print(f"Branch {branch_id} server started on port {port}")
    server.wait_for_termination()

def main():
    # Load the branch configurations from the input JSON file
    with open(sys.argv[1]) as f:
        config = json.load(f)

    # Filter branch elements from the configuration
    branches = [item for item in config if item['type'] == 'branch']
    branch_ids = [branch['id'] for branch in branches] 

    # Start each branch server in a separate process
    branch_processes = []
    for branch in branches:
        p = multiprocessing.Process(
            target=start_branch_server,
            args=(branch['id'], branch['balance'], branch_ids)
        )
        p.start()
        branch_processes.append(p)

    for p in branch_processes:
        p.join()

if __name__ == '__main__':
    main()