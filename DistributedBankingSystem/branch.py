import grpc
import banks_pb2
import banks_pb2_grpc
import threading # for lock implementation

class Branch(banks_pb2_grpc.BankServicer):
    def __init__(self, id, balance, branches):
        self.id = id
        self.balance = balance
        self.branches = branches
        self.stubList = list()
        self.writeSet: dict[int, list[int]] = {}  # Initialize writeSet
        self.lock = threading.Lock()  # Lock to synchronize propagation

        # Create gRPC stubs to communicate with other branches
        for branch_id in self.branches:
            if branch_id != self.id:
                branch_channel = grpc.insecure_channel(f'localhost:{50050 + branch_id}')
                self.stubList.append(banks_pb2_grpc.BankStub(branch_channel))

    def GetWriteID(self, request, context):
        if self.id not in self.writeSet:
            return banks_pb2.WriteIDResponse(write_id = 1)
        writeID = len(self.writeSet[self.id]) + 1
        return banks_pb2.WriteIDResponse(write_id = writeID)

    def MsgDelivery(self, request, context):
        if request.operation == "deposit":
            return self.Deposit(request, context)
        elif request.operation == "withdraw":
            return self.Withdraw(request, context)
        elif request.operation == "query":
            return self.Query(request, context)
        elif request.operation == "propagate_deposit":
            return self.Propagate_Deposit(request, context)
        elif request.operation == "propagate_withdraw":
            return self.Propagate_Withdraw(request, context)

    def Deposit(self, request, context):
        with self.lock:  # Ensure no concurrent operations during propagation
            # Validate writeSet
            if not self.compareWriteSets(request.write_set):
                return banks_pb2.TransactionResponse(status="validation_failed")
            # process deposit
            self.balance += request.amount
            for stub in self.stubList: # Propagate to other branches
                    stub.MsgDelivery(banks_pb2.TransactionRequest(
                        customer_id = request.customer_id,
                        operation = "propagate_deposit",
                        amount = request.amount,
                        write_id = request.write_id,
                        branch_id = request.branch_id
                    ))
            # Update writeSet
            self.updateWriteSet(request)
            return banks_pb2.TransactionResponse(status="success")

    def Withdraw(self, request, context):
        with self.lock:  # Ensure no concurrent operations during propagation
            # Validate writeSet
            if not self.compareWriteSets(request.write_set):
                return banks_pb2.TransactionResponse(status="validation_failed")
            # Check if sufficient funds exist
            if request.amount > self.balance:
                return banks_pb2.TransactionResponse(status="insufficient_funds")
            
            # Process withdrawal
            self.balance -= request.amount
            for stub in self.stubList: # Propagate to other branches
                stub.MsgDelivery(banks_pb2.TransactionRequest(
                    customer_id=request.customer_id,
                    operation="propagate_withdraw",
                    amount=request.amount,
                    write_id=request.write_id,
                    branch_id=request.branch_id
                ))
            # Update writeSet
            self.updateWriteSet(request)
            return banks_pb2.TransactionResponse(status="success")

    def Query(self, request, context):
        return banks_pb2.TransactionResponse(status="success", balance=self.balance)

    def Propagate_Deposit(self, request, context):
        self.balance += request.amount
        self.updateWriteSet(request)  # Update writeSet
        return banks_pb2.TransactionResponse(status="success")

    def Propagate_Withdraw(self, request, context):
        if request.amount <= self.balance:
            self.balance -= request.amount
            self.updateWriteSet(request)
            return banks_pb2.TransactionResponse(status="success")
        else:
            print(f"Branch {self.id} failed to apply a propagated withdrawal of {request.amount}. Insufficient funds.")
            return banks_pb2.TransactionResponse(status="fail")

    def compareWriteSets(self, request_write_set):
        # Deserialize request's writeSet (may be empty)
        incoming_write_set = {
            entry.branch_id: list(entry.write_ids)
            for entry in request_write_set
        }
        # Compare the incoming writeSet with the branch's writeSet
        for branch_id, write_ids in incoming_write_set.items():
            if branch_id not in self.writeSet or self.writeSet[branch_id] != write_ids:
                print(f"Validation failed for branch {branch_id}: writeSet mismatch.")
                return False
        # If there are no mismatches, validation passes
        return True

    def updateWriteSet(self, request):
        if request.branch_id not in self.writeSet:
            self.writeSet[request.branch_id] = []  # Initialize if the branch_id does not exist
        # Append the new write_id to the list of write_ids for this branch_id
        self.writeSet[request.branch_id].append(request.write_id)
