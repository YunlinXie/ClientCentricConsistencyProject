import grpc
import banks_pb2
import banks_pb2_grpc
import time
from google.protobuf.empty_pb2 import Empty
from banks_pb2 import WriteSetEntry

class Customer:
    def __init__(self, id, events):
        # Initialize customer with ID and list of events to perform
        self.id = id
        self.events = events
        self.recvMsg = list() # Store responses from branch
        self.stub = None # gRPC stub to communicate with branch
        self.writeSet: dict[int, list[int]] = {}

    def connectToBranch(self, branch_id):
        branch_address = f'localhost:{50050 + branch_id}'
        channel = grpc.insecure_channel(branch_address)
        self.stub = banks_pb2_grpc.BankStub(channel)

    def executeEvents(self):
        # Sequentially process each event/request
        for event in self.events:
            # Ensure connection to the required branch
            required_branch = event["branch"]
            self.connectToBranch(required_branch)

            # Serialize writeSet, even if empty
            write_set_entries = [
                WriteSetEntry(branch_id = branch_id, write_ids = write_ids)
                for branch_id, write_ids in self.writeSet.items()
            ] if self.writeSet else []  # Handle empty self.writeSet

            if event["interface"] in ["deposit", "withdraw"]:
                # Get unique write ID
                writeIDResponse = self.stub.GetWriteID(Empty())
                writeID = writeIDResponse.write_id

                while True:
                    response = self.stub.MsgDelivery(
                        banks_pb2.TransactionRequest(
                            customer_id = self.id,
                            operation = event["interface"],
                            amount = event.get("money", 0),
                            branch_id = required_branch,
                            write_id = writeID,
                            write_set = write_set_entries  # Send current writeSet
                        )
                    )

                    if response.status == "success":
                        # Update writeSet after successful processing
                        if required_branch not in self.writeSet:
                            self.writeSet[required_branch] = []
                        self.writeSet[required_branch].append(writeID)
                        # Store Loggings for output
                        self.recvMsg.append({
                            "id": self.id,
                            "recv": [
                                {"interface": event["interface"], "branch": required_branch, "result": response.status}
                            ]
                        })
                        break  # Exit the retry loop
                    elif response.status == "validation_failed":
                        time.sleep(1)  # Wait for propagation before retrying

            elif event["interface"] == "query":
                while True:
                    response = self.stub.MsgDelivery(
                        banks_pb2.TransactionRequest(
                            customer_id = self.id,
                            operation = "query",
                            write_set = write_set_entries
                        )
                    )
                    if response.status == "success":
                        # Store Loggings for output
                        self.recvMsg.append({
                            "id": self.id,
                            "recv": [
                                {"interface": "query", "branch": required_branch, "balance": response.balance}
                            ]
                        })
                        break  # Exit the retry loop
                    elif response.status == "validation_failed":
                        time.sleep(1)  # Wait for propagation before retrying
        print(f"Customer {self.id} received messages: {self.recvMsg}")
