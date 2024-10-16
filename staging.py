import random
import json
import wsnsimpy.wsnsimpy_tk as wsp

GATEWAY = 0
INTERVAL = 20  # Matching the actual model interval
DELAY = 2
REPLY_TIMEOUT = 15  # Consistent with the actual model
num_nodes = 25

###########################################################
def randdelay():
    '''
    Returns a random delay between 0.2 and 0.8 seconds.
    '''
    return random.uniform(0.2, 0.8)

###########################################################
class MyNode(wsp.LayeredNode):

    ###################
    def init(self):
        '''
        Initialize the node.
        '''
        super().init()

        self.txCounter = 0
        self.neighbor_table = {}  # Dictionary to store neighbors, their overheads, and paths
        self.rssi = 0
        self.overhead = 1
        self.path = GATEWAY
        self.clk_offset = 0  # Clock offset for synchronization
        self.strt_flag = False
        self.dataCache = {}
        self.reply_deadline = None  # Initialize reply deadline

    ###################
    def run(self):
        '''
        Main loop for Node.
        '''
        if self.id == GATEWAY:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the gateway node to blue
            self.scene.nodewidth(self.id, 2)

            yield self.timeout(1)
            while True:
                self.log(f"STARTING")
                self.send_dreq(self.id, self.txCounter, self.pos, self.rssi, self.overhead, self.path, self.now)

                self.reply_deadline = self.sim.env.now + REPLY_TIMEOUT

                yield self.timeout(INTERVAL)
                self.check_reply_timeout()
                self.log(f"COMPLETE")

                self.scene.clearlinks()
                yield self.timeout(5)
                self.txCounter += 1

    ###################
    def send_dreq(self, src, txCounter, pos, rssi, overhead, path, clk):
        '''
        Send a Data Request (DREQ) message to broadcast address.
        '''
        data = {'msg': 'dreq', 'src': src, 'txCounter': txCounter, 'pos': pos, 'rssi': rssi, 'overhead': overhead, 'path': path, 'clk': clk}
        json_data = json.dumps(data).encode('utf-8')  # Encode data to JSON

        self.send(wsp.BROADCAST_ADDR, msg='dreq', data=json_data)
        self.log(f"SENT: DREQ from {self.id}")

    ###################
    def send_dreply(self, src, dataCache):
        '''
        Send a Data Reply (DREP) message to the lowest overhead node.
        '''
        json_data = json.dumps(dataCache).encode('utf-8')  # Encode data to JSON

        self.strt_flag = False

        self.send(self.path, msg='dreply', src=src, data=json_data)
        self.log(f"SENT: DREP to {self.path}")

    ###################
    def on_receive(self, sender, msg, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''
        data = json.loads(kwargs['data'].decode('utf-8'))  # Load data from JSON

        if msg == 'dreq':
            self.isNewTx(data)

            if not self.neighbor_table:
                self.updateNeighborTable(sender, data)
                self.overhead = self.calculate_overhead() + data['overhead']
                if self.id != GATEWAY:
                    self.path = sender

                self.scene.addlink(sender, self.id, "parent")

                yield self.timeout(randdelay())
                self.send_dreq(sender, self.txCounter, self.pos, self.rssi, self.overhead, self.path, self.now)

                self.strt_flag = True
                self.start_reply()

            elif sender not in self.neighbor_table or data['overhead'] < self.neighbor_table[sender]['overhead']:
                self.updateNeighborTable(sender, data)

                self.scene.addlink(sender, self.id, "parent")

                lowest_neighbor = self.lowestoverheadNeighbor()
                if data['overhead'] < self.neighbor_table[lowest_neighbor]['overhead']:
                    self.overhead = self.calculate_overhead() + data['overhead']
                    if self.id != GATEWAY:
                        self.path = sender

                    yield self.timeout(randdelay())
                    self.send_dreq(sender, self.txCounter, self.pos, self.rssi, self.overhead, self.path, self.now)

                    self.strt_flag = False
                    yield self.timeout(DELAY)
                    self.strt_flag = True
                    self.start_reply()

        elif msg == 'dreply':
            self.log(f"RECEIVED: DREP from {sender}")

            self.dataCacheUpdate()

            self.dataCache.update(data)

            self.neighbor_table.setdefault(sender, {})['rx'] = 1
            
            branches = {key: neighbor for key, neighbor in self.neighbor_table.items() if neighbor.get('path') == self.id}

            if all(neighbor.get('rx', 0) == 1 for neighbor in branches.values()):
                if self.id != GATEWAY:
                    yield self.timeout(randdelay())
                    self.send_dreply(self.id, self.dataCache)
                else:
                    self.log(f"RECEIVED data from connected nodes")
                    self.log(self.format_data_cache())
                    self.scene.clearlinks()
                    for node in self.sim.nodes:
                        self.scene.nodecolor(node.id, 0, 0, 0)
                        self.scene.nodewidth(node.id, 1)
                    self.neighbor_table = {}

    ###################
    def check_reply_timeout(self):
        '''Check if the reply timeout has been reached.'''
        if self.sim.env.now >= self.reply_deadline and self.id == GATEWAY:
            self.log(f"No reply received after {REPLY_TIMEOUT} seconds.")
            self.strt_flag = True

    # (Rest of the methods remain the same as per actual implementation, with some modifications for simulation specifics)

    ###################
    def isNewTx(self, data):
        '''Check if the transaction is new and reset the node.'''
        if data['txCounter'] != self.txCounter:
            self.txCounter = data['txCounter']
            self.neighbor_table = {}
            self.rssi = 0
            self.overhead = 1
            self.path = 0
            self.strt_flag = False
            self.dataCache = {}

    ###################
    def updateNeighborTable(self, sender, data):
        '''Update the neighbor table with sender info.'''
        self.neighbor_table[sender] = {     # Update the neighbor table
            'pos': data['pos'],                 # Store the position
            'rssi': data['rssi'],               # Store the RSSI
            'overhead': data['overhead'],       # Store the overhead
            'path': data['path'],               # Store the path
            'rx': 0                             # Store the number of packets received
        }

    ###################
    def delayed_exec(self, delay, func, *args, **kwargs):
        '''Execute a function after a delay.'''
        return self.sim.delayed_exec(delay, func, *args, **kwargs)

    ###################
    def start_reply(self):
        '''The reply process'''
        def start():
            if self.isEdgeNode() and self.strt_flag:

                # Set the color of the node to red
                self.scene.nodecolor(self.id, 1, 0, 0)
                self.scene.nodewidth(self.id, 2)

                self.dataCacheUpdate()  # Add own data to the dataCache

                # Send the DREP message
                yield self.timeout(randdelay())
                self.send_dreply(self.id, self.dataCache)

        self.delayed_exec(DELAY, start)

    ###################
    def lowestoverheadNeighbor(self):
        '''
        Returns the neighbor with the lowest overhead
        '''
        return min(self.neighbor_table, key=lambda n: self.neighbor_table[n]['overhead'])

    
    ###################
    def highestoverheadNeighbor(self):
        '''
        Returns the neighbor with the highest overhead
        '''
        return max(self.neighbor_table, key=lambda n: self.neighbor_table[n]['overhead'])

    ###################
    def calculate_overhead(self):
        '''
        Assign random values to battery level, RSSI, and distance to calculate the overhead.
        '''
        battery_level = random.randint(0, 100)  # Random battery level
        rssi = random.randint(-100, -40) * -1 # Random RSSI value made positive
        # Distance between coordinates self.pos and Gateway
        distance = ((self.pos[0] - 50) ** 2 + (self.pos[1] - 50) ** 2) ** 0.5
        return round((battery_level + rssi + distance)/3)  # Calculate and return the overhead
    
    ###################
    def isEdgeNode(self):
        '''
        Determine if the node is an edge node by checking the path of all neighbors.
        The node is an edge node if its ID is not stored as the path in any neighbor's entry.
        Returns True if the node is an edge node, False otherwise.
        '''
        for neighbor in self.neighbor_table.values():
            if 'path' in neighbor and neighbor['path'] == self.id:
                return False
        return True
    
    ###################
    def dataCacheUpdate(self):
        '''
        Update the dataCache with the collected data.
        '''
        self.dataCache[str(self.id)] = {
            'time': self.now,
            'id': str(self.id),
            'pos': str(self.pos),
            'temp': random.randint(20, 30), 
            'hum': random.randint(40, 60),
            }

    ############################
    def log(self,msg):
        print(f"Node {'#'+str(self.id):4}[{self.now:10.5f}] {msg}")

    ############################
    def format_data_cache(self):
        '''
        Returns a formatted string representation of the data cache with aligned columns.
        '''
        formatted_cache = []
        header = f"Tx:{self.txCounter} DATA:\n{'Time':<11}{'Node_ID':<8}{'Position':<20}{'Temp(°C)':<10}{'Hum(%)':<10}"
        formatted_cache.append(header)
        formatted_cache.append('-' * 70)  # Divider line

        for node_id, data in self.dataCache.items():
            formatted_data = f"{data['time']:<11.4f}{node_id:<8}{str(data['pos']):<20}{data['temp']:<10}{data['hum']:<10}"
            formatted_cache.append(formatted_data)
        formatted_cache.append('-' * 70)  # Divider line

        return "\n".join(formatted_cache)


    ############################
    @property
    def now(self):
        return self.sim.env.now

###########################################################
sim = wsp.Simulator(
    until=200,
    timescale=3,
    visual=True,
    terrain_size=(350, 350),
    title="SimNet")

# Define a line style for parent links
sim.scene.linestyle("parent", color=(0, 0.8, 0), arrow="head", width=2)

# Place nodes in square grid

for x in range(int(num_nodes ** 0.5)):
    for y in range(int(num_nodes ** 0.5)):
        px = 50 + x * 60 + random.uniform(-20, 20)
        py = 50 + y * 60 + random.uniform(-20, 20)
        node = sim.add_node(MyNode, (round(px,2), round(py,2)))
        node.tx_range = 75
        node.logging = True

# Start the simulation
sim.run()