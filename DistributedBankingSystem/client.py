import grpc
import json
import sys
import multiprocessing
import customer
import time

def start_customer_process(customer_id, events):
    # Initialize Customer and execute events
    cust = customer.Customer(customer_id, events)
    cust.executeEvents()
    return cust.recvMsg

def main():
    # Load the customer configurations from the input JSON file
    with open(sys.argv[1]) as f:
        config = json.load(f)

    # Filter customer elements from the configuration
    customers = [item for item in config if item['type'] == 'customer']

    # Start each customer process sequentially with a delay to allow propagation
    for cust in customers:
        result = start_customer_process(cust['id'], cust['events'])

    # Write the output data to output.json file in the current directory
    with open("output.json", "w") as outfile:
        json.dump(result, outfile, indent=4)

if __name__ == '__main__':
    main()