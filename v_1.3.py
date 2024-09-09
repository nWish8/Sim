import random
import wsnsimpy.wsnsimpy_tk as wsp

GATEWAY = 0

def delay():
    '''
    Returns a random delay between 0.2 and 0.8 seconds.
    '''
    return random.uniform(0.2, 0.8)

class MyNode(wsp.LayeredNode):
    tx_range = 100  # Transmission range of the node

    def init(self):
        '''
        Initialize the node, setting previous node to None.
        '''
        super().init()
        self.neighbor_table = {}  # Dictionary to store neighbors and their costs
        self.cost = float('inf') if self.id != GATEWAY else 0  # Initial cost is infinite for non-gateway nodes
        self.clk_offset = 0  # Clock offset for synchronization

    def run(self):
        '''
        Main loop for the node. Sets the color and width of the node based on its role (GATEWAY or other).
        '''
        if self.id == GATEWAY:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the gateway node to blue
            self.scene.nodewidth(self.id, 2)
            yield self.timeout(1)
            self.send_rreq(self.id, self.cost, sim.env.now)
        else:
            self.scene.nodecolor(self.id, 0.7, 0.7, 0.7)  # Set the color of other nodes to gray

    def send_rreq(self, src, cost, clk):
        '''
        Send a Route Request (RREQ) message to broadcast address.
        '''
        self.send(wsp.BROADCAST_ADDR, msg='rreq', src=src, cost=cost, clk=clk)
        self.log(f"Sent RREQ with cost {cost} from {self.id}")

    def send_rreply(self, src):
        '''
        Send a Route Reply (RREP) message to the previous node.
        '''
        if self.id != GATEWAY:
            self.scene.nodecolor(self.id, 0, 0.7, 0)  # Set the color of the node to green
            self.scene.nodewidth(self.id, 2)
        next_hop = min(self.neighbor_table, key=self.neighbor_table.get)
        self.send(next_hop, msg='rreply', src=src, cost=self.cost)

    def start_send_data(self):
        '''
        Start sending data packets periodically.
        '''
        self.scene.clearlinks()
        seq = 0
        while True:
            yield self.timeout(1)
            self.log(f"Send data to {GATEWAY} with seq {seq}")
            self.send_data(self.id, seq)
            seq += 1

    def send_data(self, src, seq):
        '''
        Forward data packets to the next node in the lowest cost route.
        '''
        next_hop = self.lowestCostNeighbor()
        self.log(f"Forward data with seq {seq} via node {next_hop}")
        self.send(next_hop, msg='data', src=src, seq=seq)

    def on_receive(self, sender, msg, src, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''
        if msg == 'rreq':
            if self.id == GATEWAY:
                return  # If this node is the gateway, return

            received_cost = kwargs['cost']
            new_cost = self.calculate_cost() + received_cost  # Calculate new cost

            if sender not in self.neighbor_table or new_cost < self.neighbor_table[sender]:
                self.neighbor_table[sender] = new_cost  # Update the neighbor table
                self.scene.addlink(sender, self.id, "parent")
                self.cost = new_cost  # Update the node's cost to the gateway
                self.log(f"Receive RREQ {sender} >> {self.id} | cost {new_cost}")

                if self.isEdgeNode():
                    self.log(f"Edge RREQ from {src}")
                    yield self.timeout(delay())  # Wait for a random delay
                    self.log(f"Send RREP to {src}")
                    self.send_rreply(src)  # Send RREP message to the source
                else:
                    yield self.timeout(delay())
                    self.send_rreq(src, new_cost, sim.env.now)  # Forward the RREQ message

        elif msg == 'rreply':
            self.next = sender
            if self.id == GATEWAY:
                self.log(f"Receive RREP from {src}")
                yield self.timeout(5)
                self.log("Start sending data")
                self.start_process(self.start_send_data())
            else:
                yield self.timeout(0.2)
                self.send_rreply(src)

        elif msg == 'data':
            if self.id != GATEWAY:
                yield self.timeout(0.2)
                self.send_data(src, **kwargs)
            else:
                seq = kwargs['seq']
                self.log(f"Got data from {src} with seq {seq}")

    def isEdgeNode(self):
        '''
        Determine if the node is an edge node based on a combination of metrics.
        An edge node will meet at least two of the following criteria:
        - Few neighbors (degree-based)
        - Higher cost relative to neighbors (cost-based)
        - Neighbors only within a certain distance threshold (distance-based)
        Returns True if the node is an edge node, False otherwise.
        '''
        threshold_neighbors = 3
        threshold_distance = 0.9 * self.tx_range
        avg_neighbor_cost = sum(self.neighbor_table.values()) / len(self.neighbor_table) if self.neighbor_table else 0

        few_neighbors = len(self.neighbor_table) < threshold_neighbors
        high_relative_cost = self.cost > avg_neighbor_cost * 1.5 if self.neighbor_table else True
        close_neighbors_only = all(cost >= threshold_distance for cost in self.neighbor_table.values())

        return sum([few_neighbors, high_relative_cost, close_neighbors_only]) >= 2

    def calculate_cost(self):
        '''
        Dummy cost calculation.
        '''
        battery_level = 1  # Simulate battery level
        rssi = 1  # Simulate RSSI in -dBm
        distance = random.uniform(0, self.tx_range)  # Simulate distance
        return battery_level + rssi + distance  # Calculate and return the cost

    def lowestCostNeighbor(self):
        '''
        Returns the neighbor with the lowest cost.
        '''
        return min(self.neighbor_table, key=self.neighbor_table.get)

###########################################################
sim = wsp.Simulator(
    until=100,
    timescale=5,
    visual=True,
    terrain_size=(540, 540),
    title="VineNet Sim")

# Define a line style for parent links
sim.scene.linestyle("parent", color=(0, 0.8, 0), arrow="head", width=2)

# Place nodes over 100x100 grids
for x in range(4):
    for y in range(4):
        px = 50 + x * 60 + random.uniform(-20, 20)
        py = 50 + y * 60 + random.uniform(-20, 20)
        node = sim.add_node(MyNode, (px, py))
        node.tx_range = 75
        node.logging = True

# Start the simulation
sim.run()
