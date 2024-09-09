import random
import wsnsimpy.wsnsimpy_tk as wsp

GATEWAY = 0
num_nodes = 25

###########################################################
def randdelay():
    '''
    Returns a random delay between 0.2 and 0.6 seconds.
    '''
    return random.uniform(0.2, 0.6)

###########################################################
class MyNode(wsp.LayeredNode):
    tx_range = 75  # Transmission range of the node

    ###################
    def init(self):
        '''
        Initialize the node, setting previous node to None.
        '''
        super().init()
        self.cntr = 0
        self.neighbor_table = {}  # Dictionary to store neighbors their overheads and path
        self.overhead = 1
        self.path = 0
        self.clk_offset = 0  # Clock offset for synchronization
        self.strt_flag = False
        self.branch_flag = False
        self.delayCache = {}
        self.dataCache = ""

    ###################
    def run(self):
        '''
        Main loop for the node. Sets the color and width of the node based on its role (SOURCE, DEST, or other).
        '''
        if self.id == GATEWAY:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the source node to blue
            self.scene.nodewidth(self.id, 2)
            self.cntr = 0
            yield self.timeout(1)
            while True:
                self.send_dreq(self.id, self.cntr, self.overhead, self.path, sim.env.now)
                self.log(f"DREQ sent from {self.id}")
                yield self.timeout(180)
                self.scene.clearlinks()
                self.log(f"COMPLETE")
                yield self.timeout(5)
                self.cntr += 1

    ###########################################################
    def delay(self):
        '''
        Returns a delay based on the overhead function.
        '''
        return 0.2 + (2*num_nodes) / (self.overhead+3)
    
    ###########################################################
    def branchdelay(self):
        '''
        Returns a delay based on the overhead function.
        '''
        return (self.delayCache[1]/(num_nodes-2))/self.delayCache[2]

    ###################
    def send_dreq(self, src, cntr, overhead, path, clk):
        '''
        Send a Data Request (DREQ) message to broadcast address.
        '''
        self.send(wsp.BROADCAST_ADDR, msg='dreq', src=src, cntr=cntr, overhead=overhead, path=path, clk=clk)

    ###################
    def send_dreply(self, src):
        '''
        Send a Data Reply (DREP) message to the lowest overhead node.
        '''
        if self.id != GATEWAY:
            self.scene.nodecolor(self.id, 0, 0.7, 0)  # Set the color of the node to green
            self.scene.nodewidth(self.id, 2)
        next = min(self.neighbor_table, key=self.neighbor_table.get)
        self.send(next, msg='dreply', src=src)

    ###################
    def send_data(self, src, seq):
        '''
        Forward data packets to the next node in the lowest overhead route.
        '''
        
        # Get the index of the lowest overhead neighbor
        next = self.lowestoverheadNeighbor()
        
        # Forward the data packet to the next node
        self.send(next, msg='data', src=src, seq=seq)

        self.strt_flag = False
        self.branch_flag = False
        self.log(f"Data Reply: flags False")

    ###################
    def on_receive(self, sender, msg, src, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''

        if msg == 'dreq':
            if kwargs['cntr'] != self.cntr:
                self.cntr = kwargs['cntr']
                self.neighbor_table = {}
                self.overhead = 1
                self.path = 0
                self.delayCache = {}
                self.branch_flag = False
                self.strt_flag = False
                self.dataCache = ""

            if self.id == GATEWAY: return # If this node is the gateway, return
            new_overhead = self.calculate_overhead() + kwargs['overhead']  # Calculate node overhead

            if not self.neighbor_table :        # First DREQ message received
                self.neighbor_table[sender] = {     # Update the neighbor table
                    'overhead': kwargs['overhead'],     # Store the overhead
                    'path': kwargs['path']              # Store the path
                }
                self.overhead = new_overhead        # Update self.overhead
                self.path = sender                  # Update self.path

                self.scene.addlink(sender, self.id, "parent") # Sim: Add a link between the sender and this node

                yield self.timeout(randdelay())
                self.send_dreq(src, self.cntr, self.overhead, self.path, sim.env.now) # Forward the RREQ message to neighbors

                self.strt_flag = True # Set the start flag to True
                self.dataCache = f"Path : {self.id}" # Initialize the data cache
                self.data_reply()  # Start the reply process

            if self.neighbor_table:  # Node has received a DREQ message before
                if sender not in self.neighbor_table or kwargs['overhead'] < self.neighbor_table[sender]['overhead']:
                    self.neighbor_table[sender] = {             # Update the neighbor table
                        'overhead': kwargs['overhead'],             # Store the neighbor's overhead
                        'path': kwargs['path']                      # Store the neighbor's path
                    }
                    self.scene.addlink(sender, self.id, "parent") # Sim: Add a link between the sender and this node

                    if kwargs['overhead'] < self.neighbor_table[self.lowestoverheadNeighbor()]['overhead']:
                        self.overhead = new_overhead  # Update Node overhead
                        self.path = sender            # Update Node path

                        yield self.timeout(randdelay())
                        self.send_dreq(src, self.cntr, self.overhead, self.path, sim.env.now)  # Forward the DREQ message

                        self.strt_flag = False
                        yield self.timeout(self.delayCache[1])
                        self.strt_flag = True
                        self.data_reply() # Start the reply process again


        elif msg == 'dreply':
            self.next = sender
            if self.id == GATEWAY:
                self.log(f"Received DREP from {src}")
                yield self.timeout(5)
                self.log("Start sending data")
                #self.start_process(self.start_send_data())
            else:
                yield self.timeout(0.2)
                self.send_rreply(src)

        elif msg == 'data':
            if self.id != GATEWAY:                
                self.log(f"RECIEVED:\nNode {'#'+str(self.id):4}[----.-----] {kwargs['seq']}")

                if self.branch_flag: # If another data packet is recieved before send add to the sequence
                    self.log(f"RECIEVED: branch_flag = True")

                    self.dataCache = kwargs['seq'] + f">>{self.id}\n" + f"Node {'#'+str(self.id):4}[----.-----] " + self.dataCache # Add the node id to the sequence                  
                    self.log(f"RECIEVED: dataCache Updated")
                    
                    self.log(f"RECIEVED: Branch.. current delay at {self.delayCache[0] + self.delayCache[1]}")
                    new_delay = self.branchdelay()
                    self.log(f"RECIEVED: Branch.. new delay at {self.now + new_delay}")
                    self.delayCache[2] =+ 1
                    self.log(f"RECIEVED: Branch.. num_branch {self.delayCache[2]}")
                    self.data_reply()
                    #self.log(f"RECIEVED: Branch.. delay set")
                    return

                # Add data to seq
                self.dataCache = kwargs['seq'] + f">{self.id}"
                self.log(f"RECIEVED: dataCache Updated:")
                self.log(f"{self.dataCache}")
                new_delay = self.branchdelay()
                self.log(f"RECIEVED: new delay at {self.now + new_delay}")
                self.branch_flag = True
                self.log(f"Set branch flag true")
                self.data_reply()

            else:
                self.log(kwargs['seq'] + f">{self.id}")
                self.log(f"#{self.cntr} : Collection Success")

    ###################
    def delayed_exec(self, delay, func, *args, **kwargs):
        '''Execute a function after a delay.'''
        return self.sim.delayed_exec(delay, func, *args, **kwargs)

    ###################
    def data_reply(self):
        '''The reply process'''
        def start():
            if self.strt_flag:
                # Send the DREP message
                self.log(f"Data Reply: strt_flag True")
                self.send_data(self.id, self.dataCache)
                self.log(f"SENT: data with seq:")
                self.log(f"{self.dataCache}")

        if self.branch_flag == False:
            self.log(f"Data Reply: branch_flag False")
            self.delayCache[0] = self.now
            self.delayCache[1] = self.delay()
            self.delayCache[2] = 1
        self.log(f"Data Reply: Reply cache {self.delayCache} $ {self.overhead}")
        self.delayed_exec(self.delayCache[1], start)

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
        return (battery_level + rssi + distance)/3  # Calculate and return the overhead
    
    ###################
    def isEdgeNode(self):
        '''
        Determine if the node is an edge node by checking the path of all neighbors.
        The node is an edge node, self.id will not be the path of any neighbor in the neighbor table.
        Returns True if the node is an edge node, False otherwise.
        '''
        return self.id not in self.neighbor_table

###########################################################
sim = wsp.Simulator(
    until=200,
    timescale=1,
    visual=True,
    terrain_size=(700, 700),
    title="VineNet Sim")

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
