import random
import json
import wsnsimpy.wsnsimpy_tk as wsp

GATEWAY = 0
INTERVAL = 60
DELAY = 2
num_nodes = 25

###########################################################
def randdelay():
    '''
    Returns a random delay between 0.2 and 0.6 seconds.
    '''
    return random.uniform(0.2, 0.6)

###########################################################
class MyNode(wsp.LayeredNode):

    ###################
    def init(self):
        '''
        Initialize the node.
        '''
        super().init()

        # ID = mac addess of the node
        #self.id = network.WLAN(network.STA_IF).config('mac')

        self.cntr = 0
        self.neighbor_table = {}  # Dictionary to store neighbors their overheads and path
        self.recieved_dreply = {} # Dictionary to store recieved data packets
        self.overhead = 1
        self.path = 0
        self.clk_offset = 0  # Clock offset for synchronization
        self.strt_flag = False
        self.branch_flag = False
        self.delay = {}
        self.dataCache = {}

    ###################
    def run(self):
        '''
        Main loop for Node.
        '''
        if self.id == GATEWAY:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the source node to blue
            self.scene.nodewidth(self.id, 2)

            yield self.timeout(1)
            while True:
                self.log(f"STARTING")
                self.send_dreq(self.id, self.cntr, self.overhead, self.path, sim.env.now)

                yield self.timeout(INTERVAL)
                self.log(f"COMPLETE")

                self.scene.clearlinks()
                yield self.timeout(5)
                self.cntr += 1

    ###########################################################
    def branchdelay(self):
        '''
        Returns a delay based on the overhead function.
        '''
        return (self.delay[1]/(num_nodes-2))/self.delay[2]

    ###################
    def send_dreq(self, src, cntr, overhead, path, clk):
        '''
        Send a Data Request (DREQ) message to broadcast address.
        '''
        data = {'msg': 'dreq', 'src': src, 'cntr': cntr, 'overhead': overhead, 'path': path, 'clk': clk}
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
        self.branch_flag = False

        self.send(self.path, msg='dreply', src=src, data=json_data)
        self.log(f"SENT: DREP to {self.path}")

    ###################
    def on_receive(self, sender, msg, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''
        data = json.loads(kwargs['data'].decode('utf-8'))  # Convert the received data from JSON

        
        if msg == 'dreq':
            if data['cntr'] != self.cntr:
                self.cntr = data['cntr']
                self.neighbor_table = {}
                self.overhead = 1
                self.path = 0
                self.branch_flag = False
                self.strt_flag = False
                self.dataCache = {}
                self.delay = {}

            if self.id == GATEWAY: # If this node is the gateway, update neighbor table and return
                self.neighbor_table[sender] = {     # Update the neighbor table
                    'overhead': data['overhead'],     # Store the overhead
                    'path': data['path'],             # Store the path
                    'rx': 0}                         # Store the number of packets received
                return
            
            new_overhead = self.calculate_overhead() + data['overhead']  # Calculate node overhead

            if not self.neighbor_table :        # First DREQ message received
                self.neighbor_table[sender] = {     # Update the neighbor table
                    'overhead': data['overhead'],     # Store the overhead
                    'path': data['path'],             # Store the path
                    'rx': 0                             # Store the number of packets received
                }
                self.overhead = new_overhead        # Update self.overhead
                self.path = sender                  # Update self.path

                self.scene.addlink(sender, self.id, "parent") # Sim: Add a link between the sender and this node

                yield self.timeout(randdelay())
                self.send_dreq(sender, self.cntr, self.overhead, self.path, sim.env.now) # Forward the RREQ message to neighbors

                self.strt_flag = True # Set the start flag to True
                self.start_reply()  # Start the reply process

            if self.neighbor_table:  # Node has received a DREQ message before
                if sender not in self.neighbor_table or data['overhead'] < self.neighbor_table[sender]['overhead']:
                    self.neighbor_table[sender] = {             # Update the neighbor table
                        'overhead': data['overhead'],             # Store the neighbor's overhead
                        'path': data['path'],                     # Store the neighbor's path
                        'rx': 0                                     # Store the number of packets received
                    }
                    self.scene.addlink(sender, self.id, "parent") # Sim: Add a link between the sender and this node

                    if data['overhead'] < self.neighbor_table[self.lowestoverheadNeighbor()]['overhead']:
                        self.overhead = new_overhead  # Update Node overhead
                        self.path = sender            # Update Node path

                        yield self.timeout(randdelay())
                        self.send_dreq(sender, self.cntr, self.overhead, self.path, sim.env.now)  # Forward the DREQ message

                        self.strt_flag = False
                        yield self.timeout(self.delay[0])
                        self.strt_flag = True
                        self.start_reply() # Start the reply process again


        elif msg == 'dreply':
            self.log(f"RECIEVED: DREP from {sender}")

            # Add the data to the cache by merging dictionaries
            self.dataCache.update(data)

            
            self.neighbor_table.setdefault(sender, {})['rx'] = 1 # Update neighbor packets received

            # Log the neighbor table entries where 'path' == self.id
            matching_neighbors = {key: neighbor for key, neighbor in self.neighbor_table.items() if neighbor.get('path') == self.id}

            # Filter neighbors where 'path' == self.id and check if they all have 'rx' == 1
            if all(neighbor.get('rx', 0) == 1 for neighbor in self.neighbor_table.values() if neighbor.get('path') == self.id):
                
                self.dataCacheUpdate() # Add own data to the dataCache

                if self.id != GATEWAY: # If this node is not the gateway
                    yield self.timeout(randdelay())  # Wait for a random delay
                    self.send_dreply(self.id, self.dataCache)  # Send the data packet to the next node

                else:   # If this node is the gateway
                    self.dataCacheUpdate() # Add data to the dataCache

                    if len(self.dataCache) == num_nodes:
                        self.log(f"#{self.cntr} : All Data Received")
                    else:
                        self.log(f"Count:{self.cntr} : Partial Data Received")
                        self.log(f"{len(self.dataCache)} / {num_nodes} Node Data Received")
                        self.log(self.dataCache)

            else: 
                self.delay[1] += 1
                self.log(f"WAITING FOR: {', '.join(map(str, matching_neighbors.keys()))}")


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

        if self.branch_flag == False:
            self.delay[0] = DELAY
            self.delay[1] = 1
        self.delayed_exec(self.delay[0], start)

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
        Dummy overhead calculation.
        '''
        battery_level = 0.85  # Simulate battery level
        rssi = 0.7  # Simulate RSSI in -dBm
        distance = 40/50  # Simulate distance
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
        Update the dataCache with the node's data.
        '''
        self.dataCache[self.id] = {
            'temp': random.randint(20, 30), 
            'hum': random.randint(40, 60)
            }
    
    ############################
    def log(self,msg):
        print(f"Node {'#'+str(self.id):4}[{self.now:10.5f}] {msg}")

    ############################
    @property
    def now(self):
        return self.sim.env.now

###########################################################
sim = wsp.Simulator(
    until=200,
    timescale=2,
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
        node = sim.add_node(MyNode, (px, py))
        node.tx_range = 75
        node.logging = True

# Start the simulation
sim.run()
